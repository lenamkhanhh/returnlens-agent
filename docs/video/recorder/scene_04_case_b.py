"""Scene 04: Case B - Voice Note & Video Evidence (1:05 - 1:50)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6 & WAVE16_FINAL_VIDEO.md:
1. Customer Portal: CUS-02 (Ananya Patel) sends WhatsApp-style inquiry on ORD-7729 with:
   - Video clip: stock_black_headphones_pexels_9130360.mp4
   - Voice note: synthetic_voice_en_mismatch_ORD-7729.ogg
   - Text message: "Ordered white headphones, got black ones in the box."
2. Seller Console:
   - Triad Facts Panel shows:
     - Verified Order Facts: Catalog Color: White
     - "What the agent saw": Detected black at timestamp (ink circle: "black at 00:05")
     - "Still unverified": barcode / box label (ink arrow: "Still unverified")
   - Clicking timestamp button seeks the customer unboxing video player.
   - Visible cursor with ripples and hand-drawn ink annotations.
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
            slow_mo=50,
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()
        page.on("dialog", lambda d: d.dismiss())

        # 1. Customer Portal
        print("[04] Navigating to Customer Portal (demo scale)...")
        page.goto(f"{BASE_URL}/?tab=customer&demo=1")
        setup_page_cursor_and_ink(page)
        page.wait_for_selector(".customer-layout", timeout=10000)
        time.sleep(1.0)

        # Select Ananya Patel (CUS-02)
        print("[04] Selecting Customer CUS-02...")
        cust_select = page.locator("select.demo-select").first
        cust_select.select_option("CUS-02")
        time.sleep(0.8)

        # Attach video clip
        print("[04] Attaching stock black headphones video...")
        file_input = page.locator("input[type='file']")
        file_input.set_input_files(str(STOCK_VIDEO))
        time.sleep(0.8)

        # Fill text
        text_input = page.locator("input.messaging-input-field")
        smooth_click(page, text_input, steps=15, delay_after=0.3)
        text_input.fill("I ordered white headphones but received black ones. Here is the unboxing clip.")
        time.sleep(0.6)

        # Click Send
        print("[04] Sending message and uploading media...")
        send_btn = page.locator("button.messaging-send-btn")
        smooth_click(page, send_btn, steps=15, delay_after=2.5)

        # Also attach voice note to case via API if case exists
        try:
            res = urllib.request.urlopen(f"{BASE_URL}/api/seller/cases")
            cases = json.loads(res.read().decode())
            match = next((c for c in cases if c.get("order_id") == "ORD-7729"), None)
            if match and STOCK_VOICE.exists():
                print(f"[04] Attaching voice note {STOCK_VOICE.name} to case {match['case_id']}...")
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

        # Show WhatsApp-style customer chat
        ink_circle(page, ".messaging-phone-frame", text="WhatsApp-style customer chat", side="top", duration=3.0)
        time.sleep(2.5)
        ink_clear(page)

        # 2. Switch to Seller Console
        print("[04] Navigating to Seller Console...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        smooth_click(page, seller_tab, steps=20, delay_after=1.2)
        setup_page_cursor_and_ink(page)

        # Click on ORD-7729 case
        ord_item = page.locator(".inbox-item:has-text('ORD-7729')")
        if ord_item.count() > 0:
            smooth_click(page, ord_item.first, steps=20, delay_after=1.2)

        # 3. Inspect Triad Facts Panel
        print("[04] Highlighting Triad Facts Panel...")
        seen_section = page.locator(".triad-group:has-text('What the agent saw')")
        if seen_section.count() > 0:
            smooth_move(page, seen_section.first, steps=20)
            ink_circle(page, seen_section.first, text="black at 00:05", side="left", duration=4.0)
            time.sleep(2.5)

        unverified_section = page.locator(".triad-group:has-text('Still unverified')")
        if unverified_section.count() > 0:
            ink_arrow(page, unverified_section.first, text="Still unverified", from_side="bottom", duration=4.0)
            time.sleep(2.5)

        # 4. Click Timestamp button to seek video
        print("[04] Clicking timestamp button to seek video...")
        timestamp_btn = page.locator("button.timestamp-pill, button:has-text('00:05'), button:has-text('00:07')")
        if timestamp_btn.count() > 0:
            smooth_click(page, timestamp_btn.first, steps=18, delay_after=1.2)

            # Move cursor to video player to show seeked frame
            video_player = page.locator("video.video-player")
            if video_player.count() > 0:
                smooth_move(page, video_player.first, steps=20)
                time.sleep(2.5)

        # 5. Inspect Plan Card
        print("[04] Inspecting Plan Card...")
        plan_card = page.locator(".plan-card")
        if plan_card.count() > 0:
            smooth_move(page, plan_card.first, steps=20)
            time.sleep(2.0)

        ink_clear(page)
        time.sleep(1.0)

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
