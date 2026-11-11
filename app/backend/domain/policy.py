"""Deterministic Domain Policy Engine per 02 §5, 04 §2, and 17 §2.

Evaluates return windows, store caps, remaining refundable balances,
receipt requirements, and clarification limits by deterministic code.
"""

from __future__ import annotations

from datetime import date
from typing import Optional

from app.backend.contracts import (
    PolicyCheck,
    PolicyCheckResult,
    PolicyRuleId,
)


def check_return_window(
    delivered_at: Optional[str],
    demo_today: str = "2026-11-11",
    window_days: int = 7,
) -> PolicyCheck:
    """Evaluate return window (P_WINDOW, 04 §2 Tests 04, 05).

    Rules:
    - Missing delivery date: UNKNOWN (missing_delivery_date).
    - Future delivery date (delivered_date > demo_today): UNKNOWN (future_delivery_date).
    - Inclusive window: 0 <= diff_days <= window_days: PASS.
    - Day > window_days: FAIL (outside_window).
    """
    if not delivered_at:
        return PolicyCheck(
            rule_id=PolicyRuleId.P_WINDOW,
            result=PolicyCheckResult.UNKNOWN,
            reason_code="missing_delivery_date",
        )

    try:
        del_date = date.fromisoformat(delivered_at)
        today = date.fromisoformat(demo_today)
    except ValueError:
        return PolicyCheck(
            rule_id=PolicyRuleId.P_WINDOW,
            result=PolicyCheckResult.UNKNOWN,
            reason_code="invalid_delivery_date_format",
        )

    diff_days = (today - del_date).days

    if diff_days < 0:
        return PolicyCheck(
            rule_id=PolicyRuleId.P_WINDOW,
            result=PolicyCheckResult.UNKNOWN,
            reason_code="future_delivery_date",
        )

    if diff_days <= window_days:
        return PolicyCheck(
            rule_id=PolicyRuleId.P_WINDOW,
            result=PolicyCheckResult.PASS,
            reason_code=f"within_window_{diff_days}_days",
        )

    return PolicyCheck(
        rule_id=PolicyRuleId.P_WINDOW,
        result=PolicyCheckResult.FAIL,
        reason_code=f"outside_window_{diff_days}_days",
    )


def check_refund_limits(
    requested_minor: int,
    remaining_minor: int,
    store_cap_minor: int = 300000,
) -> PolicyCheck:
    """Evaluate refund requested vs store cap and remaining balance (P_CAP, P_BALANCE)."""
    if requested_minor <= 0:
        return PolicyCheck(
            rule_id=PolicyRuleId.P_CAP,
            result=PolicyCheckResult.FAIL,
            reason_code="non_positive_amount",
        )

    if requested_minor > store_cap_minor:
        return PolicyCheck(
            rule_id=PolicyRuleId.P_CAP,
            result=PolicyCheckResult.FAIL,
            reason_code=f"exceeds_store_cap_{store_cap_minor}",
        )

    if requested_minor > remaining_minor:
        return PolicyCheck(
            rule_id=PolicyRuleId.P_BALANCE,
            result=PolicyCheckResult.FAIL,
            reason_code=f"exceeds_remaining_balance_{remaining_minor}",
        )

    return PolicyCheck(
        rule_id=PolicyRuleId.P_BALANCE,
        result=PolicyCheckResult.PASS,
        reason_code="within_limits",
    )


def check_receipt_before_refund(
    return_status: Optional[str],
) -> PolicyCheck:
    """Evaluate P_RECEIPT: refund requires RETURN_RECEIVED before approval/issuance."""
    if return_status and return_status.lower() == "received":
        return PolicyCheck(
            rule_id=PolicyRuleId.P_RECEIPT,
            result=PolicyCheckResult.PASS,
            reason_code="return_received",
        )

    return PolicyCheck(
        rule_id=PolicyRuleId.P_RECEIPT,
        result=PolicyCheckResult.FAIL,
        reason_code="return_not_received",
    )
