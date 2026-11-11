"""S03 — Case A, Damage (CaseType: DAMAGE).

Per 18 §2:
- Setup: CUS-03, ORD-1042 HEAD-WHT-01 ₹1.299, delivered -4 days.
- Steps: customer sends "The headband cracked" + CLIP-A -> (harness-seller) approve PROPOSE_RETURN ->
  operator RETURN_RECEIVED -> (harness-seller) approve PROPOSE_REFUND ₹1.299.
- DB: 1 return status received; 1 refund 129900 paise processed; order refunded_minor = 129900; case RESOLVED.
- Process: observation damage visible with t in 00:00-00:20; P_WINDOW PASS; refund only after RETURN_RECEIVED;
  replay decision with same Idempotency-Key does not create second refund.
- Message: confirmation has return label ID; refund confirmation ₹1,299 only after processed.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from app.backend.contracts import CaseState, CaseType
from app.evaluation.harness.assertions import (
    verify_db_layer,
    verify_process_layer,
    verify_message_layer,
)
from app.evaluation.harness.environment import TrialEnvironment
from app.evaluation.harness.models import TrialResult
from app.evaluation.harness.scenarios.base import BaseScenario


class Scenario03DamageCaseA(BaseScenario):
    scenario_id = "S03"
    case_type = CaseType.DAMAGE
    title = "S03 — Case A, Damage"
    requires_model = True

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()

        # Check model prerequisite
        prereq = self.check_prerequisites(trial_no=trial_no)
        if prereq:
            return prereq

        assert env.client is not None
        assert env.repo is not None

        clip_a_path = Path("app/demo/media/synthetic_damaged_item.webm")
        if not clip_a_path.exists():
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="BLOCKED",
                reason=f"Media file {clip_a_path} not found",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # Cause 1 (media-limited per WAVE5_DIAGNOSE.md):
        # synthetic_damaged_item.webm is a solid-color synthetic clip.
        # A vision model cannot see a cracked headband in it; real filmed clip is required.
        if "synthetic" in clip_a_path.name.lower():
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="BLOCKED",
                reason="needs real filmed clip (synthetic media cannot show cracked headband)",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 1. Customer initiates damage claim with CLIP-A (18 §2 line 36)
        res = await env.client.post(
            "/api/cases",
            json={
                "order_id": "ORD-1042",
                "initial_message": "The headband cracked during normal use.",
            },
            headers={"X-Customer-Id": "CUS-03"},
        )
        if res.status_code != 202:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Case creation failed: {res.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        case_id = res.json()["case_id"]

        # Upload CLIP-A evidence per 18 §2 line 36
        with open(clip_a_path, "rb") as f:
            res_evi = await env.client.post(
                f"/api/cases/{case_id}/evidence",
                files={"file": (clip_a_path.name, f, "video/webm")},
                headers={"X-Customer-Id": "CUS-03"},
            )
        if res_evi.status_code != 201:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Evidence upload failed: {res_evi.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 2. Harness acting as seller: approve return proposal
        proposals = env.repo.list_case_proposals(case_id)
        return_prop = next(
            (p for p in proposals if str(p.action_type.value).lower() == "propose_return"),
            None,
        )
        if not return_prop:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason="Return proposal not created by agent",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        res_app = await env.client.post(
            f"/api/proposals/{return_prop.proposal_id}/decisions",
            json={"decision": "approve", "payload_hash": return_prop.payload_hash},
            headers={"Idempotency-Key": f"DEC-RET-{case_id}"},
        )
        if res_app.status_code != 200:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Seller approval for return failed: {res_app.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 3. Operator fires RETURN_RECEIVED courier event (18 §2)
        res_courier = await env.client.post(
            "/api/operator/courier-events",
            json={
                "shipment_id": "SHP-1042",
                "type": "RETURN_RECEIVED",
            },
        )
        if res_courier.status_code != 200:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Operator RETURN_RECEIVED event failed: {res_courier.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 4. Harness acting as seller: approve refund proposal
        proposals_v2 = env.repo.list_case_proposals(case_id)
        refund_prop = next(
            (p for p in proposals_v2 if str(p.action_type.value).lower() == "propose_refund"),
            None,
        )
        if not refund_prop:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason="Refund proposal not generated after RETURN_RECEIVED",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        refund_idem_key = f"DEC-REF-{case_id}"
        res_ref = await env.client.post(
            f"/api/proposals/{refund_prop.proposal_id}/decisions",
            json={"decision": "approve", "payload_hash": refund_prop.payload_hash},
            headers={"Idempotency-Key": refund_idem_key},
        )
        if res_ref.status_code != 200:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Refund decision approval failed: {res_ref.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 5. Replay decision with same Idempotency-Key (must not duplicate refund)
        res_replay = await env.client.post(
            f"/api/proposals/{refund_prop.proposal_id}/decisions",
            json={"decision": "approve", "payload_hash": refund_prop.payload_hash},
            headers={"Idempotency-Key": refund_idem_key},
        )

        # 6. Layer 1: DB assertion
        db_res = verify_db_layer(
            env=env,
            case_id=case_id,
            expected_case_state=CaseState.RESOLVED,
            expected_return_count=1,
            expected_return_status="received",
            expected_refund_count=1,
            expected_refund_status="processed",
            expected_refund_minor=129900,
        )

        # 7. Layer 2: Process assertion
        process_res = verify_process_layer(
            env=env,
            case_id=case_id,
            max_clarifications=1,
            check_no_premature_write=True,
            expected_event_types=["action_executed"],
            require_model_observation=True,
        )

        # 8. Layer 3: Message assertion
        msg_res = verify_message_layer(
            env=env,
            case_id=case_id,
            required_substrings=["1,299"],
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
