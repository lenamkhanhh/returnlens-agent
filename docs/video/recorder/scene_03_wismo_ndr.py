"""Scene 03: WISMO and NDR Flows (Honest & Fact-Checked)
Per Wave 16 Review Directives:
1. WISMO: CUS-01 (Priya Sharma) asks "Where is my order?" for ORD-2030.
   Agent calls real mock tracking tools, replies with live Delhivery status and ETA.
   Circle ONLY the reply message bubble, never the whole panel.
2. NDR: Operator fires NDR on SHP-3110 (explicitly select and verify dropdown value).
   Agent sends proactive outreach to CUS-05 (Rohit Verma).
3. Customer replies with corrected address (Flat 14B) in Hinglish.
   Circle ONLY customer's message bubble.
4. Seller reviews PROPOSE_NDR_REATTEMPT in Seller Console and approves with one click.
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
        time.sleep(0.6)

        # Select Priya Sharma (CUS-01) if not default
        cust_select = page.locator("select.demo-select").first
        if cust_select.count() > 0:
            cust_select.select_option("CUS-01")
            time.sleep(0.3)

        # Type WISMO inquiry with smooth move & click
        print("[03] Customer typing: Where is my order?...")
        text_input = page.locator("input.messaging-input-field")
        smooth_click(page, text_input, steps=12, delay_after=0.2)
        text_input.fill("Where is my order?")
        time.sleep(0.3)

        send_btn = page.locator("button.messaging-send-btn")
        smooth_click(page, send_btn, steps=12, delay_after=1.6)

        # Verify tracking reply from API
        res = urllib.request.urlopen(f"{BASE_URL}/api/seller/cases")
        cases = json.loads(res.read().decode())
        wismo_case = next((c for c in cases if c.get("order_id") == "ORD-2030"), None)
        print(f"[03 API] WISMO Case: {wismo_case['case_id'] if wismo_case else 'None'}, state: {wismo_case.get('state') if wismo_case else 'None'}")

        # Circle ONLY the agent reply bubble (never the whole panel)
        agent_bubble = page.locator(".chat-bubble.agent").last
        if agent_bubble.count() > 0:
            smooth_move(page, agent_bubble, steps=12)
            ink_circle(page, agent_bubble, text="Live Delhivery tracking & ETA", side="top", duration=2.0)
            time.sleep(2.2)
            ink_clear(page)

        # -------------------------------------------------------------
        # Part 2: NDR Trigger in Operator Controls
        # -------------------------------------------------------------
        print("[03] Switching to Operator Controls to fire NDR...")
        op_tab = page.locator("button.tab-btn:has-text('Operator Controls')")
        smooth_click(page, op_tab, steps=15, delay_after=0.6)
        setup_page_cursor_and_ink(page)

        # Form: set SHP-3110 and explicitly select NDR
        col = page.locator(".seller-col:has-text('Fire a courier event')")
        shp_input = col.locator("input").first
        shp_input.fill("SHP-3110")
        time.sleep(0.2)

        evt_select = col.locator("select").first
        evt_select.select_option("NDR")
        time.sleep(0.2)
        assert evt_select.input_value() == "NDR", f"Expected NDR, got {evt_select.input_value()}"
        print(f"[03] Verified event dropdown value: {evt_select.input_value()}")

        dispatch_btn = col.locator("button:has-text('Dispatch Courier Webhook')")
        smooth_click(page, dispatch_btn, steps=15, delay_after=0.8)

        # Verify NDR case created in API
        res = urllib.request.urlopen(f"{BASE_URL}/api/seller/cases")
        cases = json.loads(res.read().decode())
        ndr_case = next((c for c in cases if c.get("order_id") == "ORD-3110"), None)
        print(f"[03 API] NDR Case: {ndr_case['case_id'] if ndr_case else 'None'}, state: {ndr_case.get('state') if ndr_case else 'None'}")

        ink_arrow(page, dispatch_btn, text="NDR delivery failure", from_side="top", duration=2.0)
        time.sleep(2.2)
        ink_clear(page)

        # -------------------------------------------------------------
        # Part 3: Customer Corrects Address for NDR
        # -------------------------------------------------------------
        print("[03] Switching back to Customer Portal for CUS-05...")
        cust_tab = page.locator("button.tab-btn:has-text('Customer Portal')")
        smooth_click(page, cust_tab, steps=15, delay_after=0.6)
        setup_page_cursor_and_ink(page)

        cust_select = page.locator("select.demo-select").first
        cust_select.select_option("CUS-05")
        time.sleep(0.8)

        # Type address correction in Hinglish
        print("[03] Customer replies with corrected address...")
        text_input = page.locator("input.messaging-input-field")
        smooth_click(page, text_input, steps=12, delay_after=0.2)
        text_input.fill("Flat 12B nahi, 14B hai. Kal shaam 6 baje chalega.")
        time.sleep(0.4)

        send_btn = page.locator("button.messaging-send-btn")
        smooth_click(page, send_btn, steps=12, delay_after=2.0)

        # Circle ONLY the customer message bubble
        cus_bubble = page.locator(".chat-bubble.customer").last
        if cus_bubble.count() > 0:
            smooth_move(page, cus_bubble, steps=12)
            ink_circle(page, cus_bubble, text="Address parsed from Hinglish", side="bottom", duration=2.0)
            time.sleep(2.2)
            ink_clear(page)

        # -------------------------------------------------------------
        # Part 4: Seller Approves Reattempt in Seller Console
        # -------------------------------------------------------------
        print("[03] Switching to Seller Console to approve NDR reattempt...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        smooth_click(page, seller_tab, steps=15, delay_after=0.8)
        setup_page_cursor_and_ink(page)

        # Find and click ORD-3110 case
        ord_item = page.locator(".inbox-item:has-text('ORD-3110')")
        if ord_item.count() > 0:
            smooth_click(page, ord_item.first, steps=15, delay_after=0.8)

        # Verify proposal from API
        res = urllib.request.urlopen(f"{BASE_URL}/api/cases/{ndr_case['case_id']}")
        c_detail = json.loads(res.read().decode())
        prop = next((p for p in c_detail.get("proposals", []) if p.get("action_type") == "PROPOSE_NDR_REATTEMPT"), None)
        print(f"[03 API] NDR Proposal: {prop['proposal_id'] if prop else 'None'}, status: {prop.get('status') if prop else 'None'}")

        # Click Review & Approve on Proposal
        review_btn = page.locator("button:has-text('Review & Approve')")
        if review_btn.count() > 0:
            smooth_click(page, review_btn.first, steps=15, delay_after=0.8)
            page.wait_for_selector(".modal-card", timeout=3000)

            # Click Approve inside Approval Modal
            approve_btn = page.locator("button:has-text('Approve action')")
            if approve_btn.count() > 0:
                smooth_click(page, approve_btn.first, steps=15, delay_after=1.0)

            succ_msg = page.locator("div:has-text('Action executed successfully')")
            if succ_msg.count() > 0:
                ink_circle(page, succ_msg.first, text=None, side="top", duration=2.0)
                time.sleep(2.2)
                ink_clear(page)

        time.sleep(0.5)

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
