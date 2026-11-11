"""Deterministic 7-Step Autonomy Evaluation Algorithm.

Per 17 §3, 02 §5b, 23 W4:
Implements the exact 7-step sequence governing earned autonomy decisions:
Returns AUTO, DEFER_TO_SELLER, or BLOCK, accompanied by a per-step checklist
(✓/✗ + quantitative metrics) for the seller console 'Why?' button.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.backend.contracts import (
    ActionType,
    AutonomyDecision,
    AutonomyLevel,
    AutonomyPolicy,
    CaseType,
    NextStep,
    ObservationItem,
    ReliabilityResult,
    Visibility,
)
from app.backend.autonomy.reliability import check_case_type_reliability

LEVEL_REQUIREMENTS: Dict[str, AutonomyLevel] = {
    # L1: Inform
    ActionType.SEND_STATUS_REPLY.value: AutonomyLevel.L1,
    ActionType.REQUEST_EVIDENCE.value: AutonomyLevel.L1,
    NextStep.SEND_STATUS.value: AutonomyLevel.L1,
    NextStep.REQUEST_EVIDENCE.value: AutonomyLevel.L1,
    # L2: Act without money
    ActionType.CREATE_RETURN.value: AutonomyLevel.L2,
    NextStep.PROPOSE_RETURN.value: AutonomyLevel.L2,
    ActionType.NDR_ACTION.value: AutonomyLevel.L2,
    NextStep.PROPOSE_NDR_REATTEMPT.value: AutonomyLevel.L2,
    # L3: Small refund
    ActionType.ISSUE_REFUND.value: AutonomyLevel.L3,
    NextStep.PROPOSE_REFUND.value: AutonomyLevel.L3,
}

LEVEL_ORDER = {
    AutonomyLevel.L0: 0,
    AutonomyLevel.L1: 1,
    AutonomyLevel.L2: 2,
    AutonomyLevel.L3: 3,
}


class ChecklistStep(BaseModel):
    step_no: int
    title: str
    passed: bool
    status_icon: str
    details: str


class AutonomyEvaluationResult(BaseModel):
    decision: AutonomyDecision
    reason_code: str
    summary: str
    actor: Optional[str] = None
    reliability_run_id: Optional[str] = None
    checklist: List[ChecklistStep] = Field(default_factory=list)


def evaluate_autonomy_decision(
    action_type: str,
    case_type: CaseType,
    policy: AutonomyPolicy,
    amount_minor: Optional[int] = None,
    order_paid_minor: int = 0,
    order_refunded_minor: int = 0,
    order_reserved_minor: int = 0,
    customer_daily_refund_total_minor: int = 0,
    order_cumulative_refund_minor: int = 0,
    observations: Optional[List[ObservationItem]] = None,
    reliability_data: Optional[Dict[str, ReliabilityResult]] = None,
    current_agent_version: str = "",
    current_model_id: str = "gemini-3.8-flash",
    is_receipt_received: bool = False,
    is_return_to_origin: bool = False,
    is_customer_denial: bool = False,
    store_cap_minor: int = 300000,  # ₹3.000 store cap
) -> AutonomyEvaluationResult:
    """Evaluates the 7-step sequence strictly in order (17 §3).

    Produces decision and detailed checklist for the 'Why?' button (23 W4).
    """
    checklist: List[ChecklistStep] = []
    required_level = LEVEL_REQUIREMENTS.get(action_type, AutonomyLevel.L0)
    configured_level = policy.levels.get(case_type, AutonomyLevel.L0)

    # -------------------------------------------------------------------------
    # Step 1: Kill switch (17 §3 Step 1)
    # -------------------------------------------------------------------------
    if policy.kill_switch:
        checklist.append(
            ChecklistStep(
                step_no=1,
                title="Kill switch check",
                passed=False,
                status_icon="✗",
                details="Kill switch is ENGAGED by seller; all actions require manual review.",
            )
        )
        return AutonomyEvaluationResult(
            decision=AutonomyDecision.DEFER_TO_SELLER,
            reason_code="kill_switch",
            summary="Autonomy suspended by seller kill switch.",
            checklist=checklist,
        )

    checklist.append(
        ChecklistStep(
            step_no=1,
            title="Kill switch check",
            passed=True,
            status_icon="✓",
            details="Kill switch is disengaged.",
        )
    )

    # -------------------------------------------------------------------------
    # Step 2: Prohibited actions (17 §3 Step 2)
    # -------------------------------------------------------------------------
    is_prohibited = False
    prohibited_reason = ""
    is_refund = action_type in (ActionType.ISSUE_REFUND.value, NextStep.PROPOSE_REFUND.value)

    if is_customer_denial:
        is_prohibited = True
        prohibited_reason = "Customer denial is prohibited from automated execution."
    elif is_return_to_origin:
        is_prohibited = True
        prohibited_reason = "NDR return-to-origin requires explicit seller approval."
    elif is_refund and not is_receipt_received:
        is_prohibited = True
        prohibited_reason = "Refund before RETURN_RECEIVED courier event is prohibited."

    if is_prohibited:
        checklist.append(
            ChecklistStep(
                step_no=2,
                title="Prohibited actions check",
                passed=False,
                status_icon="✗",
                details=prohibited_reason,
            )
        )
        return AutonomyEvaluationResult(
            decision=AutonomyDecision.DEFER_TO_SELLER,
            reason_code="prohibited_action",
            summary=prohibited_reason,
            checklist=checklist,
        )

    checklist.append(
        ChecklistStep(
            step_no=2,
            title="Prohibited actions check",
            passed=True,
            status_icon="✓",
            details="Action is eligible for potential automation.",
        )
    )

    # -------------------------------------------------------------------------
    # Step 3: Configured autonomy level enabled (17 §3 Step 3)
    # -------------------------------------------------------------------------
    if LEVEL_ORDER[required_level] > LEVEL_ORDER[configured_level]:
        msg = (
            f"Action requires {required_level.value}, but seller configured "
            f"{configured_level.value} for {case_type.value}."
        )
        checklist.append(
            ChecklistStep(
                step_no=3,
                title="Autonomy level enabled check",
                passed=False,
                status_icon="✗",
                details=msg,
            )
        )
        return AutonomyEvaluationResult(
            decision=AutonomyDecision.DEFER_TO_SELLER,
            reason_code="level_not_enabled",
            summary=msg,
            checklist=checklist,
        )

    checklist.append(
        ChecklistStep(
            step_no=3,
            title="Autonomy level enabled check",
            passed=True,
            status_icon="✓",
            details=f"Seller configured {configured_level.value} >= required {required_level.value} for {case_type.value}.",
        )
    )

    # -------------------------------------------------------------------------
    # Step 4: Reliability gate check (17 §3 Step 4)
    # -------------------------------------------------------------------------
    rel_run_id = None
    if LEVEL_ORDER[required_level] >= LEVEL_ORDER[AutonomyLevel.L2]:
        rel_passed, rel_reason, rel_metrics = check_case_type_reliability(
            case_type=case_type,
            current_agent_version=current_agent_version,
            current_model_id=current_model_id,
            reliability_data=reliability_data,
            required_k=5,
        )
        if not rel_passed:
            checklist.append(
                ChecklistStep(
                    step_no=4,
                    title="Reliability gate check",
                    passed=False,
                    status_icon="✗",
                    details=rel_reason,
                )
            )
            return AutonomyEvaluationResult(
                decision=AutonomyDecision.DEFER_TO_SELLER,
                reason_code="reliability_locked",
                summary=rel_reason,
                checklist=checklist,
            )

        checklist.append(
            ChecklistStep(
                step_no=4,
                title="Reliability gate check",
                passed=True,
                status_icon="✓",
                details=f"Reliability passed: {case_type.value} passed 5/5 on current agent_version & model.",
            )
        )
    else:
        checklist.append(
            ChecklistStep(
                step_no=4,
                title="Reliability gate check",
                passed=True,
                status_icon="✓",
                details=f"Not required for {required_level.value} actions.",
            )
        )

    # -------------------------------------------------------------------------
    # Step 5: Unverified observations check (17 §3 Step 5, P_UNVERIFIED)
    # -------------------------------------------------------------------------
    has_unverified = False
    unverified_detail = ""
    if observations:
        for obs in observations:
            uncert = getattr(obs, "limitation", None) or getattr(obs, "uncertainty_reason", None)
            if obs.visibility != Visibility.VISIBLE or uncert:
                has_unverified = True
                obs_id = getattr(obs, "id", None) or getattr(obs, "observation_id", "OBS")
                attr_name = obs.attribute.value if hasattr(obs.attribute, "value") else str(obs.attribute)
                unverified_detail = (
                    f"Observation {obs_id} ({attr_name}) is unverified "
                    f"(visibility: {obs.visibility.value}, uncertainty: {uncert or 'none'})."
                )
                break

    if has_unverified:
        checklist.append(
            ChecklistStep(
                step_no=5,
                title="Observation clarity check (P_UNVERIFIED)",
                passed=False,
                status_icon="✗",
                details=unverified_detail,
            )
        )
        return AutonomyEvaluationResult(
            decision=AutonomyDecision.DEFER_TO_SELLER,
            reason_code="observation_unverified",
            summary=f"Deferred to seller: {unverified_detail}",
            checklist=checklist,
        )

    checklist.append(
        ChecklistStep(
            step_no=5,
            title="Observation clarity check (P_UNVERIFIED)",
            passed=True,
            status_icon="✓",
            details="All observations are clear, visible, and verified.",
        )
    )

    # -------------------------------------------------------------------------
    # Step 6: Financial limits and Cumulative gates (17 §3 Step 6)
    # -------------------------------------------------------------------------
    if amount_minor is not None and amount_minor > 0:
        # P_CAP check (store level hard cap)
        if amount_minor > store_cap_minor:
            msg = f"Requested amount ₹{amount_minor/100:.2f} exceeds store maximum cap ₹{store_cap_minor/100:.2f}."
            checklist.append(
                ChecklistStep(
                    step_no=6,
                    title="Financial limits & cumulative gate",
                    passed=False,
                    status_icon="✗",
                    details=msg,
                )
            )
            return AutonomyEvaluationResult(
                decision=AutonomyDecision.BLOCK,
                reason_code="exceeds_store_cap",
                summary=msg,
                checklist=checklist,
            )

        # P_BALANCE check (order remaining balance)
        remaining_minor = order_paid_minor - order_refunded_minor - order_reserved_minor
        if amount_minor > remaining_minor:
            msg = f"Requested amount ₹{amount_minor/100:.2f} exceeds remaining refundable balance ₹{remaining_minor/100:.2f}."
            checklist.append(
                ChecklistStep(
                    step_no=6,
                    title="Financial limits & cumulative gate",
                    passed=False,
                    status_icon="✗",
                    details=msg,
                )
            )
            return AutonomyEvaluationResult(
                decision=AutonomyDecision.BLOCK,
                reason_code="exceeds_order_balance",
                summary=msg,
                checklist=checklist,
            )

        # Cumulative Gate (P_CUMULATIVE)
        # 1. Per-order cumulative limit
        total_order_minor = order_cumulative_refund_minor + amount_minor
        if total_order_minor > policy.per_order_cap_minor:
            msg = (
                f"Order cumulative total ₹{total_order_minor/100:.2f} exceeds "
                f"per-order autonomy threshold ₹{policy.per_order_cap_minor/100:.2f}."
            )
            checklist.append(
                ChecklistStep(
                    step_no=6,
                    title="Financial limits & cumulative gate",
                    passed=False,
                    status_icon="✗",
                    details=msg,
                )
            )
            return AutonomyEvaluationResult(
                decision=AutonomyDecision.DEFER_TO_SELLER,
                reason_code="cumulative_limit",
                summary=msg,
                checklist=checklist,
            )

        # 2. Per-customer daily cumulative limit
        total_customer_daily_minor = customer_daily_refund_total_minor + amount_minor
        if total_customer_daily_minor > policy.per_customer_daily_cap_minor:
            msg = (
                f"Total today ₹{total_customer_daily_minor/100:.2f} exceeds "
                f"daily per-customer limit ₹{policy.per_customer_daily_cap_minor/100:.2f}."
            )
            checklist.append(
                ChecklistStep(
                    step_no=6,
                    title="Financial limits & cumulative gate",
                    passed=False,
                    status_icon="✗",
                    details=msg,
                )
            )
            return AutonomyEvaluationResult(
                decision=AutonomyDecision.DEFER_TO_SELLER,
                reason_code="cumulative_limit",
                summary=msg,
                checklist=checklist,
            )

        checklist.append(
            ChecklistStep(
                step_no=6,
                title="Financial limits & cumulative gate",
                passed=True,
                status_icon="✓",
                details=(
                    f"Amount ₹{amount_minor/100:.2f} is within store cap ₹{store_cap_minor/100:.2f}, "
                    f"remaining balance ₹{remaining_minor/100:.2f}, order limit ₹{policy.per_order_cap_minor/100:.2f}, "
                    f"and daily limit ₹{policy.per_customer_daily_cap_minor/100:.2f}."
                ),
            )
        )
    else:
        checklist.append(
            ChecklistStep(
                step_no=6,
                title="Financial limits & cumulative gate",
                passed=True,
                status_icon="✓",
                details="Action has no financial liability; limits check passed.",
            )
        )

    # -------------------------------------------------------------------------
    # Step 7: Autonomy Granted (17 §3 Step 7)
    # -------------------------------------------------------------------------
    actor = f"policy:autonomy@{policy.version}"
    checklist.append(
        ChecklistStep(
            step_no=7,
            title="Autonomy granted",
            passed=True,
            status_icon="✓",
            details=f"All gates passed. Auto-approved under actor '{actor}'.",
        )
    )

    return AutonomyEvaluationResult(
        decision=AutonomyDecision.AUTO,
        reason_code="auto_approved",
        summary=f"Action auto-approved by autonomy policy {policy.version}.",
        actor=actor,
        reliability_run_id=rel_run_id,
        checklist=checklist,
    )
