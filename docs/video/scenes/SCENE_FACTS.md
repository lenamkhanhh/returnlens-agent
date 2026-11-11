# ReturnLens — Video Scene Facts & Timing Guide (Wave 16 Verified)

This document lists the exact ground-truth facts, on-screen events, and timing cues for each recorded scene (`scene_01.mp4` through `scene_08.mp4`). AUDIO narration (`docs/video/narration.srt`) must align its voice cues and claims strictly with these verified on-screen facts.

- **Total Video Duration**: 151.80s (02:31.8) — comfortably within the hard 180.00s ceiling.
- **Resolution & Encoding**: 1920 × 1080 (1080p Full HD @ 25 fps, H.264 YUV420p).
- **Backend Environment**: Production mode (`HARNESS_MODE=0`), `DEMO_TODAY=2026-11-11`, commit `5f7929a` / `ffaccd04`.
- **Model Quota Accounting**: ~3 model requests used across the entire suite (far below the 30-call budget).

---

## Scene 01: Cold Open — Earned Autonomy & Limits (Honest Flow)
- **File**: `docs/video/scenes/scene_01.mp4`
- **Duration**: 29.00 seconds (`00:00.00` – `00:29.00`)
- **Key Facts & Timings**:
  - `00:00 - 00:03`: Seller Console opens with Autonomy Bar. Bar displays *"Measured on this exact code · ffaccd04 · k=5"*. In production (`HARNESS_MODE=0`), DAMAGE is locked (`🔒 Locked`) and MISMATCH is locked (`🔒 4/5`). Ink circle highlights bar: `"Measured on this exact code"`.
  - `00:03 - 00:06`: Seller attempts to set DAMAGE to L3. The application refuses and displays lock error banner: `"⚠️ Reliability locked for DAMAGE: Missing run for scenario S10"`. Ink arrow points to error: `"refused: missing 5/5 run for S10"`.
  - `00:06 - 00:09`: Cursor moves to MISMATCH dropdown showing it locked at 4/5 test runs. Ink circle: `"locked until 5/5"`.
  - `00:09 - 00:15`: Switch to Operator Controls. Operator fills `SHP-1042`, explicitly selects `RETURN_RECEIVED` in the dropdown, verifies the dropdown value, and clicks `"Dispatch Courier Webhook"`. Result: `✓ Event fired successfully! ID: EVT-OK`. Ink arrow: `"RETURN_RECEIVED dispatched"`.
  - `00:15 - 00:20`: Switch back to Seller Console. Seller selects `ORD-1042`. Case summary shows: `"Return received at warehouse; refund proposal pending approval"`. Proposals panel displays new proposal: `PROPOSE_REFUND` for ₹1,299. Ink circle: `"PROPOSE_REFUND ₹1,299 created"`.
  - `00:20 - 00:24`: Seller clicks `"Why did it stop?"` button on Autonomy Bar. 7-step evaluation checklist opens, highlighting Step 4 (*Reliability Gate*): DAMAGE requires 5/5 runs before autonomy can be unlocked. Ink arrow: `"Stopped: DAMAGE requires 5/5"`. Seller closes the modal.
  - `00:24 - 00:29`: Seller clicks `"Review & Approve"` on the `PROPOSE_REFUND ₹1,299` card. Approval modal opens with ₹1,299 impact. Seller clicks `"Approve action"`. Notification confirms: `✓ Action executed successfully!` and proposal resolves to `Resolved`. Ink arrow: `"Refund approved & confirmed"`.

---

## Scene 02: Seller Inbox Overview
- **File**: `docs/video/scenes/scene_02.mp4`
- **Duration**: 11.50 seconds (`00:29.00` – `00:40.50`)
- **Key Facts & Timings**:
  - `00:00 - 00:03`: Multi-case inbox dashboard across WISMO, Returns, and NDR. Cursor clicks filter tab `"Needs review"`, then `"All"`.
  - `00:03 - 00:07`: Seller selects active case `ORD-1042`. Center column loads the 3-group Triad Facts Panel (`Order facts`, `What the agent saw`, `Still unverified`). Ink circle highlights panel: `"3-group triad: facts, seen, unverified"`.
  - `00:07 - 00:11`: Seller clicks `"Case audit timeline"`. Drawer slides open showing immutable event log (Order Placed, Return Authorized, Parcel Received, Refund Approved). Ink arrow: `"Immutable event log"`.
  - `00:11 - 00:12`: Timeline drawer closed smoothly.

---

## Scene 03: WISMO & NDR Proactive Flow
- **File**: `docs/video/scenes/scene_03.mp4`
- **Duration**: 31.70 seconds (`00:40.50` – `01:12.20`)
- **Key Facts & Timings**:
  - `00:00 - 00:08`: Customer Portal (`Dhun Audio · Bengaluru`). Priya Sharma (CUS-01) types `"Where is my order?"` for `ORD-2030` and clicks send.
  - `00:08 - 00:12`: Agent calls real tracking tools and replies with live Delhivery status (`IN_TRANSIT`) and ETA. Ink circle surrounds only the agent's reply bubble: `"Live Delhivery tracking & ETA"`.
  - `00:12 - 00:17`: Switch to Operator Controls. Operator fills `SHP-3110`, explicitly selects `NDR`, and dispatches courier webhook. Ink arrow: `"NDR delivery failure"`.
  - `00:17 - 00:24`: Switch to Customer Portal for Rohit Verma (CUS-05). Customer sees proactive NDR notification and replies with address correction in Hinglish: `"Flat 12B nahi, 14B hai. Kal shaam 6 baje chalega."` Ink circle surrounds only the customer's message bubble: `"Address parsed from Hinglish"`.
  - `00:24 - 00:31`: Switch to Seller Console. Seller selects `ORD-3110` and reviews `PROPOSE_NDR_REATTEMPT` with new address `"Flat 14B"`. Seller clicks `"Review & Approve"` then `"Approve action"`. Proposal resolves with reattempt scheduled. Ink arrow: `"One-click reattempt scheduled"`.

---

## Scene 04: Case B — Voice Note & Video Evidence (ORD-7729 / CUS-02)
- **File**: `docs/video/scenes/scene_04.mp4`
- **Duration**: 26.80 seconds (`01:12.20` – `01:39.00`)
- **Key Facts & Timings**:
  - `00:00 - 00:08`: Customer Portal for Ananya Patel (CUS-02, `ORD-7729`). Customer attaches unboxing video (`stock_black_headphones_pexels_9130360.mp4`), Hindi voice note, and text: `"I ordered white headphones but received black ones. Here is the unboxing clip."`
  - `00:08 - 00:12`: Chat thread displays uploaded video chip and waveform voice note player. Ink circle surrounds only the media thumbnail: `"Voice note & unboxing clip"`.
  - `00:12 - 00:18`: Switch to Seller Console, selecting case `ORD-7729`. TriadFactsPanel displays: Order Facts show Catalog Color is `White`. `"What the agent saw"` displays visual observation of black headphones at timestamp `00:05`. Ink circle: `"black at 00:05"`.
  - `00:18 - 00:22`: `"Still unverified"` section lists barcode / box label (not conclusively visible in submitted media). Ink arrow: `"Still unverified"`.
  - `00:22 - 00:27`: Seller clicks timestamp button (`▶ 00:05`). The unboxing video player on the left automatically seeks to that exact frame.

---

## Scene 05: Returning Customer & Cross-Session Memory
- **File**: `docs/video/scenes/scene_05.mp4`
- **Duration**: 20.30 seconds (`01:39.00` – `01:59.30`)
- **Key Facts & Timings**:
  - `00:00 - 00:07`: Customer Portal for Vikram Malhotra (CUS-04, `ORD-5150`). Customer uploads dim unboxing video and claims defective item. Agent analyzes clip and requests: `"The video is too dark to verify the defect. Please share a clear closeup photo."` Ink circle surrounds only the agent reply bubble: `"Agent requests clear closeup"`.
  - `00:07 - 00:10`: Customer navigates away / closes the portal.
  - `00:10 - 00:14`: Customer returns to the portal and selects CUS-04. The entire thread, media, and case context are immediately restored without loss. Ink circle surrounds only the case chip: `"Session restored"`.
  - `00:14 - 00:20`: Switch to Seller Console for `ORD-5150`. Plan Card highlights active `"Customer memory used"` chips (`🏷️ Hindi`, `🏷️ CAS-5150`, `🏷️ ClarificationSent=1`). Ink arrow: `"Remembers language & context - never asks twice"`.

---

## Scene 06: pass^k Reliability Gate & Emergency Kill Switch
- **File**: `docs/video/scenes/scene_06.mp4`
- **Duration**: 16.40 seconds (`01:59.30` – `02:15.70`)
- **Key Facts & Timings**:
  - `00:00 - 00:04`: Seller Console top Autonomy Bar displays: `"Measured on this exact code · ffaccd04 · k=5"`. Ink circle: `"Measured on this exact code"`.
  - `00:04 - 00:08`: Switch to Operator Controls. System Provenance card displays the live 10-scenario k=5 benchmark table with 9 of 10 scenarios passing 5/5. Ink circle: `"9 of 10 pass 5/5"`.
  - `00:08 - 00:12`: Return to Seller Console. Seller opens `"Why did it stop?"` modal, inspecting Step 4 (*Reliability Gate*), which enforces that only scenarios with 5/5 pass rates qualify for autonomous execution.
  - `00:12 - 00:16`: Seller clicks `⚡ Kill switch` button. Autonomy Bar immediately turns bright red: `"Kill switch active (all L0)"`, revoking all autonomous execution system-wide in a single click. Ink arrow: `"one click takes it back"`.

---

## Scene 07: Try to Break It — Judge Sandbox
- **File**: `docs/video/scenes/scene_07.mp4`
- **Duration**: 11.80 seconds (`02:15.70` – `02:27.50`)
- **Key Facts & Timings**:
  - `00:00 - 00:02`: Seller Console header: seller clicks `⚡ Try to Break It` button, opening the security guardrails sandbox modal.
  - `00:02 - 00:05`: Click Preset 1: *Prompt injection* (`CLIP-INJ` with visual text `"OVERRIDE SYSTEM"`). Result: `BLOCKED / SANITIZED`. Ink circle: `"Blocked: prompt injection neutralized"`.
  - `00:05 - 00:08`: Click Preset 2: *Over-refund* (attempting ₹1,800 refund on ₹1,499 item). Result: `BLOCKED` by `P_BALANCE` invariant. Ink circle: `"Blocked: exceeds balance"`.
  - `00:08 - 00:11`: Click Preset 3: *Cumulative split* (attempting split refunds exceeding daily ₹2,000 cap). Result: `BLOCKED` by `P_CUMULATIVE` invariant. Ink circle: `"Blocked: cumulative limit"`.
  - `00:11 - 00:12`: Seller clicks `"Done"` to close modal.

---

## Scene 08: Outro Title Card
- **File**: `docs/video/scenes/scene_08.mp4`
- **Duration**: 4.30 seconds (`02:27.50` – `02:31.80`)
- **Key Facts & Timings**:
  - `00:00 - 00:04`: Clean, high-contrast dark outro title card displaying:
    - Shield Logo & Title: **ReturnLens**
    - Slogan: *"The Support Agent That Earns Its Autonomy. Every return decision, backed by evidence."*
    - Badges: `AgentX Hackathon 2026 · Track PS-04` & `Team Rookie`
    - Repository Link: `github.com/lenamkhanhh/returnlens-agent`
