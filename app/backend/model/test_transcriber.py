"""Unit tests for Audio Transcriber and Reconciliation (Card B15).

Verifies:
- Test 47: Customer verbally claims ₹1.800 (180000 paise) while order paid_minor is ₹1.499 (149900 paise).
  Discrepancy is flagged, customer claim is marked unverified, and domain ledger is strictly enforced.
- Hindi voice note transcription with Devanagari script and English translation.
- Audio constraint enforcement (size <= 5 MB, duration <= 2 min).
- Canonical VoiceNote generation with ModelRun provenance.
"""

from __future__ import annotations

import unittest
from unittest.mock import MagicMock

from app.backend.contracts import (
    ColorClass,
    Intent,
    Language,
    LineItem,
    MentionedFacts,
    Order,
    TranscriberOutput,
)
from app.backend.media.audio import validate_audio_note
from app.backend.media.evidence import MediaValidationError
from app.backend.model.client import GeminiModelAdapter
from app.backend.model.transcriber import AudioTranscriberRunner, reconcile_voice_claims


class TestAudioTranscriber(unittest.TestCase):
    def test_hindi_voice_note_transcription(self):
        """Audio transcriber correctly parses Hindi speech, Devanagari script, and translation."""
        fake_response = MagicMock()
        fake_response.text = (
            '{"transcript": "मुझे गलत रंग का हेडफोन मिला है, कृपया इसे बदलें।",'
            ' "language": "hi",'
            ' "translation_en": "I received the wrong color headphones, please replace them.",'
            ' "intent": "RETURN",'
            ' "mentioned": {"order_ids": ["ORD-7729"], "amounts_minor": [149900]},'
            ' "inaudible": false}'
        )

        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = fake_response

        adapter = GeminiModelAdapter(client=fake_client)
        runner = AudioTranscriberRunner(adapter=adapter)

        # Mock 2-second WAV bytes
        audio_bytes = b"RIFF" + b"\x00" * 200 + b"WAVE" + b"\x00" * 500

        output, model_run, voice_note = runner.transcribe(
            audio_bytes=audio_bytes,
            mime_type="audio/wav",
            evidence_id="EVI-VN-01",
            duration_ms=4000,
        )

        self.assertEqual(output.language, Language.HI)
        self.assertIn("हेडफोन", output.transcript)
        self.assertEqual(output.intent, Intent.RETURN)
        self.assertEqual(output.mentioned.order_ids, ["ORD-7729"])
        self.assertEqual(output.mentioned.amounts_minor, [149900])
        self.assertFalse(output.inaudible)

        # VoiceNote entity verification
        self.assertEqual(voice_note.evidence_id, "EVI-VN-01")
        self.assertEqual(voice_note.language_detected, Language.HI)
        self.assertEqual(voice_note.transcript_model_run_id, model_run.run_id)

    def test_47_voice_note_mentions_different_amount_than_ledger(self):
        """Test 47: Customer verbally claims ₹1.800, but ledger is ₹1.499.

        Verified ledger facts must be strictly enforced and customer speech must
        never override the financial balance.
        """
        # Verified order from DB
        order = Order(
            order_id="ORD-7729",
            store_id="store-dhun",
            customer_id="CUS-02",
            currency="INR",
            paid_minor=149900,  # ₹1.499 in paise
            refunded_minor=0,
            reserved_minor=0,
            revision=1,
            line_item=LineItem(
                item_id="item-02",
                sku="HEAD-WHT-02",
                catalog_color=ColorClass.WHITE,
                display_name="Dhun Wave Headphones",
                quantity=1,
                refundable_item_minor=149900,
            ),
        )

        # Customer verbally claimed 180000 paise (₹1.800) in the audio note
        customer_mentioned = MentionedFacts(
            order_ids=["ORD-7729"],
            amounts_minor=[180000],  # Customer claims ₹1.800
        )

        reconciliation = reconcile_voice_claims(customer_mentioned, order)

        # Check that discrepancy was flagged
        self.assertTrue(reconciliation["amount_mismatch"])
        self.assertEqual(reconciliation["status"], "DISCREPANCY_FLAGGED")
        self.assertEqual(reconciliation["spoken_amounts_minor"], [180000])
        self.assertEqual(reconciliation["verified_paid_minor"], 149900)
        # Truth enforced is from ledger, NOT customer speech
        self.assertEqual(reconciliation["enforced_amount_minor"], 149900)
        self.assertTrue(any("Customer verbally claimed amount" in d for d in reconciliation["discrepancies"]))

    def test_oversized_audio_rejected_before_dispatch(self):
        """Audio exceeding 5 MB limit is rejected prior to model dispatch."""
        oversized = b"OggS" + b"0" * (5 * 1024 * 1024 + 512)
        with self.assertRaises(MediaValidationError) as ctx:
            validate_audio_note(oversized, "note.ogg")
        self.assertEqual(ctx.exception.code, "FILE_TOO_LARGE")

    def test_non_audio_file_rejected(self):
        """Non-audio file rejected by audio validator."""
        bad_file = b"\x89PNG\r\n\x1a\n" + b"\x00" * 100
        with self.assertRaises(MediaValidationError) as ctx:
            validate_audio_note(bad_file, "photo.png")
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_MEDIA_TYPE")


if __name__ == "__main__":
    unittest.main()
