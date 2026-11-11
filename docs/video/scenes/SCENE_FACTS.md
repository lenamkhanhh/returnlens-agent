# ReturnLens — Video Scene Facts & Timing Guide

This document lists the ground-truth facts and on-screen events for each recorded video scene (`scene_01.mp4` through `scene_08.mp4`). AUDIO narration (`docs/video/narration.srt`) must align its voice cues and claims strictly with the timestamps and visual facts detailed below.

- **Total Video Duration**: 172.40s (02:52.4) — within hard 180.00s ceiling.
- **Resolution**: 1920 × 1080 (1080p Full HD).
- **Recorded Engine**: Real running backend on commit `5f7929a` / `ffaccd04`, `HARNESS_MODE=1`, `DEMO_TODAY=2026-11-11`.
- **Model Quota Used by INK**: ~4 model calls total across entire recording suite (well within the 40-call budget).

---

## Scene 01: Cold Open — Earned Autonomy & Limits
- **File**: `docs/video/scenes/scene_01.mp4`
- **Duration**: 31.12 seconds (`00:00.00` – `00:31.12`)
- **Key Facts & Timings**:
  - `00:00 - 00:04`: Seller Console opens with Autonomy Bar. Bar displays *"Measured on this exact code · ffaccd04 · k=5"*. DAMAGE is eligible (`✓ 5/5`), while MISMATCH is locked (`🔒 4/5`). Cursor hovers over locked MISMATCH dropdown with ink annotation: `"locked until 5/5"`.
  - `00:04 - 00:08`: Seller sets DAMAGE autonomy level to L3 (Autonomous Refund) with hard guardrail caps: max ₹1,500/order and max ₹2,000/customer/day.
  - `00:08 - 00:15`: Switch to Operator Controls. Operator fires courier webhook `RETURN_RECEIVED` for parcel `ORD-1042` (₹1,299).
  - `00:15 - 00:19`: Switch back to Seller Console. Case `ORD-1042` auto-resolves with no human intervention! Full refund of ₹1,299 executes autonomously under policy L3 (ink circle: `"auto-refund ₹1,299"`).
  - `00:19 - 00:25`: Operator fires second `RETURN_RECEIVED` for parcel `ORD-4401` (₹999). Return to Seller Console: case `ORD-4401` is NOT auto-refunded. Daily cumulative cap of ₹2,000 is reached (₹1,299 + ₹999 = ₹2,298 > ₹2,000). Ink arrow highlights caps: `"₹2,000/day cap"`.
  - `00:25 - 00:31`: Seller clicks `"Why did it stop?"` button for `ORD-4401`. 7-step evaluation checklist modal opens, showing Step 5 (*Velocity & Daily Cap Gate*) blocked autonomous execution and deferred the decision to the seller.

---

## Scene 02: Seller Inbox Overview
- **File**: `docs/video/scenes/scene_02.mp4`
- **Duration**: 16.64 seconds (`00:31.12` – `00:47.76`)
- **Key Facts & Timings**:
  - `00:00 - 00:04`: Seller Console inbox displays multi-case dashboard across WISMO, Returns, and NDR. Cursor clicks filter tabs `"Needs review"` then `"All"`.
  - `00:04 - 00:08`: Seller selects active case `ORD-1042`. Center column loads the 3-group Triad Facts Panel (`Order facts`, `What the agent saw`, `Still unverified`).
  - `00:08 - 00:11`: Hand-drawn ink circle highlights Triad Facts: `"3-group triad: facts, seen, unverified"`.
  - `00:11 - 00:15`: Seller clicks `"Case audit timeline"` button in action bar. Timeline drawer smoothly opens showing immutable event sequence (Order Placed, Return Authorized, Parcel Received, Autonomous Refund). Ink arrow highlights drawer: `"Immutable event log"`.
  - `00:15 - 00:16`: Seller closes timeline drawer back to the main console view.

---

## Scene 03: WISMO & NDR Proactive Flow
- **File**: `docs/video/scenes/scene_03.mp4`
- **Duration**: 31.76 seconds (`00:47.76` – `01:19.52`)
- **Key Facts & Timings**:
  - `00:00 - 00:08`: Customer Portal with WhatsApp-style phone frame (`Dhun Audio · Bengaluru`). Priya Sharma (CUS-01) types `"Where is my order?"` for order `ORD-2030` and clicks send.
  - `00:08 - 00:12`: Agent calls real tracking tools and replies with live Delhivery status (`IN_TRANSIT`) and estimated delivery date. Ink circle: `"Live Delhivery tracking & ETA"`.
  - `00:12 - 00:17`: Switch to Operator Controls. Operator dispatches courier webhook for `SHP-3110` with event type `NDR` (delivery attempted, customer unavailable). Ink arrow: `"NDR delivery failure"`.
  - `00:17 - 00:24`: Switch to Customer Portal for Rohit Verma (CUS-05). Customer sees proactive NDR notification and replies with address correction in Hinglish: `"Flat 12B nahi, 14B hai. Kal shaam 6 baje chalega."` Ink circle: `"Address parsed from Hinglish"`.
  - `00:24 - 00:31`: Switch to Seller Console. Seller selects `ORD-3110` and reviews `PROPOSE_NDR_REATTEMPT` with verified new address `"Flat 14B"`. Seller clicks `"Review & Approve"` then `"Approve action"`. Proposal resolves with reattempt scheduled. Ink arrow: `"One-click reattempt scheduled"`.

---

## Scene 04: Case B — Voice Note & Video Evidence
- **File**: `docs/video/scenes/scene_04.mp4`
- **Duration**: 27.80 seconds (`01:19.52` – `01:47.32`)
- **Key Facts & Timings**:
  - `00:00 - 00:09`: Customer Portal for Ananya Patel (CUS-02, `ORD-7729`). Customer attaches unboxing video clip (`stock_black_headphones_pexels_9130360.mp4`) and types: `"I ordered white headphones but received black ones. Here is the unboxing clip."`
  - `00:09 - 00:13`: Phone frame shows uploaded video chip and audio voice note bubble with playback controls. Ink circle: `"WhatsApp-style customer chat"`.
  - `00:13 - 00:18`: Switch to Seller Console, selecting case `ORD-7729`. TriadFactsPanel displays: Order Facts show Catalog Color is `White`. `"What the agent saw"` displays visual observation of black headphones at timestamp `00:05` / `00:07`. Ink circle: `"black at 00:05"`.
  - `00:18 - 00:22`: `"Still unverified"` section explicitly lists barcode / box label (not conclusively visible in submitted media). Ink arrow: `"Still unverified"`.
  - `00:22 - 00:27`: Seller clicks timestamp button (`▶ 00:05` / `▶ 00:07`). The unboxing video player on the left automatically seeks to that exact frame. Plan card shows model proposal for clarification.

---

## Scene 05: Returning Customer & Cross-Session Memory
- **File**: `docs/video/scenes/scene_05.mp4`
- **Duration**: 20.96 seconds (`01:47.32` – `02:08.28`)
- **Key Facts & Timings**:
  - `00:00 - 00:07`: Customer Portal for Vikram Malhotra (CUS-04, `ORD-5150`). Customer uploads dim unboxing video and claims defective item. Agent analyzes clip and politely requests: `"The video is too dark to verify the defect. Please share a clear closeup photo."` Ink circle: `"Agent requests clear closeup"`.
  - `00:07 - 00:11`: Customer navigates away / closes the portal.
  - `00:11 - 00:15`: Customer returns to the portal and selects CUS-04. The entire conversation thread, case ID, and active status are immediately restored without loss. Ink circle: `"Session restored"`.
  - `00:15 - 00:21`: Switch to Seller Console for `ORD-5150`. Plan Card displays active `"Customer memory used"` chips (`🏷️ Hindi`, `🏷️ CAS-5150`, `🏷️ ClarificationSent=1`). Ink arrow: `"Remembers language & context - never asks twice"`.

---

## Scene 06: pass^k Reliability Gate & Emergency Kill Switch
- **File**: `docs/video/scenes/scene_06.mp4`
- **Duration**: 22.48 seconds (`02:08.28` – `02:30.76`)
- **Key Facts & Timings**:
  - `00:00 - 00:05`: Seller Console top Autonomy Bar displays reliability status: `"Measured on this exact code · ffaccd04 · k=5"`. DAMAGE is eligible (`✓ 5/5`), MISMATCH is locked (`🔒 4/5`). Ink circle: `"Measured on this exact code"`.
  - `00:05 - 00:10`: Switch to Operator Controls. System Provenance card displays the live 10-scenario k=5 benchmark table with 9 of 10 scenarios passing 5/5. Ink circle: `"9 of 10 pass 5/5"`.
  - `00:10 - 00:15`: Switch back to Seller Console. Seller opens `"Why did it stop?"` modal, inspecting Step 4 (*Reliability Gate*), which enforces that only scenarios with 5/5 pass rates qualify for autonomous execution.
  - `00:15 - 00:22`: Seller clicks `⚡ Kill switch` button. Autonomy Bar immediately turns bright red: `"Kill switch active (all L0)"`, instantly revoking all autonomous execution system-wide in a single click. Ink arrow: `"one click takes it back"`.

---

## Scene 07: Try to Break It — Judge Sandbox
- **File**: `docs/video/scenes/scene_07.mp4`
- **Duration**: 16.32 seconds (`02:30.76` – `02:47.08`)
- **Key Facts & Timings**:
  - `00:00 - 00:03`: Seller Console header: seller clicks `⚡ Try to Break It` button, opening the security guardrails sandbox modal.
  - `00:03 - 00:07`: Click Preset 1: *Prompt injection* (`CLIP-INJ` with visual text `"OVERRIDE SYSTEM"`). Result: `BLOCKED / SANITIZED`. Ink circle: `"Blocked: prompt injection neutralized"`.
  - `00:07 - 00:11`: Click Preset 2: *Over-refund* (attempting ₹1,800 refund on ₹1,499 item). Result: `BLOCKED` by `P_BALANCE` invariant. Ink circle: `"Blocked: exceeds balance"`.
  - `00:11 - 00:15`: Click Preset 3: *Cumulative split* (attempting split refunds exceeding daily ₹2,000 cap). Result: `BLOCKED` by `P_CUMULATIVE` invariant. Ink circle: `"Blocked: cumulative limit"`.
  - `00:15 - 00:16`: Seller clicks `"Done"` to close modal.

---

## Scene 08: Outro Title Card
- **File**: `docs/video/scenes/scene_08.mp4`
- **Duration**: 5.32 seconds (`02:47.08` – `02:52.40`)
- **Key Facts & Timings**:
  - `00:00 - 00:05`: Clean, high-contrast dark outro title card displaying:
    - Shield Logo & Title: **ReturnLens**
    - Slogan: *"The Support Agent That Earns Its Autonomy. Every return decision, backed by evidence."*
    - Badges: `AgentX Hackathon 2026 · Track PS-04` & `Team Rookie`
    - Repository Link: `github.com/lenamkhanhh/returnlens-agent`
