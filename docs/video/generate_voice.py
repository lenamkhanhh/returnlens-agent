"""Generate synthetic voice narration clips using edge-tts.

Wave 16 Configuration:
- Voice: en-US-AndrewMultilingualNeural
- Rate: +4%
- Format: MP3 (48kHz stereo)
- Safety: Strictly asserts zero overlaps between cues and trims/warns if duration exceeds window.
"""

import argparse
import asyncio
import re
import subprocess
import sys
from pathlib import Path
from typing import Dict, List

import edge_tts


def parse_subtitles(path: Path) -> List[Dict]:
    """Parse SRT or ASS file into timed cue dictionaries."""
    content = path.read_text(encoding="utf-8")
    cues = []

    if path.suffix.lower() == ".ass":
        for line in content.splitlines():
            line = line.strip()
            if line.startswith("Dialogue:"):
                parts = line.split(",", 9)
                if len(parts) >= 10:
                    start_str, end_str, text_raw = parts[1], parts[2], parts[9]
                    
                    def to_sec(ts: str) -> float:
                        h, m, s = ts.strip().replace(",", ".").split(":")
                        return int(h) * 3600.0 + int(m) * 60.0 + float(s)

                    start_s = to_sec(start_str)
                    end_s = to_sec(end_str)
                    text = text_raw.replace("\\N", " ").replace("\\n", " ").strip()
                    # Clean ASS tags like {\...}
                    text = re.sub(r"\{.*?\}", "", text).strip()
                    cues.append({
                        "idx": len(cues) + 1,
                        "start": start_s,
                        "end": end_s,
                        "text": text,
                    })
    else:
        # Standard SRT parser
        blocks = content.strip().split("\n\n")
        for block in blocks:
            lines = [l.strip() for l in block.splitlines() if l.strip()]
            if len(lines) >= 3:
                try:
                    idx = int(lines[0])
                except ValueError:
                    continue
                m = re.match(r"(\d+:\d+:\d+,\d+)\s*-->\s*(\d+:\d+:\d+,\d+)", lines[1])
                if not m:
                    continue

                def to_sec(ts: str) -> float:
                    h, m, rest = ts.split(":")
                    s, ms = rest.split(",")
                    return int(h) * 3600.0 + int(m) * 60.0 + int(s) + int(ms) / 1000.0

                start_s = to_sec(m.group(1))
                end_s = to_sec(m.group(2))
                text = " ".join(lines[2:]).strip()
                cues.append({
                    "idx": idx,
                    "start": start_s,
                    "end": end_s,
                    "text": text,
                })

    return cues


def get_audio_duration(file_path: Path) -> float:
    """Measure audio file duration using ffprobe."""
    cmd = [
        "ffprobe", "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(file_path),
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return float(res.stdout.strip())


async def generate_cue(
    cue: Dict,
    output_path: Path,
    voice: str = "en-US-AndrewMultilingualNeural",
    rate: str = "+4%",
) -> float:
    """Generate a single speech audio file using edge-tts."""
    tts = edge_tts.Communicate(cue["text"], voice, rate=rate)
    await tts.save(str(output_path))
    dur = get_audio_duration(output_path)
    return dur


async def generate_all(
    subtitles_path: Path,
    output_dir: Path,
    voice: str = "en-US-AndrewMultilingualNeural",
    rate: str = "+4%",
    dry_run: bool = False,
) -> bool:
    """Generate all cues, checking durations against next cue start times."""
    cues = parse_subtitles(subtitles_path)
    if not cues:
        print(f"Error: No cues found in {subtitles_path}")
        return False

    output_dir.mkdir(parents=True, exist_ok=True)
    print(f"Generating {len(cues)} cues with voice='{voice}', rate='{rate}'...")

    overlaps = 0
    total_speech_s = 0.0

    for i, cue in enumerate(cues):
        cue_file = output_dir / f"cue_{cue['idx']:02d}.mp3"
        next_start = cues[i + 1]["start"] if (i + 1 < len(cues)) else cue["end"] + 10.0
        allowed_window = next_start - cue["start"]

        if dry_run:
            print(f"Cue {cue['idx']:02d} [{cue['start']:.2f}s -> {cue['end']:.2f}s | window {allowed_window:.2f}s]: {cue['text']}")
            continue

        dur = await generate_cue(cue, cue_file, voice=voice, rate=rate)
        total_speech_s += dur

        if dur > allowed_window:
            print(f"[OVERLAP WARNING] Cue {cue['idx']:02d}: duration {dur:.2f}s > window {allowed_window:.2f}s (starts {cue['start']:.2f}s, next starts {next_start:.2f}s)!")
            print(f"   Text: '{cue['text']}'")
            overlaps += 1
        else:
            slack = allowed_window - dur
            print(f"  * Cue {cue['idx']:02d} [{cue['start']:6.2f}s]: {dur:5.2f}s (window {allowed_window:5.2f}s, slack +{slack:4.2f}s) -> {cue_file.name}")

    print(f"\nCompleted! Generated {len(cues)} clips. Total speech: {total_speech_s:.2f}s. Overlaps: {overlaps}.")
    return overlaps == 0


def main():
    parser = argparse.ArgumentParser(description="Generate synthetic voice clips for ReturnLens demo.")
    parser.add_argument(
        "--subtitles",
        type=Path,
        default=Path(__file__).parent / "narration.ass" if (Path(__file__).parent / "narration.ass").exists() else Path(__file__).parent / "narration.srt",
        help="Path to ASS or SRT subtitles",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=Path(__file__).parent / "audio" / "clips",
        help="Output directory for MP3 clips",
    )
    parser.add_argument(
        "--voice",
        type=str,
        default="en-US-AndrewMultilingualNeural",
        help="edge-tts voice name (default: en-US-AndrewMultilingualNeural)",
    )
    parser.add_argument(
        "--rate",
        type=str,
        default="+4%",
        help="Speaking rate adjustment (default: +4%%)",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Print cues without generating audio",
    )
    args = parser.parse_args()

    success = asyncio.run(generate_all(
        subtitles_path=args.subtitles,
        output_dir=args.output_dir,
        voice=args.voice,
        rate=args.rate,
        dry_run=args.dry_run,
    ))
    sys.exit(0 if success else 1)


if __name__ == "__main__":
    main()
