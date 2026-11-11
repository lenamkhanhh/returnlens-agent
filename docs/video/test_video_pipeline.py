"""Unit and validation tests for ReturnLens demo video tooling (Wave 9, Role B)."""

import re
import unittest
from pathlib import Path

from docs.video.assemble import find_binary, find_font_file


class TestVideoPipeline(unittest.TestCase):
    def setUp(self):
        self.video_dir = Path(__file__).parent
        self.srt_path = self.video_dir / "narration.srt"
        self.ass_path = self.video_dir / "narration.ass"
        self.shotlist_path = self.video_dir / "SHOTLIST.md"
        self.assemble_path = self.video_dir / "assemble.py"
        self.audio_dir = self.video_dir / "audio"
        self.clips_dir = self.audio_dir / "clips"
        self.credits_path = self.video_dir / "CREDITS.md"

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

    def test_narration_ass_and_formatting(self):
        """Verify narration.ass conforms to 1080p PlayRes, max 2 lines, <=42 chars per line."""
        self.assertTrue(self.ass_path.exists(), "narration.ass missing")
        content = self.ass_path.read_text(encoding="utf-8")
        self.assertIn("PlayResX: 1920", content)
        self.assertIn("PlayResY: 1080", content)
        self.assertIn("Style: Default,Arial,32", content)
        self.assertIn("BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV", content)

        dialogues = [line for line in content.splitlines() if line.startswith("Dialogue:")]
        self.assertEqual(len(dialogues), 23, "narration.ass must have exactly 23 dialogue cues")

        for d in dialogues:
            parts = d.split(",", 9)
            self.assertGreaterEqual(len(parts), 10)
            text = parts[9].replace("\\N", "\n").replace("\\n", "\n")
            lines = [l.strip() for l in text.split("\n") if l.strip()]
            self.assertLessEqual(len(lines), 2, f"Cue has >2 lines: {text}")
            for l in lines:
                self.assertLessEqual(len(l), 42, f"Line exceeds 42 characters ({len(l)} chars): '{l}'")

    def test_audio_assets_and_credits(self):
        """Verify 23 MP3 clips exist, no WAV copies remain, music exists, and CREDITS.md is complete."""
        self.assertTrue(self.clips_dir.exists(), "Clips directory missing")
        mp3_clips = list(self.clips_dir.glob("cue_*.mp3"))
        wav_clips = list(self.clips_dir.glob("cue_*.wav"))
        self.assertEqual(len(mp3_clips), 23, "Expected exactly 23 cue MP3 files")
        self.assertEqual(len(wav_clips), 0, "No raw WAV clips should remain committed in repo")

        total_mp3_size = sum(f.stat().st_size for f in mp3_clips)
        self.assertLess(total_mp3_size, 1_000_000, "All 23 MP3 clips together should be under 1 MB")

        music_file = self.audio_dir / "gymnopedie_no1.ogg"
        self.assertTrue(music_file.exists(), "Background music gymnopedie_no1.ogg missing")

        self.assertTrue(self.credits_path.exists(), "CREDITS.md missing")
        credits_text = self.credits_path.read_text(encoding="utf-8")
        self.assertIn("synthetic", credits_text.lower())
        self.assertIn("gymnopédie", credits_text.lower())
        self.assertIn("public domain", credits_text.lower())


if __name__ == "__main__":
    unittest.main()
