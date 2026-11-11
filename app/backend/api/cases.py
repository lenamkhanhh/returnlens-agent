"""Case and Chat API Endpoints per 17 §5 and 02 §3.

Exposes REST routes for case creation, role-scoped snapshot queries,
message dispatch, and event stream timelines.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Header, HTTPException, Query, Request

from app.backend.contracts import (
    ActorRole,
    CaseSnapshotResponse,
    CaseState,
    CaseType,
    CreateCaseRequest,
    CreateCaseResponse,
    Message,
)
from app.backend.persistence.repository import Repository
from app.backend.workflow.engine import WorkflowEngine

router = APIRouter(prefix="/api", tags=["cases"])


@router.post("/cases", status_code=202, response_model=CreateCaseResponse)
async def create_case(
    payload: CreateCaseRequest,
    request: Request,
    x_customer_id: Optional[str] = Header(None, alias="X-Customer-Id"),
    customer_id_query: Optional[str] = Query(None, alias="customer_id"),
):
    """Create a case from customer inquiry, initialize durable job, and return 202."""
    repo: Repository = request.app.state.repo
    engine: WorkflowEngine = request.app.state.engine

    # Resolve customer ID (header or query or look up from order)
    customer_id = x_customer_id or customer_id_query
    order = repo.get_order(payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {payload.order_id} not found")

    # Inaccessible/scoped check (02 §1, Test 03: if customer_id supplied, it must match order)
    if customer_id and order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail=f"Order {payload.order_id} not found for customer")

    effective_customer_id = customer_id or order.customer_id

    result = engine.create_case_with_job(
        order_id=payload.order_id,
        customer_id=effective_customer_id,
        initial_message=payload.initial_message,
        client_message_id=payload.client_message_id,
    )

    return CreateCaseResponse(
        case_id=result["case_id"],
        accepted_revision=result["accepted_revision"],
        job_id=result["job_id"],
    )


@router.get("/cases/{case_id}", response_model=CaseSnapshotResponse)
async def get_case_snapshot(
    case_id: str,
    request: Request,
    x_customer_id: Optional[str] = Header(None, alias="X-Customer-Id"),
    customer_id_query: Optional[str] = Query(None, alias="customer_id"),
):
    """Retrieve full case snapshot for customer or seller console (17 §5)."""
    repo: Repository = request.app.state.repo
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    # Access boundary check
    customer_id = x_customer_id or customer_id_query
    if customer_id and case.customer_id != customer_id:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not accessible")

    order = repo.get_order(case.order_id)
    shipment = repo.get_shipment(case.order_id)
    messages = repo.get_case_messages(case_id)
    proposals = repo.list_case_proposals(case_id)
    events = repo.list_case_audit_events(case_id)
    autonomy_policy = repo.get_autonomy_policy()

    facts = {
        "order": order.model_dump() if order else None,
        "shipment": shipment.model_dump() if shipment else None,
    }

    autonomy_info = {
        "case_type_level": autonomy_policy.levels.get(case.case_type, "L0"),
        "kill_switch": autonomy_policy.kill_switch,
        "per_order_cap_minor": autonomy_policy.per_order_cap_minor,
        "per_customer_daily_cap_minor": autonomy_policy.per_customer_daily_cap_minor,
    }

    latest_event_seq = events[-1].seq if events else 0

    return CaseSnapshotResponse(
        case_id=case.case_id,
        case_type=case.case_type,
        state=case.state,
        facts=facts,
        observations=[],
        unknowns=[],
        policy_checks=[],
        plan=None,
        clarification_count=case.clarification_count,
        proposals=[p.model_dump() for p in proposals],
        autonomy=autonomy_info,
        event_cursor=latest_event_seq,
    )


@router.post("/cases/{case_id}/messages", status_code=202)
async def add_case_message(
    case_id: str,
    payload: Dict[str, Any],
    request: Request,
    x_customer_id: Optional[str] = Header(None, alias="X-Customer-Id"),
):
    """Add message to existing case and trigger subsequent workflow job."""
    repo: Repository = request.app.state.repo
    engine: WorkflowEngine = request.app.state.engine

    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message text is required")

    client_msg_id = payload.get("client_message_id")
    msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"

    # Save inbound customer message
    repo.add_message(
        message_id=msg_id,
        case_id=case_id,
        actor_id=case.customer_id,
        role=ActorRole.CUSTOMER,
        text=text,
        client_message_id=client_msg_id,
    )

    # Append audit event
    repo.append_audit_event(
        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
        actor=f"customer:{case.customer_id}",
        event_type="message_received",
        outcome="Inbound customer message received",
        case_id=case_id,
        safe_payload={"text": text, "client_message_id": client_msg_id},
    )

    # Enqueue new job
    job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, case_id, input_revision, status, attempts, trigger_type, created_at, updated_at)
            VALUES (?, ?, ?, 'pending', 0, 'message', ?, ?)
            """,
            (job_id, case_id, case.input_revision + 1, now_iso, now_iso),
        )

    # Process job synchronously
    engine.process_job(job_id)

    return {"status": "accepted", "job_id": job_id}


@router.get("/cases/{case_id}/events")
async def get_case_events(
    case_id: str,
    request: Request,
    after_seq: int = Query(0, ge=0),
):
    """Stream or poll case audit events for timeline drawer (17 §6, 02 §8)."""
    repo: Repository = request.app.state.repo
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    events = repo.list_case_audit_events(case_id, after_seq=after_seq)
    return [e.model_dump() for e in events]


@router.get("/seller/cases")
async def list_seller_cases(
    request: Request,
    state: Optional[str] = None,
):
    """List all cases for seller inbox (02 §3)."""
    repo: Repository = request.app.state.repo
    with repo.db.cursor() as cur:
        if state:
            cur.execute("SELECT * FROM cases WHERE state = ? ORDER BY updated_at DESC", (state,))
        else:
            cur.execute("SELECT * FROM cases ORDER BY updated_at DESC")
        cases = []
        for row in cur.fetchall():
            cases.append(
                {
                    "case_id": row["case_id"],
                    "order_id": row["order_id"],
                    "customer_id": row["customer_id"],
                    "case_type": row["case_type"],
                    "state": row["state"],
                    "clarification_count": row["clarification_count"],
                    "summary": row["summary"],
                    "updated_at": row["updated_at"],
                }
            )
        return cases
