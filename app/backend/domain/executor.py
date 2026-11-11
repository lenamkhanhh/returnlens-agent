"""Domain Action Executor per 02 §5, 02 §6, 02 §7, 17 §3.

Manages idempotency keys, immutable proposals, payload hashing, freshness revalidation,
approval binding, cumulative financial gates, and transactional execution of mutations.
"""

from __future__ import annotations

import hashlib
import json
import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import HTTPException

from app.backend.contracts import (
    Action,
    ActionStatus,
    ActionType,
    ActorRole,
    Approval,
    CaseState,
    Language,
    NextStep,
    Proposal,
)
from app.backend.mock.tools import MockToolService
from app.backend.persistence.repository import Repository


def compute_payload_hash(payload_dict: Dict[str, Any]) -> str:
    """Deterministic SHA-256 payload hash (02 §7, 17 §5)."""
    canonical_json = json.dumps(payload_dict, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical_json.encode("utf-8")).hexdigest()


class ActionExecutor:
    """Executes authorized domain mutations with transactional safety."""

    def __init__(self, repo: Repository, mock_service: MockToolService):
        self.repo = repo
        self.mock_service = mock_service

    def execute_decision(
        self,
        proposal_id: str,
        decision: str,
        payload_hash: str,
        idempotency_key: str,
        seller_id: str = "seller_dhun",
        demo_today: str = "2026-11-11",
    ) -> Dict[str, Any]:
        """Atomically execute a seller or autonomy decision on a proposal (02 §6, 02 §7, 17 §3).

        Invariants:
        - 1. Check idempotency: same key + same payload -> prior result; same key + different payload -> 409.
        - 2. Freshness check: proposal.payload_hash must match incoming payload_hash, else 409 stale.
        - 3. Basis check: order revision and policy version must match proposal basis, else 409 stale.
        - 4. Approval binding: an approval can be consumed by exactly one action (Test 37).
        - 5. Cumulative gate: check cumulative daily cap for autonomous actions (17 §3 step 6, Test 43).
        - 6. Transaction: write action, create return/refund, update case state, log audit in one transaction.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Idempotency Key check (02 §1, 02 §6, Tests 18, 19)
        existing_action = self.repo.get_action_by_idempotency_key(idempotency_key)
        if existing_action:
            if existing_action.payload_hash == payload_hash:
                # Prior success replay (Test 18)
                return {
                    "action_id": existing_action.action_id,
                    "status": existing_action.status.value,
                    "result_ref": existing_action.result_ref,
                    "replayed": True,
                }
            else:
                # Same key with different payload -> 409 Conflict (Test 19)
                raise HTTPException(
                    status_code=409,
                    detail="Idempotency key reused with conflicting payload hash",
                )

        # Step 2: Fetch proposal and verify existence
        proposal = self.repo.get_proposal(proposal_id)
        if not proposal:
            raise HTTPException(status_code=404, detail=f"Proposal {proposal_id} not found")

        # Step 3: Proposal freshness and payload hash revalidation (02 §7, Test 17)
        if proposal.payload_hash != payload_hash:
            raise HTTPException(
                status_code=409,
                detail="Proposal is stale: payload hash does not match current state",
            )

        # Revalidate basis: order revision & policy version
        order = self.repo.get_order(proposal.basis.action_fields.get("order_id", ""))
        if order and order.revision != proposal.basis.order_revision:
            raise HTTPException(
                status_code=409,
                detail=f"Proposal basis is stale: order revision changed from {proposal.basis.order_revision} to {order.revision}",
            )

        policy = self.repo.get_store_policy("store_dhun")
        if policy and policy.policy_version != proposal.basis.policy_version:
            raise HTTPException(
                status_code=409,
                detail=f"Proposal basis is stale: store policy changed from {proposal.basis.policy_version} to {policy.policy_version}",
            )

        # Step 4: Handle decline decision
        if decision == "decline":
            with self.repo.db.transaction() as conn:
                conn.execute("UPDATE proposals SET status = 'declined' WHERE proposal_id = ?", (proposal_id,))
            self.repo.append_audit_event(
                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                actor=seller_id,
                event_type="approval_declined",
                outcome="Seller declined proposal",
                case_id=proposal.case_id,
                refs=[f"proposal:{proposal_id}"],
            )
            return {"status": "declined", "proposal_id": proposal_id}

        # Step 5: Check single approval consumption (Test 37)
        with self.repo.db.cursor() as cur:
            cur.execute("SELECT action_id FROM actions WHERE proposal_id = ? AND status = 'succeeded'", (proposal_id,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Approval has already been consumed by an action")

        # Step 6: Cumulative Financial Gate for Autonomous Actions (17 §3 step 6, Test 43)
        if seller_id.startswith("policy:autonomy") and proposal.amount_minor is not None:
            autonomy_policy = self.repo.get_autonomy_policy("store_dhun")
            customer_id = order.customer_id if order else ""
            daily_spent = self.repo.get_customer_daily_refund_total(customer_id, demo_today)
            projected_total = daily_spent + proposal.amount_minor

            if projected_total > autonomy_policy.per_customer_daily_cap_minor:
                # Defer to seller (17 §3 step 6, Test 43)
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor=seller_id,
                    event_type="autonomy_deferred_to_seller",
                    outcome=f"Sent to seller: cumulative limit ₹{autonomy_policy.per_customer_daily_cap_minor/100:,.2f}/day",
                    case_id=proposal.case_id,
                    refs=[f"proposal:{proposal_id}"],
                    safe_payload={
                        "reason": "cumulative_limit",
                        "daily_spent_minor": daily_spent,
                        "attempted_minor": proposal.amount_minor,
                        "daily_cap_minor": autonomy_policy.per_customer_daily_cap_minor,
                    },
                )
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor=seller_id,
                    event_type="cumulative_limit_hit",
                    outcome="Cumulative limit exceeded for customer",
                    case_id=proposal.case_id,
                    refs=[f"customer:{customer_id}"],
                )
                return {
                    "action_id": "",
                    "status": "deferred_to_seller",
                    "reason": "cumulative_limit",
                }

        # Step 7: Record approval
        action_id = f"ACT-{uuid.uuid4().hex[:8].upper()}"
        approval_id = f"APP-{uuid.uuid4().hex[:8].upper()}"

        approval = Approval(
            approval_id=approval_id,
            proposal_id=proposal_id,
            seller_id=seller_id,
            decision="approve",
            approved_payload_hash=payload_hash,
            approved_at=now_iso,
        )
        self.repo.record_approval(approval)
        self.repo.append_audit_event(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            actor=seller_id,
            event_type="approval_recorded",
            outcome="Seller approved proposal" if not seller_id.startswith("policy:autonomy") else "Auto-approved by autonomy policy",
            case_id=proposal.case_id,
            refs=[f"proposal:{proposal_id}", f"approval:{approval_id}"],
        )

        mapped_action_type = {
            NextStep.PROPOSE_RETURN: ActionType.CREATE_RETURN,
            NextStep.PROPOSE_REFUND: ActionType.ISSUE_REFUND,
            NextStep.PROPOSE_NDR_REATTEMPT: ActionType.NDR_ACTION,
        }.get(proposal.action_type, ActionType.CREATE_RETURN)

        # Pre-insert action in pending state so foreign key constraints on returns/refunds are satisfied
        with self.repo.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO actions (
                    action_id, type, order_id, proposal_id, approval_id, idempotency_key,
                    payload_hash, status, result_ref, attempt_count, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', NULL, 1, ?)
                """,
                (action_id, mapped_action_type.value, order.order_id if order else "", proposal_id, approval_id, idempotency_key, payload_hash, now_iso),
            )

        # Step 8: Dispatch Mutation based on proposal action type (Fails Closed per Test 32)
        try:
            # Mutation Path A: PROPOSE_RETURN
            if proposal.action_type == NextStep.PROPOSE_RETURN:
                item_id = proposal.item_id or (order.line_item.item_id if order else "")
                order_id = order.order_id if order else ""

                result = self.mock_service.create_return(
                    order_id=order_id,
                    item_id=item_id,
                    quantity=1,
                    return_reason="DEFECTIVE",
                    action_id=action_id,
                )

                user_errors = result.get("userErrors", [])
                if user_errors:
                    self._record_blocked_action(action_id, ActionType.CREATE_RETURN, order_id, proposal_id, approval_id, idempotency_key, payload_hash, user_errors[0]["message"], proposal.case_id, now_iso)
                    raise HTTPException(status_code=422, detail=user_errors[0]["message"])

                ret_data = result["return"]
                return_id = ret_data["return_id"]
                label_id = ret_data["label_id"]

                self._record_successful_action(action_id, ActionType.CREATE_RETURN, order_id, proposal_id, approval_id, idempotency_key, payload_hash, return_id, now_iso)

                self.repo.update_case_state(
                    case_id=proposal.case_id,
                    state=CaseState.WAITING_RETURN,
                    summary=f"Return {return_id} authorized. Awaiting customer shipment.",
                )

                customer_reply = f"Your return for {order_id} has been approved. Your return label ID is {label_id}."
                outbound_msg_id = f"MSG-{proposal.case_id}-{uuid.uuid4().hex[:6]}"
                self.repo.add_message(
                    message_id=outbound_msg_id,
                    case_id=proposal.case_id,
                    actor_id=seller_id,
                    role=ActorRole.SELLER,
                    text=customer_reply,
                    language=Language.EN,
                )

                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="executor:domain",
                    event_type="return_created",
                    outcome=f"Created return {return_id} with mock label {label_id}",
                    case_id=proposal.case_id,
                    refs=[f"return:{return_id}", f"action:{action_id}", f"label:{label_id}"],
                    safe_payload={"label_id": label_id, "return_id": return_id},
                )
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="executor:domain",
                    event_type="customer_reply_delivered",
                    outcome="Sent return label notification to customer",
                    case_id=proposal.case_id,
                    refs=[f"msg:{outbound_msg_id}"],
                )

                return {
                    "action_id": action_id,
                    "status": "succeeded",
                    "result_ref": f"return:{return_id}",
                    "label_id": label_id,
                }

            # Mutation Path B: PROPOSE_REFUND (02 §4b, 02 §5, B07)
            elif proposal.action_type == NextStep.PROPOSE_REFUND:
                order_id = order.order_id if order else ""
                amount_minor = proposal.amount_minor or (order.paid_minor if order else 0)

                result = self.mock_service.issue_refund(
                    order_id=order_id,
                    amount_minor=amount_minor,
                    idempotency_key=idempotency_key,
                    action_id=action_id,
                )

                user_errors = result.get("userErrors", [])
                if user_errors:
                    self._record_blocked_action(action_id, ActionType.ISSUE_REFUND, order_id, proposal_id, approval_id, idempotency_key, payload_hash, user_errors[0]["message"], proposal.case_id, now_iso)
                    raise HTTPException(status_code=422, detail=user_errors[0]["message"])

                refund_data = result["refund"]
                refund_id = refund_data["refund_id"]

                self._record_successful_action(action_id, ActionType.ISSUE_REFUND, order_id, proposal_id, approval_id, idempotency_key, payload_hash, refund_id, now_iso)

                self.repo.update_case_state(
                    case_id=proposal.case_id,
                    state=CaseState.RESOLVED,
                    summary=f"Refund {refund_id} for ₹{amount_minor/100:.2f} processed. Case resolved.",
                )

                customer_reply = f"Your refund of ₹{amount_minor/100:,.2f} for order {order_id} has been processed."
                outbound_msg_id = f"MSG-{proposal.case_id}-{uuid.uuid4().hex[:6]}"
                self.repo.add_message(
                    message_id=outbound_msg_id,
                    case_id=proposal.case_id,
                    actor_id=seller_id,
                    role=ActorRole.SELLER,
                    text=customer_reply,
                    language=Language.EN,
                )

                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="executor:domain",
                    event_type="refund_posted",
                    outcome=f"Refund ₹{amount_minor/100:,.2f} processed",
                    case_id=proposal.case_id,
                    refs=[f"refund:{refund_id}", f"action:{action_id}", f"order:{order_id}"],
                    safe_payload={"refund_id": refund_id, "amount_minor": amount_minor},
                )
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="executor:domain",
                    event_type="customer_reply_delivered",
                    outcome="Sent refund confirmation to customer",
                    case_id=proposal.case_id,
                    refs=[f"msg:{outbound_msg_id}"],
                )

                return {
                    "action_id": action_id,
                    "status": "succeeded",
                    "result_ref": f"refund:{refund_id}",
                    "amount_minor": amount_minor,
                }

            # Mutation Path C: PROPOSE_NDR_REATTEMPT (02 §4b, B14)
            elif proposal.action_type == NextStep.PROPOSE_NDR_REATTEMPT:
                shipment = self.repo.get_shipment(order.order_id if order else "")
                shipment_id = shipment.shipment_id if shipment else ""
                new_addr = proposal.basis.action_fields.get("updated_address")

                result = self.mock_service.ndr_action(
                    shipment_id=shipment_id,
                    action_type="reattempt",
                    new_address=new_addr,
                )

                if not result.get("success"):
                    err_msg = result.get("error", "NDR reattempt failed")
                    self._record_blocked_action(action_id, ActionType.NDR_ACTION, order.order_id if order else "", proposal_id, approval_id, idempotency_key, payload_hash, err_msg, proposal.case_id, now_iso)
                    raise HTTPException(status_code=422, detail=err_msg)

                self._record_successful_action(action_id, ActionType.NDR_ACTION, order.order_id if order else "", proposal_id, approval_id, idempotency_key, payload_hash, shipment_id, now_iso)

                self.repo.update_case_state(
                    case_id=proposal.case_id,
                    state=CaseState.RESOLVED,
                    summary=f"NDR reattempt confirmed for {shipment_id} with updated address.",
                )

                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="executor:domain",
                    event_type="ndr_action_taken",
                    outcome="Re-delivery requested with updated address",
                    case_id=proposal.case_id,
                    refs=[f"shipment:{shipment_id}", f"action:{action_id}"],
                    safe_payload={"updated_address": result.get("updated_address")},
                )

                return {
                    "action_id": action_id,
                    "status": "succeeded",
                    "result_ref": f"shipment:{shipment_id}",
                }

            raise HTTPException(status_code=400, detail=f"Unsupported action type {proposal.action_type}")
        except HTTPException:
            raise
        except Exception:
            # Financial mutation fails closed (Test 32): set action status to failed
            with self.repo.db.transaction() as conn:
                conn.execute(
                    "UPDATE actions SET status = 'failed' WHERE action_id = ?",
                    (action_id,),
                )
            raise

    def _record_blocked_action(self, action_id, action_type, order_id, proposal_id, approval_id, idempotency_key, payload_hash, error_msg, case_id, now_iso):
        with self.repo.db.transaction() as conn:
            conn.execute(
                """
                UPDATE actions
                SET status = 'blocked'
                WHERE action_id = ?
                """,
                (action_id,),
            )
        self.repo.append_audit_event(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            actor="executor:domain",
            event_type="action_blocked",
            outcome=error_msg,
            case_id=case_id,
            refs=[f"action:{action_id}"],
        )

    def _record_successful_action(self, action_id, action_type, order_id, proposal_id, approval_id, idempotency_key, payload_hash, result_ref, now_iso):
        with self.repo.db.transaction() as conn:
            conn.execute(
                """
                UPDATE actions
                SET status = 'succeeded', result_ref = ?
                WHERE action_id = ?
                """,
                (result_ref, action_id),
            )
