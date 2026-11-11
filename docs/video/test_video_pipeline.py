"""Unit and validation tests for ReturnLens demo video tooling (Wave 9, Role B)."""

import re
import unittest
from pathlib import Path

from docs.video.assemble import find_binary, find_font_file


class TestVideoPipeline(unittest.TestCase):
    def setUp(self):
        self.video_dir = Path(__file__).parent
        self.srt_path = self.video_dir / "narration.srt"
        self.shotlist_path = self.video_dir / "SHOTLIST.md"
        self.assemble_path = self.video_dir / "assemble.py"

    def test_narration_srt_integrity(self):
        """Verify narration.srt exists, has 23 blocks, and contains no raw unmeasured placeholders."""
        self.assertTrue(self.srt_path.exists(), "narration.srt missing")
        content = self.srt_path.read_text(encoding="utf-8")

        # Verify no un-substituted bracketed placeholders from 19 §1 remain
        self.assertNotIn("[MEASURED:", content, "narration.srt still contains unresolved [MEASURED: ...] placeholder!")

        # Verify contains the measured pass^k result from reliability.json
        self.assertIn("8 of 10 scenarios passed all five runs", content)

        # Count subtitle blocks
        blocks = re.findall(r"^\d+\s*$", content, re.MULTILINE)
        self.assertEqual(len(blocks), 23, "narration.srt should have exactly 23 timed subtitle blocks")

        # Verify timing bounds (ends near 02:59)
        self.assertIn("00:02:48,000 --> 00:02:59,500", content)

    def test_shotlist_covers_all_eight_scenes(self):
        """Verify SHOTLIST.md exists and covers scenes 01 through 08 per 18 §3 and 19 §1."""
        self.assertTrue(self.shotlist_path.exists(), "SHOTLIST.md missing")
        content = self.shotlist_path.read_text(encoding="utf-8")

        for i in range(1, 9):
            scene_header = f"Scene 0{i}"
            self.assertIn(scene_header, content, f"SHOTLIST.md must define {scene_header}")

        self.assertTrue("2x speed" in content.lower() or "2× speed" in content.lower())
        self.assertIn("ORD-1042", content)
        self.assertIn("ORD-4401", content)
        self.assertIn("agent_version", content)

    def test_ffmpeg_and_fonts_discoverable(self):
        """Verify FFmpeg binary can be located on the system."""
        ffmpeg_bin = find_binary("ffmpeg")
        self.assertTrue(Path(ffmpeg_bin).exists())
        self.assertTrue(ffmpeg_bin.lower().endswith("ffmpeg.exe"))

        font_file = find_font_file()
        if font_file:
            self.assertTrue(Path(font_file).exists())


if __name__ == "__main__":
    unittest.main()
