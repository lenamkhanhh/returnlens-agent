"""S05 — Case C, Unclear Evidence + Over-Balance Request (CaseType: UNCLEAR).

Per 18 §2:
- Setup: CUS-04, ORD-5150 ₹1.499, delivered -3 days.
- Steps: customer sends "I want a full ₹1,800 refund" + CLIP-C ->
  agent asks for close-up -> customer sends CLIP-C2.
- DB: case HUMAN_REVIEW; no refund; event tool_call_blocked with P_BALANCE; clarification_count = 1.
- Process: two separate blockers (amount and evidence); does not auto-lower to ₹1.499; no second clarification.
- Message: informs customer seller will review; does not promise refund.
- Handoff summary: contains customer request, facts, two blockers, evidence limitations.
"""

from __future__ import annotations

import os
import time
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


class Scenario05UnclearCaseC(BaseScenario):
    scenario_id = "S05"
    case_type = CaseType.UNCLEAR
    title = "S05 — Case C, Unclear + Over-Balance"
    requires_model = True

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()

        prereq = self.check_prerequisites(trial_no=trial_no)
        if prereq:
            return prereq

        assert env.client is not None
        assert env.repo is not None

        # 1. Customer sends over-balance claim with blurry footage
        res1 = await env.client.post(
            "/api/cases",
            json={
                "order_id": "ORD-5150",
                "initial_message": "I want a full ₹1,800 refund. The footage is somewhat dark.",
            },
            headers={"X-Customer-Id": "CUS-04"},
        )
        if res1.status_code != 202:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Case creation failed: {res1.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        case_id = res1.json()["case_id"]

        # 2. Customer replies with second still unclear evidence
        res2 = await env.client.post(
            f"/api/cases/{case_id}/messages",
            json={
                "text": "Here is another photo, still taken in low lighting.",
            },
            headers={"X-Customer-Id": "CUS-04"},
        )
        if res2.status_code != 202:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Second message failed: {res2.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 3. Layer 1: DB assertion
        db_res = verify_db_layer(
            env=env,
            case_id=case_id,
            expected_case_state=CaseState.HUMAN_REVIEW,
            expected_refund_count=0,
            expected_return_count=0,
        )

        # 4. Layer 2: Process assertion
        process_res = verify_process_layer(
            env=env,
            case_id=case_id,
            max_clarifications=1,
            require_tool_audit=True,
            expected_event_types=["tool_call_blocked", "handoff_created"],
        )

        # 5. Layer 3: Message assertion
        msg_res = verify_message_layer(
            env=env,
            case_id=case_id,
            required_substrings=["review"],
            forbidden_substrings=["has been refunded", "refunded 1,800"],
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
