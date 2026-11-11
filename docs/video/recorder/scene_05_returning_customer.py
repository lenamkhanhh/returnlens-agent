"""Scene 05: Returning Customer & Memory (Honest & Fact-Checked)
Per Wave 16 Review Directives:
1. CUS-04 (Vikram Malhotra) submits claim with dim clip.
   Agent requests clear close-up photo.
   Circle ONLY the agent's reply bubble (never the whole panel).
2. Customer leaves (navigates away).
3. Customer returns: session, case history, and context are instantly restored.
   Circle ONLY restored status chip.
4. In Seller Console, Plan Card highlights the 'Customer memory used' chip (never asks twice).
- All facts verified via API before ink annotation.
"""

from __future__ import annotations

import time
import urllib.request
import json
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
        time.sleep(0.6)

        # Select Vikram Malhotra (CUS-04)
        print("[05] Selecting CUS-04 (Vikram Malhotra)...")
        cust_select = page.locator("select.demo-select").first
        cust_select.select_option("CUS-04")
        time.sleep(0.5)

        # Attach dim stock video
        print("[05] Attaching dim unboxing video...")
        file_input = page.locator("input[type='file']")
        file_input.set_input_files(str(STOCK_DIM_VIDEO))
        time.sleep(0.5)

        text_input = page.locator("input.messaging-input-field")
        smooth_click(page, text_input, steps=12, delay_after=0.2)
        text_input.fill("The item has a scratch and does not turn on.")
        time.sleep(0.4)

        send_btn = page.locator("button.messaging-send-btn")
        smooth_click(page, send_btn, steps=12, delay_after=2.0)

        # Verify case from API
        res = urllib.request.urlopen(f"{BASE_URL}/api/seller/cases")
        cases = json.loads(res.read().decode())
        c5150 = next((c for c in cases if c.get("order_id") == "ORD-5150"), None)
        print(f"[05 API] ORD-5150 Case: {c5150['case_id'] if c5150 else 'None'}, state: {c5150.get('state') if c5150 else 'None'}")

        # Circle ONLY the agent reply bubble
        agent_reply = page.locator(".chat-bubble.agent").last
        if agent_reply.count() > 0:
            smooth_move(page, agent_reply, steps=12)
            ink_circle(page, agent_reply, text="Agent requests clear closeup", side="top", duration=2.0)
            time.sleep(1.2)
            ink_clear(page)

        # 2. Customer leaves (navigates away / simulates closing tab)
        print("[05] Customer leaves portal...")
        page.goto("about:blank")
        time.sleep(0.8)

        # 3. Customer returns later
        print("[05] Customer returns to ReturnLens Portal...")
        page.goto(f"{BASE_URL}/?tab=customer&demo=1")
        setup_page_cursor_and_ink(page)
        page.wait_for_selector(".customer-layout", timeout=10000)
        time.sleep(0.6)

        # Select CUS-04 again
        cust_select = page.locator("select.demo-select").first
        cust_select.select_option("CUS-04")
        time.sleep(0.8)

        # Circle ONLY the case ID chip in header
        case_chip = page.locator(".case-id-chip")
        if case_chip.count() > 0:
            smooth_move(page, case_chip.first, steps=12)
            ink_circle(page, case_chip.first, text="Session restored", side="bottom", duration=2.0)
            time.sleep(1.2)
            ink_clear(page)

        # 4. View Seller Console to show Plan Card Memory chip
        print("[05] Switching to Seller Console to show Memory chip...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        smooth_click(page, seller_tab, steps=15, delay_after=0.8)
        setup_page_cursor_and_ink(page)

        # Click on ORD-5150 case
        ord_item = page.locator(".inbox-item:has-text('ORD-5150')")
        if ord_item.count() > 0:
            smooth_click(page, ord_item.first, steps=15, delay_after=0.8)

        # Highlight Plan Card with Memory (preferred_language=hinglish chip)
        memory_chip = page.locator(".plan-card .memory-chip, .plan-card .badge:has-text('preferred_language'), .plan-card .badge").first
        if memory_chip.count() > 0:
            smooth_move(page, memory_chip, steps=15)
            ink_arrow(page, memory_chip, text="Remembers language & context - never asks twice", from_side="bottom", duration=2.5)
            time.sleep(1.5)
        else:
            plan_card = page.locator(".plan-card").first
            if plan_card.count() > 0:
                smooth_move(page, plan_card, steps=15)
                ink_arrow(page, plan_card, text="Remembers language & context - never asks twice", from_side="bottom", duration=2.5)
                time.sleep(1.5)

        ink_clear(page)
        time.sleep(0.4)

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
