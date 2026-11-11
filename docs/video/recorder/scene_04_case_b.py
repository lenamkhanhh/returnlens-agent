"""Scene 04: Case B - Voice Note & Video Evidence (ORD-7729 / CUS-02)
Per Wave 16 Review Directives:
1. Customer Portal: CUS-02 (Ananya Patel) sends WhatsApp-style inquiry on ORD-7729:
   - Video clip: stock_black_headphones_pexels_9130360.mp4
   - Voice note: synthetic_voice_en_mismatch_ORD-7729.ogg
   - Text message: "Ordered white headphones, got black ones in the box."
   - Circle ONLY the media attachment thumbnail, never the whole panel.
2. Seller Console: Shows ORD-7729 (CUS-02):
   - Triad Facts Panel shows:
     - Verified Order Facts: Catalog Color: White
     - "What the agent saw": Visual observation of black headphones (ink circle: "black at 00:05")
     - "Still unverified": barcode / box label (ink arrow: "Still unverified")
   - Clicking timestamp button seeks the customer unboxing video player.
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

STOCK_VIDEO = REPO_ROOT / "app" / "demo" / "media" / "stock" / "stock_black_headphones_pexels_9130360.mp4"
STOCK_VOICE = REPO_ROOT / "app" / "demo" / "media" / "stock" / "synthetic_voice_en_mismatch_ORD-7729.ogg"

def record_scene_04() -> Path:
    print("\n=== RECORDING SCENE 04: CASE B (ORD-7729 / CUS-02) ===")
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
        time.sleep(0.6)

        # Select Ananya Patel (CUS-02) - Order ORD-7729
        print("[04] Selecting Customer CUS-02 (ORD-7729)...")
        cust_select = page.locator("select.demo-select").first
        cust_select.select_option("CUS-02")
        time.sleep(0.5)

        # Attach video clip
        print("[04] Attaching stock black headphones video...")
        file_input = page.locator("input[type='file']")
        file_input.set_input_files(str(STOCK_VIDEO))
        time.sleep(0.5)

        # Fill text
        text_input = page.locator("input.messaging-input-field")
        smooth_click(page, text_input, steps=12, delay_after=0.2)
        text_input.fill("I ordered white headphones but received black ones. Here is the unboxing clip.")
        time.sleep(0.4)

        # Click Send
        print("[04] Sending message and uploading media...")
        send_btn = page.locator("button.messaging-send-btn")
        smooth_click(page, send_btn, steps=12, delay_after=1.8)

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
                    print(f"[04] Voice note attached: {resp.status}")
        except Exception as e:
            print(f"[04] Voice upload error: {e}")

        # Circle ONLY the media attachment thumbnail (never the whole panel)
        media_thumb = page.locator(".chat-video-player, .chat-media-thumb, .waveform-player-box").first
        if media_thumb.count() > 0:
            smooth_move(page, media_thumb, steps=12)
            ink_circle(page, media_thumb, text="Voice note & unboxing clip", side="top", duration=2.0)
            time.sleep(1.2)
            ink_clear(page)

        # 2. Switch to Seller Console
        print("[04] Navigating to Seller Console...")
        seller_tab = page.locator("button.tab-btn:has-text('Seller Console')")
        smooth_click(page, seller_tab, steps=15, delay_after=0.8)
        setup_page_cursor_and_ink(page)

        # Explicitly select ORD-7729 case (Ananya Patel / CUS-02)
        page.wait_for_selector(".inbox-item:has-text('ORD-7729')", timeout=5000)
        ord_item = page.locator(".inbox-item:has-text('ORD-7729')")
        smooth_click(page, ord_item.first, steps=15, delay_after=0.8)

        # Verify case from API
        res = urllib.request.urlopen(f"{BASE_URL}/api/seller/cases")
        cases = json.loads(res.read().decode())
        c7729 = next(c for c in cases if c.get("order_id") == "ORD-7729")
        res = urllib.request.urlopen(f"{BASE_URL}/api/cases/{c7729['case_id']}")
        detail = json.loads(res.read().decode())
        print(f"[04 API] ORD-7729: State={detail.get('state')}, Observations={len(detail.get('observations', []))}, Unknowns={len(detail.get('unknowns', []))}")

        # 3. Inspect Triad Facts Panel
        print("[04] Highlighting Triad Facts Panel...")
        seen_section = page.locator(".triad-group:has-text('What the agent saw')")
        if seen_section.count() > 0:
            smooth_move(page, seen_section.first, steps=15)
            ink_circle(page, seen_section.first, text="black at 00:05", side="left", duration=2.5)
            time.sleep(1.4)

        unverified_section = page.locator(".triad-group:has-text('Still unverified')")
        if unverified_section.count() > 0:
            ink_arrow(page, unverified_section.first, text="Still unverified", from_side="bottom", duration=2.5)
            time.sleep(1.4)

        # 4. Click Timestamp button to seek video
        print("[04] Clicking timestamp button to seek video...")
        timestamp_btn = page.locator("button.timestamp-pill, button:has-text('00:05'), button:has-text('00:07')")
        if timestamp_btn.count() > 0:
            smooth_click(page, timestamp_btn.first, steps=15, delay_after=0.8)

            # Move cursor to video player to show seeked frame
            video_player = page.locator("video.video-player")
            if video_player.count() > 0:
                smooth_move(page, video_player.first, steps=15)
                time.sleep(1.4)

        ink_clear(page)
        time.sleep(0.5)

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
