"""Scene 07: Try to Break It - Judge Sandbox (2:35 - 2:55)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6 & WAVE16_FINAL_VIDEO.md:
Demonstrates the 3 judge attack presets:
1. Preset 1: Visual Prompt Injection (CLIP-INJ) -> BLOCKED / SANITIZED
2. Preset 2: ₹1,800 Over-Refund (P_BALANCE violation) -> BLOCKED
3. Preset 3: Cumulative Split Refund (P_CUMULATIVE violation) -> BLOCKED
- Hand-drawn ink annotations and visible cursor with click ripples.
"""

from __future__ import annotations

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

from docs.video.recorder.common import (
    BASE_URL,
    SCENES_DIR,
    convert_webm_to_mp4,
    get_video_duration,
    setup_page_cursor_and_ink,
    smooth_move,
    smooth_click,
    ink_circle,
    ink_arrow,
    ink_clear,
)

def record_scene_07() -> Path:
    print("\n=== RECORDING SCENE 07: TRY TO BREAK IT ===")

    temp_dir = SCENES_DIR / "temp_07"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            slow_mo=50,
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.on("dialog", lambda d: d.dismiss())

        # 1. Open Seller Console
        print("[07] Navigating to ReturnLens Console (demo scale)...")
        page.goto(f"{BASE_URL}/?tab=seller&demo=1")
        setup_page_cursor_and_ink(page)
        page.wait_for_selector(".app-header", timeout=10000)
        time.sleep(0.8)

        # 2. Click "⚡ Try to Break It" button in Header
        print("[07] Clicking 'Try to Break It' button in Header...")
        break_it_btn = page.locator("button:has-text('Try to Break It')")
        smooth_click(page, break_it_btn.first, steps=15, delay_after=0.8)
        page.wait_for_selector(".modal-card", timeout=5000)
        setup_page_cursor_and_ink(page)

        # 3. Preset 1: Prompt Injection
        print("[07] Running Preset 1: Prompt Injection...")
        preset1 = page.locator("button:has-text('1. Prompt injection')")
        smooth_click(page, preset1.first, steps=15, delay_after=0.8)
        ink_circle(page, ".modal-card", text="Blocked: prompt injection neutralized", side="bottom", duration=2.0)
        time.sleep(1.2)
        ink_clear(page)

        # 4. Preset 2: ₹1,800 Over-Refund
        print("[07] Running Preset 2: Over-refund...")
        preset2 = page.locator("button:has-text('2. Over-refund')")
        smooth_click(page, preset2.first, steps=15, delay_after=0.8)
        ink_circle(page, ".modal-card", text="Blocked: exceeds balance", side="bottom", duration=2.0)
        time.sleep(1.2)
        ink_clear(page)

        # 5. Preset 3: Cumulative Split Refund
        print("[07] Running Preset 3: Cumulative split...")
        preset3 = page.locator("button:has-text('3. Cumulative split')")
        smooth_click(page, preset3.first, steps=15, delay_after=0.8)
        ink_circle(page, ".modal-card", text="Blocked: cumulative limit", side="bottom", duration=2.0)
        time.sleep(1.2)
        ink_clear(page)

        # 6. Close Modal
        print("[07] Closing Break It modal...")
        done_btn = page.locator(".modal-footer button:has-text('Done')")
        if done_btn.count() > 0:
            smooth_click(page, done_btn.first, steps=12, delay_after=0.6)
        else:
            close_btn = page.locator(".modal-header button:has-text('✕')")
            if close_btn.count() > 0:
                smooth_click(page, close_btn.first, steps=12, delay_after=0.6)

        time.sleep(0.5)

        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = Path(video_obj.path())
        final_webm = SCENES_DIR / "scene_07.webm"
        final_mp4 = SCENES_DIR / "scene_07.mp4"

        if final_webm.exists():
            final_webm.unlink()
        raw_video_path.rename(final_webm)

        try:
            temp_dir.rmdir()
        except Exception:
            pass

        convert_webm_to_mp4(final_webm, final_mp4)
        duration = get_video_duration(final_mp4)
        print(f"[07 DONE] scene_07 saved: {final_webm.name} & {final_mp4.name} ({duration:.1f}s)")
        return final_webm

if __name__ == "__main__":
    record_scene_07()
