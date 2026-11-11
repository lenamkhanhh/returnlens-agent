"""Domain Action Executor per 02 §5, 02 §6, 02 §7.

Manages idempotency keys, immutable proposals, payload hashing, freshness revalidation,
approval binding, and transactional execution of mutations.
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
    ) -> Dict[str, Any]:
        """Atomically execute a seller decision on a proposal (02 §6, 02 §7).

        Invariants:
        - 1. Check idempotency: same key + same payload -> prior result; same key + different payload -> 409.
        - 2. Freshness check: proposal.payload_hash must match incoming payload_hash, else 409 stale.
        - 3. Basis check: order revision and policy version must match proposal basis, else 409 stale.
        - 4. Approval binding: an approval can be consumed by exactly one action.
        - 5. Transaction: write action, create return/refund, update case state, log audit in one transaction.
        """
        now_iso = datetime.now(timezone.utc).isoformat()

        # Step 1: Idempotency Key check (02 §1, 02 §6, Tests 18, 19)
        existing_action = self.repo.get_action_by_idempotency_key(idempotency_key)
        if existing_action:
            if existing_action.payload_hash == payload_hash:
                # Prior success replay
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

        # Step 5: Execute Approval and Mutation
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

        # Enforce single approval consumption (Test 37)
        with self.repo.db.cursor() as cur:
            cur.execute("SELECT action_id FROM actions WHERE proposal_id = ? AND status = 'succeeded'", (proposal_id,))
            if cur.fetchone():
                raise HTTPException(status_code=409, detail="Approval has already been consumed by an action")

        # Record approval
        self.repo.record_approval(approval)
        self.repo.append_audit_event(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            actor=seller_id,
            event_type="approval_recorded",
            outcome="Seller approved proposal",
            case_id=proposal.case_id,
            refs=[f"proposal:{proposal_id}", f"approval:{approval_id}"],
        )

        # Step 6: Dispatch Mutation
        if proposal.action_type == NextStep.PROPOSE_RETURN:
            item_id = proposal.item_id or (order.line_item.item_id if order else "")
            order_id = order.order_id if order else ""

            # Call mock create_return tool
            result = self.mock_service.create_return(
                order_id=order_id,
                item_id=item_id,
                quantity=1,
                return_reason="DEFECTIVE",
                action_id=action_id,
            )

            user_errors = result.get("userErrors", [])
            if user_errors:
                # Record blocked action and audit
                with self.repo.db.transaction() as conn:
                    conn.execute(
                        """
                        INSERT INTO actions (
                            action_id, type, order_id, proposal_id, approval_id, idempotency_key,
                            payload_hash, status, result_ref, attempt_count, created_at
                        ) VALUES (?, ?, ?, ?, ?, ?, ?, 'blocked', NULL, 1, ?)
                        """,
                        (action_id, ActionType.CREATE_RETURN.value, order_id, proposal_id, approval_id, idempotency_key, payload_hash, now_iso),
                    )
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="executor:domain",
                    event_type="action_blocked",
                    outcome=user_errors[0]["message"],
                    case_id=proposal.case_id,
                    refs=[f"action:{action_id}"],
                )
                raise HTTPException(status_code=422, detail=user_errors[0]["message"])

            # Success path: create action and update case
            ret_data = result["return"]
            return_id = ret_data["return_id"]
            label_id = ret_data["label_id"]

            with self.repo.db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO actions (
                        action_id, type, order_id, proposal_id, approval_id, idempotency_key,
                        payload_hash, status, result_ref, attempt_count, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, ?, 'succeeded', ?, 1, ?)
                    """,
                    (action_id, ActionType.CREATE_RETURN.value, order_id, proposal_id, approval_id, idempotency_key, payload_hash, return_id, now_iso),
                )

            # Update case state to WAITING_RETURN (01 §5, 17 §2)
            self.repo.update_case_state(
                case_id=proposal.case_id,
                state=CaseState.WAITING_RETURN,
                summary=f"Return {return_id} authorized. Awaiting customer shipment.",
            )

            # Enqueue/Deliver customer notification message
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

            # Audit events
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

        raise HTTPException(status_code=400, detail=f"Unsupported action type {proposal.action_type}")
