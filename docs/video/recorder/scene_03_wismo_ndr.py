"""Scene 03: WISMO and NDR Flows (0:40 - 1:05)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6:
1. WISMO: CUS-01 (Priya Sharma) asks "Where is my order?" for ORD-2030.
   Agent calls real mock tracking tools, replies with live Delhivery status and ETA.
2. NDR: Operator fires NDR on ORD-3110 (SHP-3110).
   Agent sends proactive outreach to CUS-05 (Rohit Verma).
3. Customer replies with corrected address (Flat 14B) in Hinglish.
4. Seller reviews PROPOSE_NDR_REATTEMPT in Seller Console and approves with one click.
- Features visible cursor with ripples and hand-drawn ink annotations.
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

def record_scene_03() -> Path:
    print("\n=== RECORDING SCENE 03: WISMO & NDR ===")
    reset_demo_database()

    temp_dir = SCENES_DIR / "temp_03"
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

        # -------------------------------------------------------------
        # Part 1: WISMO (CUS-01, ORD-2030)
        # -------------------------------------------------------------
        print("[03] Navigating to Customer Portal for WISMO...")
        page.goto(f"{BASE_URL}/?tab=customer&demo=1")
        setup_page_cursor_and_ink(page)
        page.wait_for_selector(".customer-layout", timeout=10000)
        time.sleep(1.0)

        # Select Priya Sharma (CUS-01) if not default
        cust_select = page.locator("select.demo-select").first
        if cust_select.count() > 0:
            cust_select.select_option("CUS-01")
            time.sleep(0.5)

        # Type WISMO inquiry with smooth move & click
        print("[03] Customer typing: Where is my order?...")
        text_input = page.locator("input.messaging-input-field")
        smooth_click(page, text_input, steps=15, delay_after=0.3)
        text_input.fill("Where is my order?")
        time.sleep(0.6)

        send_btn = page.locator("button.messaging-send-btn")
        smooth_click(page, send_btn, steps=15, delay_after=2.0)

        # Annotate live tracking response
        ink_circle(page, ".messaging-phone-frame", text="Live Delhivery tracking & ETA", side="top", duration=3.0)
        time.sleep(1.8)
        ink_clear(page)

        # -------------------------------------------------------------
        # Part 2: NDR Trigger in Operator Controls
        # -------------------------------------------------------------
        print("[03] Switching to Operator Controls to fire NDR...")
        op_tab = page.locator("button.tab-btn:has-text('Operator Controls')")
        smooth_click(page, op_tab, steps=20, delay_after=1.0)
        setup_page_cursor_and_ink(page)

        # Form has default SHP-3110 and NDR
        dispatch_btn = page.locator("button:has-text('Dispatch Courier Webhook')")
        smooth_click(page, dispatch_btn, steps=20, delay_after=0.8)
        ink_arrow(page, dispatch_btn, text="NDR delivery failure", from_side="top", duration=2.5)
        time.sleep(1.8)
        ink_clear(page)

        # -------------------------------------------------------------
        # Part 3: Customer Corrects Address for NDR
        # -------------------------------------------------------------
        print("[03] Switching back to Customer Portal for CUS-05...")
        cust_tab = page.locator("button.tab-btn:has-text('Customer Portal')")
        smooth_click(page, cust_tab, steps=20, delay_after=1.0)
        setup_page_cursor_and_ink(page)

        cust_select = page.locator("select.demo-select").first
        cust_select.select_option("CUS-05")
        time.sleep(1.2)

        # Type address correction in Hinglish
        print("[03] Customer replies with corrected address...")
        text_input = page.locator("input.messaging-input-field")
        smooth_click(page, text_input, steps=15, delay_after=0.3)
        text_input.fill("Flat 12B nahi, 14B hai. Kal shaam 6 baje chalega.")
        time.sleep(0.6)

        send_btn = page.locator("button.messaging-send-btn")
        smooth_click(page, send_btn, steps=15, delay_after=2.8)

        ink_circle(page, ".messaging-phone-frame", text="Address parsed from Hinglish", side="bottom", duration=3.0)
        time.sleep(1.8)
        ink_clear(page)

        # -------------------------------------------------------------
        # Part 4: Seller Approves Reattempt in Seller Console
        # -------------------------------------------------------------
        print("[03] Switching to Seller Console to approve NDR reattempt...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        smooth_click(page, seller_tab, steps=20, delay_after=1.2)
        setup_page_cursor_and_ink(page)

        # Find and click ORD-3110 case
        ord_item = page.locator(".inbox-item:has-text('ORD-3110')")
        if ord_item.count() > 0:
            smooth_click(page, ord_item.first, steps=20, delay_after=1.0)

        # Click Review & Approve on Proposal
        review_btn = page.locator("button:has-text('Review & Approve')")
        if review_btn.count() > 0:
            smooth_click(page, review_btn.first, steps=18, delay_after=1.0)

            # Click Approve inside Approval Modal
            approve_btn = page.locator("button:has-text('Approve action')")
            if approve_btn.count() > 0:
                smooth_click(page, approve_btn.first, steps=18, delay_after=1.5)

        ink_arrow(page, ".seller-col:has-text('Proposals')", text="One-click reattempt scheduled", from_side="left", duration=3.0)
        time.sleep(1.8)
        ink_clear(page)
        time.sleep(0.8)

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
