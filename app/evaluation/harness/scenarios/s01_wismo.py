"""S01 — WISMO (CaseType: WISMO).

Per 18 §2:
- Setup: CUS-01, ORD-2030 In transit, ETA DEMO_TODAY+2.
- Steps: Customer sends "Where is my order?"
- DB: case RESOLVED; no return/refund/action written.
- Process: calls get_order + get_tracking; does not call observer; <=1 model call (0 if fast path).
- Message: contains status "In transit" and ETA matching date.
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


class Scenario01Wismo(BaseScenario):
    scenario_id = "S01"
    case_type = CaseType.WISMO
    title = "S01 — WISMO"
    requires_model = False

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()
        assert env.client is not None

        # 1. Customer sends WISMO inquiry
        res = await env.client.post(
            "/api/cases",
            json={
                "order_id": "ORD-2030",
                "initial_message": "Where is my order?",
            },
            headers={"X-Customer-Id": "CUS-01"},
        )
        if res.status_code != 202:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Case creation failed with HTTP {res.status_code}: {res.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        case_id = res.json()["case_id"]

        # 2. Layer 1: DB assertion
        db_res = verify_db_layer(
            env=env,
            case_id=case_id,
            expected_case_state=CaseState.RESOLVED,
            expected_refund_count=0,
            expected_return_count=0,
        )

        # 3. Layer 2: Process assertion
        process_res = verify_process_layer(
            env=env,
            case_id=case_id,
            max_clarifications=0,
            require_tool_audit=True,
            expected_event_types=["customer_reply_delivered"],
        )

        # 4. Layer 3: Message assertion
        # Order ORD-2030 in seed has ETA = DEMO_TODAY + 2 days = 2026-11-13
        msg_res = verify_message_layer(
            env=env,
            case_id=case_id,
            required_substrings=["in transit", "2026-11-13"],
            forbidden_substrings=["fraud", "scam", "refund"],
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
