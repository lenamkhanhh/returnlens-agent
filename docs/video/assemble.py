#!/usr/bin/env python3
"""ReturnLens Demo Video Assembly Pipeline (13 §6, 18 §3, 19 §1).

Discovers ffmpeg/ffprobe, normalizes scene clips (1080p 30fps stereo),
applies the '2× speed' badge to fast-forwarded scenes (Scene 03),
concatenates scenes 01 through 08, burns subtitles (narration.srt),
and validates that output duration <= 3:00 (180 seconds).

Includes a standalone '--test' mode that generates synthetic test clips
to verify the pipeline end-to-end without real footage or model calls.
"""

from __future__ import annotations

import argparse
import glob
import json
import os
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def find_binary(binary_name: str) -> str:
    """Find executable path for ffmpeg or ffprobe, searching PATH, WinGet, and standard directories."""
    # 1. Standard PATH
    found = shutil.which(binary_name)
    if found:
        return found

    # 2. Environment variable override
    env_var = f"{binary_name.upper()}_PATH"
    if os.environ.get(env_var) and os.path.isfile(os.environ[env_var]):
        return os.environ[env_var]

    # 3. Known WinGet / Gyan FFmpeg paths on Windows
    local_app_data = os.environ.get("LOCALAPPDATA", "")
    if local_app_data:
        winget_pattern = os.path.join(
            local_app_data,
            "Microsoft",
            "WinGet",
            "Packages",
            "*FFmpeg*",
            "**",
            f"{binary_name}.exe",
        )
        matches = glob.glob(winget_pattern, recursive=True)
        if matches:
            return matches[0]

    # 4. Standard Windows / Program Files locations
    candidates = [
        f"C:\\ffmpeg\\bin\\{binary_name}.exe",
        f"C:\\ProgramData\\chocolatey\\bin\\{binary_name}.exe",
        f"C:\\Program Files\\FFmpeg\\bin\\{binary_name}.exe",
    ]
    for candidate in candidates:
        if os.path.isfile(candidate):
            return candidate

    raise FileNotFoundError(
        f"Could not locate '{binary_name}'. Please ensure FFmpeg is installed "
        f"and in your PATH, or set {binary_name.upper()}_PATH in your environment."
    )


def find_font_file() -> Optional[str]:
    """Find a readable Arial/Sans TrueType font for drawtext overlays."""
    candidates = [
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/arial.ttf",
        "C:/Windows/Fonts/segoeui.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        "/System/Library/Fonts/Helvetica.ttc",
    ]
    for c in candidates:
        if os.path.isfile(c):
            return c
    return None


def probe_media(probe_bin: str, file_path: Path) -> Dict:
    """Extract format and stream metadata using ffprobe."""
    cmd = [
        probe_bin,
        "-v", "error",
        "-print_format", "json",
        "-show_format",
        "-show_streams",
        str(file_path),
    ]
    result = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, check=True)
    return json.loads(result.stdout)


def escape_ffmpeg_filter_path(path: str) -> str:
    """Escape colons and backslashes for FFmpeg filter arguments on Windows."""
    clean = path.replace("\\", "/")
    clean = clean.replace(":", "\\:")
    clean = clean.replace("'", "\\'")
    return clean


def escape_drawtext_text(text: str) -> str:
    """Escape special characters for drawtext text parameter."""
    clean = text.replace("\\", "\\\\")
    clean = clean.replace(":", "\\:")
    clean = clean.replace("'", "\\'")
    clean = clean.replace("%", "\\%")
    return clean


def run_ffmpeg(cmd: List[str]) -> None:
    """Execute FFmpeg command and display descriptive error on failure."""
    try:
        subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, check=True)
    except subprocess.CalledProcessError as e:
        err_msg = e.stderr.decode("utf-8", errors="replace")
        print(f"\n[FFmpeg Execution Error]\nCommand: {' '.join(cmd)}\n{err_msg}", file=sys.stderr)
        raise


def normalize_scene(
    ffmpeg_bin: str,
    probe_bin: str,
    input_path: Path,
    output_path: Path,
    add_speed_badge: bool = False,
    font_file: Optional[str] = None,
) -> None:
    """Normalize input clip to 1080p 30fps yuv420p with stereo 48kHz audio.
    Generates silent audio if input has no audio stream.
    Adds a '2× speed' badge if requested.
    """
    info = probe_media(probe_bin, input_path)
    has_audio = any(s.get("codec_type") == "audio" for s in info.get("streams", []))

    video_filters = [
        "scale=1920:1080:force_original_aspect_ratio=decrease",
        "pad=1920:1080:(ow-iw)/2:(oh-ih)/2:black",
        "fps=30",
        "format=yuv420p",
    ]

    if add_speed_badge:
        # Render a sleek translucent badge in upper-right corner
        badge_text = "2x speed"
        font_arg = f":fontfile='{escape_ffmpeg_filter_path(font_file)}'" if font_file else ""
        drawtext_filter = (
            f"drawtext=text='{badge_text}'{font_arg}"
            f":fontcolor=white:fontsize=32"
            f":box=1:boxcolor=black@0.65:boxborderw=12"
            f":x=w-tw-48:y=48"
        )
        video_filters.append(drawtext_filter)

    vf_arg = ",".join(video_filters)

    cmd = [ffmpeg_bin, "-y"]
    cmd.extend(["-i", str(input_path)])

    if not has_audio:
        # Add silent stereo audio track
        cmd.extend(["-f", "lavfi", "-i", "anullsrc=r=48000:cl=stereo"])
        cmd.extend(["-vf", vf_arg])
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "22"])
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-shortest"])
        cmd.extend(["-map", "0:v:0", "-map", "1:a:0"])
    else:
        cmd.extend(["-vf", vf_arg])
        cmd.extend(["-c:v", "libx264", "-preset", "fast", "-crf", "22"])
        cmd.extend(["-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2"])

    cmd.append(str(output_path))
    run_ffmpeg(cmd)


def concatenate_scenes(
    ffmpeg_bin: str,
    normalized_scenes: List[Path],
    output_path: Path,
) -> None:
    """Concatenate normalized video files using FFmpeg's concat demuxer."""
    with tempfile.NamedTemporaryFile("w", suffix=".txt", delete=False) as f:
        list_file = Path(f.name)
        for scene in normalized_scenes:
            escaped = str(scene.resolve()).replace("\\", "/")
            f.write(f"file '{escaped}'\n")

    try:
        cmd = [
            ffmpeg_bin,
            "-y",
            "-f", "concat",
            "-safe", "0",
            "-i", str(list_file),
            "-c", "copy",
            str(output_path),
        ]
        run_ffmpeg(cmd)
    finally:
        if list_file.exists():
            list_file.unlink()


def burn_subtitles(
    ffmpeg_bin: str,
    input_path: Path,
    subtitles_path: Path,
    output_path: Path,
) -> None:
    """Burn in SRT subtitles using libass with readable styling."""
    escaped_sub = escape_ffmpeg_filter_path(str(subtitles_path.resolve()))
    style = (
        "FontName=Arial,"
        "FontSize=22,"
        "PrimaryColour=&H00FFFFFF,"
        "OutlineColour=&H00000000,"
        "BackColour=&H80000000,"
        "BorderStyle=3,"
        "MarginV=36"
    )
    sub_filter = f"subtitles='{escaped_sub}':force_style='{style}'"

    cmd = [
        ffmpeg_bin,
        "-y",
        "-i", str(input_path),
        "-vf", sub_filter,
        "-c:v", "libx264",
        "-preset", "medium",
        "-crf", "20",
        "-c:a", "copy",
        str(output_path),
    ]
    run_ffmpeg(cmd)


def generate_synthetic_scene(
    ffmpeg_bin: str,
    output_path: Path,
    duration: float,
    color: str,
    title: str,
    font_file: Optional[str] = None,
) -> None:
    """Generate a synthetic test clip with color background, label, and audio tone."""
    font_arg = f":fontfile='{escape_ffmpeg_filter_path(font_file)}'" if font_file else ""
    escaped_title = escape_drawtext_text(title)
    vf = (
        f"drawtext=text='{escaped_title}'{font_arg}"
        f":fontcolor=white:fontsize=48"
        f":x=(w-tw)/2:y=(h-th)/2"
    )

    cmd = [
        ffmpeg_bin,
        "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:s=1920x1080:d={duration}:r=30",
        "-f", "lavfi",
        "-i", f"sine=frequency=440:duration={duration}",
        "-vf", vf,
        "-c:v", "libx264",
        "-preset", "ultrafast",
        "-c:a", "aac",
        "-shortest",
        str(output_path),
    ]
    run_ffmpeg(cmd)


def assemble_video(
    scenes_dir: Path,
    output_path: Path,
    subtitles_path: Optional[Path] = None,
    badge_scenes: Optional[List[str]] = None,
) -> Tuple[bool, float, str]:
    """Execute complete assembly pipeline.
    Returns (success, duration_seconds, message).
    """
    ffmpeg_bin = find_binary("ffmpeg")
    probe_bin = find_binary("ffprobe")
    font_file = find_font_file()

    if badge_scenes is None:
        badge_scenes = ["scene_03", "3"]

    # Locate scene files (deduplicating by scene index, preferring .mp4)
    scene_pattern = re.compile(r"scene_?0*([0-9]+)\.(mp4|webm|mov|mkv)$", re.IGNORECASE)
    scene_map: Dict[int, Path] = {}
    ext_priority = {".mp4": 1, ".mkv": 2, ".mov": 3, ".webm": 4}

    for f in scenes_dir.iterdir():
        if f.is_file():
            m = scene_pattern.search(f.name)
            if m:
                idx = int(m.group(1))
                if idx not in scene_map:
                    scene_map[idx] = f
                else:
                    cur_ext = scene_map[idx].suffix.lower()
                    new_ext = f.suffix.lower()
                    if ext_priority.get(new_ext, 99) < ext_priority.get(cur_ext, 99):
                        scene_map[idx] = f

    scene_files = sorted(scene_map.items(), key=lambda x: x[0])

    if not scene_files:
        return False, 0.0, f"No scene files (e.g. scene_01.mp4 ... scene_08.mp4) found in {scenes_dir}"

    scene_files.sort(key=lambda x: x[0])
    print(f"Found {len(scene_files)} scenes to assemble: {[f.name for _, f in scene_files]}")

    with tempfile.TemporaryDirectory(prefix="returnlens_assemble_") as tmp_dir:
        tmp_path = Path(tmp_dir)
        normalized_files: List[Path] = []

        print("\n--- Phase 1: Normalizing scenes (1080p, 30fps, stereo audio, badges) ---")
        for idx, src_file in scene_files:
            norm_file = tmp_path / f"norm_scene_{idx:02d}.mp4"
            add_badge = str(idx) in badge_scenes or f"scene_{idx:02d}" in badge_scenes or f"scene_{idx}" in badge_scenes
            badge_str = " [+ '2x speed' badge]" if add_badge else ""
            print(f"  * Scene {idx:02d}: {src_file.name}{badge_str} -> {norm_file.name}")
            normalize_scene(
                ffmpeg_bin=ffmpeg_bin,
                probe_bin=probe_bin,
                input_path=src_file,
                output_path=norm_file,
                add_speed_badge=add_badge,
                font_file=font_file,
            )
            normalized_files.append(norm_file)

        print("\n--- Phase 2: Concatenating scenes ---")
        concat_file = tmp_path / "concatenated.mp4"
        concatenate_scenes(ffmpeg_bin, normalized_files, concat_file)
        print(f"  * Concatenated output saved to {concat_file.name}")

        output_path.parent.mkdir(parents=True, exist_ok=True)

        if subtitles_path and subtitles_path.exists():
            print("\n--- Phase 3: Burning subtitles ---")
            print(f"  * Subtitles file: {subtitles_path}")
            burn_subtitles(
                ffmpeg_bin=ffmpeg_bin,
                input_path=concat_file,
                subtitles_path=subtitles_path,
                output_path=output_path,
            )
            print(f"  * Subtitled output saved to {output_path}")
        else:
            print("\n--- Phase 3: Skipping subtitles (no subtitles file provided or found) ---")
            shutil.copy2(concat_file, output_path)

        print("\n--- Phase 4: Validating output video ---")
        meta = probe_media(probe_bin, output_path)
        format_info = meta.get("format", {})
        duration = float(format_info.get("duration", 0.0))
        size_bytes = int(format_info.get("size", 0))

        v_stream = next((s for s in meta.get("streams", []) if s.get("codec_type") == "video"), None)
        a_stream = next((s for s in meta.get("streams", []) if s.get("codec_type") == "audio"), None)

        if not v_stream:
            return False, duration, "Output file has no video stream!"
        if not a_stream:
            return False, duration, "Output file has no audio stream!"

        w = v_stream.get("width")
        h = v_stream.get("height")
        if (w, h) != (1920, 1080):
            return False, duration, f"Invalid resolution {w}x{h}, expected 1920x1080."

        print(f"  * Output Resolution: {w}x{h}")
        print(f"  * Total Duration: {duration:.2f} seconds ({duration/60:.2f} minutes)")
        print(f"  * File Size: {size_bytes / (1024*1024):.2f} MB")

        # Hard ceiling check: <= 180 seconds (allow 0.5s float slack)
        if duration > 180.5:
            msg = f"Duration {duration:.2f}s exceeds the 3:00 (180s) competition limit!"
            return False, duration, msg

        return True, duration, "Assembly succeeded and passed all validation checks."


def run_pipeline_test(output_path: Path, subtitles_path: Optional[Path] = None) -> bool:
    """Generate 8 synthetic scenes and run the full assembly pipeline in test mode."""
    print("=================================================================")
    print("ReturnLens Video Assembly Test Mode (Synthetic End-to-End Test)")
    print("=================================================================")

    ffmpeg_bin = find_binary("ffmpeg")
    font_file = find_font_file()

    test_scenes_def = [
        ("scene_01.mp4", 3.0, "darkblue", "Scene 01: Cold Open (Earned Autonomy)"),
        ("scene_02.mp4", 2.0, "darkgreen", "Scene 02: Seller Inbox Overview"),
        ("scene_03.mp4", 3.0, "purple", "Scene 03: WISMO and NDR (2x Speed)"),
        ("scene_04.mp4", 4.0, "teal", "Scene 04: Voice Note and Video Case B"),
        ("scene_05.mp4", 2.5, "navy", "Scene 05: Returning Customer Memory"),
        ("scene_06.mp4", 3.0, "maroon", "Scene 06: pass^k Gate and Kill Switch"),
        ("scene_07.mp4", 2.5, "darkslategray", "Scene 07: Architecture and Safety"),
        ("scene_08.mp4", 2.0, "black", "Scene 08: Outro and Repo Link"),
    ]

    with tempfile.TemporaryDirectory(prefix="returnlens_test_scenes_") as tmp_dir:
        tmp_scenes_path = Path(tmp_dir)
        print(f"Generating 8 synthetic test scenes in {tmp_scenes_path}...")
        for name, dur, col, title in test_scenes_def:
            p = tmp_scenes_path / name
            generate_synthetic_scene(ffmpeg_bin, p, dur, col, title, font_file)

        ok, dur, msg = assemble_video(
            scenes_dir=tmp_scenes_path,
            output_path=output_path,
            subtitles_path=subtitles_path,
            badge_scenes=["scene_03", "3"],
        )

        if ok:
            print("\n" + "=" * 65)
            print(f"[TEST PASSED] Output video generated: {output_path}")
            print(f"Total Duration: {dur:.2f}s (<= 180s)")
            print(f"Status Message: {msg}")
            print("=" * 65)
            return True
        else:
            print("\n" + "=" * 65)
            print(f"[TEST FAILED] {msg}")
            print("=" * 65)
            return False


def main() -> None:
    parser = argparse.ArgumentParser(
        description="ReturnLens Demo Video Assembly Pipeline (1080p 30fps concat & subtitle burner)"
    )
    parser.add_argument(
        "--scenes-dir",
        type=Path,
        default=Path(__file__).parent / "scenes",
        help="Directory containing scene_01.mp4 ... scene_08.mp4",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "returnlens_demo_3min.mp4",
        help="Path for output assembled MP4 file",
    )
    parser.add_argument(
        "--subtitles",
        type=Path,
        default=Path(__file__).parent / "narration.srt",
        help="Path to SRT subtitles file (burned into output)",
    )
    parser.add_argument(
        "--badge-scenes",
        type=str,
        default="scene_03,3",
        help="Comma-separated scene identifiers to receive '2x speed' badge",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run end-to-end pipeline test with synthetic test clips",
    )

    args = parser.parse_args()

    badge_list = [b.strip() for b in args.badge_scenes.split(",") if b.strip()]

    if args.test:
        test_out = args.output
        if test_out == Path(__file__).parent / "returnlens_demo_3min.mp4":
            test_out = Path(__file__).parent / "test_assembled_output.mp4"
        success = run_pipeline_test(
            output_path=test_out,
            subtitles_path=args.subtitles if args.subtitles.exists() else None,
        )
        sys.exit(0 if success else 1)

    subtitles = args.subtitles if args.subtitles and args.subtitles.exists() else None
    success, duration, message = assemble_video(
        scenes_dir=args.scenes_dir,
        output_path=args.output,
        subtitles_path=subtitles,
        badge_scenes=badge_list,
    )

    if not success:
        print(f"\nAssembly failed: {message}", file=sys.stderr)
        sys.exit(1)

    print(f"\nAssembly complete! Video created at: {args.output}")


if __name__ == "__main__":
    main()
