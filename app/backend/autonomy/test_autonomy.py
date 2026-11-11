"""Unit and Integration Tests for Autonomy Module (Card B12).

Tests:
- Test 40: Seller enables L2/L3 when ReliabilityResult is locked -> HTTP 422 reliability_locked.
- Test 41: L3 enabled, but refund attempted before RETURN_RECEIVED -> DEFER_TO_SELLER (prohibited action).
- Test 42: L3 enabled, but case has unverified observations (Case B) -> DEFER_TO_SELLER (observation_unverified).
- Test 43: Cumulative split: refund causes customer daily total to exceed limit (₹2,298 > ₹2,000) -> DEFER_TO_SELLER (cumulative_limit).
- Test 44: Kill switch engaged -> DEFER_TO_SELLER (kill_switch).
- Financial caps: exceeding store cap (₹3,000) or order balance returns BLOCK.
- 7-step checklist for UI 'Why?' button (23 W4).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from fastapi import HTTPException

from app.backend.contracts import (
    ActionType,
    AutonomyDecision,
    AutonomyLevel,
    AutonomyPolicy,
    CaseType,
    ColorClass,
    NextStep,
    ObservationAttribute,
    ObservationItem,
    ReliabilityResult,
    UpdateAutonomyRequest,
    Visibility,
)
from app.backend.autonomy.decision import evaluate_autonomy_decision
from app.backend.autonomy.reliability import check_case_type_reliability
from app.backend.autonomy.router import update_autonomy_policy
from app.backend.autonomy.version import compute_agent_version
from app.backend.persistence.db import Database
from app.backend.persistence.repository import Repository


class TestAutonomyDecision(unittest.TestCase):
    def setUp(self):
        self.agent_ver = compute_agent_version()
        self.model_id = "gemini-3.8-flash"
        self.policy = AutonomyPolicy(
            store_id="store_dhun",
            version="1.0",
            levels={
                CaseType.DAMAGE: AutonomyLevel.L3,
                CaseType.MISMATCH: AutonomyLevel.L2,
                CaseType.WISMO: AutonomyLevel.L1,
                CaseType.UNCLEAR: AutonomyLevel.L0,
            },
            per_order_cap_minor=150000,          # ₹1,500
            per_customer_daily_cap_minor=200000,  # ₹2,000
            kill_switch=False,
        )

    def _make_passed_reliability(self, scenario_ids: list[str]) -> dict[str, ReliabilityResult]:
        res = {}
        for sid in scenario_ids:
            res[sid] = ReliabilityResult(
                run_id=f"RUN-{sid}",
                scenario_id=sid,
                case_type=CaseType.DAMAGE,
                k=5,
                passes=5,
                pass_at_1=1.0,
                pass_pow_k=1.0,
                agent_version=self.agent_ver,
                model_id=self.model_id,
                ran_at="2026-11-11T10:00:00Z",
                synthetic=False,
            )
        return res

    def test_44_kill_switch_engaged(self):
        """Test 44: When kill switch is engaged, all actions are deferred to seller."""
        killed_policy = self.policy.model_copy(update={"kill_switch": True})
        res = evaluate_autonomy_decision(
            action_type=NextStep.PROPOSE_RETURN.value,
            case_type=CaseType.DAMAGE,
            policy=killed_policy,
        )
        self.assertEqual(res.decision, AutonomyDecision.DEFER_TO_SELLER)
        self.assertEqual(res.reason_code, "kill_switch")
        self.assertEqual(res.checklist[0].status_icon, "✗")
        self.assertFalse(res.checklist[0].passed)

    def test_41_refund_before_receipt_prohibited(self):
        """Test 41: L3 enabled, but refund proposed before RETURN_RECEIVED is received."""
        rel_data = self._make_passed_reliability(["S03", "S10"])
        res = evaluate_autonomy_decision(
            action_type=ActionType.ISSUE_REFUND.value,
            case_type=CaseType.DAMAGE,
            policy=self.policy,
            amount_minor=129900,  # ₹1,299
            order_paid_minor=129900,
            is_receipt_received=False,  # NOT received yet!
            reliability_data=rel_data,
            current_agent_version=self.agent_ver,
            current_model_id=self.model_id,
        )
        self.assertEqual(res.decision, AutonomyDecision.DEFER_TO_SELLER)
        self.assertEqual(res.reason_code, "prohibited_action")
        self.assertIn("RETURN_RECEIVED", res.summary)
        self.assertEqual(res.checklist[1].status_icon, "✗")

    def test_42_unverified_observation_defers_to_seller(self):
        """Test 42: L3 enabled, but evidence has unverified observation (Case B)."""
        rel_data = self._make_passed_reliability(["S03", "S10"])
        unclear_obs = ObservationItem(
            id="OBS-B1",
            evidence_id="EVI-01",
            t="00:07",
            attribute=ObservationAttribute.COLOR,
            value="black item",
            color_class=ColorClass.BLACK,
            visibility=Visibility.UNCLEAR,  # UNCLEAR!
            limitation="Dim lighting in unboxing video",
        )

        res = evaluate_autonomy_decision(
            action_type=ActionType.ISSUE_REFUND.value,
            case_type=CaseType.DAMAGE,
            policy=self.policy,
            amount_minor=129900,
            order_paid_minor=129900,
            is_receipt_received=True,
            observations=[unclear_obs],
            reliability_data=rel_data,
            current_agent_version=self.agent_ver,
            current_model_id=self.model_id,
        )
        self.assertEqual(res.decision, AutonomyDecision.DEFER_TO_SELLER)
        self.assertEqual(res.reason_code, "observation_unverified")
        self.assertEqual(res.checklist[4].status_icon, "✗")

    def test_43_cumulative_daily_split_defers_to_seller(self):
        """Test 43: Refund exceeds daily cumulative threshold (ORD-4401 ₹999 + prior ₹1,299 = ₹2,298 > ₹2,000)."""
        rel_data = self._make_passed_reliability(["S03", "S10"])
        obs = ObservationItem(
            id="OBS-01",
            evidence_id="EVI-01",
            t="00:03",
            attribute=ObservationAttribute.DAMAGE,
            value="shattered headband",
            visibility=Visibility.VISIBLE,
        )

        # Prior refunds today = ₹1,299 (129900 paise).
        # Attempting second refund of ₹999 (99900 paise). Total = ₹2,298 > ₹2,000 daily cap.
        res = evaluate_autonomy_decision(
            action_type=ActionType.ISSUE_REFUND.value,
            case_type=CaseType.DAMAGE,
            policy=self.policy,
            amount_minor=99900,  # ₹999
            order_paid_minor=99900,
            customer_daily_refund_total_minor=129900,  # ₹1,299 already refunded today
            is_receipt_received=True,
            observations=[obs],
            reliability_data=rel_data,
            current_agent_version=self.agent_ver,
            current_model_id=self.model_id,
        )
        self.assertEqual(res.decision, AutonomyDecision.DEFER_TO_SELLER)
        self.assertEqual(res.reason_code, "cumulative_limit")
        self.assertIn("Total today", res.summary)
        self.assertEqual(res.checklist[5].status_icon, "✗")

    def test_happy_path_auto_approval(self):
        """All 7 steps pass -> AUTO approval under policy actor."""
        rel_data = self._make_passed_reliability(["S03", "S10"])
        obs = ObservationItem(
            id="OBS-01",
            evidence_id="EVI-01",
            t="00:03",
            attribute=ObservationAttribute.DAMAGE,
            value="cracked casing",
            visibility=Visibility.VISIBLE,
        )

        res = evaluate_autonomy_decision(
            action_type=ActionType.ISSUE_REFUND.value,
            case_type=CaseType.DAMAGE,
            policy=self.policy,
            amount_minor=129900,  # ₹1,299
            order_paid_minor=129900,
            customer_daily_refund_total_minor=0,
            is_receipt_received=True,
            observations=[obs],
            reliability_data=rel_data,
            current_agent_version=self.agent_ver,
            current_model_id=self.model_id,
        )
        self.assertEqual(res.decision, AutonomyDecision.AUTO)
        self.assertEqual(res.reason_code, "auto_approved")
        self.assertEqual(res.actor, "policy:autonomy@1.0")
        self.assertTrue(all(step.passed for step in res.checklist))

    def test_exceeding_store_cap_or_balance_returns_block(self):
        """Store cap (₹3,000) or order balance exceeded -> BLOCK."""
        rel_data = self._make_passed_reliability(["S03", "S10"])
        # Over store cap
        res_cap = evaluate_autonomy_decision(
            action_type=ActionType.ISSUE_REFUND.value,
            case_type=CaseType.DAMAGE,
            policy=self.policy,
            amount_minor=350000,  # ₹3,500 > ₹3,000 store cap
            order_paid_minor=400000,
            is_receipt_received=True,
            reliability_data=rel_data,
            current_agent_version=self.agent_ver,
            current_model_id=self.model_id,
            store_cap_minor=300000,
        )
        self.assertEqual(res_cap.decision, AutonomyDecision.BLOCK)
        self.assertEqual(res_cap.reason_code, "exceeds_store_cap")

        # Over order balance
        res_bal = evaluate_autonomy_decision(
            action_type=ActionType.ISSUE_REFUND.value,
            case_type=CaseType.DAMAGE,
            policy=self.policy,
            amount_minor=149900,  # ₹1,499
            order_paid_minor=149900,
            order_refunded_minor=50000,  # remaining is 99,900
            is_receipt_received=True,
            reliability_data=rel_data,
            current_agent_version=self.agent_ver,
            current_model_id=self.model_id,
        )
        self.assertEqual(res_bal.decision, AutonomyDecision.BLOCK)
        self.assertEqual(res_bal.reason_code, "exceeds_order_balance")

    def test_40_put_autonomy_rejected_when_reliability_locked(self):
        """Test 40: PUT /api/seller/autonomy returns HTTP 422 if reliability is not 5/5 on matching version."""
        mock_repo = MagicMock()
        # Reliability is NOT passed (e.g. empty or missing results)
        req = UpdateAutonomyRequest(
            levels={CaseType.UNCLEAR: AutonomyLevel.L3},  # UNCLEAR has no passed runs
            per_order_cap_minor=150000,
            per_customer_daily_cap_minor=200000,
        )
        with self.assertRaises(HTTPException) as ctx:
            update_autonomy_policy(payload=req, repo=mock_repo)

        self.assertEqual(ctx.exception.status_code, 422)
        detail = ctx.exception.detail
        self.assertEqual(detail["code"], "reliability_locked")
        self.assertEqual(detail["case_type"], "UNCLEAR")


if __name__ == "__main__":
    unittest.main()
