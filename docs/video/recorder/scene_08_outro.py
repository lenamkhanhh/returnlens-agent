"""Scene 08: Outro & Repository Link (2:55 - 3:00)
Per docs/video/SHOTLIST.md §3:
5-second high-contrast closing title card:
- Logo & Slogan: "ReturnLens — Every return decision, backed by evidence."
- Repository & Hackathon Badge: AgentX Hackathon 2026 | Track PS-04
"""

from __future__ import annotations

import time
from pathlib import Path
from playwright.sync_api import sync_playwright

from docs.video.recorder.common import (
    SCENES_DIR,
    convert_webm_to_mp4,
    get_video_duration,
)

OUTRO_HTML = """<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  body {
    background: #111418;
    color: #ffffff;
    font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, Helvetica, Arial, sans-serif;
    display: flex;
    flex-direction: column;
    justify-content: center;
    align-items: center;
    height: 100vh;
    width: 100vw;
  }
  .brand {
    display: flex;
    align-items: center;
    gap: 16px;
    margin-bottom: 24px;
  }
  .logo-icon {
    font-size: 64px;
  }
  .brand-title {
    font-size: 56px;
    font-weight: 800;
    letter-spacing: -1px;
    color: #2a9d8f;
  }
  .slogan {
    font-size: 26px;
    font-weight: 500;
    color: #e2e8f0;
    margin-bottom: 36px;
    text-align: center;
    line-height: 1.4;
  }
  .badge-row {
    display: flex;
    gap: 16px;
    margin-bottom: 30px;
  }
  .badge {
    background: #1e293b;
    border: 1px solid #334155;
    padding: 8px 18px;
    border-radius: 9999px;
    font-size: 16px;
    font-weight: 600;
    color: #94a3b8;
  }
  .badge.highlight {
    background: #064e3b;
    border-color: #059669;
    color: #34d399;
  }
  .repo-url {
    font-family: ui-monospace, SFMono-Regular, Menlo, Monaco, Consolas, monospace;
    font-size: 18px;
    color: #64748b;
  }
</style>
<script>
  let tick = 0;
  function animate() {
    tick++;
    document.title = "ReturnLens Outro " + tick;
    requestAnimationFrame(animate);
  }
  requestAnimationFrame(animate);
</script>
</head>
<body>
  <div class="brand">
    <span class="logo-icon">🛡️</span>
    <span class="brand-title">ReturnLens</span>
  </div>
  <div class="slogan">
    The Support Agent That Earns Its Autonomy.<br>
    <span style="font-size: 22px; color: #94a3b8; font-weight: 400;">Every return decision, backed by evidence.</span>
  </div>
  <div class="badge-row">
    <div class="badge highlight">AgentX Hackathon 2026 · Track PS-04</div>
    <div class="badge">Team Rookie</div>
  </div>
  <div class="repo-url">github.com/lenamkhanhh/returnlens-agent</div>
</body>
</html>
"""

def record_scene_08() -> Path:
    print("\n=== RECORDING SCENE 08: OUTRO TITLE CARD ===")

    temp_dir = SCENES_DIR / "temp_08"
    temp_dir.mkdir(parents=True, exist_ok=True)

    with sync_playwright() as p:
        browser = p.chromium.launch(
            headless=True,
            slow_mo=0,
        )
        context = browser.new_context(
            viewport={"width": 1920, "height": 1080},
            record_video_dir=str(temp_dir),
            record_video_size={"width": 1920, "height": 1080},
        )
        page = context.new_page()

        print("[08] Displaying high-contrast outro title card...")
        page.set_content(OUTRO_HTML)
        page.wait_for_timeout(7000)

        video_obj = page.video
        context.close()
        browser.close()

        raw_video_path = Path(video_obj.path())
        final_webm = SCENES_DIR / "scene_08.webm"
        final_mp4 = SCENES_DIR / "scene_08.mp4"

        if final_webm.exists():
            final_webm.unlink()
        raw_video_path.rename(final_webm)

        try:
            temp_dir.rmdir()
        except Exception:
            pass

        convert_webm_to_mp4(final_webm, final_mp4)
        duration = get_video_duration(final_mp4)
        print(f"[08 DONE] scene_08 saved: {final_webm.name} & {final_mp4.name} ({duration:.1f}s)")
        return final_webm

if __name__ == "__main__":
    record_scene_08()
