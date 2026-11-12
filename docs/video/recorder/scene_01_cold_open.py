"""Scene 01: Cold Open — Earned Autonomy & Limits (Honest Flow)
Per Wave 16 Coordinator Directive:
1. Autonomy bar shows "measured on this exact code · ffaccd04 · k=5".
   DAMAGE locked (S10 missing in production), MISMATCH locked (4/5).
2. Seller tries to set DAMAGE -> L3; app refuses with lock error.
3. Show MISMATCH locked 4/5 (ink: "locked until 5/5").
4. Operator fires RETURN_RECEIVED for SHP-1042 (select event type explicitly and verify).
5. The agent creates a PROPOSE_REFUND ₹1,299 for the seller.
6. Open "Why did it stop?" checklist modal.
7. Seller reviews & approves the refund.
8. Refund confirmed successfully.
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

def record_scene_01() -> Path:
    print("\n=== RECORDING SCENE 01: COLD OPEN (HONEST AUTONOMY & REFUND) ===")
    reset_demo_database()

    temp_dir = SCENES_DIR / "temp_01"
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

        # Intercept PUT /api/seller/autonomy to include required caps in body
        def handle_autonomy_put(route):
            req = route.request
            if req.method == "PUT":
                post_data = req.post_data_json or {}
                levels = post_data.get("levels", {})
                sanitized = {
                    "levels": levels,
                    "per_order_cap_minor": 150000,
                    "per_customer_daily_cap_minor": 200000,
                }
                route.continue_(post_data=json.dumps(sanitized))
            else:
                route.continue_()

        page.route("**/api/seller/autonomy", handle_autonomy_put)

        # 1. Open Seller Console
        print("[01] Opening Seller Console (demo scale)...")
        page.goto(f"{BASE_URL}/?tab=seller&demo=1")
        setup_page_cursor_and_ink(page)
        page.wait_for_selector(".app-header", timeout=10000)
        time.sleep(0.8)

        # Verify initial autonomy state from API
        res = urllib.request.urlopen(f"{BASE_URL}/api/seller/autonomy")
        autonomy_data = json.loads(res.read().decode())
        print(f"[01 API] Version: {autonomy_data.get('agent_version')[:8]}, DAMAGE eligible: {autonomy_data['lock_status']['DAMAGE']['eligible_for_l2_l3']}")

        # 2. Inspect Autonomy Bar
        prov_text = page.locator("#autonomy-bar div:has-text('Measured on this exact code')").first
        if prov_text.count() > 0:
            smooth_move(page, prov_text, steps=15)
            ink_circle(page, prov_text, text="Measured on this exact code", side="bottom", duration=2.0)
        else:
            code_chip = page.locator("#autonomy-bar code").first
            smooth_move(page, code_chip, steps=15)
            ink_circle(page, code_chip, text="Measured on this exact code", side="bottom", duration=2.0)
        time.sleep(2.2)
        ink_clear(page)

        # 3. Seller tries to set DAMAGE -> L3; app refuses
        print("[01] Attempting to set DAMAGE to L3...")
        page.evaluate("""() => {
            const select = Array.from(document.querySelectorAll('#autonomy-bar select'))[1];
            if (select) {
                const opt = select.querySelector('option[value="L3"]');
                if (opt) opt.disabled = false;
                select.value = 'L3';
                select.dispatchEvent(new Event('change', { bubbles: true }));
            }
        }""")
        time.sleep(0.8)

        # Verify refusal message on screen (plain words banner)
        lock_error_loc = page.locator("#autonomy-bar div:has-text('go above L1')")
        if lock_error_loc.count() > 0:
            banner_box = page.evaluate("""() => {
                const els = Array.from(document.querySelectorAll('#autonomy-bar div'))
                  .filter(e => e.textContent.includes('go above L1') && e.getBoundingClientRect().width > 700);
                if (!els.length) return null;
                els.sort((a, b) => a.getBoundingClientRect().height - b.getBoundingClientRect().height);
                const r = els[0].getBoundingClientRect();
                return {x: r.left, y: r.top, width: r.width, height: r.height};
            }""")
            ink_circle(page, banner_box or lock_error_loc.first, text=None, side="bottom", duration=2.5)
            time.sleep(2.2)
            ink_clear(page)

        # 4. Show MISMATCH locked 4/5
        print("[01] Highlighting locked MISMATCH...")
        mismatch_card = page.locator("div:has-text('MISMATCH'):has-text('Locked')").first
        if mismatch_card.count() > 0:
            smooth_move(page, mismatch_card, steps=15)
            ink_circle(page, mismatch_card, text="locked until 5/5", side="only-top", duration=2.0)
        else:
            mismatch_col = page.locator("div:has-text('MISMATCH')").first
            smooth_move(page, mismatch_col, steps=15)
            ink_circle(page, mismatch_col, text="locked until 5/5", side="bottom", duration=2.0)
        time.sleep(2.2)
        ink_clear(page)

        # 5. Switch to Operator Controls to fire RETURN_RECEIVED
        print("[01] Navigating to Operator Controls...")
        op_tab = page.locator("button.tab-btn:has-text('Operator Controls')")
        smooth_click(page, op_tab, steps=15, delay_after=0.6)
        setup_page_cursor_and_ink(page)

        # Form: set SHP-1042 and explicitly select RETURN_RECEIVED
        shp_input = page.locator(".seller-col:has-text('Fire a courier event') input").first
        shp_input.fill("SHP-1042")
        time.sleep(0.3)

        evt_select = page.locator(".seller-col:has-text('Fire a courier event') select").first
        evt_select.select_option("RETURN_RECEIVED")
        time.sleep(0.3)
        assert evt_select.input_value() == "RETURN_RECEIVED", f"Expected RETURN_RECEIVED, got {evt_select.input_value()}"
        print(f"[01] Verified event dropdown value: {evt_select.input_value()}")

        dispatch_btn = page.locator("button:has-text('Dispatch Courier Webhook')")
        smooth_click(page, dispatch_btn, steps=15, delay_after=0.8)

        # Verify event fired from API
        res = urllib.request.urlopen(f"{BASE_URL}/api/seller/cases")
        cases = json.loads(res.read().decode())
        c1042 = next((c for c in cases if c.get("order_id") == "ORD-1042"), None)
        assert c1042 is not None, "ORD-1042 not found"
        print(f"[01 API] ORD-1042 state after event: {c1042['state']}")

        ink_arrow(page, dispatch_btn, text="RETURN_RECEIVED dispatched", from_side="top", duration=2.0)
        time.sleep(2.2)
        ink_clear(page)

        # 6. Switch back to Seller Console
        print("[01] Returning to Seller Console...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        smooth_click(page, seller_tab, steps=15, delay_after=0.6)
        setup_page_cursor_and_ink(page)

        # Select case ORD-1042
        ord_item = page.locator(".inbox-item:has-text('ORD-1042')")
        smooth_click(page, ord_item.first, steps=15, delay_after=0.6)

        # Verify PROPOSE_REFUND ₹1,299 exists
        res = urllib.request.urlopen(f"{BASE_URL}/api/cases/{c1042['case_id']}")
        c_detail = json.loads(res.read().decode())
        pending_props = [p for p in c_detail.get("proposals", []) if p.get("status") == "pending"]
        assert len(pending_props) > 0, "No pending proposals found"
        print(f"[01 API] Pending proposal: {pending_props[0]['action_type']} for {pending_props[0]['amount_minor']}")

        # Annotate PROPOSE_REFUND ₹1,299
        prop_badge = page.locator(".proposal-box:has-text('PROPOSE REFUND') .badge, .proposal-box:has-text('PROPOSE REFUND') strong:has-text('₹1,299')").first
        if prop_badge.count() > 0:
            prop_badge.scroll_into_view_if_needed()
            time.sleep(0.4)
            ink_circle(page, prop_badge, text="PROPOSE_REFUND ₹1,299 created", side="right", duration=2.5)
            time.sleep(2.2)
            ink_clear(page)
        else:
            prop_box = page.locator(".proposal-box:has-text('PROPOSE REFUND')").first
            if prop_box.count() > 0:
                prop_box.scroll_into_view_if_needed()
                time.sleep(0.4)
                ink_circle(page, prop_box, text="PROPOSE_REFUND ₹1,299 created", side="bottom", duration=2.5)
                time.sleep(2.2)
                ink_clear(page)

        # 7. Open "Why did it stop?"
        print("[01] Opening 'Why did it stop?' modal...")
        why_btn = page.locator("button:has-text('Why did it stop?')")
        if why_btn.count() > 0:
            smooth_click(page, why_btn.first, steps=15, delay_after=0.8)
            page.wait_for_selector(".modal-card", timeout=3000)

            step4 = page.locator(".checklist-step:has-text('Reliability Gate'), div:has-text('Step 4')")
            if step4.count() > 0:
                smooth_move(page, step4.first, steps=15)
                ink_arrow(page, step4.first, text="Stopped: DAMAGE requires 5/5", from_side="left", duration=2.5)
                time.sleep(2.2)
                ink_clear(page)

            close_btn = page.locator(".modal-header button:has-text('✕')")
            if close_btn.count() > 0:
                smooth_click(page, close_btn.first, steps=12, delay_after=0.5)
            else:
                page.keyboard.press("Escape")
            time.sleep(0.3)

        # 8. Seller reviews and approves the refund
        print("[01] Seller approving refund...")
        rev_btn = page.locator("button:has-text('Review & Approve')")
        if rev_btn.count() > 0:
            rev_btn.first.scroll_into_view_if_needed()
            smooth_click(page, rev_btn.first, steps=15, delay_after=0.6)
            page.wait_for_selector(".modal-card:has-text('Seller authorization required')", timeout=5000)

            app_btn = page.locator("button:has-text('Approve action')")
            smooth_click(page, app_btn.first, steps=15, delay_after=1.0)

            # Read confirmation from API
            res = urllib.request.urlopen(f"{BASE_URL}/api/cases/{c1042['case_id']}")
            updated_detail = json.loads(res.read().decode())
            all_approved = all(p.get("status") == "approved" for p in updated_detail.get("proposals", []))
            print(f"[01 API] All proposals approved: {all_approved}")

            succ_msg = page.locator("div:has-text('Action executed successfully')")
            if succ_msg.count() > 0:
                ink_arrow(page, succ_msg.first, text="Refund approved & confirmed", from_side="bottom", duration=2.5)
                time.sleep(2.2)
                ink_clear(page)

        time.sleep(0.5)

        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = Path(video_obj.path())
        final_webm = SCENES_DIR / "scene_01.webm"
        final_mp4 = SCENES_DIR / "scene_01.mp4"

        if final_webm.exists():
            final_webm.unlink()
        raw_video_path.rename(final_webm)

        try:
            temp_dir.rmdir()
        except Exception:
            pass

        convert_webm_to_mp4(final_webm, final_mp4)
        duration = get_video_duration(final_mp4)
        print(f"[01 DONE] scene_01 saved: {final_webm.name} & {final_mp4.name} ({duration:.1f}s)")
        return final_webm

if __name__ == "__main__":
    record_scene_01()
