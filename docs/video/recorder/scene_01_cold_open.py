"""Scene 01: Cold Open (0:00 - 0:25)
Wave 16 (01:25 12/11) specification:
- Autonomy bar shows "measured on this exact code" and DAMAGE eligible, MISMATCH locked 4/5.
- Seller sets DAMAGE to L3 (caps ₹1,500 / ₹2,000).
- Try to set MISMATCH to L3 and show it refused (ink: "locked until 5/5").
- Operator fires RETURN_RECEIVED for ORD-1042 -> refund executes automatically (ink circle on the refund).
- Then RETURN_RECEIVED for ORD-4401 -> deferred to the seller by the cumulative daily limit (ink: "₹2,000/day cap").
- Open "Why did it stop?" for ORD-4401.
"""

from __future__ import annotations

import json
import time
from pathlib import Path
from playwright.sync_api import sync_playwright

from docs.video.recorder.common import (
    BASE_URL,
    SCENES_DIR,
    convert_webm_to_mp4,
    get_video_duration,
    ink_arrow,
    ink_circle,
    ink_clear,
    reset_demo_database,
    setup_page_cursor_and_ink,
    smooth_click,
    smooth_move,
)

def record_scene_01() -> Path:
    print("\n=== RECORDING SCENE 01: COLD OPEN (WAVE 16) ===")
    reset_demo_database()

    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = SCENES_DIR / "temp_01"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            slow_mo=100,
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # Route interceptor ensuring PUT autonomy passes valid schema
        def handle_autonomy_put(route):
            req = route.request
            if req.method == "PUT" and "/api/seller/autonomy" in req.url:
                body = req.post_data_json or {}
                clean_body = {
                    "levels": body.get("levels", {}),
                    "per_order_cap_minor": body.get("per_order_cap_minor", 150000),
                    "per_customer_daily_cap_minor": body.get("per_customer_daily_cap_minor", 200000),
                }
                route.continue_(post_data=json.dumps(clean_body))
            else:
                route.continue_()

        page.route("**/api/seller/autonomy", handle_autonomy_put)

        # Install cursor and ink overlay
        setup_page_cursor_and_ink(page)

        # 1. Open Seller Console
        print("[01] Opening Seller Console (?demo=1)...")
        page.goto(f"{BASE_URL}/?tab=seller&demo=1")
        page.wait_for_selector(".app-header", timeout=10000)
        time.sleep(1.0)

        # 2. Highlight Autonomy Bar metadata ("measured on this exact code")
        print("[01] Hovering on Autonomy Bar...")
        smooth_move(page, "text=Measured on this exact code", steps=25)
        time.sleep(0.8)

        # 3. Seller sets DAMAGE to L3
        print("[01] Setting DAMAGE to L3 Autonomy...")
        dmg_select = page.locator(".autonomy-bar-container select").nth(1)
        smooth_move(page, dmg_select, steps=25)
        dmg_select.select_option("L3")
        time.sleep(1.0)

        # 4. Try to set MISMATCH to L3 -> show it refused/disabled ("locked until 5/5")
        print("[01] Attempting MISMATCH L3 -> Refused/locked...")
        mismatch_card = page.locator(".autonomy-bar-container select").nth(2)
        smooth_move(page, mismatch_card, steps=25)
        ink_circle(page, mismatch_card, text="locked until 5/5", side="bottom", duration=3.2)
        time.sleep(1.5)

        # 5. Switch to Operator Controls tab
        print("[01] Switching to Operator Controls...")
        smooth_click(page, "button.tab-btn:has-text('Operator Controls')", steps=25, delay_after=0.8)

        # Fire RETURN_RECEIVED for SHP-1042
        print("[01] Firing RETURN_RECEIVED for SHP-1042...")
        shipment_input = page.locator("input.select-field").first
        smooth_click(page, shipment_input, steps=20, delay_after=0.2)
        shipment_input.fill("SHP-1042")
        time.sleep(0.3)

        event_select = page.locator("select.select-field").first
        event_select.select_option("RETURN_RECEIVED")
        time.sleep(0.3)

        dispatch_btn = page.locator("button:has-text('Dispatch Courier Webhook')")
        smooth_click(page, dispatch_btn, steps=20, delay_after=1.2)

        # 6. Return to Seller Console: ORD-1042 auto-refunds
        print("[01] Returning to Seller Console -> ORD-1042 auto-refunds...")
        smooth_click(page, "button.tab-btn:has-text('Seller Console')", steps=25, delay_after=1.0)

        # Click on ORD-1042 in inbox
        ord1042_item = page.locator(".inbox-item:has-text('ORD-1042')").first
        if ord1042_item.count() > 0:
            smooth_click(page, ord1042_item, steps=20, delay_after=0.8)

        # Ink annotation on refund: "auto-refund ₹1,299"
        refund_target = page.locator("text=PROPOSE RETURN, text=REFUND, text=PROPOSE_REFUND, text=Waiting, text=ORD-1042").first
        ink_circle(page, refund_target if refund_target.count() > 0 else ord1042_item, text="auto-refund ₹1,299", side="top", duration=3.0)
        time.sleep(1.8)

        # 7. Switch back to Operator Controls for ORD-4401
        print("[01] Firing RETURN_RECEIVED for SHP-4401...")
        smooth_click(page, "button.tab-btn:has-text('Operator Controls')", steps=25, delay_after=0.8)
        shipment_input = page.locator("input.select-field").first
        smooth_click(page, shipment_input, steps=20, delay_after=0.2)
        shipment_input.fill("SHP-4401")
        time.sleep(0.3)
        dispatch_btn = page.locator("button:has-text('Dispatch Courier Webhook')")
        smooth_click(page, dispatch_btn, steps=20, delay_after=1.2)

        # 8. Return to Seller Console: ORD-4401 is deferred to seller
        print("[01] Returning to Seller Console -> ORD-4401 deferred by daily cap...")
        smooth_click(page, "button.tab-btn:has-text('Seller Console')", steps=25, delay_after=1.0)
        ord4401_item = page.locator(".inbox-item:has-text('ORD-4401')").first
        if ord4401_item.count() > 0:
            smooth_click(page, ord4401_item, steps=20, delay_after=0.8)

        # Ink arrow: "₹2,000/day cap"
        ink_arrow(page, "text=Caps:", text="₹2,000/day cap", from_side="bottom", duration=3.0)
        time.sleep(1.5)

        # 9. Open "Why did it stop?" modal for ORD-4401
        print("[01] Opening 'Why did it stop?' modal...")
        why_btn = page.locator("button:has-text('Why did it stop?'), button:has-text('Why?')").first
        if why_btn.count() > 0:
            smooth_click(page, why_btn, steps=20, delay_after=2.5)
            # Close modal
            close_btn = page.locator(".modal-header button:has-text('✕')").first
            if close_btn.count() > 0:
                smooth_click(page, close_btn, steps=15, delay_after=0.6)

        # Finish recording
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

        # Convert to mp4
        convert_webm_to_mp4(final_webm, final_mp4)
        duration = get_video_duration(final_mp4)
        print(f"[01 DONE] scene_01 saved: {final_mp4.name} ({duration:.1f}s)")
        return final_mp4

if __name__ == "__main__":
    record_scene_01()
