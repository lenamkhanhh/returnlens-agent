"""Comprehensive test script for Wave 14 Role E (INK chat):
Tests both annotations (circle + arrow) on the real live UI simultaneously,
verifying cursor, click ripple, Patrick Hand font rendering with soft white halo,
and intelligent empty-space placement that never obscures UI text.
Saves test images/video under TEMP directory so git tracking remains clean.
"""

from __future__ import annotations

import os
import subprocess
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

from docs.video.recorder.common import (
    BASE_URL,
    FFMPEG_PATH,
    INK_DIR,
    SCENES_DIR,
    convert_webm_to_mp4,
    get_video_duration,
    ink_arrow,
    ink_circle,
    ink_clear,
    reset_demo_database,
    setup_page_cursor_and_ink,
    smooth_click,
    smooth_move,
)

TEMP_TEST_DIR = Path(os.environ.get("TEMP", "C:/Users/HP/AppData/Local/Temp")) / "returnlens_ink_test"

def run_test() -> tuple[Path, Path]:
    print("\n=== RUNNING FULL INK & CURSOR VERIFICATION (TEMP DIR) ===")
    reset_demo_database()

    TEMP_TEST_DIR.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            slow_mo=100,
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(TEMP_TEST_DIR),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # Install cursor and ink overlay
        setup_page_cursor_and_ink(page)

        # 1. Load Seller Console
        print("[TEST] Loading Seller Console (?demo=1)...")
        page.goto(f"{BASE_URL}/?tab=seller&demo=1")
        page.wait_for_selector(".app-header", timeout=10000)
        time.sleep(1.0)

        # 2. Circle the DAMAGE locked badge
        print("[TEST] Circling DAMAGE locked badge...")
        locked_badge = page.locator("text=L2/L3 locked").first
        smooth_move(page, locked_badge, steps=25)
        ink_circle(page, locked_badge, text="locked until 5/5", side="top", duration=5.0)
        time.sleep(0.8)

        # 3. Arrow pointing to Kill Switch with empty-space auto-positioning
        print("[TEST] Arrow pointing to Kill Switch with empty space placement...")
        kill_switch_btn = page.locator("button:has-text('Kill Switch')").first
        ink_arrow(page, kill_switch_btn, text="one click takes it back", from_side="auto", duration=5.0)
        smooth_move(page, kill_switch_btn, steps=25)
        time.sleep(1.0)

        # Capture combined screenshot of both annotations + cursor into temp dir
        combined_screenshot = TEMP_TEST_DIR / "test_both_annotations.png"
        page.screenshot(path=str(combined_screenshot))
        print(f"[TEST] Combined screenshot saved in temp: {combined_screenshot}")

        # 4. Test click ripple on inbox item
        print("[TEST] Testing smooth click on inbox item...")
        first_item = page.locator(".inbox-item").first
        smooth_click(page, first_item, steps=25, delay_after=1.0)

        # Finish recording
        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = Path(video_obj.path())
        test_webm = TEMP_TEST_DIR / "test_ink_recording.webm"
        test_mp4 = TEMP_TEST_DIR / "test_ink_recording.mp4"

        if test_webm.exists():
            test_webm.unlink()
        raw_video_path.rename(test_webm)

        # Convert to mp4
        convert_webm_to_mp4(test_webm, test_mp4)
        duration = get_video_duration(test_mp4)
        print(f"[TEST DONE] Recorded test video: {test_mp4} ({duration:.1f}s)")

        # Extract frame at 2.5s showing both annotations in video
        extracted_frame = TEMP_TEST_DIR / "test_video_frame.png"
        if FFMPEG_PATH.exists():
            cmd = [
                str(FFMPEG_PATH),
                "-y",
                "-ss", "00:00:02.500",
                "-i", str(test_mp4),
                "-vframes", "1",
                str(extracted_frame),
            ]
            subprocess.run(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
            print(f"[TEST] Extracted video frame in temp: {extracted_frame}")

        return test_mp4, combined_screenshot

if __name__ == "__main__":
    run_test()
