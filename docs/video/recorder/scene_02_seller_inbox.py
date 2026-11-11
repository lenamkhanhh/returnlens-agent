"""Scene 02: Seller Inbox Overview (0:25 - 0:40)
Per BRIEF_E_RECORDING & 13_FINAL_PLAYBOOK §6:
Shows a solo D2C Indian merchant's support console:
- Multi-case inbox across WISMO, Returns, and NDR.
- Filtering by status (ALL, Needs Review, PROCESSING).
- 3-Group Fact Panel: Verified Order Facts, Observed in Evidence, Still Unverified.
- Plan card with memory chips and action proposals.
- Chronological Audit Timeline drawer with human-readable event labels.
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
)

def record_scene_02() -> Path:
    print("\n=== RECORDING SCENE 02: SELLER INBOX OVERVIEW ===")

    temp_dir = SCENES_DIR / "temp_02"
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
        page.on("dialog", lambda d: d.dismiss())

        # 1. Open Seller Console
        print("[02] Navigating to Seller Console...")
        page.goto(f"{BASE_URL}/?tab=seller")
        page.wait_for_selector(".app-header", timeout=10000)
        page.wait_for_timeout(2000)

        # 2. Browse Inbox & Filter Tabs
        print("[02] Testing Inbox filter tabs...")
        needs_review_btn = page.locator("button:has-text('Needs Review')")
        if needs_review_btn.count() > 0:
            needs_review_btn.first.click()
            page.wait_for_timeout(1500)

        all_filter_btn = page.locator("button:has-text('ALL')")
        if all_filter_btn.count() > 0:
            all_filter_btn.first.click()
            page.wait_for_timeout(1500)

        # 3. Select an active case with rich details (e.g. ORD-1042 or first available)
        print("[02] Selecting inbox case...")
        inbox_items = page.locator(".inbox-item").all()
        if len(inbox_items) > 0:
            inbox_items[0].click()
            page.wait_for_timeout(2000)

        # Hover over Triad Facts Panel
        facts_panel = page.locator(".facts-panel, .seller-col:has-text('Verified Order Facts')")
        if facts_panel.count() > 0:
            facts_panel.first.hover()
            page.wait_for_timeout(1500)

        # 4. Open Timeline Drawer
        print("[02] Opening Audit Timeline Drawer...")
        timeline_btn = page.locator("button:has-text('Open Timeline Drawer')")
        if timeline_btn.count() > 0:
            timeline_btn.first.click()
            page.wait_for_timeout(3000)  # Pause to inspect audit events

            # Scroll timeline drawer if scrollable
            timeline_drawer = page.locator(".timeline-drawer")
            if timeline_drawer.count() > 0:
                timeline_drawer.evaluate("el => el.scrollTop = 200")
                page.wait_for_timeout(1500)

            # Close timeline drawer
            close_drawer_btn = page.locator(".timeline-drawer button:has-text('✕')")
            if close_drawer_btn.count() > 0:
                close_drawer_btn.first.click()
                page.wait_for_timeout(1000)

        # Pause on full console view
        page.wait_for_timeout(1500)

        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = Path(video_obj.path())
        final_webm = SCENES_DIR / "scene_02.webm"
        final_mp4 = SCENES_DIR / "scene_02.mp4"

        if final_webm.exists():
            final_webm.unlink()
        raw_video_path.rename(final_webm)

        try:
            temp_dir.rmdir()
        except Exception:
            pass

        convert_webm_to_mp4(final_webm, final_mp4)
        duration = get_video_duration(final_mp4)
        print(f"[02 DONE] scene_02 saved: {final_webm.name} & {final_mp4.name} ({duration:.1f}s)")
        return final_webm

if __name__ == "__main__":
    record_scene_02()
