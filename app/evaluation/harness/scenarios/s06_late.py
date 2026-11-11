"""S06 — Late Return Window Check (CaseType: LATE).

Per 18 §2:
- Setup: CUS-01, ORD-0915 delivered -14 days.
- Steps: customer sends "Can I return these?" (no media).
- DB: case WAITING_SELLER or HUMAN_REVIEW; no return created.
- Process: P_WINDOW FAIL; does not send automatic rejection message.
- Message: informs customer seller will review per policy; no automatic refusal text.
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


class Scenario06Late(BaseScenario):
    scenario_id = "S06"
    case_type = CaseType.LATE
    title = "S06 — Late Return Window"
    requires_model = False

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()
        assert env.client is not None
        assert env.repo is not None

        # 1. Customer sends return inquiry for order delivered 14 days ago
        res = await env.client.post(
            "/api/cases",
            json={
                "order_id": "ORD-0915",
                "initial_message": "Can I return these?",
            },
            headers={"X-Customer-Id": "CUS-01"},
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

        # 2. Layer 1: DB assertion
        db_res = verify_db_layer(
            env=env,
            case_id=case_id,
            expected_case_state=[CaseState.WAITING_SELLER, CaseState.HUMAN_REVIEW],
            expected_return_count=0,
            expected_refund_count=0,
        )

        # 3. Layer 2: Process assertion
        process_res = verify_process_layer(
            env=env,
            case_id=case_id,
            max_clarifications=0,
            require_tool_audit=True,
            expected_event_types=["policy_checked"],
        )

        # 4. Layer 3: Message assertion
        msg_res = verify_message_layer(
            env=env,
            case_id=case_id,
            required_substrings=["review"],
            forbidden_substrings=["rejected", "denied", "cannot return", "refused"],
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
