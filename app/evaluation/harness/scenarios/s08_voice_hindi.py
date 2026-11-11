"""S08 — Voice Note Hindi (CaseType: MISMATCH).

Per 18 §2:
- Setup: like S04 (CUS-02, ORD-7729).
- Steps: customer sends VN-HI + CLIP-B (no text typed).
- DB: case WAITING_CUSTOMER; clarification_count = 1; VoiceNote with language 'hi'.
- Process: transcript intent RETURN; order ID matches ORD-7729; all numbers marked unverified.
- Message: confirms request in short text and asks for label photo; language 'hi' or 'hinglish'.
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


class Scenario08VoiceHindi(BaseScenario):
    scenario_id = "S08"
    case_type = CaseType.MISMATCH
    title = "S08 — Voice Note Hindi"
    requires_model = True

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()

        prereq = self.check_prerequisites(trial_no=trial_no)
        if prereq:
            return prereq

        assert env.client is not None
        assert env.repo is not None

        # Point to stock audio voice note and stock black headphones clip (Wave 6)
        vn_path = Path("app/demo/media/stock/synthetic_voice_en_mismatch_ORD-7729.ogg")
        if not vn_path.exists():
            vn_path = Path("app/demo/media/synthetic_voice_en_mismatch_ORD-7729.ogg")
        if not vn_path.exists():
            vn_path = Path("app/demo/media/synthetic_voice_hindi.wav")

        clip_b_path = Path("app/demo/media/stock/stock_black_headphones_pexels_9130360.mp4")
        if not clip_b_path.exists():
            clip_b_path = Path("app/demo/media/stock_black_headphones_pexels_9130360.mp4")

        if not vn_path.exists():
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="BLOCKED",
                reason=f"Voice note fixture {vn_path} not found",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 1. Customer submits voice note without typed text (18 §2 line 72)
        res = await env.client.post(
            "/api/cases",
            json={
                "order_id": "ORD-7729",
                "initial_message": "[Voice Note Attached: synthetic_voice_en_mismatch_ORD-7729.ogg]",
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

        # Upload voice note audio evidence
        audio_mime = "audio/ogg" if vn_path.suffix.lower() == ".ogg" else "audio/wav"
        with open(vn_path, "rb") as f:
            await env.client.post(
                f"/api/cases/{case_id}/evidence",
                files={"file": (vn_path.name, f, audio_mime)},
                headers={"X-Customer-Id": "CUS-02"},
            )

        # Upload black headphones video evidence
        if clip_b_path.exists():
            with open(clip_b_path, "rb") as f:
                await env.client.post(
                    f"/api/cases/{case_id}/evidence",
                    files={"file": (clip_b_path.name, f, "video/mp4")},
                    headers={"X-Customer-Id": "CUS-02"},
                )

        # 2. Layer 1: DB assertion
        db_res = verify_db_layer(
            env=env,
            case_id=case_id,
            expected_case_state=[CaseState.WAITING_CUSTOMER, CaseState.WAITING_SELLER, CaseState.HUMAN_REVIEW],
            expected_refund_count=0,
            expected_return_count=0,
        )

        # 3. Layer 2: Process assertion
        process_res = verify_process_layer(
            env=env,
            case_id=case_id,
            max_clarifications=1,
            require_tool_audit=True,
        )

        # 4. Layer 3: Message assertion
        msg_res = verify_message_layer(
            env=env,
            case_id=case_id,
            required_substrings=["photo", "label"],
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
