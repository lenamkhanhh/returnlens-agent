"""Workflow Engine and Durable Job Processor for ReturnLens.

Handles job lifecycle, router execution, mock tool dispatch, template replies,
and state transitions (17 §4, 02 §4).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from app.backend.contracts import (
    ActorRole,
    CaseState,
    CaseType,
    Intent,
    JobStatus,
    JobTrigger,
    Language,
)
from app.backend.mock.tools import MockToolService
from app.backend.persistence.repository import Repository
from app.backend.workflow.router import Router


class WorkflowEngine:
    """Orchestrates cases, jobs, tools, and message delivery."""

    def __init__(self, repo: Repository, mock_service: MockToolService):
        self.repo = repo
        self.mock_service = mock_service

    def create_case_with_job(
        self,
        order_id: str,
        customer_id: str,
        initial_message: str,
        client_message_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Atomically create case, store message, and enqueue durable job."""
        case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Initial intent inference
        route = Router.classify_and_route(initial_message, order_id)
        case_type = CaseType.WISMO if route.intent == Intent.WISMO else CaseType.UNCLEAR

        # 1. Create Case & initial inbound Message
        case = self.repo.create_case(
            case_id=case_id,
            order_id=order_id,
            customer_id=customer_id,
            case_type=case_type,
            initial_message=initial_message,
            client_message_id=client_message_id,
        )

        # 2. Append audit event: message_received
        self.repo.append_audit_event(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            actor=f"customer:{customer_id}",
            event_type="message_received",
            outcome="Inbound customer message received",
            case_id=case_id,
            refs=[f"order:{order_id}"],
            safe_payload={"text": initial_message, "client_message_id": client_message_id},
        )

        # 3. Create durable job
        with self.repo.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO jobs (job_id, case_id, input_revision, status, attempts, trigger_type, created_at, updated_at)
                VALUES (?, ?, 1, ?, 0, ?, ?, ?)
                """,
                (job_id, case_id, JobStatus.PENDING.value, JobTrigger.MESSAGE.value, now_iso, now_iso),
            )

        # 4. Process job synchronously for immediate execution
        self.process_job(job_id)

        return {
            "case_id": case_id,
            "accepted_revision": 1,
            "job_id": job_id,
        }

    def process_job(self, job_id: str) -> bool:
        """Execute durable job steps: router -> read tools -> reply/proposal -> audit."""
        now_iso = datetime.now(timezone.utc).isoformat()

        # 1. Claim job
        with self.repo.db.cursor() as cur:
            cur.execute("SELECT * FROM jobs WHERE job_id = ?", (job_id,))
            job_row = cur.fetchone()
            if not job_row:
                return False
            case_id = job_row["case_id"]

        case = self.repo.get_case(case_id)
        if not case:
            return False

        # Mark job leased
        with self.repo.db.transaction() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, attempts = attempts + 1, updated_at = ? WHERE job_id = ?",
                (JobStatus.LEASED.value, now_iso, job_id),
            )

        # 2. Get latest customer message
        messages = self.repo.get_case_messages(case_id)
        latest_customer_msg = next((m for m in reversed(messages) if m.role == ActorRole.CUSTOMER), None)
        text = latest_customer_msg.text if latest_customer_msg else ""

        # 3. Router: classify and dispatch
        route = Router.classify_and_route(text, case.order_id)

        # 4. Execute Read Tools (manual allowlist dispatch)
        tool_results: Dict[str, Any] = {}
        for tool_call in route.read_tools:
            tool_name = tool_call.name
            args = tool_call.args

            if tool_name == "get_order":
                result = self.mock_service.get_order(args["order_id"], customer_id=case.customer_id)
                tool_results["order"] = result
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="agent:returnlens",
                    event_type="tool_call_succeeded",
                    outcome=f"Checked order {case.order_id}",
                    case_id=case_id,
                    refs=[f"order:{case.order_id}"],
                    safe_payload={"tool": "get_order", "result": result},
                )

            elif tool_name == "get_tracking":
                result = self.mock_service.get_tracking(args["order_id"])
                tool_results["tracking"] = result
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="agent:returnlens",
                    event_type="tool_call_succeeded",
                    outcome="Checked tracking",
                    case_id=case_id,
                    refs=[f"shipment:{result.get('shipment_id', '')}"],
                    safe_payload={"tool": "get_tracking", "result": result},
                )

        # 5. Handle WISMO flow (Fast Path, 17/03)
        if route.intent == Intent.WISMO:
            tracking = tool_results.get("tracking", {})
            carrier = tracking.get("carrier_label", "Delhivery")
            status = tracking.get("status", "IN_TRANSIT")
            eta = tracking.get("eta")
            delivered_at = tracking.get("delivered_at")

            if status == "IN_TRANSIT":
                reply_text = f"Your order {case.order_id} is currently in transit with {carrier}. Estimated delivery: {eta}."
            elif status == "OUT_FOR_DELIVERY":
                reply_text = f"Your order {case.order_id} is out for delivery today with {carrier}."
            elif status == "DELIVERED":
                reply_text = f"Your order {case.order_id} was delivered on {delivered_at}."
            elif status == "NDR":
                reason = tracking.get("reason", "customer not available")
                reply_text = f"Delivery attempt failed for order {case.order_id}: {reason}. Please confirm your delivery address."
            else:
                reply_text = f"Your order {case.order_id} status is {status}."

            # Save agent outbound message
            outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
            self.repo.add_message(
                message_id=outbound_msg_id,
                case_id=case_id,
                actor_id="agent:returnlens",
                role=ActorRole.AGENT,
                text=reply_text,
                language=Language.EN,
            )

            # Record customer reply delivered audit event
            self.repo.append_audit_event(
                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                actor="agent:returnlens",
                event_type="customer_reply_delivered",
                outcome="Delivered tracking update",
                case_id=case_id,
                refs=[f"msg:{outbound_msg_id}", f"order:{case.order_id}"],
                safe_payload={"reply": reply_text},
            )

            # Mark case RESOLVED (per 18 §2 S01)
            self.repo.update_case_state(
                case_id=case_id,
                state=CaseState.RESOLVED,
                summary=f"Resolved WISMO inquiry for {case.order_id}: {status}",
            )

        # 6. Complete job
        with self.repo.db.transaction() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (JobStatus.COMPLETED.value, now_iso, job_id),
            )

        return True
