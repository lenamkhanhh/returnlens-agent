"""Scene 03: WISMO and NDR Flows (0:40 - 1:05)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6:
1. WISMO: CUS-01 (Priya Sharma) asks "Where is my order?" for ORD-2030.
   Agent calls real mock tracking tools, replies with live Delhivery status and ETA.
2. NDR: Operator fires NDR on ORD-3110 (SHP-3110).
   Agent sends proactive outreach to CUS-05 (Rohit Verma).
   Customer replies with corrected address (Flat 14B).
   Seller reviews PROPOSE_NDR_REATTEMPT in Seller Console and approves.
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

def record_scene_03() -> Path:
    print("\n=== RECORDING SCENE 03: WISMO & NDR ===")
    reset_demo_database()

    temp_dir = SCENES_DIR / "temp_03"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            slow_mo=120,
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.on("dialog", lambda d: d.dismiss())

        # -------------------------------------------------------------
        # Part 1: WISMO (CUS-01, ORD-2030)
        # -------------------------------------------------------------
        print("[03] Navigating to Customer Portal for WISMO (demo scale)...")
        page.goto(f"{BASE_URL}/?tab=customer&demo=1")
        page.wait_for_selector(".customer-layout", timeout=10000)
        page.wait_for_timeout(1500)

        # Select Priya Sharma (CUS-01) if not already selected
        cust_select = page.locator("select.select-field").first
        cust_select.select_option("CUS-01")
        page.wait_for_timeout(800)

        # Type WISMO inquiry
        print("[03] Customer typing: Where is my order?...")
        text_input = page.locator("input.text-input")
        text_input.fill("Where is my order?")
        page.wait_for_timeout(800)

        # Click Send
        send_btn = page.locator("button.btn-primary:has-text('Send')")
        send_btn.click()
        page.wait_for_timeout(2200)  # Wait for mock tools and reply

        # -------------------------------------------------------------
        # Part 2: NDR Trigger in Operator Controls
        # -------------------------------------------------------------
        print("[03] Switching to Operator Controls to fire NDR...")
        op_tab = page.locator("button.tab-btn:has-text('Operator Controls')")
        op_tab.click()
        page.wait_for_timeout(1500)

        # Fill SHP-3110 and fire NDR
        shipment_input = page.locator("input.select-field").first
        shipment_input.fill("SHP-3110")
        page.wait_for_timeout(600)

        event_select = page.locator("select.select-field").first
        event_select.select_option("NDR")
        page.wait_for_timeout(600)

        dispatch_btn = page.locator("button:has-text('Dispatch Courier Webhook')")
        dispatch_btn.click()
        page.wait_for_timeout(2000)

        # -------------------------------------------------------------
        # Part 3: Customer Corrects Address for NDR
        # -------------------------------------------------------------
        print("[03] Switching back to Customer Portal for Rohit Verma (CUS-05)...")
        cust_tab = page.locator("button.tab-btn:has-text('Customer Portal')")
        cust_tab.click()
        page.wait_for_timeout(1500)

        cust_select = page.locator("select.select-field").first
        cust_select.select_option("CUS-05")
        page.wait_for_timeout(2000)

        # Type address correction
        print("[03] Customer replies with corrected address...")
        text_input = page.locator("input.text-input")
        text_input.fill("Flat 12B nahi, 14B hai. Kal shaam 6 baje chalega.")
        page.wait_for_timeout(1000)
        send_btn = page.locator("button.btn-primary:has-text('Send')")
        send_btn.click()
        page.wait_for_timeout(3500)

        # -------------------------------------------------------------
        # Part 4: Seller Approves Reattempt in Seller Console
        # -------------------------------------------------------------
        print("[03] Switching to Seller Console to approve NDR reattempt...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        seller_tab.click()
        page.wait_for_timeout(2000)

        # Find and click ORD-3110 case
        inbox_items = page.locator(".inbox-item").all()
        for it in inbox_items:
            if "ORD-3110" in it.inner_text():
                it.click()
                break
        page.wait_for_timeout(2000)

        # Click Review & Decide on Proposal if available
        review_btn = page.locator("button:has-text('Review & Decide')")
        if review_btn.count() > 0:
            review_btn.first.click()
            page.wait_for_timeout(1500)

            # Click Approve inside Approval Modal
            approve_btn = page.locator(".modal-footer button.btn-primary:has-text('Approve')")
            if approve_btn.count() > 0:
                approve_btn.first.click()
                page.wait_for_timeout(2500)

        # Pause to view resolved reattempt
        page.wait_for_timeout(2000)

        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = Path(video_obj.path())
        final_webm = SCENES_DIR / "scene_03.webm"
        final_mp4 = SCENES_DIR / "scene_03.mp4"

        if final_webm.exists():
            final_webm.unlink()
        raw_video_path.rename(final_webm)

        try:
            temp_dir.rmdir()
        except Exception:
            pass

        convert_webm_to_mp4(final_webm, final_mp4)
        duration = get_video_duration(final_mp4)
        print(f"[03 DONE] scene_03 saved: {final_webm.name} & {final_mp4.name} ({duration:.1f}s)")
        return final_webm

if __name__ == "__main__":
    record_scene_03()
