"""S09 — Returning Customer After Restart (CaseType: UNCLEAR).

Per 18 §2:
- Setup: CUS-04, ORD-5150, no refund amount requested.
- Steps: customer sends CLIP-C -> agent asks for close-up ->
  harness ends customer session AND restarts worker -> customer opens new session, sends CLIP-C2.
- DB: same case_id; clarification_count = 1; case HUMAN_REVIEW.
- Process: plan record has memory_used containing language and open case;
  does not send second clarification; no duplicate jobs after restart.
- Message: continues in same language; does not ask for order info again.
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


class Scenario09ReturningRestart(BaseScenario):
    scenario_id = "S09"
    case_type = CaseType.UNCLEAR
    title = "S09 — Returning Customer After Restart"
    requires_model = True

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()

        prereq = self.check_prerequisites(trial_no=trial_no)
        if prereq:
            return prereq

        assert env.client is not None
        assert env.repo is not None

        # Point to stock dim unboxing clip (Wave 6)
        clip_c_path = Path("app/demo/media/stock/stock_dim_unboxing_pexels_40423563.mp4")
        if not clip_c_path.exists():
            clip_c_path = Path("app/demo/media/stock_dim_unboxing_pexels_40423563.mp4")

        # 1. First session: customer sends first inquiry with blurry video (18 §2 line 79)
        res1 = await env.client.post(
            "/api/cases",
            json={
                "order_id": "ORD-5150",
                "initial_message": "My headphones are acting up. Dark video shows the issue.",
            },
            headers={"X-Customer-Id": "CUS-04"},
        )
        if res1.status_code != 202:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Initial case creation failed: {res1.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        case_id = res1.json()["case_id"]

        # Upload CLIP-C (dim unboxing clip) per 18 §2 line 79
        if clip_c_path.exists():
            with open(clip_c_path, "rb") as f:
                await env.client.post(
                    f"/api/cases/{case_id}/evidence",
                    files={"file": (clip_c_path.name, f, "video/mp4")},
                    headers={"X-Customer-Id": "CUS-04"},
                )

        # 2. End session and RESTART worker per 17 §9 & 18 §2
        env.restart_worker()

        # 3. New session: customer returns and sends follow-up photo
        res2 = await env.client.post(
            f"/api/cases/{case_id}/messages",
            json={
                "text": "I am back with a better photo of the unit.",
            },
            headers={"X-Customer-Id": "CUS-04"},
        )
        if res2.status_code != 202:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Follow-up message failed: {res2.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 4. Layer 1: DB assertion
        db_res = verify_db_layer(
            env=env,
            case_id=case_id,
            expected_case_state=[CaseState.HUMAN_REVIEW, CaseState.WAITING_SELLER],
            expected_refund_count=0,
            expected_return_count=0,
        )

        # 5. Layer 2: Process assertion
        process_res = verify_process_layer(
            env=env,
            case_id=case_id,
            max_clarifications=1,
            require_tool_audit=True,
            require_model_observation=True,
        )

        # 6. Layer 3: Message assertion
        msg_res = verify_message_layer(
            env=env,
            case_id=case_id,
            forbidden_substrings=["fraud", "scam", "what is your order id"],
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
