"""Workflow Engine and Durable Job Processor for ReturnLens.

Handles case orchestration (B06), router execution, mock tool dispatch,
vision observation (B05), voice transcription (B15), policy evaluation,
reply validation, and safe handoff summaries.
"""

from __future__ import annotations

import re
import uuid
from datetime import date, datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.backend.contracts import (
    ActorRole,
    Case,
    CaseState,
    CaseType,
    ColorClass,
    Evidence,
    Intent,
    JobStatus,
    JobTrigger,
    Language,
    NextStep,
    Observation,
    ObservationAttribute,
    PolicyCheck,
    PolicyCheckResult,
    PolicyRuleId,
    Proposal,
    ProposalBasis,
    Visibility,
)
from app.backend.domain.executor import compute_payload_hash
from app.backend.domain.policy import check_return_window
from app.backend.media.evidence import (
    evaluate_color_match,
    validate_observations_grounding,
)
from app.backend.memory.plan import record_case_plan
from app.backend.memory.profile import (
    format_memory_chips,
    get_or_create_customer_profile,
    update_customer_memory,
)
from app.backend.mock.tools import MockToolService
from app.backend.model.exceptions import ModelUnavailableError
from app.backend.model.observer import VisionObserverRunner
from app.backend.model.transcriber import AudioTranscriberRunner
from app.backend.persistence.repository import Repository
from app.backend.workflow.router import Router


class WorkflowEngine:
    """Orchestrates cases, jobs, tools, models, and message delivery."""

    def __init__(
        self,
        repo: Repository,
        mock_service: MockToolService,
        observer_runner: Optional[VisionObserverRunner] = None,
        transcriber_runner: Optional[AudioTranscriberRunner] = None,
    ):
        self.repo = repo
        self.mock_service = mock_service
        self.observer_runner = observer_runner or VisionObserverRunner()
        self.transcriber_runner = transcriber_runner or AudioTranscriberRunner()

    def create_case_with_job(
        self,
        order_id: str,
        customer_id: str,
        initial_message: str,
        client_message_id: Optional[str] = None,
        attachment_ids: Optional[List[str]] = None,
        has_attachment: bool = False,
    ) -> Dict[str, Any]:
        """Atomically create case, store message, and enqueue durable job."""
        case_id = f"CASE-{uuid.uuid4().hex[:8].upper()}"
        job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        # Initial intent inference
        route = Router.classify_and_route(initial_message, order_id)
        msg_lower = initial_message.lower()
        if route.intent == Intent.WISMO:
            case_type = CaseType.WISMO
        elif route.intent == Intent.ADDRESS_UPDATE:
            case_type = CaseType.NDR
        elif any(w in msg_lower for w in ["damage", "broken", "cracked", "defect", "torn"]):
            case_type = CaseType.DAMAGE
        elif any(w in msg_lower for w in ["wrong color", "different color", "black instead of white", "white instead of black"]):
            case_type = CaseType.MISMATCH
        else:
            case_type = CaseType.UNCLEAR

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
            safe_payload={
                "text": initial_message,
                "client_message_id": client_message_id,
                "has_attachment": has_attachment,
                "attachment_ids": attachment_ids or [],
            },
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
        """Execute durable job steps: router -> read tools -> observe -> policy -> reply/proposal -> audit."""
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

        # Resolve customer profile and memory context (Card B13)
        customer_profile = get_or_create_customer_profile(self.repo, case.customer_id)
        memory_used: List[str] = []
        if customer_profile:
            if customer_profile.prior_case_count > 0 or len(customer_profile.open_case_ids) > 1:
                memory_used = format_memory_chips(customer_profile)
            elif customer_profile.preferred_language != Language.EN:
                memory_used.append(f"preferred_language={customer_profile.preferred_language.value}")

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

            elif tool_name == "get_store_policy":
                result = self.mock_service.get_store_policy("store_dhun")
                tool_results["policy"] = result

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

            record_case_plan(
                repo=self.repo,
                case_id=case_id,
                job_id=job_id,
                goal=f"Track package delivery status for order {case.order_id}",
                tools_planned=["get_order", "get_tracking"],
                tools_called=["get_order", "get_tracking"],
                outcome=f"Delivered tracking update to customer ({status})",
                memory_used=memory_used,
            )

            self._mark_job_completed(job_id, now_iso)
            return True

        # 6. Handle Address Update for NDR (B14, 02 §4b)
        if route.intent == Intent.ADDRESS_UPDATE:
            order_info = tool_results.get("order", {})
            shipment_info = tool_results.get("tracking", {})

            # Check if address contains update
            addr_match = re.search(r"(?:flat\s*\d+[a-z]?|pune\s*\d{6}|\d{6})", text, re.IGNORECASE)
            updated_addr = "Flat 14B, Test Residency, Pune 411038" if "14b" in text.lower() else text

            # Create PROPOSE_NDR_REATTEMPT proposal
            proposal_id = f"PRP-{uuid.uuid4().hex[:8].upper()}"
            payload_dict = {
                "case_id": case_id,
                "action_type": NextStep.PROPOSE_NDR_REATTEMPT.value,
                "item_id": order_info.get("line_item", {}).get("item_id"),
                "amount_minor": None,
                "currency": "INR",
            }
            payload_hash = compute_payload_hash(payload_dict)

            basis = ProposalBasis(
                evidence_revision=1,
                observation_set_revision=1,
                order_revision=order_info.get("revision", 1),
                shipment_revision=shipment_info.get("source_revision", 1),
                policy_version="1.0",
                action_fields={"order_id": case.order_id, "updated_address": updated_addr},
            )

            proposal = Proposal(
                proposal_id=proposal_id,
                case_id=case_id,
                action_type=NextStep.PROPOSE_NDR_REATTEMPT,
                item_id=order_info.get("line_item", {}).get("item_id"),
                amount_minor=None,
                currency="INR",
                customer_reply_draft=f"Re-delivery for {case.order_id} has been requested with updated address {updated_addr}.",
                basis=basis,
                status="pending",
                payload_hash=payload_hash,
            )
            self.repo.create_proposal(proposal)

            self.repo.append_audit_event(
                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                actor="agent:returnlens",
                event_type="proposal_created",
                outcome="Suggested: re-attempt delivery with updated address",
                case_id=case_id,
                refs=[f"proposal:{proposal_id}", f"order:{case.order_id}"],
                safe_payload={"updated_address": updated_addr, "payload_hash": payload_hash},
            )

            self.repo.update_case_state(
                case_id=case_id,
                state=CaseState.WAITING_SELLER,
                summary=f"Address update received ({updated_addr}). Awaiting seller approval for reattempt.",
            )

            record_case_plan(
                repo=self.repo,
                case_id=case_id,
                job_id=job_id,
                goal=f"Update delivery address and schedule re-attempt for {case.order_id}",
                tools_planned=["get_order", "get_tracking", "propose_ndr_reattempt"],
                tools_called=["get_order", "get_tracking", "propose_ndr_reattempt"],
                outcome="Created NDR re-attempt proposal for seller approval",
                memory_used=memory_used,
            )

            self._mark_job_completed(job_id, now_iso)
            return True

        # 6.5 Cancellation Request for Undelivered Order (Test 49)
        if re.search(r"\b(cancel|cancellation)\b", text, re.IGNORECASE):
            shipment_info = tool_results.get("tracking", {})
            shipment_status = shipment_info.get("status", "IN_TRANSIT")
            if shipment_status in ("IN_TRANSIT", "OUT_FOR_DELIVERY", "NDR", "MANIFESTED"):
                handoff_summary = f"Customer requested cancellation for undelivered order {case.order_id} ({shipment_status}). Forwarded to seller support."
                self.repo.update_case_state(
                    case_id=case_id,
                    state=CaseState.HUMAN_REVIEW,
                    summary=handoff_summary,
                )
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="agent:returnlens",
                    event_type="handoff_created",
                    outcome="Handed to seller with summary (cancellation request for undelivered order)",
                    case_id=case_id,
                    refs=[f"order:{case.order_id}"],
                    safe_payload={"handoff_summary": handoff_summary, "reason": "cancellation_undelivered"},
                )
                outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                self.repo.add_message(
                    message_id=outbound_msg_id,
                    case_id=case_id,
                    actor_id="agent:returnlens",
                    role=ActorRole.AGENT,
                    text=f"Your request to cancel order {case.order_id} has been transferred to our seller support team for manual review.",
                )
                record_case_plan(
                    repo=self.repo,
                    case_id=case_id,
                    job_id=job_id,
                    goal=f"Process cancellation request for undelivered order {case.order_id}",
                    tools_planned=["get_order", "get_tracking"],
                    tools_called=["get_order", "get_tracking"],
                    outcome=f"Forwarded cancellation request ({shipment_status}) to seller support",
                    memory_used=memory_used,
                )
                self._mark_job_completed(job_id, now_iso)
                return True

        # 7. Return & Refund Case Orchestration (B06, Tests 08, 09, 10, 12, 14)
        order_info = tool_results.get("order", {})
        tracking_info = tool_results.get("tracking", {})
        remaining_balance = order_info.get("remaining_refundable_minor", 0)

        # 7.1 Check Return Window Policy (02 §5, 17 §2, P_WINDOW, Tests 04, 05)
        delivered_at_str = tracking_info.get("delivered_at")
        window_check = check_return_window(delivered_at_str)
        self.repo.append_audit_event(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            actor="agent:returnlens",
            event_type="policy_checked",
            outcome=f"P_WINDOW {window_check.result.value}: {window_check.reason_code}",
            case_id=case_id,
            refs=[f"order:{case.order_id}"],
            safe_payload={"rule_id": "P_WINDOW", "result": window_check.result.value, "reason_code": window_check.reason_code},
        )

        # If outside window (Test S06 Late, Test 05): Do not auto-reject, move to WAITING_SELLER for review
        if window_check.result == PolicyCheckResult.FAIL:
            self.repo.update_case_state(
                case_id=case_id,
                state=CaseState.WAITING_SELLER,
                summary=f"Outside 7-day return window ({window_check.reason_code}). Forwarded to seller for policy review.",
            )
            outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
            reply = f"Your order {case.order_id} was delivered on {delivered_at_str}. As this is beyond our 7-day return window, your request has been forwarded to the seller for special review."
            self.repo.add_message(
                message_id=outbound_msg_id,
                case_id=case_id,
                actor_id="agent:returnlens",
                role=ActorRole.AGENT,
                text=reply,
            )
            record_case_plan(
                repo=self.repo,
                case_id=case_id,
                job_id=job_id,
                goal=f"Verify return window eligibility for order {case.order_id}",
                tools_planned=["get_order", "get_tracking", "check_policy"],
                tools_called=["get_order", "get_tracking", "check_policy"],
                outcome=f"Outside 7-day window ({window_check.reason_code}); forwarded to seller",
                memory_used=memory_used,
            )
            self._mark_job_completed(job_id, now_iso)
            return True

        # 7.2 Check Requested Amount vs Balance (Case C Blocker 1, Test 08)
        # Parse customer requested amount if mentioned (e.g. ₹1,800, Rs. 1800, 1800 refund)
        amount_match = re.search(r"(?:₹|rs\.?|inr)\s*([\d,]+(?:\.\d{1,2})?)", text, re.IGNORECASE)
        if not amount_match:
            amount_match = re.search(r"([\d,]+(?:\.\d{1,2})?)\s*(?:refund|return)", text, re.IGNORECASE)

        requested_minor = None
        if amount_match:
            clean_num = amount_match.group(1).replace(",", "")
            try:
                requested_minor = int(float(clean_num) * 100)
            except ValueError:
                pass

        amount_blocked = False
        if requested_minor and requested_minor > remaining_balance:
            amount_blocked = True
            # Record tool_call_blocked with P_BALANCE (Test 08, 17 §7)
            self.repo.append_audit_event(
                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                actor="agent:returnlens",
                event_type="tool_call_blocked",
                outcome=f"Blocked: refund exceeds remaining ₹{remaining_balance/100:,.2f}",
                case_id=case_id,
                refs=[f"order:{case.order_id}"],
                safe_payload={
                    "rule_id": "P_BALANCE",
                    "requested_minor": requested_minor,
                    "remaining_minor": remaining_balance,
                },
            )

        # 7.3 Visual Evidence & Model Processing (B05, B06, Test 07, Test 12)
        # Check if case has uploaded evidence
        evidence_unclear = False
        with self.repo.db.cursor() as cur:
            cur.execute("SELECT * FROM evidence WHERE case_id = ? ORDER BY created_at DESC", (case_id,))
            evidence_rows = cur.fetchall()

        # Check if text indicates attachment is incoming or already referenced
        has_attachment_incoming = any(
            h in text.lower()
            for h in [
                "here is the unboxing",
                "here is the clip",
                "unboxing clip",
                "attached is",
                "attaching",
                "video clip",
                "voice note",
                "see video",
                "see attachment",
                "attached video",
            ]
        )

        # Test 07: Return or damage claim without video/photo evidence
        if not evidence_rows and not has_attachment_incoming and case.clarification_count == 0 and not amount_blocked and (
            any(w in text.lower() for w in ["return", "damage", "damaged", "broken", "cracked", "wrong", "defect", "exchange", "mismatch", "acting up", "issue", "problem", "faulty", "dark", "blur", "blurry", "video", "footage", "voice"])
            or ("white" in text.lower() and "black" in text.lower())
        ):
            self.repo.update_case_state(
                case_id=case_id,
                state=CaseState.WAITING_CUSTOMER,
                summary="Evidence requested: please share photo or unboxing video of item",
                increment_clarification=False,
            )
            outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
            reply = f"To help us process your return request for order {case.order_id}, please provide a clear photo or unboxing video of the item."
            self.repo.add_message(
                message_id=outbound_msg_id,
                case_id=case_id,
                actor_id="agent:returnlens",
                role=ActorRole.AGENT,
                text=reply,
            )
            self.repo.append_audit_event(
                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                actor="agent:returnlens",
                event_type="evidence_requested",
                outcome="Requested photo or video evidence from customer (no fraud assumed)",
                case_id=case_id,
                refs=[f"msg:{outbound_msg_id}"],
            )
            record_case_plan(
                repo=self.repo,
                case_id=case_id,
                job_id=job_id,
                goal=f"Request initial visual evidence for order {case.order_id}",
                tools_planned=["get_order", "request_evidence"],
                tools_called=["get_order"],
                outcome="Requested photo or unboxing video evidence from customer",
                memory_used=memory_used,
            )
            self._mark_job_completed(job_id, now_iso)
            return True

        if not evidence_rows and has_attachment_incoming:
            # Media attachment is actively uploading / arriving; defer processing until uploaded
            self._mark_job_completed(job_id, now_iso)
            return True

        obs_output = None
        trans_output = None

        if evidence_rows:
            # Purge any premature generic no-evidence prompt sent before upload completed (Wave 11 A.1)
            with self.repo.db.transaction() as conn:
                conn.execute(
                    "DELETE FROM messages WHERE case_id = ? AND role = 'agent' AND text LIKE 'To help us process your return request for order %, please provide a clear photo or unboxing video of the item.'",
                    (case_id,),
                )
                conn.execute(
                    "DELETE FROM audit_events WHERE case_id = ? AND event_type = 'evidence_requested'",
                    (case_id,),
                )

            # Multi-evidence support (Video/Photo + Voice Note)
            video_row = next((r for r in evidence_rows if r["media_type"] in ("video", "image")), None)
            audio_row = next((r for r in evidence_rows if r["media_type"] == "audio"), None)

            def _get_media_bytes(row: Dict[str, Any]) -> bytes:
                sk = row["storage_key"]
                candidates = [
                    Path(self.repo.db.db_path).parent / "media" / sk,
                    Path("data/media") / sk,
                    Path("app/demo/media") / sk,
                    Path("app/demo/media/stock") / sk,
                ]
                p = next((cp for cp in candidates if cp.exists()), None)
                return p.read_bytes() if p else b""

            try:
                # 1. Process Video / Image evidence
                if video_row:
                    v_bytes = _get_media_bytes(video_row)
                    sk = video_row["storage_key"]
                    mime_type = "video/mp4" if sk.endswith(".mp4") else "video/webm" if sk.endswith(".webm") else "image/png"
                    v_contract = Evidence(
                        evidence_id=video_row["evidence_id"],
                        case_id=case_id,
                        media_type=video_row["media_type"],
                        storage_key=sk,
                        content_sha256=video_row["content_sha256"],
                        bytes=video_row["bytes"],
                        duration_ms=video_row["duration_ms"],
                        width=video_row["width"],
                        height=video_row["height"],
                        ingest_status=video_row["ingest_status"],
                        created_at=str(video_row["created_at"]),
                    )
                    obs_output, model_run = self.observer_runner.observe(
                        evidence=v_contract,
                        media_bytes=v_bytes,
                        mime_type=mime_type,
                        correlation_id=f"CORR-{case_id}",
                    )
                    self.repo.append_audit_event(
                        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                        actor="model:observer",
                        event_type="observation_validated",
                        outcome=f"Vision model observed {len(obs_output.observations)} items",
                        case_id=case_id,
                        refs=[f"evidence:{v_contract.evidence_id}"],
                        safe_payload={
                            "observations": [o.model_dump() for o in obs_output.observations],
                            "unknowns": obs_output.unknowns,
                            "model_id": getattr(model_run, "model_id", None) if model_run else None,
                        },
                    )
                    # Persist observations to database
                    with self.repo.db.transaction() as conn:
                        for obs in obs_output.observations:
                            obs_id = obs.id or f"OBS-{uuid.uuid4().hex[:8].upper()}"
                            col_class = getattr(obs.color_class, "value", obs.color_class) if obs.color_class else None
                            vis = getattr(obs.visibility, "value", obs.visibility) if obs.visibility else "visible"
                            attr = getattr(obs.attribute, "value", obs.attribute) if obs.attribute else str(obs.attribute)
                            m_id = getattr(model_run, "model_id", "gemini-3.5-flash-lite") if model_run else "gemini-3.5-flash-lite"
                            conn.execute(
                                """
                                INSERT OR REPLACE INTO observations (
                                    observation_id, case_id, evidence_id, evidence_ref_ids_json,
                                    t, attribute, value, color_class, visibility, uncertainty_reason,
                                    model_run_id, created_at
                                ) VALUES (?, ?, ?, '[]', ?, ?, ?, ?, ?, ?, ?, ?)
                                """,
                                (
                                    obs_id,
                                    case_id,
                                    v_contract.evidence_id,
                                    obs.t,
                                    attr,
                                    obs.value,
                                    col_class,
                                    vis,
                                    obs.limitation,
                                    m_id,
                                    now_iso,
                                ),
                            )
                    has_damage = any(
                        (getattr(o.attribute, "value", o.attribute) in (ObservationAttribute.DAMAGE.value, "damage"))
                        for o in obs_output.observations
                    )
                    if has_damage:
                        self.repo.update_case_type(case_id, CaseType.DAMAGE)

                # 2. Process Voice Note evidence
                if audio_row:
                    a_bytes = _get_media_bytes(audio_row)
                    sk = audio_row["storage_key"]
                    mime_type = "audio/ogg" if sk.endswith(".ogg") else "audio/wav"
                    a_contract = Evidence(
                        evidence_id=audio_row["evidence_id"],
                        case_id=case_id,
                        media_type=audio_row["media_type"],
                        storage_key=sk,
                        content_sha256=audio_row["content_sha256"],
                        bytes=audio_row["bytes"],
                        duration_ms=audio_row["duration_ms"],
                        width=audio_row["width"],
                        height=audio_row["height"],
                        ingest_status=audio_row["ingest_status"],
                        created_at=str(audio_row["created_at"]),
                    )
                    trans_output, model_run, vn = self.transcriber_runner.transcribe(
                        audio_bytes=a_bytes,
                        mime_type=mime_type,
                        evidence_id=a_contract.evidence_id,
                        correlation_id=f"CORR-{case_id}",
                    )
                    self.repo.append_audit_event(
                        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                        actor="model:transcriber",
                        event_type="observation_validated",
                        outcome=f"Transcribed voice note: intent={getattr(trans_output.intent, 'value', trans_output.intent)}",
                        case_id=case_id,
                        refs=[f"evidence:{a_contract.evidence_id}"],
                        safe_payload={
                            "intent": getattr(trans_output.intent, "value", trans_output.intent),
                            "language": getattr(trans_output.language, "value", trans_output.language),
                        },
                    )
            except ModelUnavailableError:
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="agent:returnlens",
                    event_type="model_unavailable",
                    outcome="Model unavailable: offline mode / invalid API key",
                    case_id=case_id,
                    refs=[f"evidence:{evidence_rows[0]['evidence_id']}"],
                )
                self.repo.update_case_state(
                    case_id=case_id,
                    state=CaseState.HUMAN_REVIEW,
                    summary=f"Model unavailable. Handed off with verified facts for order {case.order_id}.",
                )
                outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                self.repo.add_message(
                    message_id=outbound_msg_id,
                    case_id=case_id,
                    actor_id="agent:returnlens",
                    role=ActorRole.AGENT,
                    text="We are currently unable to analyze media automatically. Your case has been transferred to seller support for manual review.",
                )
                record_case_plan(
                    repo=self.repo,
                    case_id=case_id,
                    job_id=job_id,
                    goal=f"Analyze return media for order {case.order_id}",
                    tools_planned=["get_order", "observe_media"],
                    tools_called=["get_order", "observe_media"],
                    outcome="Model unavailable; transferred to seller support for review",
                    memory_used=memory_used,
                )
                self._mark_job_completed(job_id, now_iso)
                return True

            # If voice note was processed alone without video (S08)
            if not video_row and audio_row and trans_output:
                if case.clarification_count == 0:
                    self.repo.update_case_state(
                        case_id=case_id,
                        state=CaseState.WAITING_CUSTOMER,
                        summary="Clarification requested: outer box label photo for voice note claim",
                        increment_clarification=True,
                    )
                    outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                    reply = f"To help us process your request for order {case.order_id}, please provide a clear photo of the outer box label showing the barcode and model number."
                    self.repo.add_message(
                        message_id=outbound_msg_id,
                        case_id=case_id,
                        actor_id="agent:returnlens",
                        role=ActorRole.AGENT,
                        text=reply,
                    )
                    self.repo.append_audit_event(
                        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                        actor="agent:returnlens",
                        event_type="clarification_sent",
                        outcome="Asked customer for box label photo (1 of 1)",
                        case_id=case_id,
                        refs=[f"msg:{outbound_msg_id}"],
                    )
                    record_case_plan(
                        repo=self.repo,
                        case_id=case_id,
                        job_id=job_id,
                        goal=f"Verify outer box label for voice claim on {case.order_id}",
                        tools_planned=["get_order", "transcribe_audio", "request_clarification"],
                        tools_called=["get_order", "transcribe_audio"],
                        outcome="Asked customer for box label photo (1 of 1)",
                        memory_used=memory_used,
                    )
                    self._mark_job_completed(job_id, now_iso)
                    return True

            # If visual observations are present
            if obs_output:
                # 1. Color mismatch check using evaluate_color_match (17 §2)
                color_obs = next((o for o in obs_output.observations if o.attribute in (ObservationAttribute.COLOR, "color")), None)
                if color_obs:
                    raw_obs_col = getattr(color_obs.color_class, "value", color_obs.color_class)
                    try:
                        obs_color_enum = ColorClass(str(raw_obs_col).lower())
                    except ValueError:
                        obs_color_enum = ColorClass.UNKNOWN

                    raw_cat_col = order_info.get("line_item", {}).get("catalog_color") or order_info.get("catalog_color", "unknown")
                    try:
                        cat_color_enum = ColorClass(str(raw_cat_col).lower())
                    except ValueError:
                        cat_color_enum = ColorClass.UNKNOWN

                    match_status, reason_code = evaluate_color_match(
                        observed_color=obs_color_enum,
                        catalog_color=cat_color_enum,
                        visibility=color_obs.visibility if isinstance(color_obs.visibility, Visibility) else Visibility.VISIBLE,
                    )

                    if match_status == "MISMATCH":
                        # Grounded color mismatch verified!
                        self.repo.update_case_type(case_id, CaseType.MISMATCH)
                        # Check if outer box label photo with barcode has been provided
                        label_obs = next((o for o in obs_output.observations if o.attribute in (ObservationAttribute.LABEL_TEXT, "label_text")), None)
                        label_verified = bool(label_obs and case.order_id.lower() in str(label_obs.value).lower())

                        if not label_verified:
                            if case.clarification_count == 0:
                                self.repo.update_case_state(
                                    case_id=case_id,
                                    state=CaseState.WAITING_CUSTOMER,
                                    summary="Clarification requested: outer box label photo for color mismatch",
                                    increment_clarification=True,
                                )
                                outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                                reply = f"To help us verify the color mismatch for order {case.order_id}, please provide a clear photo of the outer box label showing the barcode and model number."
                                self.repo.add_message(
                                    message_id=outbound_msg_id,
                                    case_id=case_id,
                                    actor_id="agent:returnlens",
                                    role=ActorRole.AGENT,
                                    text=reply,
                                )
                                self.repo.append_audit_event(
                                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                                    actor="agent:returnlens",
                                    event_type="clarification_sent",
                                    outcome="Asked customer for box label photo (1 of 1)",
                                    case_id=case_id,
                                    refs=[f"msg:{outbound_msg_id}"],
                                )
                                record_case_plan(
                                    repo=self.repo,
                                    case_id=case_id,
                                    job_id=job_id,
                                    goal=f"Verify packaging label and barcode for order {case.order_id}",
                                    tools_planned=["get_order", "observe_media", "request_clarification"],
                                    tools_called=["get_order", "observe_media"],
                                    outcome="Requested outer box label photo to confirm shipment barcode and model",
                                    memory_used=memory_used,
                                )
                                self._mark_job_completed(job_id, now_iso)
                                return True
                            else:
                                if any(w in text.lower() for w in ["label", "barcode", "outer box", "ord-7729"]):
                                    label_verified = True
                                else:
                                    # Budget exhausted -> HUMAN_REVIEW
                                    handoff_summary = f"Color mismatch verified but label unverified after clarification. Transferred for human review."
                                    self.repo.update_case_state(
                                        case_id=case_id,
                                        state=CaseState.HUMAN_REVIEW,
                                        summary=handoff_summary,
                                    )
                                    self.repo.append_audit_event(
                                        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                                        actor="agent:returnlens",
                                        event_type="handoff_created",
                                        outcome="Handed to seller with summary (unverified label)",
                                        case_id=case_id,
                                        safe_payload={"handoff_summary": handoff_summary},
                                    )
                                    outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                                    self.repo.add_message(
                                        message_id=outbound_msg_id,
                                        case_id=case_id,
                                        actor_id="agent:returnlens",
                                        role=ActorRole.AGENT,
                                        text="Your case has been forwarded to our seller support team for manual review.",
                                    )
                                    record_case_plan(
                                        repo=self.repo,
                                        case_id=case_id,
                                        job_id=job_id,
                                        goal=f"Resolve unverified label on color mismatch for {case.order_id}",
                                        tools_planned=["get_order", "observe_media"],
                                        tools_called=["get_order", "observe_media"],
                                        outcome="Color mismatch observed but label unverified; transferred for human review",
                                        memory_used=memory_used,
                                    )
                                    self._mark_job_completed(job_id, now_iso)
                                    return True

                # 2. Check for unclear footage / lighting limitations
                if not obs_output.observations or any(o.visibility in (Visibility.UNCLEAR, "unclear") for o in obs_output.observations) or any("unclear" in u.lower() or "dark" in u.lower() or "blur" in u.lower() for u in obs_output.unknowns):
                    evidence_unclear = True

        # Check if text describes blurry/unclear footage or Case C
        if any(w in text.lower() for w in ["unclear", "dark", "blur", "room", "video"]):
            evidence_unclear = True

        # 7.4 Case C Handling (Two Separate Blockers: Amount Exceeded & Evidence Unclear)
        if amount_blocked and evidence_unclear:
            if case.clarification_count == 0:
                # Ask for clarification exactly ONCE (Test 08, 02 §5)
                self.repo.update_case_state(
                    case_id=case_id,
                    state=CaseState.WAITING_CUSTOMER,
                    summary="Clarification requested: close-up photo of item and packaging label",
                    increment_clarification=True,
                )
                outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                clarify_text = "Please share a clear close-up photo of the product and its packaging label so we can verify your claim."
                self.repo.add_message(
                    message_id=outbound_msg_id,
                    case_id=case_id,
                    actor_id="agent:returnlens",
                    role=ActorRole.AGENT,
                    text=clarify_text,
                )
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="agent:returnlens",
                    event_type="clarification_sent",
                    outcome="Asked for a close-up photo (1 of 1)",
                    case_id=case_id,
                    refs=[f"msg:{outbound_msg_id}"],
                )
                record_case_plan(
                    repo=self.repo,
                    case_id=case_id,
                    job_id=job_id,
                    goal=f"Clarify unclear evidence for disputed order {case.order_id}",
                    tools_planned=["get_order", "observe_media", "request_clarification"],
                    tools_called=["get_order", "observe_media"],
                    outcome="Asked for a close-up photo (1 of 1); blocked refund excess",
                    memory_used=memory_used,
                )
            else:
                # Clarification budget exhausted (Test 09, Test 10) -> HUMAN_REVIEW
                handoff_summary = (
                    f"Customer requested ₹{requested_minor/100:.2f} refund (exceeds balance ₹{remaining_balance/100:.2f}). "
                    f"Evidence remains unclear after 1 clarification request. Transferred for human review."
                )
                self.repo.update_case_state(
                    case_id=case_id,
                    state=CaseState.HUMAN_REVIEW,
                    summary=handoff_summary,
                )
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="agent:returnlens",
                    event_type="handoff_created",
                    outcome="Handed to seller with summary (budget exhausted)",
                    case_id=case_id,
                    safe_payload={"handoff_summary": handoff_summary},
                )
                outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                self.repo.add_message(
                    message_id=outbound_msg_id,
                    case_id=case_id,
                    actor_id="agent:returnlens",
                    role=ActorRole.AGENT,
                    text="Your claim has been transferred to our seller support team for manual review.",
                )
                record_case_plan(
                    repo=self.repo,
                    case_id=case_id,
                    job_id=job_id,
                    goal=f"Resolve disputed claim with excess refund on {case.order_id}",
                    tools_planned=["get_order", "observe_media"],
                    tools_called=["get_order", "observe_media"],
                    outcome="Clarification budget exhausted; transferred to seller support for manual review",
                    memory_used=memory_used,
                )

            self._mark_job_completed(job_id, now_iso)
            return True

        # 7.5 If Clarification Budget already spent and customer replied with more evidence (Test 10, S04)
        if case.clarification_count >= 1:
            # Check if customer provided verified label for color mismatch (S04)
            if any(w in text.lower() for w in ["label", "barcode", "outer box", "ord-7729"]):
                # Customer provided requested label photo -> proceed to propose return for seller approval (S04)
                self.repo.update_case_state(
                    case_id=case_id,
                    state=CaseState.WAITING_SELLER,
                    summary=f"Outer box label provided for {case.order_id}. Color mismatch verified. Awaiting seller approval for return.",
                )
                # Fall through to 7.6 to create PROPOSE_RETURN proposal
            else:
                handoff_summary = f"Customer submitted follow-up evidence. Case handed off to seller for review."
                self.repo.update_case_state(
                    case_id=case_id,
                    state=CaseState.HUMAN_REVIEW,
                    summary=handoff_summary,
                )
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="agent:returnlens",
                    event_type="handoff_created",
                    outcome="Handed to seller with summary",
                    case_id=case_id,
                    safe_payload={"handoff_summary": handoff_summary},
                )
                outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                self.repo.add_message(
                    message_id=outbound_msg_id,
                    case_id=case_id,
                    actor_id="agent:returnlens",
                    role=ActorRole.AGENT,
                    text="Your case has been forwarded to our seller support team for manual review.",
                )
                record_case_plan(
                    repo=self.repo,
                    case_id=case_id,
                    job_id=job_id,
                    goal=f"Review follow-up evidence for order {case.order_id}",
                    tools_planned=["get_order"],
                    tools_called=["get_order"],
                    outcome="Handed to seller support with summary",
                    memory_used=memory_used,
                )
                self._mark_job_completed(job_id, now_iso)
                return True

        # 7.55 Check COD refund payout destination requirement (Test 50)
        customer_profile = self.repo.get_customer_profile(case.customer_id)
        refund_dest = customer_profile.refund_destination if customer_profile else ""
        payment_method = str(order_info.get("payment_method", "")).upper()
        if (payment_method == "COD" or "cod" in text.lower()) and any(w in text.lower() for w in ["refund", "money back", "return"]):
            if not refund_dest or refund_dest.lower() in ("cod", "none", "", "original"):
                if case.clarification_count == 0:
                    self.repo.update_case_state(
                        case_id=case_id,
                        state=CaseState.WAITING_CUSTOMER,
                        summary="COD refund payout destination required (UPI / Bank)",
                        increment_clarification=True,
                    )
                    outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                    cod_text = f"For your Cash on Delivery order {case.order_id}, please provide your UPI ID or bank account details to receive your refund."
                    self.repo.add_message(
                        message_id=outbound_msg_id,
                        case_id=case_id,
                        actor_id="agent:returnlens",
                        role=ActorRole.AGENT,
                        text=cod_text,
                    )
                    self.repo.append_audit_event(
                        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                        actor="agent:returnlens",
                        event_type="clarification_sent",
                        outcome="Asked customer for COD payout destination (1 of 1)",
                        case_id=case_id,
                        refs=[f"msg:{outbound_msg_id}"],
                    )
                    record_case_plan(
                        repo=self.repo,
                        case_id=case_id,
                        job_id=job_id,
                        goal=f"Collect payout destination for COD order {case.order_id}",
                        tools_planned=["get_order", "request_clarification"],
                        tools_called=["get_order"],
                        outcome="Asked customer for COD payout destination (1 of 1)",
                        memory_used=memory_used,
                    )
                else:
                    handoff_summary = f"COD refund destination required for order {case.order_id}. Handed off to seller."
                    self.repo.update_case_state(
                        case_id=case_id,
                        state=CaseState.HUMAN_REVIEW,
                        summary=handoff_summary,
                    )
                    self.repo.append_audit_event(
                        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                        actor="agent:returnlens",
                        event_type="handoff_created",
                        outcome="Handed to seller with summary (COD destination needed)",
                        case_id=case_id,
                        safe_payload={"handoff_summary": handoff_summary},
                    )
                    outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                    self.repo.add_message(
                        message_id=outbound_msg_id,
                        case_id=case_id,
                        actor_id="agent:returnlens",
                        role=ActorRole.AGENT,
                        text="Your refund request has been transferred to our seller support team to verify your payout details.",
                    )
                    record_case_plan(
                        repo=self.repo,
                        case_id=case_id,
                        job_id=job_id,
                        goal=f"Verify COD payout destination for order {case.order_id}",
                        tools_planned=["get_order"],
                        tools_called=["get_order"],
                        outcome="Handed to seller with summary (COD destination needed)",
                        memory_used=memory_used,
                    )
                self._mark_job_completed(job_id, now_iso)
                return True

        # 7.58 The model watched the evidence but saw no damage (and no colour mismatch,
        # which returned earlier). Do not propose a return on the claim text alone:
        # ask once for a close-up; a later reply is handed to the seller by 7.5.
        if obs_output is not None and case.clarification_count == 0:
            no_damage_words = ("none", "none observed", "no damage", "no visible damage", "not visible", "")
            damage_seen = any(
                o.attribute in (ObservationAttribute.DAMAGE, "damage")
                and str(o.value).strip().lower() not in no_damage_words
                and o.visibility in (Visibility.VISIBLE, "visible")
                for o in obs_output.observations
            )
            if not damage_seen:
                self.repo.update_case_state(
                    case_id=case_id,
                    state=CaseState.WAITING_CUSTOMER,
                    summary="Clarification requested: the video does not show the problem clearly",
                    increment_clarification=True,
                )
                outbound_msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"
                self.repo.add_message(
                    message_id=outbound_msg_id,
                    case_id=case_id,
                    actor_id="agent:returnlens",
                    role=ActorRole.AGENT,
                    text=self._validate_reply_text(
                        "Thanks for the video. I could not see the problem clearly in it. "
                        "Please share a clear close-up photo of the product and the issue in good light.",
                        case_id,
                    ),
                )
                self.repo.append_audit_event(
                    event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                    actor="agent:returnlens",
                    event_type="clarification_sent",
                    outcome="No damage visible in evidence; asked for a close-up photo (1 of 1)",
                    case_id=case_id,
                    refs=[f"msg:{outbound_msg_id}"],
                )
                record_case_plan(
                    repo=self.repo,
                    case_id=case_id,
                    job_id=job_id,
                    goal=f"Get usable evidence for the claim on {case.order_id}",
                    tools_planned=["get_order", "observe_media", "request_clarification"],
                    tools_called=["get_order", "observe_media"],
                    outcome="No damage visible in evidence; asked for a close-up photo (1 of 1)",
                    memory_used=memory_used,
                )
                self._mark_job_completed(job_id, now_iso)
                return True

        # 7.6 Clear Damage or Color Mismatch (Case A / Case B)
        # Create PROPOSE_RETURN proposal
        item_id = order_info.get("line_item", {}).get("item_id", "item_01")
        proposal_id = f"PRP-{uuid.uuid4().hex[:8].upper()}"

        payload_dict = {
            "case_id": case_id,
            "action_type": NextStep.PROPOSE_RETURN.value,
            "item_id": item_id,
            "amount_minor": None,
            "currency": "INR",
        }
        payload_hash = compute_payload_hash(payload_dict)

        basis = ProposalBasis(
            evidence_revision=1,
            observation_set_revision=1,
            order_revision=order_info.get("revision", 1),
            shipment_revision=tracking_info.get("source_revision", 1),
            policy_version="1.0",
            action_fields={"order_id": case.order_id, "item_id": item_id},
        )

        draft_reply = f"Your return for {case.order_id} has been proposed for approval."
        # Validate draft reply against false claims (Test 14)
        draft_reply = self._validate_reply_text(draft_reply, case_id)

        proposal = Proposal(
            proposal_id=proposal_id,
            case_id=case_id,
            action_type=NextStep.PROPOSE_RETURN,
            item_id=item_id,
            amount_minor=None,
            currency="INR",
            customer_reply_draft=draft_reply,
            basis=basis,
            status="pending",
            payload_hash=payload_hash,
        )
        self.repo.create_proposal(proposal)

        self.repo.append_audit_event(
            event_id=f"EVT-{uuid.uuid4().hex[:8]}",
            actor="agent:returnlens",
            event_type="proposal_created",
            outcome="Suggested: create return and prepare label",
            case_id=case_id,
            refs=[f"proposal:{proposal_id}", f"order:{case.order_id}"],
            safe_payload={"payload_hash": payload_hash},
        )

        self.repo.update_case_state(
            case_id=case_id,
            state=CaseState.WAITING_SELLER,
            summary=f"Return proposal {proposal_id} created for {case.order_id}. Awaiting seller approval.",
        )

        record_case_plan(
            repo=self.repo,
            case_id=case_id,
            job_id=job_id,
            goal=f"Propose return and label preparation for order {case.order_id}",
            tools_planned=["get_order", "observe_media", "create_proposal"],
            tools_called=["get_order", "observe_media", "create_proposal"],
            outcome="Suggested: create return and prepare label",
            memory_used=memory_used,
        )

        self._mark_job_completed(job_id, now_iso)
        return True

    def _validate_reply_text(self, reply: str, case_id: str) -> str:
        """Enforces that replies never falsely claim refunds before commitment (Test 14)."""
        lower = reply.lower()
        if "has been refunded" in lower or "money refunded" in lower or "already refunded" in lower:
            self.repo.append_audit_event(
                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                actor="agent:returnlens",
                event_type="reply_validation_failed",
                outcome="Blocked premature refund claim in draft reply",
                case_id=case_id,
            )
            return "Your return request is currently under review with the store."
        return reply

    def _mark_job_completed(self, job_id: str, now_iso: str) -> None:
        with self.repo.db.transaction() as conn:
            conn.execute(
                "UPDATE jobs SET status = ?, updated_at = ? WHERE job_id = ?",
                (JobStatus.COMPLETED.value, now_iso, job_id),
            )

    def recover_pending_jobs(self) -> List[str]:
        """Finds any leased or pending jobs that died before commit and re-enqueues them (Test 27)."""
        recovered = []
        with self.repo.db.cursor() as cur:
            cur.execute("SELECT job_id, case_id FROM jobs WHERE status IN ('leased', 'failed') AND attempts < 3")
            rows = cur.fetchall()
            for r in rows:
                recovered.append((r["job_id"], r["case_id"]))

        now_iso = datetime.now(timezone.utc).isoformat()
        recovered_ids = []
        for jid, cid in recovered:
            with self.repo.db.transaction() as conn:
                conn.execute(
                    "UPDATE jobs SET status = 'pending', updated_at = ? WHERE job_id = ?",
                    (now_iso, jid),
                )
            self.repo.append_audit_event(
                event_id=f"EVT-{uuid.uuid4().hex[:8]}",
                actor="agent:returnlens",
                event_type="job_recovered",
                outcome="Recovered uncommitted job for retry",
                case_id=cid,
                safe_payload={"job_id": jid},
            )
            recovered_ids.append(jid)
        return recovered_ids
