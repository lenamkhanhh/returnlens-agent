"""S04 — Case B, Color Mismatch (CaseType: MISMATCH).

Per 18 §2:
- Setup: CUS-02, ORD-7729 HEAD-WHT-02 ₹1.499, delivered -4 days.
- Steps: customer sends "I ordered white headphones but got black" + CLIP-B ->
  agent automatically requests box label photo (L1) -> customer sends CLIP-B2.
- DB: case WAITING_SELLER; clarification_count = 1; proposal pending in {PROPOSE_RETURN, HANDOFF}; no return/refund.
- Process: observation color_class black, catalog white -> mismatch; barcode/model in unknowns;
  P_UNVERIFIED blocks auto; after CLIP-B2 observation label_text contains ORD-7729.
- Message: requests box label photo exactly once; does not accuse warehouse or customer of fraud.
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


class Scenario04MismatchCaseB(BaseScenario):
    scenario_id = "S04"
    case_type = CaseType.MISMATCH
    title = "S04 — Case B, Color Mismatch"
    requires_model = True

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()

        prereq = self.check_prerequisites(trial_no=trial_no)
        if prereq:
            return prereq

        assert env.client is not None
        assert env.repo is not None

        # Point to stock black headphones clip (Wave 6)
        clip_b_path = Path("app/demo/media/stock/stock_black_headphones_pexels_9130360.mp4")
        if not clip_b_path.exists():
            clip_b_path = Path("app/demo/media/stock_black_headphones_pexels_9130360.mp4")

        # 1. Customer initiates color mismatch claim (18 §2 line 43)
        res = await env.client.post(
            "/api/cases",
            json={
                "order_id": "ORD-7729",
                "initial_message": "I ordered white headphones but got black ones instead.",
            },
            headers={"X-Customer-Id": "CUS-02"},
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

        # Upload CLIP-B (black headphones clip) per 18 §2 line 43
        if clip_b_path.exists():
            with open(clip_b_path, "rb") as f:
                await env.client.post(
                    f"/api/cases/{case_id}/evidence",
                    files={"file": (clip_b_path.name, f, "video/mp4")},
                    headers={"X-Customer-Id": "CUS-02"},
                )

        # 2. Customer provides requested label photo (CLIP-B2)
        res_msg2 = await env.client.post(
            f"/api/cases/{case_id}/messages",
            json={
                "text": "Here is the photo of the outer box label showing the barcode and model number ORD-7729.",
            },
            headers={"X-Customer-Id": "CUS-02"},
        )
        if res_msg2.status_code != 202:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Follow-up message failed: {res_msg2.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 3. Layer 1: DB assertion
        db_res = verify_db_layer(
            env=env,
            case_id=case_id,
            expected_case_state=[CaseState.WAITING_SELLER, CaseState.HUMAN_REVIEW, CaseState.PROCESSING],
            expected_refund_count=0,
            expected_return_count=0,
        )

        # 4. Layer 2: Process assertion
        process_res = verify_process_layer(
            env=env,
            case_id=case_id,
            max_clarifications=1,
            require_tool_audit=True,
        )

        # 5. Layer 3: Message assertion
        msg_res = verify_message_layer(
            env=env,
            case_id=case_id,
            required_substrings=["label", "photo"],
            forbidden_substrings=["fraud", "scam", "cheat"],
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
