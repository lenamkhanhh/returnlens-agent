"""Reply Template Hydration and Hallucination Validator.

Per 17 §4, 03 §5, Test 14:
- Populates customer_reply_draft placeholders ({{order_id}}, {{amount}}, {{tracking_status}}, {{eta}})
  strictly from verified DB facts.
- Detects handwritten mismatched amounts or order IDs.
- Prevents premature mutation claims (e.g. claiming a refund or label has been processed
  before action status is committed and succeeded).
- Automatically substitutes store-approved template and flags reply_validation_failed on discrepancy.
"""

from __future__ import annotations

import re
from typing import Optional, Tuple
from pydantic import BaseModel

from app.backend.contracts import CaseType, Language

# Regex patterns to detect handwritten numbers and IDs
ORDER_ID_PATTERN = re.compile(r"\bORD-\d{4,}\b", re.IGNORECASE)
CURRENCY_PATTERN = re.compile(r"₹\s*([0-9,]+(?:\.[0-9]{2})?)|\bINR\s*([0-9,]+)\b", re.IGNORECASE)

PREMATURE_REFUND_PHRASES = [
    "has been refunded",
    "have refunded",
    "refund has been processed",
    "refund is processed",
    "money has been transferred",
    "amount has been credited",
    "refund is complete",
]

PREMATURE_RETURN_PHRASES = [
    "return label has been generated",
    "return label has been created",
    "pickup has been scheduled",
]


class VerifiedReplyContext(BaseModel):
    order_id: str
    amount_minor: Optional[int] = None
    tracking_status: Optional[str] = None
    eta: Optional[str] = None
    action_status: str = "none"  # "none", "pending", "succeeded", "blocked", "failed"
    case_type: Optional[CaseType] = None
    language: Language = Language.EN


def get_approved_template(context: VerifiedReplyContext) -> str:
    """Return canonical store-approved template based on case context."""
    amt_str = f"₹{context.amount_minor / 100:.2f}" if context.amount_minor else ""

    if context.language == Language.HI:
        if context.case_type == CaseType.WISMO:
            return f"आपके ऑर्डर {context.order_id} का स्टेटस {context.tracking_status or 'रास्ते में'} है।"
        return f"आपके ऑर्डर {context.order_id} के संबंध में अनुरोध की समीक्षा की जा रही है।"

    # English / Hinglish
    if context.case_type == CaseType.WISMO:
        status_txt = context.tracking_status or "in transit"
        eta_txt = f" Expected delivery: {context.eta}." if context.eta else ""
        return f"Your order {context.order_id} is currently {status_txt}.{eta_txt}"

    if context.action_status == "succeeded" and context.amount_minor:
        return f"Your refund of {amt_str} for order {context.order_id} has been processed successfully."

    return (
        f"Thank you for contacting Dhun Audio support. We are reviewing your request "
        f"for order {context.order_id}."
    )


def validate_and_hydrate_reply(
    draft: str,
    context: VerifiedReplyContext,
) -> Tuple[str, bool, Optional[str]]:
    """Hydrate template placeholders and validate customer reply against DB facts.

    Returns:
        (final_reply: str, is_valid: bool, failure_reason: Optional[str])
    """
    if not draft or not draft.strip():
        return get_approved_template(context), False, "empty_draft"

    # 1. Hydrate valid placeholders
    hydrated = draft.replace("{{order_id}}", context.order_id)

    if context.amount_minor is not None:
        if context.amount_minor % 100 == 0:
            formatted_amt = f"₹{context.amount_minor // 100:,}"
        else:
            formatted_amt = f"₹{context.amount_minor / 100:,.2f}"
        hydrated = hydrated.replace("{{amount}}", formatted_amt)

    if context.tracking_status:
        hydrated = hydrated.replace("{{tracking_status}}", context.tracking_status)

    if context.eta:
        hydrated = hydrated.replace("{{eta}}", context.eta)

    # 2. Check for handwritten mismatched Order IDs
    found_order_ids = ORDER_ID_PATTERN.findall(hydrated)
    for found_id in found_order_ids:
        if found_id.upper() != context.order_id.upper():
            return (
                get_approved_template(context),
                False,
                f"reply_validation_failed: draft mentions order {found_id} but active order is {context.order_id}",
            )

    # 3. Check for handwritten mismatched amounts
    if context.amount_minor is not None:
        expected_rupees = context.amount_minor / 100.0
        # Search for any ₹ amounts
        for match in CURRENCY_PATTERN.finditer(hydrated):
            raw_amt_str = match.group(1) or match.group(2)
            try:
                num = float(raw_amt_str.replace(",", ""))
                # Compare with 1 rupee tolerance
                if abs(num - expected_rupees) > 1.0:
                    return (
                        get_approved_template(context),
                        False,
                        f"reply_validation_failed: draft mentions ₹{num:.2f} but verified amount is ₹{expected_rupees:.2f}",
                    )
            except ValueError:
                pass

    # 4. Check for premature mutation claims (Test 14)
    lower_text = hydrated.lower()
    if context.action_status != "succeeded":
        for phrase in PREMATURE_REFUND_PHRASES:
            if phrase in lower_text:
                return (
                    get_approved_template(context),
                    False,
                    f"reply_validation_failed: premature refund claim '{phrase}' before action commit",
                )
        for phrase in PREMATURE_RETURN_PHRASES:
            if phrase in lower_text:
                return (
                    get_approved_template(context),
                    False,
                    f"reply_validation_failed: premature return label claim '{phrase}' before action commit",
                )

    return hydrated, True, None
