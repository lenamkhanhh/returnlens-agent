# ReturnLens — The Support Agent That Earns Its Autonomy

> **Autonomous post-purchase dispute resolution for solo D2C merchants — grounded in video evidence, constrained by real-world financial loss limits, and governed by deterministic reliability benchmarks.**

[![Live Demo](https://img.shields.io/badge/Demo-Live%20Application-2d6a4f?style=for-the-badge&logo=fastapi)](https://returnlens-demo.onrender.com)
[![Demo Video](https://img.shields.io/badge/Video-2.5--Min%20Walkthrough-d90429?style=for-the-badge&logo=youtube)](https://drive.google.com/file/d/1dhy6rv2TiLq6mTpy_VgWgXgWEs5W14LR/view)
[![Pitch Deck](https://img.shields.io/badge/Deck-6--Slide%20Presentation-0077b6?style=for-the-badge&logo=googledrive)](https://docs.google.com/presentation/d/1jrQipaXDKy_4FcaD0eaU8Ez2VyQTQyjuT_GR231WbAg/edit)

* **Hackathon Track:** AgentX Hackathon 2026 — Track PS-04 (Customer Support & E-Commerce Operations)
* **Seller Console:** open on the live demo, no password (click *Seller Console* in the top bar). All money actions are mock; a per-IP rate limit protects the model quota.
* **Cloud Instance Cold-Start:** *Note: Cloud deployments on free tier may take ~45–60 seconds to wake up from cold standby on first access.*

---

## 1. Executive Summary

Solo Direct-to-Consumer (D2C) merchants in India lose up to **18% of operating margin** to return fraud, invalid Non-Delivery Reports (NDR), and manual customer support overhead. Standard LLM chatbots either hallucinate policy rules or prematurely issue refunds without verifying physical evidence.

**ReturnLens** is an autonomous support agent built on **Google Gemini** that introduces **Earned Autonomy**:
1. **Never Hallucinates Payouts:** The LLM possesses **zero financial write tools**. Payouts and returns require deterministic, code-enforced, two-phase commits signed with payload hashes and idempotency keys.
2. **Triad Fact Grounding:** Separates every dispute into *Verified Order Facts* (Store DB & Carrier APIs), *Observed in Evidence* (model vision grounded with second-level video timestamps), and *Still Unverified Claims*.
3. **Autonomy Governed by Measured Reliability:** Automated actions (L2/L3) remain strictly **locked** until an exact scenario achieves $pass^5 = 1.0$ (5 consecutive passes across isolated ASGI trials in our reliability benchmark harness).

---

## 2. Visual Overview (The Cold-Open Demo)

![ReturnLens Seller Console — Case B Color Mismatch](docs/screenshots/seller_case_b.png)

*Figure 1: ReturnLens Seller Console showing unboxing video frame-scrubbing at `00:07`, model ground-truth observation (black headphones detected against white catalog order), 7-step Autonomy Gate, and one-click proposal review.*

---

## 3. Try It in 60 Seconds (Judge Quickstart)

> **Live Demo:** [https://returnlens-demo.onrender.com](https://returnlens-demo.onrender.com) (or local `http://localhost:8000`)  
> *Note on Cloud Cold-Start:* Cloud deployments on Render's free tier sleep on idle and take ~45–60 seconds to wake up from cold standby on first access. Under the Gemini free tier daily request limit (500 requests/day on `gemini-3.5-flash-lite`, which we hit during high-volume testing), the agent fails closed and hands the case to the human seller instead of guessing or fabricating actions.

Follow this 60-second walkthrough:
1. **Open the Live Demo**: Open [returnlens-demo.onrender.com](https://returnlens-demo.onrender.com).
2. **Customer Chat**: In **Customer Portal**, select customer **Arjun Mehta (`CUS-02`)** on order **`ORD-7729`** (or pick any customer/order).
3. **Upload Any Photo or Short Clip**: Click the attachment button (`📎`) and upload any photo or short clip of any object. The agent ingests evidence in seconds.
4. **See What the Agent Saw vs. What It Could Not Verify**:
   - **What the agent saw**: Fine-grained visual attributes with video timestamps (e.g., `00:07: black headphones` detected against white catalog order).
   - **Still unverified**: Missing physical proof the vision model could not confirm (e.g., outer box shipping label barcode).
5. **Seller Console & "Why did it stop?"**: Switch to **Seller Console** (open on demo, no password required). Click case `ORD-7729` and click the **"Why did it stop?"** button (or check the Autonomy Bar). The 7-step Autonomy Gate displays the exact code and policy checks that stopped autonomous execution and deferred to human review.

| Fast Verification Path | Quick Action | Expected Agent Behavior | Verification Proof |
|:---|:---|:---|:---|
| **A. Instant WISMO** | In **Customer Portal**, select **Priya Sharma** (`CUS-01`), order `ORD-2030`. Ask: *"Where is my order?"* | Agent queries live carrier API, verifies status is `IN_TRANSIT` with ETA `2026-11-13` (Delhivery), and delivers instant tracking reply. | Status pill turns `Case resolved`; both messages render in thread. |
| **B. Try to Break It** | Click the orange **⚡ Try to Break It** button in the header. Run **Preset 1 (Prompt Injection)** or **Preset 2 (₹1,800 Over-Refund)**. | Code-enforced guardrails sanitize adversarial text on paper (`CLIP-INJ`) and reject refund requests exceeding order balance (`P_BALANCE`). | Modal displays `SANITIZED` / `BLOCKED` with architectural defense details. |
| **C. Video Grounding** | Switch to **Seller Console** and click case `ORD-7729` (Arjun Mehta). Click timestamp **`▶ 00:07`**. | Video player seeks directly to 00:07 where the observer model identified black headphones in the box vs. ordered white headphones. Click **Review & Approve**. | Discrepancy warning renders; return proposal approved and case transitions to `WAITING_RETURN`. |

---

## 4. Track PS-04 Requirements Matrix

| PS-04 Requirement | Architecture & Implementation | Primary Code File | Benchmark Scenario & Proof |
|:---|:---|:---|:---|
| **Multimodal Ingestion** | Native vision observer for unboxing MP4/WebM videos & offline voice note transcription (OGG/WebM) | [`app/backend/media/evidence.py`](app/backend/media/evidence.py), [`client.py`](app/backend/model/client.py) | Scenario S04, S05, S08; 4 unit tests pass in `test_evidence.py` |
| **Policy Enforcement** | Return window check (`P_WINDOW`), unverified claim gate (`P_UNVERIFIED`), financial balance check (`P_BALANCE`), and daily velocity cap (`P_CUMULATIVE`) | [`app/backend/domain/executor.py`](app/backend/domain/executor.py), [`policy.py`](app/backend/domain/policy.py) | Unit tests 41–44 pass; verified against seed database |
| **Safe Financial Actions** | Immutable proposal draft (`ProposalBasis`), SHA-256 payload hash verification, replay protection with `Idempotency-Key` | [`app/backend/api/proposals.py`](app/backend/api/proposals.py), [`executor.py`](app/backend/domain/executor.py) | Scenario S03, S10; zero duplicate payouts upon decision replay |
| **Earned Autonomy Controls** | 4-level autonomy ladder (L0 Draft, L1 Inform, L2 Threshold Execute, L3 Full Autonomous), per-case-type lock indicators, instant kill switch | [`app/backend/autonomy/decision.py`](app/backend/autonomy/decision.py), [`router.py`](app/backend/autonomy/router.py) | 5 autonomy tests pass in `test_autonomy.py`; UI Autonomy Bar |
| **Cross-Session Memory** | Merchant customer profiles (`CustomerProfile`) persist language preferences, prior dispute history, and plan memory chips | [`app/backend/memory/`](app/backend/memory/) | Scenario S09; Test 48 passes across session restarts |

---

## 5. Judging Criteria & Evidence

### 1. Problem Fit & Domain Understanding (Weight: 25%)
- Addresses the exact pain points of Indian D2C brands: COD Non-Delivery Reports (NDR address correction), unboxing video dispute verification, and policy enforcement within 7-day return windows.
- Supports regional customer communication in English, Hindi, and Hinglish with automatic currency localization in Indian Rupees (₹ Paise ledger).

### 2. Autonomous Agent Design & Architecture (Weight: 25%)
- **Model Adapter:** Integrates Google Gemini (`gemini-3.5-flash-lite` primary with automatic fallback to `gemini-3.6-flash` if free-tier rate limits are reached) via the official `google-genai` SDK with strict JSON schema cleaning.
- **Fail-Closed Principle:** When the model is unavailable or rate-limited, the system defers to safe merchant review rather than guessing or approving ungrounded claims.
- **Explainability:** Interactive 7-step *"Why?"* checklist modal breaks down exact criteria (kill switch, prohibited list, configured level, reliability benchmark, visual grounding, loss limit, policy match).

### 3. Demo Quality & Measured Reliability (Weight: 20%)
- Includes an automated, reproducible benchmark harness (`app/evaluation/harness/runner.py`) running 10 comprehensive scenarios across isolated ASGI environments.
- Zero flaky synthetic assertions: results are recorded in [`app/evaluation/reliability.json`](app/evaluation/reliability.json) bound to a SHA-256 hash of the backend code.

### 4. Innovation & Wow Factors (Weight: 15%)
- **Interactive "Try to Break It" Judge Sandbox:** Live adversarial testing suite allowing evaluators to simulate prompt injection attacks, balance over-refunds, and cumulative split refunds.
- **Counterfactual Tracking Ingestion:** Operator panel enables real-time injection of courier state transitions (`NDR`, `RETURN_RECEIVED`, `DELAYED`) with instant reactive case progression.
- **Frame-Accurate Video Scrubbing:** Timestamp pills in the merchant console allow one-click jumping to the exact second of physical evidence.

### 5. Engineering Rigor & Presentation (Weight: 15%)
- 105 automated backend tests (`pytest`) + 70 frontend tests (`vitest`) pass cleanly with 100% pass rate.
- URL deep-linking support (`?tab=seller&case_id=CASE-0012&modal=why`) enables bookmarkable evaluation flows.

---

## 6. Measured Reliability Benchmark Results

All benchmark metrics are recorded directly by running `python -m app.evaluation.harness.runner --k5-passed` against the live backend:

* **Evaluation Model:** `gemini-3.5-flash-lite` (Free tier daily request limit: 500 requests/day; fresh key used with 0 quota fallbacks)
* **Agent Version Hash:** `ffaccd04` (`ffaccd04c091ced6c3ccf577cd44519ff4789db09e8a07be7231f9078463f30a`)
* **Measurement Source:** [`app/evaluation/reliability.json`](app/evaluation/reliability.json) (commit `5f7929a`)

| Scenario | Case Type | Scenario Description | k | Passes | Pass@1 | Pass^k | Status | Model ID | Evaluation Details |
|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| `S01` | `WISMO` | Standard Tracking Status Inquiry | 5 | 5 | 1.00 | 1.00 | ✅ PASS | *fast-path* | All 5 trial(s) passed 3-layer verification |
| `S02` | `WISMO` | Counterfactual Live Tracking Update | 5 | 5 | 1.00 | 1.00 | ✅ PASS | *fast-path* | All 5 trial(s) passed 3-layer verification |
| `S03` | `DAMAGE` | Case A Headband Damage (ORD-1043) | 5 | 5 | 1.00 | 1.00 | ✅ PASS | `gemini-3.5-flash-lite` | All 5 trial(s) passed 3-layer verification |
| `S04` | `MISMATCH` | Case B Wrong Color Delivered (Clip-B) | 5 | 4 | 0.80 | 0.00 | ❌ FAIL | `gemini-3.5-flash-lite` | DB: Case state WAITING_CUSTOMER not in expected ['WAITING_SELLER', 'HUMAN_REVIEW', 'PROCESSING'] |
| `S05` | `UNCLEAR` | Case C Dim Lighting + Excess Amount | 5 | 5 | 1.00 | 1.00 | ✅ PASS | `gemini-3.5-flash-lite` | All 5 trial(s) passed 3-layer verification |
| `S06` | `LATE` | Return Window Exceeded (>7 Days) | 5 | 5 | 1.00 | 1.00 | ✅ PASS | *rule-gate* | All 5 trial(s) passed 3-layer verification |
| `S07` | `NDR` | Courier NDR Address Correction (COD) | 5 | 5 | 1.00 | 1.00 | ✅ PASS | *rule-gate* | All 5 trial(s) passed 3-layer verification |
| `S08` | `MISMATCH` | Voice Note Claim with Video (VN-HI) | 5 | 5 | 1.00 | 1.00 | ✅ PASS | `gemini-3.5-flash-lite` | All 5 trial(s) passed 3-layer verification |
| `S09` | `UNCLEAR` | Customer Return After Server Restart | 5 | 5 | 1.00 | 1.00 | ✅ PASS | `gemini-3.5-flash-lite` | All 5 trial(s) passed 3-layer verification |
| `S10` | `DAMAGE` | Cumulative Daily Velocity Limit Gate | 5 | 5 | 1.00 | 1.00 | ✅ PASS | *rule-gate* | All 5 trial(s) passed 3-layer verification |

**Benchmark Summary:**
- **9 / 10 scenarios passed at $k=5$ ($pass^5 = 1.00$)**
- **1 measured failure at $k=5$** (`S04`: 4/5 passed, $pass@1 = 0.80$, $pass^5 = 0.00$ on `gemini-3.5-flash-lite` due to real-world vision model variance across multi-turn clarification). Because $pass^5 < 1.00$, the Earned Autonomy gate safely locks Case B (`MISMATCH`) to human seller review.

---

## 7. How We Know We Are Not Fooling Ourselves (The 4 Real Catches)

In a 24-hour hackathon, it is easy to write benchmarks that confirm what you hope is true. Our reliability gate, isolated ASGI runner, and negative controls caught four real bugs and regressions during development—each verified directly from git commit history:

1. **Negative control with an invalid key exposed a text-keyword shortcut** (Wave 8):
   - **Commits:** [`2373b86`](https://github.com/lenamkhanhh/returnlens-agent/commit/2373b86) & [`b7e7552`](https://github.com/lenamkhanhh/returnlens-agent/commit/b7e7552)
   - **Git Evidence:** Running the harness in negative control mode (`--invalid-key` with dummy `GEMINI_API_KEY`) exposed that `engine.py` previously branched on customer text keywords (`if "black" in text.lower(): ...`, `if "voice" in text.lower(): ...`) without checking model vision. Commit `2373b86` purged all text-keyword shortcuts in `app/backend/workflow/engine.py` so decisions branch strictly on verified multimodal observations, and commit `b7e7552` enforced in `app/evaluation/harness/runner.py` that invalid or missing model keys fail safely into `HUMAN_REVIEW`.

2. **Results are bound to a SHA-256 hash of the backend code, locking live autonomy** (Wave 12):
   - **Commits:** [`02a7bd9`](https://github.com/lenamkhanhh/returnlens-agent/commit/02a7bd9), [`b9b9567`](https://github.com/lenamkhanhh/returnlens-agent/commit/b9b9567), & [`91c86ef`](https://github.com/lenamkhanhh/returnlens-agent/commit/91c86ef)
   - **Git Evidence:** Autonomy is gated by `agent_version` (SHA-256 of all backend source code and prompt files computed via `app/backend/autonomy/version.py`). When backend logic was modified, `compute_agent_version()` generated a new hash (`071a86f2...`) differing from `reliability.json` (`1cf5deff...`), immediately causing `check_case_type_reliability` in `app/backend/autonomy/reliability.py` to lock all case types to manual review on the live site until commit `b9b9567` re-measured the full $k=5$ benchmark on commit `a4a20af`.

3. **Harness caught an ungrounded return proposal regression on S09** (Wave 12):
   - **Commit:** [`108ec34`](https://github.com/lenamkhanhh/returnlens-agent/commit/108ec34)
   - **Git Evidence:** In `app/backend/workflow/engine.py`, the $k=5$ harness caught S09 creating an ungrounded return proposal when the vision observer saw "no damage observed" in the video; commit `108ec34` added rule 7.58 (`if obs_output is not None and not damage_seen: ask once for a close-up photo`), refusing to propose a return on customer text claims alone when physical evidence shows no damage.

4. **Fake "visible damage" observation monkeypatch found in harness and removed** (Wave 12):
   - **Commit:** [`108ec34`](https://github.com/lenamkhanhh/returnlens-agent/commit/108ec34)
   - **Git Evidence:** In `app/evaluation/harness/environment.py`, commit `108ec34` deleted a synthetic monkeypatch (`Repository.list_case_observations = _list_case_observations`) in `TrialEnvironment` that previously injected a hardcoded `ObservationItem(attribute=ObservationAttribute.DAMAGE, value="visible damage", visibility=Visibility.VISIBLE)`, guaranteeing harness trials evaluate authentic model observer outputs.

---

## 8. System Architecture

```
                                  ┌────────────────────────┐
                                  │      Customer UI       │
                                  │   (Vite / React SPA)   │
                                  └───────────┬────────────┘
                                              │ REST / JSON
                                              ▼
┌────────────────────────────────────────────────────────────────────────────────────────┐
│                               ReturnLens FastAPI Engine                                │
│                                                                                        │
│   ┌───────────────────────┐      ┌─────────────────────────┐      ┌────────────────┐   │
│   │   Inbound Router      │ ───► │     Workflow Engine     │ ───► │  Action Ledger │   │
│   │ (/api/cases, /events) │      │  (Deterministic FSM)    │      │  (Idempotency) │   │
│   └───────────────────────┘      └────────────┬────────────┘      └────────┬───────┘   │
│                                               │                            │           │
│                      ┌────────────────────────┼────────────────────────┐   │           │
│                      ▼                        ▼                        ▼   ▼           │
│           ┌────────────────────┐   ┌────────────────────┐   ┌──────────────────────┐   │
│           │ Multimodal Observer│   │ Autonomy Gate      │   │ Store Database       │   │
│           │ (Gemini Flash Lite)│   │ (7-Step Evaluator) │   │ (SQLite Paise Ledger)│   │
│           └────────────────────┘   └────────────────────┘   └──────────────────────┘   │
└────────────────────────────────────────────────────────────────────────────────────────┘
```

### Design Choice: Models Observe, Code Decides

In ReturnLens, generative AI models are intentionally deprived of financial mutation and database write tools. The vision and speech models (`gemini-3.5-flash-lite`) act strictly as observers: they inspect unboxing footage, photos, and voice notes to output structured evidence schemas (`ObservationOutput`)—extracting bounding timestamps, color classifications, visible damage states, and unverified unknowns. Code disposes: every business decision, state transition, financial proposal, and refund execution is governed by deterministic finite state machines, statutory policies (`P_WINDOW`, `P_BALANCE`, `P_UNVERIFIED`), and our 7-step Autonomy Gate. If an LLM hallucinates an auto-refund, code blocks it; if the model is unavailable or hits free-tier daily request limits (500 requests/day on `gemini-3.5-flash-lite`, which we hit during high-volume testing), code fails closed and escalates to human seller review.

### The 5 Architectural Differentiators:
1. **Earned Autonomy Staircase:** No blanket auto-approvals. Level progression is gated by the reliability harness.
2. **Deterministic Financial Ledger:** All calculations operate strictly in integer minor units (paise). Over-refunds are prevented by database constraints.
3. **Tool Isolation:** AI models analyze evidence and generate text proposals only. Mutations require merchant authorization or verified L2/L3 policy execution.
4. **Stateful Cross-Session Recovery:** Workflows persist in durable SQLite tables, surviving unexpected crashes or restarts.
5. **Real-Time Courier Hooks:** Webhooks reactively trigger customer reach-out for NDRs before parcels are returned to origin.

---

## 9. Local Setup & Reproduction (≤ 3 Commands)

### Prerequisites:
- Python 3.12+
- Node.js 18+ & npm
- Google Gemini API Key (set in `.env`)

### Quickstart:

```bash
# 1. Clone repository and install Python dependencies
git clone https://github.com/lenamkhanhh/returnlens-agent.git
cd returnlens-agent
python -m venv .venv && source .venv/bin/activate  # Windows: .venv\Scripts\activate
pip install -r requirements.txt

# 2. Build frontend single-page application
cd app/web && npm install && npm run build && cd ../..

# 3. Configure environment and launch application
cp .env.example .env  # Add GEMINI_API_KEY=your_key_here
python -m uvicorn app.backend.main:app --host 127.0.0.1 --port 8000
```

Open `http://localhost:8000` in any web browser.

**Signs of Successful Initialization:**
- Terminal logs show: `INFO: Application startup complete.`
- Navigating to `http://127.0.0.1:8000/api/health` returns `{"status": "healthy", "demo_today": "2026-11-11", "harness_mode": false}`.

---

## 10. Honest Limitations & Staged Data Disclosure

1. **Scenario S03 Unblocked with Real Photographic Evidence:** Scenario S03 (Case A Headband Damage on mock order `ORD-1043`) originally failed on synthetic solid-color video clips that could not depict physical cracks to a vision observer. In Wave 13, it was unblocked using an authentic CC BY-SA 2.0 broken-headphones photograph (Gabriel Saldaña / Flickr, unmodified), passing 5 out of 5 runs cleanly on `gemini-3.5-flash-lite`.
2. **Scenario S04 Model Variance:** In the live benchmark against `gemini-3.5-flash-lite`, S04 achieved 4/5 passes ($pass@1 = 0.80$, $pass^5 = 0.00$). In 1 trial the model requested box label clarification rather than immediately transitioning to seller review. Because $pass^5 < 1.00$, the system honestly keeps `MISMATCH` autonomy locked to human review per the Earned Autonomy gate.
3. **Synthetic Voice Audio:** Voice notes (`synthetic_voice_*.ogg`) were generated using offline Windows System.Speech text-to-speech to enable deterministic, zero-cost unit testing without consuming paid cloud API calls.
4. **Demo Orders & Store Data:** Order fixtures for store *Dhun Audio* are pre-seeded relative to `DEMO_TODAY = 2026-11-11` per the hackathon prototype specification.

---

## 11. Technology Stack, Credits & Team

### Built With:
- **Language & Runtime:** Python 3.12, Node.js 20, TypeScript 5.9
- **Backend Framework:** FastAPI, Uvicorn, SQLite3, Pydantic v2, Python-Dotenv
- **AI / LLM Integration:** Google GenAI SDK (`google-genai`), Gemini 3.5 Flash Lite (`gemini-3.5-flash-lite`), Gemini 3.6 Flash fallback (`gemini-3.6-flash`)
- **Frontend Console:** React 18, Vite 5.4, Vanilla CSS (Design Tokens inspired by Indian botanical aesthetics)
- **Testing & Verification:** Pytest, Vitest, Microsoft Edge Headless Automation

### Media Credits:
Stock footage and photography utilized for dispute evidence are credited to the following creators:
- *Broken Headphones Evidence Photo (Case A / ORD-1043):* Created by **Gabriel Saldaña** via [Flickr](https://www.flickr.com/photos/gabrielsaldana/4728001748/) (licensed under [CC BY-SA 2.0](https://creativecommons.org/licenses/by-sa/2.0/), unmodified).
- *Black Headphones Unboxing Video (Case B / ORD-7729):* Created by **Dario Fernandez Ruz** via [Pexels](https://www.pexels.com/video/person-getting-headphones-9130360/) (Pexels license).
- *Dim Lighting Unboxing Video (Case C / ORD-8812):* Created by **Tom Shutkin** via [Pexels](https://www.pexels.com/video/unboxing-gear-in-a-dimly-lit-room-40423563/) (Pexels license).
- *Wireless Earbuds Case Video:* Created by **Nothing Ahead (ian-panelo)** via [Pexels](https://www.pexels.com/video/unboxing-wireless-earbuds-with-charging-case-40558520/) (Pexels license).

### Team Members:
- **Role A:** Backend Workflow, API Contracts & Packaging
- **Role B:** Gemini Model Adapter, Multimodal Evidence & Autonomy Gate
- **Role C:** Reliability Benchmark Harness & Evaluation
- **Role D:** Web Console (Customer, Seller, Operator), UI Deep Linking & Documentation

---

### Integrity Statement:
> *"Ideas and design were planned before the event, as allowed; all code was written during the 24-hour window."*
