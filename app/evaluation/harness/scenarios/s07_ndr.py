"""S07 — NDR COD Order (CaseType: NDR).

Per 18 §2:
- Setup: CUS-05 (Hinglish), ORD-3110 COD, shipment NDR attempt 1.
- Steps: operator triggers NDR -> duplicate NDR sent with same event_id ->
  agent automatically messages customer (L1) -> customer replies with updated address ->
  (harness-seller) approve PROPOSE_NDR_REATTEMPT.
- DB: shipment address changed Flat 12B -> 14B, pincode remains 411038,
  status reattempt requested; case RESOLVED.
- Process: job trigger = courier_event; P_NDR PASS; duplicate event only creates 1 message.
- Message: first message in customer language; reattempt confirmed.
"""

from __future__ import annotations

import time
from app.backend.contracts import CaseState, CaseType
from app.evaluation.harness.assertions import (
    verify_db_layer,
    verify_process_layer,
    verify_message_layer,
)
from app.evaluation.harness.environment import TrialEnvironment
from app.evaluation.harness.models import TrialResult
from app.evaluation.harness.scenarios.base import BaseScenario


class Scenario07Ndr(BaseScenario):
    scenario_id = "S07"
    case_type = CaseType.NDR
    title = "S07 — NDR Reattempt"
    requires_model = False

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()
        assert env.client is not None
        assert env.repo is not None

        # 1. Operator fires NDR courier event (18 §2)
        res_ndr = await env.client.post(
            "/api/operator/courier-events",
            json={
                "shipment_id": "SHP-3110",
                "type": "NDR",
                "attempt_no": 1,
                "reason": "customer_not_available",
            },
        )
        if res_ndr.status_code != 200:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"NDR courier event failed: {res_ndr.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        case_id = res_ndr.json()["case_id"]

        # 2. Replay duplicate NDR event with same parameters (must be deduped)
        res_dup = await env.client.post(
            "/api/operator/courier-events",
            json={
                "shipment_id": "SHP-3110",
                "type": "NDR",
                "attempt_no": 1,
                "reason": "customer_not_available",
            },
        )

        # 3. Customer replies with address correction
        res_reply = await env.client.post(
            f"/api/cases/{case_id}/messages",
            json={
                "text": "Flat 12B nahi, 14B hai. Kal shaam 6 baje chalega.",
            },
            headers={"X-Customer-Id": "CUS-05"},
        )
        if res_reply.status_code != 202:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Customer address reply failed: {res_reply.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 4. Harness acting as seller: approve PROPOSE_NDR_REATTEMPT proposal
        proposals = env.repo.list_case_proposals(case_id)
        ndr_prop = next(
            (p for p in proposals if "reattempt" in p.action_type.value.lower()),
            None,
        )
        if not ndr_prop:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason="PROPOSE_NDR_REATTEMPT proposal not generated",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        res_app = await env.client.post(
            f"/api/proposals/{ndr_prop.proposal_id}/decisions",
            json={"decision": "approve", "payload_hash": ndr_prop.payload_hash},
            headers={"Idempotency-Key": f"DEC-NDR-{case_id}"},
        )
        if res_app.status_code != 200:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"NDR proposal decision failed: {res_app.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 5. Layer 1: DB assertion
        db_res = verify_db_layer(
            env=env,
            case_id=case_id,
            expected_case_state=CaseState.RESOLVED,
            expected_shipment_status="REATTEMPT_REQUESTED",
            expected_shipment_address_substring="Flat 14B",
        )

        # 6. Layer 2: Process assertion
        process_res = verify_process_layer(
            env=env,
            case_id=case_id,
            max_clarifications=1,
            require_tool_audit=True,
            expected_event_types=["courier_event_received", "ndr_action_taken"],
        )

        # 7. Layer 3: Message assertion
        msg_res = verify_message_layer(
            env=env,
            case_id=case_id,
            required_substrings=["deliver", "address"],
            forbidden_substrings=["fraud", "scam"],
        )

        passed = db_res.passed and process_res.passed and msg_res.passed
        duration_ms = (time.perf_counter() - start_time) * 1000

        reasons = []
        if not db_res.passed:
            reasons.append(f"DB: {db_res.reason}")
        if not process_res.passed:
            reasons.append(f"Process: {process_res.reason}")
        if not msg_res.passed:
            reasons.append(f"Message: {msg_res.reason}")

        return TrialResult(
            scenario_id=self.scenario_id,
            trial_no=trial_no,
            passed=passed,
            status="PASS" if passed else "FAIL",
            reason="All 3 layers verified" if passed else " | ".join(reasons),
            db_layer=db_res,
            process_layer=process_res,
            message_layer=msg_res,
            duration_ms=duration_ms,
        )
