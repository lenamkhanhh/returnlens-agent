"""Contact sheet frame extractor for ReturnLens video scenes.
Wave 17 (Role E / INK chat).

Extracts one frame per second from docs/video/scenes/scene_XX.mp4
into docs/video/scenes/frames/scene_XX/ (git-ignored) for visual verification
and SCENE_FACTS.md alignment.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path

# Paths
REPO_ROOT = Path(__file__).resolve().parents[3]
SCENES_DIR = REPO_ROOT / "docs" / "video" / "scenes"
FRAMES_DIR = SCENES_DIR / "frames"

# FFmpeg resolution
DEFAULT_FFMPEG_PATH = Path(
    r"C:\Users\HP\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
)

def get_ffmpeg_binary() -> str:
    """Find ffmpeg binary either in Winget packages or in PATH."""
    if DEFAULT_FFMPEG_PATH.exists():
        return str(DEFAULT_FFMPEG_PATH)
    shutil_path = shutil.which("ffmpeg")
    if shutil_path:
        return shutil_path
    raise FileNotFoundError("ffmpeg binary not found. Please ensure ffmpeg is installed.")

def extract_scene_frames(scene_id: int | str, clean: bool = True) -> list[Path]:
    """Extract 1 frame per second from scene_XX.mp4 into scenes/frames/scene_XX/."""
    if isinstance(scene_id, int):
        scene_str = f"scene_{scene_id:02d}"
    else:
        scene_str = scene_id if scene_id.startswith("scene_") else f"scene_{int(scene_id):02d}"

    mp4_path = SCENES_DIR / f"{scene_str}.mp4"
    if not mp4_path.exists():
        print(f"[CONTACT_SHEET] Video not found: {mp4_path}")
        return []

    out_dir = FRAMES_DIR / scene_str
    if clean and out_dir.exists():
        for old_file in out_dir.glob("*.png"):
            try:
                old_file.unlink()
            except Exception:
                pass
    out_dir.mkdir(parents=True, exist_ok=True)

    ffmpeg_bin = get_ffmpeg_binary()
    output_pattern = str(out_dir / "frame_%03ds.png")

    # Extract 1 frame per second (-vf fps=1)
    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(mp4_path),
        "-vf", "fps=1",
        output_pattern
    ]

    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode != 0:
        print(f"[CONTACT_SHEET ERROR] ffmpeg failed for {scene_str}: {res.stderr.decode()[:300]}")
        return []

    extracted_frames = sorted(out_dir.glob("frame_*.png"))
    print(f"[CONTACT_SHEET] {scene_str}: extracted {len(extracted_frames)} frames (1 fps) -> {out_dir}")
    return extracted_frames

def extract_all_scenes(clean: bool = True) -> dict[str, list[Path]]:
    """Extract 1 frame per second for all 8 scenes (scene_01 to scene_08)."""
    results: dict[str, list[Path]] = {}
    for i in range(1, 9):
        scene_name = f"scene_{i:02d}"
        mp4_path = SCENES_DIR / f"{scene_name}.mp4"
        if mp4_path.exists():
            frames = extract_scene_frames(i, clean=clean)
            results[scene_name] = frames
        else:
            print(f"[CONTACT_SHEET SKIP] {mp4_path.name} does not exist.")
    return results

def main() -> None:
    parser = argparse.ArgumentParser(description="Extract 1 frame per second for ReturnLens video scenes")
    parser.add_argument(
        "scene",
        nargs="?",
        default="all",
        help="Scene to extract (e.g. '01', 'scene_01', or 'all' for all 8 scenes)"
    )
    parser.add_argument(
        "--no-clean",
        action="store_true",
        help="Do not delete existing frame images in the output directory"
    )

    args = parser.parse_args()
    clean = not args.no_clean

    if args.scene.lower() == "all":
        print(f"[CONTACT_SHEET] Extracting frames for ALL available scenes into {FRAMES_DIR}...")
        results = extract_all_scenes(clean=clean)
        total_frames = sum(len(f) for f in results.values())
        print(f"[CONTACT_SHEET DONE] Extracted total {total_frames} frames across {len(results)} scenes.")
    else:
        extract_scene_frames(args.scene, clean=clean)

if __name__ == "__main__":
    main()
