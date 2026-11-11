"""Scene 01: Cold Open (0:00 - 0:25)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6:
1. Load cold-open snapshot (DEMO_SNAPSHOT).
2. Autonomy bar shows case types, caps ₹1,500/order · ₹2,000/day.
3. Attempt to enable DAMAGE L3 (shows real reliability gate check).
4. Operator tab: fire RETURN_RECEIVED for ORD-1042 then ORD-4401.
5. Return to Seller Console: inspect proposals, open "Why?" 7-step checklist.
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
    reset_demo_database,
)

def record_scene_01() -> Path:
    print("\n=== RECORDING SCENE 01: COLD OPEN ===")
    reset_demo_database()

    SCENES_DIR.mkdir(parents=True, exist_ok=True)
    temp_dir = SCENES_DIR / "temp_01"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            slow_mo=250,
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        # Handle route to ensure PUT autonomy passes full payload structure
        def handle_autonomy_put(route):
            req = route.request
            if req.method == "PUT" and "/api/seller/autonomy" in req.url:
                body = req.post_data_json or {}
                body["per_order_cap_minor"] = 150000
                body["per_customer_daily_cap_minor"] = 200000
                route.continue_(post_data=json.dumps(body))
            else:
                route.continue_()

        page.route("**/api/seller/autonomy", handle_autonomy_put)

        # 1. Open Seller Console
        print("[01] Opening Seller Console...")
        page.goto(f"{BASE_URL}/?tab=seller")
        page.wait_for_selector(".app-header", timeout=10000)
        page.wait_for_timeout(2000)

        # 2. Inspect Autonomy Bar
        print("[01] Highlighting Autonomy Bar...")
        autonomy_bar = page.locator("strong:has-text('Autonomy Bar')")
        autonomy_bar.hover()
        page.wait_for_timeout(1500)

        # Attempt to select L3 on DAMAGE (triggers live reliability gate check)
        print("[01] Attempting to set DAMAGE to L3...")
        selects = page.locator(".app-header ~ main select").all()
        if len(selects) >= 2:
            selects[1].select_option("L3")
            page.wait_for_timeout(2500)  # Let viewer see live reliability gate alert

        # 3. Switch to Operator Controls tab
        print("[01] Switching to Operator Controls...")
        operator_tab = page.locator("button.tab-btn:has-text('Operator Controls')")
        operator_tab.click()
        page.wait_for_timeout(2000)

        # Fire RETURN_RECEIVED for ORD-1042 (SHP-1042)
        print("[01] Firing RETURN_RECEIVED for SHP-1042...")
        shipment_input = page.locator("input.select-field").first
        shipment_input.fill("SHP-1042")
        page.wait_for_timeout(800)

        # Select RETURN_RECEIVED event
        event_select = page.locator("select.select-field").first
        event_select.select_option("RETURN_RECEIVED")
        page.wait_for_timeout(800)

        dispatch_btn = page.locator("button:has-text('Dispatch Courier Webhook')")
        dispatch_btn.click()
        page.wait_for_timeout(2000)

        # Fire RETURN_RECEIVED for ORD-4401 (SHP-4401)
        print("[01] Firing RETURN_RECEIVED for SHP-4401...")
        shipment_input.fill("SHP-4401")
        page.wait_for_timeout(800)
        dispatch_btn.click()
        page.wait_for_timeout(2000)

        # 4. Switch back to Seller Console
        print("[01] Returning to Seller Console...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        seller_tab.click()
        page.wait_for_timeout(2500)

        # Click on ORD-1042 case in inbox
        inbox_items = page.locator(".inbox-item").all()
        for it in inbox_items:
            if "ORD-1042" in it.inner_text():
                it.click()
                break
        page.wait_for_timeout(2000)

        # Open "Why?" Checklist modal
        print("[01] Opening 7-step Why? checklist modal...")
        why_btn = page.locator("button:has-text('Why?')")
        if why_btn.count() > 0:
            why_btn.first.click()
            page.wait_for_timeout(5000)  # Pause to let viewer read all 7 criteria

            # Close Why modal
            close_btn = page.locator(".modal-header button:has-text('✕')")
            if close_btn.count() > 0:
                close_btn.first.click()
                page.wait_for_timeout(1000)

        # Finish up recording
        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = Path(video_obj.path())
        final_webm = SCENES_DIR / "scene_01.webm"
        final_mp4 = SCENES_DIR / "scene_01.mp4"

        if final_webm.exists():
            final_webm.unlink()
        raw_video_path.rename(final_webm)

        # Clean up temp dir
        try:
            temp_dir.rmdir()
        except Exception:
            pass

        # Convert to mp4
        convert_webm_to_mp4(final_webm, final_mp4)
        duration = get_video_duration(final_mp4)
        print(f"[01 DONE] scene_01 saved: {final_webm.name} & {final_mp4.name} ({duration:.1f}s)")
        return final_webm

if __name__ == "__main__":
    record_scene_01()
