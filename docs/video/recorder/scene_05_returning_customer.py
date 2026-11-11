"""Scene 05: Returning Customer & Memory (1:50 - 2:10)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6:
1. CUS-04 (Vikram Malhotra) submits claim with dim clip (stock_dim_unboxing_pexels_40423563.mp4).
2. Agent requests clear close-up photo.
3. Customer leaves (closes tab / navigates away).
4. Customer returns: session, case history, and context are instantly restored.
5. In Seller Console, Plan Card highlights the 'Memory used' chip (never asks twice).
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
            slow_mo=200,
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.on("dialog", lambda d: d.dismiss())

        # 1. Customer submits first turn
        print("[05] Opening Customer Portal...")
        page.goto(f"{BASE_URL}/?tab=customer")
        page.wait_for_selector(".customer-layout", timeout=10000)
        page.wait_for_timeout(2000)

        # Select Vikram Malhotra (CUS-04)
        print("[05] Selecting CUS-04 (Vikram Malhotra)...")
        cust_select = page.locator("select.select-field").first
        cust_select.select_option("CUS-04")
        page.wait_for_timeout(1500)

        # Attach dim stock video
        print("[05] Attaching dim unboxing video...")
        file_input = page.locator("input[type='file']")
        file_input.set_input_files(str(STOCK_DIM_VIDEO))
        page.wait_for_timeout(1000)

        text_input = page.locator("input.text-input")
        text_input.fill("I want a full refund for this defective item.")
        page.wait_for_timeout(1000)

        send_btn = page.locator("button.btn-primary:has-text('Send')")
        send_btn.click()
        print("[05] Submitted first claim with dim clip. Waiting for agent clarification reply...")
        page.wait_for_timeout(4500)

        # 2. Customer leaves (navigates away / simulates closing tab)
        print("[05] Customer closes tab / leaves portal...")
        page.goto("about:blank")
        page.wait_for_timeout(2000)

        # 3. Customer returns later
        print("[05] Customer returns to ReturnLens Portal...")
        page.goto(f"{BASE_URL}/?tab=customer")
        page.wait_for_selector(".customer-layout", timeout=10000)
        page.wait_for_timeout(1500)

        # Select CUS-04 again
        cust_select = page.locator("select.select-field").first
        cust_select.select_option("CUS-04")
        page.wait_for_timeout(2500)  # Pause to show restored history and state!

        # 4. View Seller Console to show Plan Card Memory chip
        print("[05] Switching to Seller Console to show Memory chip...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        seller_tab.click()
        page.wait_for_timeout(2500)

        # Click on ORD-5150 case
        inbox_items = page.locator(".inbox-item").all()
        for it in inbox_items:
            if "ORD-5150" in it.inner_text():
                it.click()
                break
        page.wait_for_timeout(2500)

        # Highlight Plan Card with Memory
        plan_card = page.locator(".plan-card, .seller-col:has-text('Plan')")
        if plan_card.count() > 0:
            plan_card.first.hover()
            page.wait_for_timeout(3000)

        page.wait_for_timeout(1500)

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
