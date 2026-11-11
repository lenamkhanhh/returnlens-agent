"""Scene 04: Case B - Voice Note & Video Evidence (1:05 - 1:50)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6:
1. CUS-02 (Ananya Patel) sends mismatch inquiry on ORD-7729 with:
   - Voice note: synthetic_voice_en_mismatch_ORD-7729.ogg
   - Video clip: stock_black_headphones_pexels_9130360.mp4
2. Grounded Vision Observer detects black headphones at 00:07 vs White in catalog.
3. Barcode and exact model kept in 'Still Unverified'.
4. Seller opens case, sees Triad Facts Panel, and clicks timestamp (▶ 00:07)
   causing the video player to seek to 00:07.
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
)

STOCK_VIDEO = REPO_ROOT / "app" / "demo" / "media" / "stock" / "stock_black_headphones_pexels_9130360.mp4"
STOCK_VOICE = REPO_ROOT / "app" / "demo" / "media" / "stock" / "synthetic_voice_en_mismatch_ORD-7729.ogg"

def record_scene_04() -> Path:
    print("\n=== RECORDING SCENE 04: CASE B (VOICE & VIDEO) ===")
    reset_demo_database()

    temp_dir = SCENES_DIR / "temp_04"
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

        # 1. Customer Portal
        print("[04] Navigating to Customer Portal...")
        page.goto(f"{BASE_URL}/?tab=customer")
        page.wait_for_selector(".customer-layout", timeout=10000)
        page.wait_for_timeout(2000)

        # Select Ananya Patel (CUS-02)
        print("[04] Selecting Customer CUS-02...")
        cust_select = page.locator("select.select-field").first
        cust_select.select_option("CUS-02")
        page.wait_for_timeout(1500)

        # Attach video clip
        print("[04] Attaching stock black headphones video...")
        file_input = page.locator("input[type='file']")
        file_input.set_input_files(str(STOCK_VIDEO))
        page.wait_for_timeout(1000)

        # Fill text
        text_input = page.locator("input.text-input")
        text_input.fill("I ordered white headphones but received black ones. Here is the unboxing clip.")
        page.wait_for_timeout(1000)

        # Click Send
        print("[04] Sending message and uploading media...")
        send_btn = page.locator("button.btn-primary:has-text('Send')")
        send_btn.click()
        page.wait_for_timeout(4000)

        # Also attach voice note to case via API if case exists
        try:
            res = urllib.request.urlopen(f"{BASE_URL}/api/seller/cases")
            cases = json.loads(res.read().decode())
            match = next((c for c in cases if c.get("order_id") == "ORD-7729"), None)
            if match and STOCK_VOICE.exists():
                print(f"[04] Attaching voice note {STOCK_VOICE.name} to case {match['case_id']}...")
                # Upload via multipart
                data = STOCK_VOICE.read_bytes()
                boundary = "----WebKitFormBoundary7MA4YWxkTrZu0gW"
                body = (
                    f"--{boundary}\r\n"
                    f'Content-Disposition: form-data; name="file"; filename="{STOCK_VOICE.name}"\r\n'
                    f"Content-Type: audio/ogg\r\n\r\n"
                ).encode("utf-8") + data + f"\r\n--{boundary}--\r\n".encode("utf-8")

                req = urllib.request.Request(
                    f"{BASE_URL}/api/cases/{match['case_id']}/evidence",
                    data=body,
                    headers={"Content-Type": f"multipart/form-data; boundary={boundary}"},
                    method="POST",
                )
                with urllib.request.urlopen(req) as resp:
                    print(f"[04] Voice note attached successfully: {resp.status}")
        except Exception as e:
            print(f"[04] Note: Voice upload via API: {e}")

        # Wait for model analysis to settle
        page.wait_for_timeout(3000)

        # 2. Switch to Seller Console
        print("[04] Navigating to Seller Console...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        seller_tab.click()
        page.wait_for_timeout(2500)

        # Click on ORD-7729 case
        inbox_items = page.locator(".inbox-item").all()
        for it in inbox_items:
            if "ORD-7729" in it.inner_text():
                it.click()
                break
        page.wait_for_timeout(2500)

        # 3. Inspect Triad Facts Panel
        print("[04] Hovering on Triad Facts Panel...")
        triad_panel = page.locator(".seller-col:has-text('Verified Order Facts')")
        if triad_panel.count() > 0:
            triad_panel.first.hover()
            page.wait_for_timeout(2000)

        # 4. Click Timestamp ▶ 00:07 to seek video
        print("[04] Clicking timestamp button to seek video...")
        timestamp_btn = page.locator("button:has-text('00:07'), button:has-text('0:07'), .timestamp-chip")
        if timestamp_btn.count() > 0:
            timestamp_btn.first.click()
            page.wait_for_timeout(3500)  # Pause to see video playing at 00:07!

        # 5. Inspect Plan Card & Proposal
        print("[04] Inspecting Plan Card and Proposal...")
        plan_card = page.locator(".plan-card, .seller-col:has-text('Plan')")
        if plan_card.count() > 0:
            plan_card.first.hover()
            page.wait_for_timeout(2000)

        # Review & Decide proposal if available
        review_btn = page.locator("button:has-text('Review & Decide')")
        if review_btn.count() > 0:
            review_btn.first.click()
            page.wait_for_timeout(2500)

            close_modal = page.locator(".modal-header button:has-text('✕')")
            if close_modal.count() > 0:
                close_modal.first.click()
                page.wait_for_timeout(1000)

        page.wait_for_timeout(2000)

        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = Path(video_obj.path())
        final_webm = SCENES_DIR / "scene_04.webm"
        final_mp4 = SCENES_DIR / "scene_04.mp4"

        if final_webm.exists():
            final_webm.unlink()
        raw_video_path.rename(final_webm)

        try:
            temp_dir.rmdir()
        except Exception:
            pass

        convert_webm_to_mp4(final_webm, final_mp4)
        duration = get_video_duration(final_mp4)
        print(f"[04 DONE] scene_04 saved: {final_webm.name} & {final_mp4.name} ({duration:.1f}s)")
        return final_webm

if __name__ == "__main__":
    record_scene_04()
