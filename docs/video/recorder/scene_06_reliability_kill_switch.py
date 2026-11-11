"""Scene 06: Reliability Benchmark & Kill Switch (2:10 - 2:35)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6:
1. Seller Console: Autonomy Bar shows reliability status & locked levels.
2. Operator Controls: System Provenance shows 10-scenario k=5 benchmark.
3. Open "Why?" checklist to explain Step 4: Reliability Gate.
4. Merchant clicks ⚡ Kill Switch:
   - Instant transition: all case types revert to L0.
   - Banner turns red: KILL SWITCH ENGAGED.
   - One click takes all autonomy back.
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
    reset_demo_database,
)

def record_scene_06() -> Path:
    print("\n=== RECORDING SCENE 06: RELIABILITY & KILL SWITCH ===")
    reset_demo_database()

    temp_dir = SCENES_DIR / "temp_06"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            slow_mo=200,
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.on("dialog", lambda d: d.dismiss())

        # 1. Open Seller Console
        print("[06] Opening Seller Console...")
        page.goto(f"{BASE_URL}/?tab=seller")
        page.wait_for_selector(".app-header", timeout=10000)
        page.wait_for_timeout(2000)

        # Inspect Autonomy Bar
        autonomy_bar = page.locator("strong:has-text('Autonomy Bar')")
        autonomy_bar.hover()
        page.wait_for_timeout(2000)

        # 2. Open Operator Controls to show System Provenance & Benchmark
        print("[06] Viewing System Provenance in Operator Controls...")
        op_tab = page.locator("button.tab-btn:has-text('Operator Controls')")
        op_tab.click()
        page.wait_for_timeout(1500)

        provenance_card = page.locator(".seller-col:has-text('System Provenance')")
        if provenance_card.count() > 0:
            provenance_card.first.hover()
            page.wait_for_timeout(3000)

        # 3. Return to Seller Console
        print("[06] Returning to Seller Console...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        seller_tab.click()
        page.wait_for_timeout(2000)

        # Open "Why?" Checklist
        print("[06] Opening Why? checklist to show Step 4: Reliability Gate...")
        why_btn = page.locator("button:has-text('Why?')")
        if why_btn.count() > 0:
            why_btn.first.click()
            page.wait_for_timeout(4000)  # Pause to inspect Step 4 Reliability Gate

            close_modal = page.locator(".modal-header button:has-text('✕')")
            if close_modal.count() > 0:
                close_modal.first.click()
                page.wait_for_timeout(1000)

        # 4. Trigger Kill Switch!
        print("[06] Engaging Kill Switch...")
        kill_btn = page.locator("button:has-text('Kill Switch')")
        if kill_btn.count() > 0:
            kill_btn.first.hover()
            page.wait_for_timeout(1000)
            kill_btn.first.click()
            print("[06] Kill Switch clicked! Inspecting red alert state...")
            page.wait_for_timeout(4000)  # Let viewer observe full red warning and all L0

        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = Path(video_obj.path())
        final_webm = SCENES_DIR / "scene_06.webm"
        final_mp4 = SCENES_DIR / "scene_06.mp4"

        if final_webm.exists():
            final_webm.unlink()
        raw_video_path.rename(final_webm)

        try:
            temp_dir.rmdir()
        except Exception:
            pass

        convert_webm_to_mp4(final_webm, final_mp4)
        duration = get_video_duration(final_mp4)
        print(f"[06 DONE] scene_06 saved: {final_webm.name} & {final_mp4.name} ({duration:.1f}s)")
        return final_webm

if __name__ == "__main__":
    record_scene_06()
