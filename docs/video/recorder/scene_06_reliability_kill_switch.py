"""Scene 06: Reliability Benchmark & Kill Switch (2:10 - 2:35)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6 & WAVE16_FINAL_VIDEO.md:
1. Seller Console: Autonomy Bar shows reliability status & locked levels.
   - DAMAGE eligible (5/5), MISMATCH locked (4/5).
2. Operator Controls: System Provenance shows 10-scenario k=5 benchmark (9/10 pass 5/5).
3. Open "Why did it stop?" checklist to explain Step 4: Reliability Gate.
4. Merchant clicks ⚡ Kill switch:
   - Instant transition: all case types revert to L0.
   - Banner turns red: Kill switch active (all L0).
   - Hand-drawn ink arrow: "one click takes it back".
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
    setup_page_cursor_and_ink,
    smooth_move,
    smooth_click,
    ink_circle,
    ink_arrow,
    ink_clear,
)

def record_scene_06() -> Path:
    print("\n=== RECORDING SCENE 06: RELIABILITY & KILL SWITCH ===")
    reset_demo_database()

    temp_dir = SCENES_DIR / "temp_06"
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
        print("[06] Opening Seller Console (demo scale)...")
        page.goto(f"{BASE_URL}/?tab=seller&demo=1")
        setup_page_cursor_and_ink(page)
        page.wait_for_selector(".app-header", timeout=10000)
        time.sleep(1.2)

        # Inspect Autonomy Bar
        autonomy_bar = page.locator("#autonomy-bar")
        smooth_move(page, autonomy_bar.first, steps=20)
        ink_circle(page, autonomy_bar.first, text="Measured on this exact code", side="bottom", duration=3.0)
        time.sleep(2.0)
        ink_clear(page)

        # 2. Open Operator Controls to show System Provenance & Benchmark
        print("[06] Viewing System Provenance in Operator Controls...")
        op_tab = page.locator("button.tab-btn:has-text('Operator Controls')")
        smooth_click(page, op_tab, steps=20, delay_after=1.0)
        setup_page_cursor_and_ink(page)

        provenance_card = page.locator(".seller-col:has-text('System provenance')")
        if provenance_card.count() > 0:
            smooth_move(page, provenance_card.first, steps=20)
            ink_circle(page, provenance_card.first, text="9 of 10 pass 5/5", side="left", duration=3.0)
            time.sleep(2.2)
            ink_clear(page)

        # 3. Return to Seller Console
        print("[06] Returning to Seller Console...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        smooth_click(page, seller_tab, steps=20, delay_after=1.0)
        setup_page_cursor_and_ink(page)

        # Select case ORD-1042 so activeCaseId is set
        ord_item = page.locator(".inbox-item:has-text('ORD-1042')")
        if ord_item.count() > 0:
            smooth_click(page, ord_item.first, steps=18, delay_after=0.8)

        # Open "Why did it stop?" Checklist
        print("[06] Opening Why did it stop? checklist...")
        why_btn = page.locator("button:has-text('Why did it stop?')")
        if why_btn.count() > 0:
            smooth_click(page, why_btn.first, steps=18, delay_after=1.2)
            page.wait_for_selector(".modal-card", timeout=3000)

            # Move cursor to Step 4: Reliability Gate
            step4 = page.locator(".checklist-step:has-text('Reliability Gate'), div:has-text('Step 4')")
            if step4.count() > 0:
                smooth_move(page, step4.first, steps=18)
            time.sleep(2.0)

            close_modal = page.locator(".modal-header button:has-text('✕')")
            if close_modal.count() > 0:
                smooth_click(page, close_modal.first, steps=15, delay_after=0.8)

        # 4. Trigger Kill Switch!
        print("[06] Engaging Kill switch...")
        kill_btn = page.locator("button:has-text('Kill switch')")
        if kill_btn.count() > 0:
            smooth_click(page, kill_btn.first, steps=20, delay_after=1.0)
            print("[06] Kill Switch clicked! Red alert banner active...")

            ink_arrow(page, "#autonomy-bar", text="one click takes it back", from_side="bottom", duration=3.5)
            time.sleep(2.8)

        ink_clear(page)
        time.sleep(0.8)

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
