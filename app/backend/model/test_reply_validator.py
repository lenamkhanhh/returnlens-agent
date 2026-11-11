"""Unit tests for Customer Reply Template Validator (Card B12/17 §4/Test 14).

Verifies:
- Placeholders {{order_id}}, {{amount}}, {{tracking_status}}, {{eta}} populated from DB.
- Mismatched order ID triggers template fallback and reply_validation_failed.
- Mismatched amount triggers template fallback and reply_validation_failed.
- Test 14: Premature refund or return claim before action succeeded triggers template fallback.
- Valid draft passes without alteration.
"""

from __future__ import annotations

import unittest

from app.backend.contracts import CaseType, Language
from app.backend.model.reply_validator import (
    VerifiedReplyContext,
    validate_and_hydrate_reply,
)


class TestReplyValidator(unittest.TestCase):
    def setUp(self):
        self.context = VerifiedReplyContext(
            order_id="ORD-7729",
            amount_minor=149900,  # ₹1,499
            tracking_status="Out for Delivery",
            eta="today by 6 PM",
            action_status="pending",
            case_type=CaseType.MISMATCH,
            language=Language.EN,
        )

    def test_placeholder_hydration(self):
        """Placeholders are cleanly substituted from verified context."""
        draft = "Hello! Order {{order_id}} has amount {{amount}}. Status is {{tracking_status}} ({{eta}})."
        hydrated, is_valid, reason = validate_and_hydrate_reply(draft, self.context)

        self.assertTrue(is_valid)
        self.assertIsNone(reason)
        self.assertIn("ORD-7729", hydrated)
        self.assertIn("₹1,499", hydrated)
        self.assertIn("Out for Delivery", hydrated)
        self.assertIn("today by 6 PM", hydrated)

    def test_mismatched_order_id_triggers_fallback(self):
        """Handwritten incorrect order ID causes validation failure and template fallback."""
        draft = "We found your package under order ORD-9999. It will arrive shortly."
        reply, is_valid, reason = validate_and_hydrate_reply(draft, self.context)

        self.assertFalse(is_valid)
        self.assertIn("reply_validation_failed", reason)
        self.assertIn("ORD-9999", reason)
        # Replaced with approved template referencing the real order
        self.assertIn("ORD-7729", reply)
        self.assertNotIn("ORD-9999", reply)

    def test_mismatched_amount_triggers_fallback(self):
        """Handwritten incorrect monetary amount causes validation failure and template fallback."""
        draft = "Your claim for order {{order_id}} for ₹1,800 has been reviewed."
        reply, is_valid, reason = validate_and_hydrate_reply(draft, self.context)

        self.assertFalse(is_valid)
        self.assertIn("reply_validation_failed", reason)
        self.assertIn("₹1800.00", reason)
        self.assertNotIn("₹1,800", reply)

    def test_14_premature_refund_claim_blocked(self):
        """Test 14: LLM draft claims money was refunded before action succeeded."""
        draft = "Good news! We have refunded {{amount}} for order {{order_id}}."
        # Context has action_status = 'pending'
        reply, is_valid, reason = validate_and_hydrate_reply(draft, self.context)

        self.assertFalse(is_valid)
        self.assertIn("reply_validation_failed", reason)
        self.assertIn("premature refund claim", reason)
        # Overridden with safe template
        self.assertNotIn("have refunded", reply)
        self.assertIn("ORD-7729", reply)

    def test_valid_draft_after_success_allowed(self):
        """When action has succeeded, accurate confirmation draft is accepted."""
        success_ctx = self.context.model_copy(update={"action_status": "succeeded"})
        draft = "Your refund of {{amount}} for order {{order_id}} has been processed."
        reply, is_valid, reason = validate_and_hydrate_reply(draft, success_ctx)

        self.assertTrue(is_valid)
        self.assertIsNone(reason)
        self.assertIn("₹1,499", reply)
        self.assertIn("ORD-7729", reply)


if __name__ == "__main__":
    unittest.main()
