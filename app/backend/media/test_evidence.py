"""Unit and integration tests for Evidence Slice Backend (Card B05).

Verifies:
- Test 06: Observed Black + barcode unverified (CLIP-B mismatch scenario).
- Test 11: Timestamp outside clip duration rejected by code validation.
- Test 30: Oversized file or invalid format rejected prior to model dispatch.
- Test 31: Boundary timestamp validation on short clips (00:00, 00:10).
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock

from app.backend.contracts import (
    ColorClass,
    Evidence,
    ObservationAttribute,
    ObservationItem,
    ObserverOutput,
    Visibility,
)
from app.backend.media.evidence import (
    MAX_AUDIO_BYTES,
    MAX_IMAGE_BYTES,
    MAX_VIDEO_BYTES,
    MediaValidationError,
    evaluate_color_match,
    ingest_evidence,
    parse_timestamp_ms,
    validate_observations_grounding,
    validate_timestamp,
)
from app.backend.model.client import GeminiModelAdapter
from app.backend.model.observer import VisionObserverRunner


class TestEvidenceSlice(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.media_dir = Path(self.temp_dir.name)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_parse_timestamp_ms(self):
        """Timestamp parsing to milliseconds."""
        self.assertEqual(parse_timestamp_ms("00:00"), 0)
        self.assertEqual(parse_timestamp_ms("00:07"), 7000)
        self.assertEqual(parse_timestamp_ms("01:30"), 90000)
        self.assertIsNone(parse_timestamp_ms("invalid"))
        self.assertIsNone(parse_timestamp_ms(None))

    def test_31_boundary_timestamps_on_short_clip(self):
        """Test 31: Validates exact boundaries (00:00, 00:10) on a 10-second clip."""
        duration_ms = 10000
        # Within duration
        self.assertTrue(validate_timestamp("00:00", duration_ms))
        self.assertTrue(validate_timestamp("00:07", duration_ms))
        self.assertTrue(validate_timestamp("00:10", duration_ms))
        # 1-second rounding tolerance
        self.assertTrue(validate_timestamp("00:11", duration_ms))
        # Out of bounds (> duration + tolerance)
        self.assertFalse(validate_timestamp("00:15", duration_ms))
        self.assertFalse(validate_timestamp("01:00", duration_ms))

    def test_11_timestamp_outside_clip_duration_rejected(self):
        """Test 11: Model returns invalid frame timestamp; code grounding rejects observation."""
        evidence_id = "EVI-12345"
        duration_ms = 10000  # 10 seconds

        obs_valid = ObservationItem(
            id="OBS-1",
            evidence_id=evidence_id,
            t="00:07",
            attribute=ObservationAttribute.COLOR,
            value="black casing",
            color_class=ColorClass.BLACK,
            visibility=Visibility.VISIBLE,
        )
        obs_invalid_t = ObservationItem(
            id="OBS-2",
            evidence_id=evidence_id,
            t="00:45",  # 45 seconds on a 10 second clip!
            attribute=ObservationAttribute.DAMAGE,
            value="hallucinated crack",
            visibility=Visibility.VISIBLE,
        )
        obs_wrong_evi = ObservationItem(
            id="OBS-3",
            evidence_id="EVI-WRONG",
            t="00:05",
            attribute=ObservationAttribute.ITEM_TYPE,
            value="headphones",
            visibility=Visibility.VISIBLE,
        )

        valid, rejections = validate_observations_grounding(
            [obs_valid, obs_invalid_t, obs_wrong_evi],
            evidence_id=evidence_id,
            duration_ms=duration_ms,
        )

        self.assertEqual(len(valid), 1)
        self.assertEqual(valid[0].id, "OBS-1")
        self.assertEqual(len(rejections), 2)
        self.assertTrue(any("outside valid clip duration" in r for r in rejections))
        self.assertTrue(any("EVI-WRONG" in r for r in rejections))

    def test_30_file_too_large_rejected_before_model_call(self):
        """Test 30: Reject file exceeding size limit without calling model."""
        oversized_video = b"\x1a\x45\xdf\xa3" + b"0" * (MAX_VIDEO_BYTES + 1024)
        with self.assertRaises(MediaValidationError) as ctx:
            ingest_evidence(
                file_bytes=oversized_video,
                filename="large.webm",
                case_id="CASE-01",
                media_dir=self.media_dir,
            )
        self.assertEqual(ctx.exception.code, "FILE_TOO_LARGE")

    def test_30_unsupported_format_rejected(self):
        """Test 30: Reject unsupported file format."""
        bad_file = b"MZ\x90\x00\x03\x00\x00\x00"  # Windows EXE header
        with self.assertRaises(MediaValidationError) as ctx:
            ingest_evidence(
                file_bytes=bad_file,
                filename="script.exe",
                case_id="CASE-01",
                media_dir=self.media_dir,
            )
        self.assertEqual(ctx.exception.code, "UNSUPPORTED_MEDIA_TYPE")

    def test_06_clip_b_observed_black_and_barcode_unverified(self):
        """Test 06 (CLIP-B): Observed Black at 00:07, barcode unreadable, color mismatch evaluated in code."""
        # 1. Ingest synthetic webm
        video_bytes = b"\x1a\x45\xdf\xa3" + b"\x00" * 500  # valid webm header bytes
        evi = ingest_evidence(
            file_bytes=video_bytes,
            filename="unboxing.webm",
            case_id="CASE-0012",
            media_dir=self.media_dir,
            duration_ms=18000,
        )
        self.assertEqual(evi.media_type, "video")
        self.assertEqual(evi.duration_ms, 18000)

        # 2. Mock model returning Case B observation
        mock_model_response = MagicMock()
        mock_model_response.text = (
            '{"observations": ['
            '  {"id": "OBS-B1", "evidence_id": "' + evi.evidence_id + '", "t": "00:07", '
            '   "attribute": "color", "value": "black headphones", "color_class": "black", "visibility": "visible"}'
            '],'
            '"unknowns": ["barcode_unreadable", "serial_number_unreadable"],'
            '"ignored_instructions": false}'
        )

        fake_client = MagicMock()
        fake_client.models.generate_content.return_value = mock_model_response

        adapter = GeminiModelAdapter(client=fake_client)
        runner = VisionObserverRunner(adapter=adapter)

        output, model_run = runner.observe(
            evidence=evi,
            media_bytes=video_bytes,
            mime_type="video/webm",
        )

        # 3. Verify grounded observation
        self.assertEqual(len(output.observations), 1)
        obs = output.observations[0]
        self.assertEqual(obs.color_class, ColorClass.BLACK)
        self.assertEqual(obs.t, "00:07")
        self.assertEqual(obs.visibility, Visibility.VISIBLE)

        # 4. Unknowns preserved
        self.assertIn("barcode_unreadable", output.unknowns)
        self.assertIn("serial_number_unreadable", output.unknowns)

        # 5. Code comparison against catalog white (ORD-7729 catalog_color is white)
        match_status, reason = evaluate_color_match(
            observed_color=obs.color_class,
            catalog_color=ColorClass.WHITE,
            visibility=obs.visibility,
        )
        self.assertEqual(match_status, "MISMATCH")
        self.assertEqual(reason, "observed_black_catalog_white")


if __name__ == "__main__":
    unittest.main()
