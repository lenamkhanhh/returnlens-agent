"""Common utilities for ReturnLens video recorders.
Role E: automated scene recording for the demo video.
"""

from __future__ import annotations

import os
import subprocess
import time
import urllib.request
import json
from pathlib import Path
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page

BASE_URL = "http://localhost:8000"
REPO_ROOT = Path(__file__).resolve().parents[3]
SCENES_DIR = REPO_ROOT / "docs" / "video" / "scenes"
RECORDER_DIR = REPO_ROOT / "docs" / "video" / "recorder"

FFMPEG_PATH = Path(
    r"C:\Users\HP\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-9.0.2-full_build\bin\ffmpeg.exe"
)

def reset_demo_database() -> dict:
    """Reset the demo database to the cold-open snapshot."""
    url = f"{BASE_URL}/api/operator/reset"
    req = urllib.request.Request(
        url,
        data=b"{}",
        headers={"Content-Type": "application/json"},
        method="POST"
    )
    try:
        with urllib.request.urlopen(req) as resp:
            data = json.loads(resp.read().decode())
            print(f"[RESET] Demo reset: {data}")
            return data
    except Exception as e:
        print(f"[RESET ERROR] Failed to reset demo: {e}")
        raise

def convert_webm_to_mp4(webm_path: Path, mp4_path: Path) -> bool:
    """Convert a recorded webm file to mp4 using Gyan.FFmpeg."""
    if not webm_path.exists():
        print(f"[FFMPEG] Source {webm_path} does not exist.")
        return False
    if not FFMPEG_PATH.exists():
        print(f"[FFMPEG] ffmpeg binary not found at {FFMPEG_PATH}")
        return False

    cmd = [
        str(FFMPEG_PATH),
        "-y",
        "-i", str(webm_path),
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        "-preset", "fast",
        "-crf", "22",
        str(mp4_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    if res.returncode == 0:
        print(f"[FFMPEG] Converted to {mp4_path}")
        return True
    else:
        print(f"[FFMPEG ERROR] return code {res.returncode}: {res.stderr.decode()[:200]}")
        return False

def get_video_duration(video_path: Path) -> float:
    """Get duration of video in seconds using ffprobe or ffmpeg."""
    if not FFMPEG_PATH.exists():
        return 0.0
    ffprobe_path = FFMPEG_PATH.parent / "ffprobe.exe"
    if not ffprobe_path.exists():
        return 0.0
    cmd = [
        str(ffprobe_path),
        "-v", "error",
        "-show_entries", "format=duration",
        "-of", "default=noprint_wrappers=1:nokey=1",
        str(video_path)
    ]
    res = subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    try:
        return float(res.stdout.decode().strip())
    except Exception:
        return 0.0
