"""ReturnLens Demo Video Suite Orchestrator.
Role E: automated scene recording for the demo video.

Runs all scene recorders in 13 §6 order:
- scene_01: Cold Open
- scene_02: Seller Inbox Overview
- scene_03: WISMO and NDR
- scene_04: Case B (Voice Note & Video Evidence)
- scene_05: Returning Customer & Memory
- scene_06: Reliability Benchmark & Kill Switch
- scene_07: Try to Break It (Judge Sandbox)

Verifies both .webm and .mp4 outputs, measures durations, and prints summary table.
"""

from __future__ import annotations

import sys
import time
from pathlib import Path

from docs.video.recorder.common import SCENES_DIR, get_video_duration
from docs.video.recorder.scene_01_cold_open import record_scene_01
from docs.video.recorder.scene_02_seller_inbox import record_scene_02
from docs.video.recorder.scene_03_wismo_ndr import record_scene_03
from docs.video.recorder.scene_04_case_b import record_scene_04
from docs.video.recorder.scene_05_returning_customer import record_scene_05
from docs.video.recorder.scene_06_reliability_kill_switch import record_scene_06
from docs.video.recorder.scene_07_try_to_break_it import record_scene_07
from docs.video.recorder.scene_08_outro import record_scene_08

RECORDERS = [
    ("scene_01", "Cold Open (Autonomy Bar, Caps, Courier RETURN_RECEIVED, Why?)", record_scene_01),
    ("scene_02", "Seller Inbox Overview (Multi-case inbox, Filters, Fact Groups, Timeline)", record_scene_02),
    ("scene_03", "WISMO & NDR (Mock tracking tool reply, Courier NDR, Address update, Approval)", record_scene_03),
    ("scene_04", "Case B Voice & Video (Stock black clip, Voice note, Timestamp seek 00:07)", record_scene_04),
    ("scene_05", "Returning Customer (Dim clip, Leave & Return, Session restored, Memory chip)", record_scene_05),
    ("scene_06", "Reliability & Kill Switch (Benchmark gate, Provenance, 1-Click Kill Switch)", record_scene_06),
    ("scene_07", "Try to Break It (Prompt injection, Over-refund, Cumulative split, Custom attack)", record_scene_07),
    ("scene_08", "Outro & Repository Link (Closing title card, Track badge, Repo link)", record_scene_08),
]

def record_all(selected_scenes: list[str] | None = None) -> list[dict]:
    results = []
    print("=" * 70)
    print("RETURNLENS AUTOMATED DEMO SCENE RECORDER (ROLE E)")
    print("=" * 70)

    for scene_id, desc, fn in RECORDERS:
        if selected_scenes and scene_id not in selected_scenes:
            continue
        try:
            t0 = time.time()
            fn()
            elapsed = time.time() - t0

            webm_path = SCENES_DIR / f"{scene_id}.webm"
            mp4_path = SCENES_DIR / f"{scene_id}.mp4"

            duration = get_video_duration(mp4_path) if mp4_path.exists() else 0.0
            size_mb = (mp4_path.stat().st_size / (1024 * 1024)) if mp4_path.exists() else 0.0

            results.append({
                "scene": scene_id,
                "description": desc,
                "duration_sec": duration,
                "size_mb": size_mb,
                "status": "SUCCESS" if mp4_path.exists() and duration > 0 else "FAILED",
            })
        except Exception as e:
            print(f"[ERROR] Failed recording {scene_id}: {e}")
            results.append({
                "scene": scene_id,
                "description": desc,
                "duration_sec": 0.0,
                "size_mb": 0.0,
                "status": f"ERROR: {e}",
            })

    print("\n" + "=" * 70)
    print("RECORDING SUITE SUMMARY REPORT")
    print("=" * 70)
    print(f"{'Scene':<10} | {'Duration':<10} | {'Size':<10} | {'Status':<10} | Description")
    print("-" * 70)
    total_dur = 0.0
    for r in results:
        total_dur += r["duration_sec"]
        print(f"{r['scene']:<10} | {r['duration_sec']:>7.1f} s  | {r['size_mb']:>6.2f} MB | {r['status']:<10} | {r['description'][:35]}...")
    print("-" * 70)
    print(f"Total Video Footage: {total_dur:.1f} seconds ({total_dur / 60:.2f} minutes)")
    print("=" * 70)
    return results

if __name__ == "__main__":
    scenes = sys.argv[1:] if len(sys.argv) > 1 else None
    record_all(scenes)
