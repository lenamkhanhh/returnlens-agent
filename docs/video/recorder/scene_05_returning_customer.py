"""Scene 05: Returning Customer & Memory (1:50 - 2:10)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6 & WAVE16_FINAL_VIDEO.md:
1. CUS-04 (Vikram Malhotra) submits claim with dim clip.
2. Agent requests clear close-up photo.
3. Customer leaves (navigates away).
4. Customer returns: session, case history, and context are instantly restored.
5. In Seller Console, Plan Card highlights the 'Customer memory used' chip (never asks twice).
- Visible cursor with ripples and hand-drawn ink annotations.
"""

from __future__ import annotations

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

from docs.video.recorder.common import (
    BASE_URL,
    REPO_ROOT,
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

STOCK_DIM_VIDEO = REPO_ROOT / "app" / "demo" / "media" / "stock" / "stock_dim_unboxing_pexels_40423563.mp4"

def record_scene_05() -> Path:
    print("\n=== RECORDING SCENE 05: RETURNING CUSTOMER (MEMORY) ===")
    reset_demo_database()

    temp_dir = SCENES_DIR / "temp_05"
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

        # 1. Customer submits first turn
        print("[05] Opening Customer Portal (demo scale)...")
        page.goto(f"{BASE_URL}/?tab=customer&demo=1")
        setup_page_cursor_and_ink(page)
        page.wait_for_selector(".customer-layout", timeout=10000)
        time.sleep(1.0)

        # Select Vikram Malhotra (CUS-04)
        print("[05] Selecting CUS-04 (Vikram Malhotra)...")
        cust_select = page.locator("select.demo-select").first
        cust_select.select_option("CUS-04")
        time.sleep(0.8)

        # Attach dim stock video
        print("[05] Attaching dim unboxing video...")
        file_input = page.locator("input[type='file']")
        file_input.set_input_files(str(STOCK_DIM_VIDEO))
        time.sleep(0.8)

        text_input = page.locator("input.messaging-input-field")
        smooth_click(page, text_input, steps=15, delay_after=0.3)
        text_input.fill("The item has a scratch and does not turn on.")
        time.sleep(0.6)

        send_btn = page.locator("button.messaging-send-btn")
        smooth_click(page, send_btn, steps=15, delay_after=2.5)

        ink_circle(page, ".messaging-phone-frame", text="Agent requests clear closeup", side="top", duration=2.5)
        time.sleep(1.8)
        ink_clear(page)

        # 2. Customer leaves (navigates away / simulates closing tab)
        print("[05] Customer leaves portal...")
        page.goto("about:blank")
        time.sleep(1.2)

        # 3. Customer returns later
        print("[05] Customer returns to ReturnLens Portal...")
        page.goto(f"{BASE_URL}/?tab=customer&demo=1")
        setup_page_cursor_and_ink(page)
        page.wait_for_selector(".customer-layout", timeout=10000)
        time.sleep(1.0)

        # Select CUS-04 again
        cust_select = page.locator("select.demo-select").first
        cust_select.select_option("CUS-04")
        time.sleep(1.5)  # Show restored history and state

        ink_circle(page, ".messaging-phone-frame", text="Session restored", side="top", duration=2.5)
        time.sleep(2.0)
        ink_clear(page)

        # 4. View Seller Console to show Plan Card Memory chip
        print("[05] Switching to Seller Console to show Memory chip...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        smooth_click(page, seller_tab, steps=20, delay_after=1.2)
        setup_page_cursor_and_ink(page)

        # Click on ORD-5150 case
        ord_item = page.locator(".inbox-item:has-text('ORD-5150')")
        if ord_item.count() > 0:
            smooth_click(page, ord_item.first, steps=20, delay_after=1.2)

        # Highlight Plan Card with Memory
        plan_card = page.locator(".plan-card")
        if plan_card.count() > 0:
            smooth_move(page, plan_card.first, steps=20)
            ink_arrow(page, plan_card.first, text="Remembers language & context - never asks twice", from_side="left", duration=3.5)
            time.sleep(2.5)

        ink_clear(page)
        time.sleep(0.8)

        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = Path(video_obj.path())
        final_webm = SCENES_DIR / "scene_05.webm"
        final_mp4 = SCENES_DIR / "scene_05.mp4"

        if final_webm.exists():
            final_webm.unlink()
        raw_video_path.rename(final_webm)

        try:
            temp_dir.rmdir()
        except Exception:
            pass

        convert_webm_to_mp4(final_webm, final_mp4)
        duration = get_video_duration(final_mp4)
        print(f"[05 DONE] scene_05 saved: {final_webm.name} & {final_mp4.name} ({duration:.1f}s)")
        return final_webm

if __name__ == "__main__":
    record_scene_05()
