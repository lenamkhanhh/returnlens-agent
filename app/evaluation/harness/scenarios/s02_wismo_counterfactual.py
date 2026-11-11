"""S02 — WISMO Counterfactual (CaseType: WISMO).

Per 18 §2:
- Setup: like S01 (CUS-01, ORD-2030).
- Steps: Ask -> operator changes tracking to Out for delivery -> ask again.
- DB: shipment revision increases by 1; status is OUT_FOR_DELIVERY.
- Process: second inquiry calls get_tracking again (fresh read, not cached).
- Message: reply 2 contains "Out for delivery", differs from reply 1.
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
from app.evaluation.harness.models import LayerResult, TrialResult
from app.evaluation.harness.scenarios.base import BaseScenario


class Scenario02WismoCounterfactual(BaseScenario):
    scenario_id = "S02"
    case_type = CaseType.WISMO
    title = "S02 — WISMO counterfactual"
    requires_model = False

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()
        assert env.client is not None
        assert env.repo is not None

        # 1. Customer asks first question
        res1 = await env.client.post(
            "/api/cases",
            json={
                "order_id": "ORD-2030",
                "initial_message": "Where is my order?",
            },
            headers={"X-Customer-Id": "CUS-01"},
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

        case1_id = res1.json()["case_id"]
        messages1 = env.repo.get_case_messages(case1_id)
        reply1_text = next((m.text for m in messages1 if m.role.value == "agent"), "")

        # 2. Operator updates tracking to Out for delivery, incrementing revision (18 §2)
        with env.repo.db.transaction() as conn:
            conn.execute(
                """
                UPDATE shipments
                SET status = 'OUT_FOR_DELIVERY', source_revision = source_revision + 1
                WHERE shipment_id = 'SHP-2030'
                """
            )

        # 3. Customer asks again (second question)
        res2 = await env.client.post(
            "/api/cases",
            json={
                "order_id": "ORD-2030",
                "initial_message": "Any update on where my order is right now?",
            },
            headers={"X-Customer-Id": "CUS-01"},
        )
        if res2.status_code != 202:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Second case creation failed: {res2.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        case2_id = res2.json()["case_id"]

        # 4. Layer 1: DB assertion
        db_res = verify_db_layer(
            env=env,
            case_id=case2_id,
            expected_case_state=CaseState.RESOLVED,
            expected_shipment_status="OUT_FOR_DELIVERY",
            expected_shipment_revision_min=2,
            expected_refund_count=0,
            expected_return_count=0,
        )

        # 5. Layer 2: Process assertion
        process_res = verify_process_layer(
            env=env,
            case_id=case2_id,
            max_clarifications=0,
            require_tool_audit=True,
            expected_event_types=["customer_reply_delivered"],
        )

        # 6. Layer 3: Message assertion
        messages2 = env.repo.get_case_messages(case2_id)
        reply2_text = next((m.text for m in messages2 if m.role.value == "agent"), "")

        msg_failures = []
        if "out for delivery" not in reply2_text.lower():
            msg_failures.append("Second reply does not contain 'Out for delivery'")
        if reply2_text.strip() == reply1_text.strip():
            msg_failures.append("Second reply is identical to first reply (stale data used)")

        msg_passed = len(msg_failures) == 0
        msg_res = LayerResult(
            layer="message",
            passed=msg_passed,
            reason="Message layer verified" if msg_passed else "; ".join(msg_failures),
            details={"reply1": reply1_text, "reply2": reply2_text},
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
