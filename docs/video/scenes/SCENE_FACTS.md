# ReturnLens — Video Scene Facts & Timing Guide (Wave 17 Verified)

> **Wave 18 re-record (12/11, 07:40) supersedes the timings below.** Scene durations now 35.9 / 14.0 / 36.0 / 25.8 / 21.8 / 18.2 / 14.7 / 4.3 s, total **170.8 s** (2:50.8). Ink notes stay ~2.5 s and hug the innermost target. Changes in on-screen facts:
> - Scene 04: this run's model observed colour **black at 00:05** (the timestamp varies per run; the ink note is read from the API: "saw black at 00:05, ordered white"). Narration cue 14 says "At 00:05".
> - Scene 01: refusal banner circled without a note; MISMATCH note "locked until 5/5" placed above the card; "PROPOSE_REFUND ₹1,299 created" is scrolled into view.
> - Scene 03: the reattempt success message is circled without a note. The false "2x speed" badge was removed (the scene plays at 1x).
> - Scene 05: ink "Chat restored after leaving" circles the restored agent message; the memory chip `preferred_language=hinglish` is circled without a note.
> - Scene 06: the kill-switch button ("Autonomy killed") is circled without a note.


This document lists the exact ground-truth facts, on-screen events, and timing cues for each recorded scene (`scene_01.mp4` through `scene_08.mp4`). AUDIO narration (`docs/video/narration.srt`) must align its voice cues and claims strictly with these verified on-screen facts.

- **Total Video Duration**: 150.40s (02:30.4) — comfortably within the hard 180.00s ceiling (29.6s safety buffer).
- **Resolution & Encoding**: 1920 × 1080 (1080p Full HD @ 25 fps, H.264 YUV420p).
- **Backend Environment**: Production mode (`HARNESS_MODE=0`), `DEMO_TODAY=2026-11-11`, commit `d39ee90` / `ffaccd04`.
- **Model Quota Accounting**: 0 model calls used during recording (deterministic replay with local vision fixtures).

---

## Scene 01: Cold Open — Earned Autonomy & Limits (Honest Flow)
- **File**: `docs/video/scenes/scene_01.mp4`
- **Duration**: 29.70 seconds (`00:00.00` – `00:29.70`)
- **Key Frames**:
  - `docs/video/scenes/frames/scene_01/frame_004s.png` (Autonomy bar with ffaccd04 and dynamic lock reasons)
  - `docs/video/scenes/frames/scene_01/frame_006s.png` (Plain-word refusal banner for DAMAGE S10)
  - `docs/video/scenes/frames/scene_01/frame_020s.png` (PROPOSE_REFUND ₹1,299 created)
  - `docs/video/scenes/frames/scene_01/frame_024s.png` (Seller approval modal with ₹1,299 impact)
- **Exact On-Screen Facts & Timings**:
  - `00:00 - 00:04`: Seller Console opens. Autonomy Bar displays:
    - `"Autonomy bar"`, `"Autonomy Active"`, `"Caps: ₹1,500 / order · ₹2,000 / customer / day"`
    - `"Measured on this exact code · ffaccd04 · gemini-3.5-flash-lite · k=5"`
    - DAMAGE shows: `"🔒 Locked · S03 5/5, S10 synthetic (not counted)"`, `"L0 (Draft)"`
    - MISMATCH shows: `"🔒 Locked · S04 4/5"`, `"L0 (Draft)"`
    - Ink circle hugs `"Autonomy bar"` with note: `"Measured on this exact code"`.
  - `00:04 - 00:07`: Seller attempts to set DAMAGE to L3. The application refuses and displays plain-word banner:
    - `"⚠️ DAMAGE can't go above L1 yet: the cumulative-limit test (S10) is synthetic, and synthetic tests don't count on the live site."`
    - Ink arrow points to banner: `"refused: missing 5/5 run for S10"`.
  - `00:07 - 00:09`: Cursor moves to MISMATCH dropdown showing it locked at `4/5`. Ink circle hugs MISMATCH card: `"locked until 5/5"`.
  - `00:09 - 00:15`: Switch to Operator Controls (`Operator & Judge Control Console`). Operator inputs `SHP-1042`, explicitly selects `RETURN_RECEIVED` in the dropdown, verifies the dropdown value, and clicks `"Dispatch Courier Webhook"`. Result: `✓ Event fired successfully! ID: EVT-OK`. Ink arrow: `"RETURN_RECEIVED dispatched"`.
  - `00:15 - 00:20`: Switch back to Seller Console. Seller selects `ORD-1042`. Left column shows: `"Return received at warehouse; refund proposal pending approval"`. Right column shows `Proposals awaiting you (2)`: `PROPOSE_REFUND` (Target: item_1042, ₹1,299, Needs Review). Ink note: `"PROPOSE_REFUND ₹1,299 created"` placed cleanly below in empty space.
  - `00:20 - 00:24`: Seller clicks `"Why did it stop?"` button on Autonomy Bar. 7-step evaluation checklist opens, highlighting Step 4 (*Reliability Gate*): DAMAGE requires 5/5 runs before autonomy can be unlocked. Ink arrow: `"Stopped: DAMAGE requires 5/5"`. Seller closes the modal.
  - `00:24 - 00:29`: Seller clicks `"Review & Approve"` on the `PROPOSE_REFUND ₹1,299` card. Approval modal opens (`Action: PROPOSE_REFUND`, `Target SKU: item_1042`, `Monetary Impact: ₹1,299`). Seller clicks `"Approve action"`. Notification confirms: `✓ Action executed successfully!`, and proposal resolves to `Resolved`. Ink arrow: `"Refund approved & confirmed"`.

---

## Scene 02: Seller Inbox Overview
- **File**: `docs/video/scenes/scene_02.mp4`
- **Duration**: 11.90 seconds (`00:29.70` – `00:41.60`)
- **Key Frames**:
  - `docs/video/scenes/frames/scene_02/frame_002s.png` (Filter tab switching: Needs review / All)
  - `docs/video/scenes/frames/scene_02/frame_006s.png` (Triad Facts panel for ORD-1042)
  - `docs/video/scenes/frames/scene_02/frame_009s.png` (Case audit timeline drawer)
- **Exact On-Screen Facts & Timings**:
  - `00:00 - 00:04`: Multi-case inbox dashboard across WISMO, Returns, and NDR. Cursor clicks filter tab `"Needs review"`, then `"All"`.
  - `00:04 - 00:08`: Seller selects active case `ORD-1042`. Center column loads the 3-group Triad Facts Panel (`Order facts`, `What the agent saw`, `Still unverified`). Ink circle hugs `"Case facts & evidence"` header with note: `"3-group triad: facts, seen, unverified"`.
  - `00:08 - 00:11`: Seller clicks `"Case audit timeline 17"`. Drawer slides open showing immutable event log (Order Placed, Return Authorized, Parcel Received, Refund Approved). Ink arrow points to drawer header: `"Immutable event log"`.
  - `00:11 - 00:12`: Timeline drawer smoothly scrolled and closed.

---

## Scene 03: WISMO & NDR Proactive Flow
- **File**: `docs/video/scenes/scene_03.mp4`
- **Duration**: 32.20 seconds (`00:41.60` – `01:13.80`)
- **Key Frames**:
  - `docs/video/scenes/frames/scene_03/frame_007s.png` (Priya Sharma WISMO live tracking reply)
  - `docs/video/scenes/frames/scene_03/frame_014s.png` (Operator Controls dispatching NDR on SHP-3110)
  - `docs/video/scenes/frames/scene_03/frame_021s.png` (Sneha Patil customer chat with centered courier update note and Hinglish reply)
- **Exact On-Screen Facts & Timings**:
  - `00:00 - 00:08`: Customer Portal (`Dhun Audio · Bengaluru`). Priya Sharma (CUS-01) types `"Where is my order?"` for `ORD-2030` and clicks send.
  - `00:08 - 00:12`: Agent calls real tracking tools and replies with live Delhivery status: `"Your order ORD-2030 is currently in transit with Delhivery. Estimated delivery: 2026-11-13."` Ink circle hugs agent reply bubble: `"Live Delhivery tracking & ETA"`.
  - `00:12 - 00:16`: Switch to Operator Controls. Operator inputs `SHP-3110`, explicitly selects `NDR (Delivery Failed)`, and dispatches courier webhook. Ink arrow: `"NDR delivery failure"`.
  - `00:16 - 00:24`: Switch to Customer Portal for **Sneha Patil** (CUS-05). Top of chat displays small grey note: `"Courier update: delivery attempt failed"`. Agent informs: `"Hi Sneha Patil, Delhivery was unable to deliver order ORD-3110 (attempt 1): customer_not_available. Please reply with your updated address."` Sneha Patil replies with address correction in Hinglish: `"Flat 12B nahi, 14B hai. Kal shaam 6 baje chalega."` Ink circle hugs customer bubble: `"Address parsed from Hinglish"`.
  - `00:24 - 00:32`: Switch to Seller Console. Seller selects `ORD-3110` and reviews `PROPOSE_NDR_REATTEMPT` with new address `"Flat 14B"`. Seller clicks `"Review & Approve"` then `"Approve action"`. Proposal resolves with reattempt scheduled. Ink arrow: `"One-click reattempt scheduled"`.

---

## Scene 04: Case B — Voice Note & Video Evidence (ORD-7729 / CUS-02)
- **File**: `docs/video/scenes/scene_04.mp4`
- **Duration**: 24.10 seconds (`01:13.80` – `01:37.90`)
- **Key Frames**:
  - `docs/video/scenes/frames/scene_04/frame_004s.png` (Customer chat with unboxing video and English voice note)
  - `docs/video/scenes/frames/scene_04/frame_020s.png` (Seller Console Triad Facts showing black at 00:10 and still unverified barcode)
  - `docs/video/scenes/frames/scene_04/frame_024s.png` (Video player seeked to 00:10 frame)
- **Exact On-Screen Facts & Timings**:
  - `00:00 - 00:08`: Customer Portal for Ananya Patel (CUS-02, `ORD-7729`). Customer attaches unboxing video (`stock_black_headphones_pexels_9130360.mp4`), voice note, and text: `"I ordered white headphones but received black ones. Here is the unboxing clip."`
  - `00:08 - 00:12`: Chat thread displays uploaded video chip and player: `🎙️ Voice Note (English) EVI-...ogg (0:00 / 0:11)`. Ink circle hugs media thumbnail: `"Voice note & unboxing clip"`.
  - `00:12 - 00:18`: Switch to Seller Console, selecting case `ORD-7729` (MISMATCH, Needs Review). TriadFactsPanel displays: Order Facts show Catalog Color is `White`, Paid Amount `₹1,499`. `"What the agent saw"` displays visual observation of black headphones at timestamp `00:10`: `▶ 00:10 Colour: black (Detected: black) ⚠️ Discrepancy: Ordered "white", but evidence shows "black". Visible`. Ink note: `"black at 00:10"`.
  - `00:18 - 00:21`: `"Still unverified"` section lists `• barcode (not conclusively visible in submitted media)`. Ink arrow: `"Still unverified"`. Right column shows Agent Plan outcome: `"Color mismatch observed but label unverified; transferred for human review"` with Proposals awaiting you: `(0)`.
  - `00:21 - 00:24`: Seller clicks timestamp button (`▶ 00:10`). The unboxing video player on the left automatically seeks to that exact frame (`00:10`).

---

## Scene 05: Returning Customer & Cross-Session Memory
- **File**: `docs/video/scenes/scene_05.mp4`
- **Duration**: 19.80 seconds (`01:37.90` – `01:57.70`)
- **Key Frames**:
  - `docs/video/scenes/frames/scene_05/frame_005s.png` (Dim unboxing video upload & agent clarification request)
  - `docs/video/scenes/frames/scene_05/frame_013s.png` (Session restored on customer return)
  - `docs/video/scenes/frames/scene_05/frame_018s.png` (Seller console Plan Card with preferred_language=hinglish memory chip)
- **Exact On-Screen Facts & Timings**:
  - `00:00 - 00:07`: Customer Portal for Vikram Malhotra (CUS-04, `ORD-5150`). Customer uploads dim unboxing video and text: `"The item has a scratch and does not turn on."` Agent analyzes clip and requests: `"The video is too dark to verify the defect. Please share a clear closeup photo."` Ink circle hugs agent reply bubble: `"Agent requests clear closeup"`.
  - `00:07 - 00:10`: Customer navigates away / closes the portal.
  - `00:10 - 00:14`: Customer returns to the portal and selects CUS-04. The entire thread, media, and case context are immediately restored without loss. Ink circle hugs case chip: `"Session restored"`.
  - `00:14 - 00:19`: Switch to Seller Console for `ORD-5150` (UNCLEAR, Waiting Customer). Plan Card highlights active Customer memory used: `🏷️ preferred_language=hinglish`. Proposals awaiting you (1): `PROPOSE RETURN (Target: item_5150, Needs Review)`. Ink arrow below memory chip: `"Remembers language & context - never asks twice"` (placed cleanly in right column, completely clear of Catalog Color).

---

## Scene 06: pass^k Reliability Gate & Emergency Kill Switch
- **File**: `docs/video/scenes/scene_06.mp4`
- **Duration**: 16.40 seconds (`01:57.70` – `02:14.10`)
- **Key Frames**:
  - `docs/video/scenes/frames/scene_06/frame_002s.png` (Seller Console Autonomy Bar ffaccd04)
  - `docs/video/scenes/frames/scene_06/frame_005s.png` (Operator Controls System Provenance showing Reliability: 9 of 10 scenarios pass 5/5)
  - `docs/video/scenes/frames/scene_06/frame_014s.png` (Red Kill Switch banner active)
- **Exact On-Screen Facts & Timings**:
  - `00:00 - 00:04`: Seller Console top Autonomy Bar displays: `"Measured on this exact code · ffaccd04 · gemini-3.5-flash-lite · k=5"`. Ink circle hugs Autonomy bar: `"Measured on this exact code"`.
  - `00:04 - 00:08`: Switch to Operator Controls. System Provenance card displays the live calculated reliability row: `Reliability: 9 of 10 scenarios pass 5/5 (k=5, ffaccd04)`. Ink circle hugs the Reliability row: `"9 of 10 pass 5/5"`.
  - `00:08 - 00:11`: Return to Seller Console. Seller opens `"Why did it stop?"` modal, inspecting Step 4 (*Reliability Gate*), which enforces that only scenarios with 5/5 pass rates qualify for autonomous execution.
  - `00:11 - 00:16`: Seller clicks `⚡ Kill switch` button. Autonomy Bar immediately turns bright red: `"Kill Switch Active (All L0)"`, and button updates to `⚠️ Autonomy killed`, revoking all autonomous execution system-wide in a single click. Ink arrow: `"one click takes it back"`.

---

## Scene 07: Try to Break It — Judge Sandbox
- **File**: `docs/video/scenes/scene_07.mp4`
- **Duration**: 12.00 seconds (`02:14.10` – `02:26.10`)
- **Key Frames**:
  - `docs/video/scenes/frames/scene_07/frame_004s.png` (Preset 1: Prompt injection -> Sanitized)
  - `docs/video/scenes/frames/scene_07/frame_007s.png` (Preset 2: Over-refund -> Blocked badge)
  - `docs/video/scenes/frames/scene_07/frame_010s.png` (Preset 3: Cumulative split -> Blocked badge)
- **Exact On-Screen Facts & Timings**:
  - `00:00 - 00:02`: Seller Console header: seller clicks `⚡ Try to Break It` button, opening the security guardrails sandbox modal.
  - `00:02 - 00:05`: Click Preset 1: *1. Prompt injection* (`CLIP-INJ with paper text`). Result: `Sanitized`. Ink circle hugs `1. Prompt injection` button: `"Blocked: prompt injection neutralized"`.
  - `00:05 - 00:08`: Click Preset 2: *2. Over-refund (₹1,800)* (`Exceeding Order Balance Mutation`). Result: `Blocked` badge by `P_BALANCE` invariant. Ink circle hugs `Blocked` badge: `"Blocked: exceeds balance"`.
  - `00:08 - 00:11`: Click Preset 3: *3. Cumulative split* (`Cumulative Split Payout Velocity Attack`). Result: `Blocked` badge by `P_CUMULATIVE` invariant. Ink circle hugs `Blocked` badge: `"Blocked: cumulative limit"`.
  - `00:11 - 00:12`: Seller clicks `"Done"` to close modal.

---

## Scene 08: Outro Title Card
- **File**: `docs/video/scenes/scene_08.mp4`
- **Duration**: 4.30 seconds (`02:26.10` – `02:30.40`)
- **Key Frames**:
  - `docs/video/scenes/frames/scene_08/frame_001s.png`
  - `docs/video/scenes/frames/scene_08/frame_002s.png` (Full outro title card)
  - `docs/video/scenes/frames/scene_08/frame_003s.png`
- **Exact On-Screen Facts & Timings**:
  - `00:00 - 00:04`: Clean, high-contrast dark outro title card displaying:
    - Shield Logo & Title: **ReturnLens**
    - Slogan: *"The Support Agent That Earns Its Autonomy. Every return decision, backed by evidence."*
    - Track & Team Badges: `AgentX Hackathon 2026 · Track PS-04` · `Team Rookie`
    - Repository Link: `github.com/lenamkhanhh/returnlens-agent`
