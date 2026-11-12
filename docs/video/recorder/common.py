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
from typing import Any, Union
from playwright.sync_api import sync_playwright, Browser, BrowserContext, Page, Locator

BASE_URL = "http://localhost:8000"
REPO_ROOT = Path(__file__).resolve().parents[3]
SCENES_DIR = REPO_ROOT / "docs" / "video" / "scenes"
RECORDER_DIR = REPO_ROOT / "docs" / "video" / "recorder"
INK_DIR = REPO_ROOT / "docs" / "video" / "ink"
OVERLAY_JS_PATH = INK_DIR / "overlay.js"

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


# ---------------------------------------------------------------------------
# Wave 14: Cursor & Ink Overlay Helpers (Role E / INK Chat)
# ---------------------------------------------------------------------------

_OVERLAY_SCRIPT_CACHE: str | None = None

def get_overlay_script() -> str:
    """Get the contents of docs/video/ink/overlay.js."""
    global _OVERLAY_SCRIPT_CACHE
    if _OVERLAY_SCRIPT_CACHE is None:
        if not OVERLAY_JS_PATH.exists():
            from docs.video.ink.build_overlay import build_overlay_js
            build_overlay_js()
        _OVERLAY_SCRIPT_CACHE = OVERLAY_JS_PATH.read_text(encoding="utf-8")
    return _OVERLAY_SCRIPT_CACHE

def setup_page_cursor_and_ink(page: Page) -> None:
    """Install cursor & ink overlay on the page both as an init script and evaluated now."""
    script_content = get_overlay_script()
    page.add_init_script(script_content)
    try:
        page.evaluate(script_content)
    except Exception:
        pass

def smooth_move(page: Page, target: Union[str, Locator, dict], steps: int = 25) -> tuple[float, float]:
    """Smoothly move the mouse to a target selector, Locator, or coord dict using `steps=25`."""
    if isinstance(target, dict):
        tx = float(target.get("x", 0))
        ty = float(target.get("y", 0))
    elif isinstance(target, Locator):
        box = target.bounding_box()
        if not box:
            return (0.0, 0.0)
        tx = box["x"] + box["width"] / 2.0
        ty = box["y"] + box["height"] / 2.0
    else:
        # String selector
        loc = page.locator(target).first
        box = loc.bounding_box()
        if not box:
            return (0.0, 0.0)
        tx = box["x"] + box["width"] / 2.0
        ty = box["y"] + box["height"] / 2.0

    page.mouse.move(tx, ty, steps=steps)
    return (tx, ty)

def smooth_click(
    page: Page,
    target: Union[str, Locator],
    steps: int = 25,
    delay_after: float = 0.5,
) -> None:
    """Smoothly move mouse to target with steps=25, fire click with visual ripple, then wait."""
    if isinstance(target, Locator):
        loc = target
    else:
        loc = page.locator(target).first

    try:
        loc.scroll_into_view_if_needed(timeout=2000)
    except Exception:
        pass
    box = loc.bounding_box()
    if box:
        tx = box["x"] + box["width"] / 2.0
        ty = box["y"] + box["height"] / 2.0
        page.mouse.move(tx, ty, steps=steps)
        time.sleep(0.08)
        page.mouse.click(tx, ty)
    else:
        loc.click()

    if delay_after > 0:
        time.sleep(delay_after)

def _tight_box(target: Locator):
    """Bounding box of the innermost visible match.

    Selectors like "div:has-text('X')" match every ancestor div; `.first` is then the
    outermost one (often the whole page). Ink must hug the smallest element instead.
    """
    try:
        sel = target._impl_obj._selector
        base = sel.replace(" >> nth=0", "")
        if base != sel:
            rects = target.page.locator(base).evaluate_all(
                """els => els.map(e => { const r = e.getBoundingClientRect();
                    return {x: r.left, y: r.top, width: r.width, height: r.height}; })
                    .filter(r => r.width > 8 && r.height > 8 && r.y < window.innerHeight && r.y + r.height > 0)"""
            )
            if rects:
                return min(rects, key=lambda r: r["width"] * r["height"])
    except Exception:
        pass
    return target.bounding_box()


def ink_circle(
    page: Page,
    target: Union[str, Locator, dict],
    text: str | None = None,
    side: str = "auto",
    duration: float = 3.0,
    color: str = "#e11d48",
) -> None:
    """Draw a hand-drawn wobbly ink circle around target with optional Patrick Hand note."""
    if isinstance(target, Locator):
        box = _tight_box(target)
        js_target = box if box else None
    elif isinstance(target, dict):
        js_target = target
    else:
        # Check if target is a simple CSS selector or contains Playwright extensions
        # If locator finds a bounding box, pass box directly for 100% precision
        try:
            loc = page.locator(target).first
            box = loc.bounding_box()
            js_target = box if box else target
        except Exception:
            js_target = target

    if not js_target:
        return

    page.evaluate(
        """([target, text, options]) => {
            if (window.ReturnLensInk) {
                window.ReturnLensInk.circle(target, text, options);
            }
        }""",
        [
            js_target,
            text,
            {
                "side": side,
                "duration": int(max(duration, 5.0) * 1000),
                "color": color,
            },
        ],
    )

def ink_arrow(
    page: Page,
    target: Union[str, Locator, dict],
    text: str,
    from_side: str = "auto",
    duration: float = 3.0,
    color: str = "#e11d48",
) -> None:
    """Draw a hand-drawn curving arrow from Patrick Hand note to target element."""
    if isinstance(target, Locator):
        box = _tight_box(target)
        js_target = box if box else None
    elif isinstance(target, dict):
        js_target = target
    else:
        try:
            loc = page.locator(target).first
            box = loc.bounding_box()
            js_target = box if box else target
        except Exception:
            js_target = target

    if not js_target:
        return

    page.evaluate(
        """([target, text, options]) => {
            if (window.ReturnLensInk) {
                window.ReturnLensInk.arrow(target, text, options);
            }
        }""",
        [
            js_target,
            text,
            {
                "fromSide": from_side,
                "duration": int(max(duration, 5.0) * 1000),
                "color": color,
            },
        ],
    )

def ink_clear(page: Page) -> None:
    """Clear all active ink annotations."""
    try:
        page.evaluate("() => { if (window.ReturnLensInk) window.ReturnLensInk.clear(); }")
    except Exception:
        pass
