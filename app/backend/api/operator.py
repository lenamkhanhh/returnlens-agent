"""Operator API Endpoints for Mock Courier Events and Reset Control.

Per 17 §5, 02 §2, 02 §3, B14 (NDR), and B07 (RETURN_RECEIVED).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, HTTPException, Request

from app.backend.contracts import (
    ActorRole,
    CaseState,
    CaseType,
    CourierEvent,
    CourierEventRequest,
    CourierEventType,
    Language,
    NextStep,
    Proposal,
    ProposalBasis,
)
from app.backend.domain.executor import compute_payload_hash
from app.backend.persistence.repository import Repository
from app.backend.workflow.engine import WorkflowEngine

router = APIRouter(prefix="/api/operator", tags=["operator"])


@router.post("/courier-events", status_code=200)
async def post_courier_event(
    payload: CourierEventRequest,
    request: Request,
):
    """Receive mock courier status webhook (NDR, RETURN_RECEIVED, DELAYED).

    Invariants:
    - Dedupe by event_id (Test 45).
    - If NDR: triggers job with trigger=courier_event, sends outreach in customer language.
    - If RETURN_RECEIVED: marks return received, creates separate PROPOSE_REFUND proposal (B07).
    """
    repo: Repository = request.app.state.repo
    engine: WorkflowEngine = request.app.state.engine
    now_iso = datetime.now(timezone.utc).isoformat()

    event_id = getattr(payload, "event_id", None) or f"EVT-COUR-{payload.shipment_id}-{payload.type.value}-{payload.attempt_no}"

    # 1. Dedupe check by event_id (Test 45)
    with repo.db.cursor() as cur:
        cur.execute("SELECT * FROM courier_events WHERE event_id = ?", (event_id,))
        if cur.fetchone():
            return {
                "status": "replayed",
                "event_id": event_id,
                "message": "Courier event already processed",
            }

    # 2. Insert courier event record
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO courier_events (event_id, shipment_id, type, attempt_no, reason, received_at, simulated)
            VALUES (?, ?, ?, ?, ?, ?, 1)
            """,
            (event_id, payload.shipment_id, payload.type.value, payload.attempt_no, payload.reason, now_iso),
        )

    # 3. Locate shipment and order
    with repo.db.cursor() as cur:
        cur.execute("SELECT * FROM shipments WHERE shipment_id = ?", (payload.shipment_id,))
        shp_row = cur.fetchone()
        if not shp_row:
            # Maybe shipment_id was passed as return shipment ID
            cur.execute("SELECT * FROM returns WHERE return_id = ?", (payload.shipment_id,))
            ret_row = cur.fetchone()
            if ret_row:
                order_id = ret_row["order_id"]
            else:
                raise HTTPException(status_code=404, detail=f"Shipment {payload.shipment_id} not found")
        else:
            order_id = shp_row["order_id"]

    order = repo.get_order(order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {order_id} not found")

    customer = repo.get_customer_profile(order.customer_id)

    # 4. Handle NDR Event (02 §4b, B14)
    if payload.type == CourierEventType.NDR:
        # Find existing case or create NDR case
        with repo.db.cursor() as cur:
            cur.execute(
                "SELECT case_id FROM cases WHERE order_id = ? AND state NOT IN ('RESOLVED') ORDER BY created_at DESC",
                (order_id,),
            )
            case_row = cur.fetchone()

        if case_row:
            case_id = case_row["case_id"]
        else:
            case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
            repo.create_case(
                case_id=case_id,
                order_id=order_id,
                customer_id=order.customer_id,
                case_type=CaseType.NDR,
                initial_message=f"Courier NDR: {payload.reason}",
            )

        # Append courier_event_received audit event (17 §7)
        repo.append_audit_event(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            actor="courier:mock",
            event_type="courier_event_received",
            outcome=f"Courier: delivery failed (attempt {payload.attempt_no})",
            case_id=case_id,
            refs=[f"shipment:{payload.shipment_id}", f"event:{event_id}"],
            safe_payload={"reason": payload.reason, "attempt_no": payload.attempt_no},
        )

        # Enqueue job with trigger_type = courier_event (Test 45)
        job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        with repo.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, case_id, input_revision, status, attempts, trigger_type, created_at, updated_at)
                VALUES (?, ?, 1, 'pending', 0, 'courier_event', ?, ?)
                """,
                (job_id, case_id, now_iso, now_iso),
            )

        # Agent sends proactive notification in customer language (17 §6, 18 §2 S07)
        customer_lang = customer.preferred_language if customer else Language.EN
        if customer_lang == Language.HINGLISH:
            outreach = f"Hi {customer.name if customer else ''}, Delhivery was unable to deliver order {order_id} (attempt {payload.attempt_no}): {payload.reason or 'customer not available'}. Please reply with your updated address."
        else:
            outreach = f"Hi {customer.name if customer else ''}, delivery attempt {payload.attempt_no} for order {order_id} failed: {payload.reason or 'customer not available'}. Please reply to confirm or update your address."

        outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
        repo.add_message(
            message_id=outbound_msg_id,
            case_id=case_id,
            actor_id="agent:returnlens",
            role=ActorRole.AGENT,
            text=outreach,
            language=customer_lang,
        )

        repo.append_audit_event(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            actor="agent:returnlens",
            event_type="customer_reply_delivered",
            outcome="Sent NDR address verification message",
            case_id=case_id,
            refs=[f"msg:{outbound_msg_id}"],
        )

        repo.update_case_state(case_id, CaseState.WAITING_CUSTOMER, summary="Awaiting customer address update for NDR reattempt")

        return {
            "status": "processed",
            "type": "NDR",
            "case_id": case_id,
            "job_id": job_id,
        }

    # 5. Handle RETURN_RECEIVED Event (02 §4b, B07)
    elif payload.type == CourierEventType.RETURN_RECEIVED:
        # Mark return record as received
        with repo.db.transaction() as conn:
            conn.execute(
                """
                UPDATE returns
                SET status = 'received'
                WHERE order_id = ? AND status = 'requested'
                """,
                (order_id,),
            )

        # Find active case in WAITING_RETURN
        with repo.db.cursor() as cur:
            cur.execute(
                """
                SELECT case_id FROM cases
                WHERE order_id = ? AND state IN ('WAITING_RETURN', 'WAITING_SELLER', 'PROCESSING')
                ORDER BY created_at DESC
                """,
                (order_id,),
            )
            case_row = cur.fetchone()
            case_id = case_row["case_id"] if case_row else f"CASE-{uuid.uuid4().hex[:8].upper()}"

        # Append courier_event_received audit event (17 §7)
        repo.append_audit_event(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            actor="courier:mock",
            event_type="courier_event_received",
            outcome="Courier: return received at warehouse",
            case_id=case_id,
            refs=[f"order:{order_id}", f"event:{event_id}"],
        )

        # Create separate refund proposal (02 §4b, B07)
        refund_amount_minor = order.paid_minor - order.refunded_minor - order.reserved_minor
        proposal_id = f"PRP-{uuid.uuid4().hex[:8].upper()}"

        payload_dict = {
            "case_id": case_id,
            "action_type": NextStep.PROPOSE_REFUND.value,
            "item_id": order.line_item.item_id,
            "amount_minor": refund_amount_minor,
            "currency": "INR",
        }
        payload_hash = compute_payload_hash(payload_dict)

        basis = ProposalBasis(
            evidence_revision=1,
            observation_set_revision=1,
            order_revision=order.revision,
            shipment_revision=1,
            policy_version="1.0",
            action_fields={"order_id": order_id, "amount_minor": refund_amount_minor},
            amount_minor=refund_amount_minor,
        )

        proposal = Proposal(
            proposal_id=proposal_id,
            case_id=case_id,
            action_type=NextStep.PROPOSE_REFUND,
            item_id=order.line_item.item_id,
            amount_minor=refund_amount_minor,
            currency="INR",
            customer_reply_draft=f"Your refund of ₹{refund_amount_minor/100:.2f} for {order_id} has been authorized.",
            basis=basis,
            status="pending",
            payload_hash=payload_hash,
        )
        repo.create_proposal(proposal)

        repo.append_audit_event(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            actor="agent:returnlens",
            event_type="proposal_created",
            outcome=f"Created proposal for PROPOSE_REFUND (₹{refund_amount_minor/100:.2f})",
            case_id=case_id,
            refs=[f"proposal:{proposal_id}", f"order:{order_id}"],
            safe_payload={"amount_minor": refund_amount_minor, "payload_hash": payload_hash},
        )

        repo.update_case_state(case_id, CaseState.WAITING_SELLER, summary="Return received at warehouse; refund proposal pending approval")

        return {
            "status": "processed",
            "type": "RETURN_RECEIVED",
            "case_id": case_id,
            "proposal_id": proposal_id,
            "refund_amount_minor": refund_amount_minor,
        }

    return {"status": "unhandled_type", "type": payload.type.value}
