# ReturnLens — The Support Agent That Earns Its Autonomy

> **Autonomous post-purchase dispute resolution for solo D2C merchants — grounded in video evidence, constrained by real-world financial loss limits, and governed by deterministic reliability benchmarks.**

[![Live Demo](https://img.shields.io/badge/Demo-Live%20Application-2d6a4f?style=for-the-badge&logo=fastapi)](TODO:Coordinator_Live_Demo_URL)
[![Demo Video](https://img.shields.io/badge/Video-2.5--Min%20Walkthrough-d90429?style=for-the-badge&logo=youtube)](https://drive.google.com/file/d/1dhy6rv2TiLq6mTpy_VgWgXgWEs5W14LR/view)
[![Pitch Deck](https://img.shields.io/badge/Deck-6--Slide%20Presentation-0077b6?style=for-the-badge&logo=googledrive)](https://docs.google.com/presentation/d/1jrQipaXDKy_4FcaD0eaU8Ez2VyQTQyjuT_GR231WbAg/edit)

* **Hackathon Track:** AgentX Hackathon 2026 — Track PS-04 (Customer Support & E-Commerce Operations)
* **Merchant Console Credentials:** `SELLER_DEMO_PASSWORD=demo` (or click *Seller Console* in navigation)
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

When accessing the running application at `http://localhost:8000`:

| Step | Action | Expected Agent Behavior | Verification Proof |
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
- Zero flaky synthetic assertions: results are recorded in [`app/evaluation/reliability.json`](app/evaluation/reliability.json) with cryptographic agent version hashing.

### 4. Innovation & Wow Factors (Weight: 15%)
- **Interactive "Try to Break It" Judge Sandbox:** Live adversarial testing suite allowing evaluators to simulate prompt injection attacks, balance over-refunds, and cumulative split refunds.
- **Counterfactual Tracking Ingestion:** Operator panel enables real-time injection of courier state transitions (`NDR`, `RETURN_RECEIVED`, `DELAYED`) with instant reactive case progression.
- **Frame-Accurate Video Scrubbing:** Timestamp pills in the merchant console allow one-click jumping to the exact second of physical evidence.

### 5. Engineering Rigor & Presentation (Weight: 15%)
- 94 automated backend tests (`pytest`) + 39 frontend tests (`vitest`) pass cleanly with 100% pass rate.
- URL deep-linking support (`?tab=seller&case_id=CASE-0012&modal=why`) enables bookmarkable evaluation flows.

---

## 6. Measured Reliability Benchmark Results

All benchmark metrics are recorded directly by running `python -m app.evaluation.harness.runner --k5-passed` against the live backend:

* **Evaluation Model:** `gemini-3.5-flash-lite` (Free Tier quota: 15 RPM / 1,500 RPD)
* **Agent Version Hash:** `5b1e4f68` (Deterministic SHA-256 CRLF->LF normalized)
* **Measurement Source:** [`app/evaluation/reliability.json`](app/evaluation/reliability.json) & [`H0_DISPATCH/STATUS_C.md`](../returnlens-planning/H0_DISPATCH/STATUS_C.md)

| Scenario | Case Type | Scenario Description | k | Passes | Pass@1 | Pass^k | Status | Model ID | Evaluation Details |
|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---:|:---|
| `S01` | `WISMO` | Standard Tracking Status Inquiry | 5 | 5 | 1.00 | 1.00 | ✅ PASS | *fast-path* | All 5 trial(s) passed 3-layer verification |
| `S02` | `WISMO` | Counterfactual Live Tracking Update | 5 | 5 | 1.00 | 1.00 | ✅ PASS | *fast-path* | All 5 trial(s) passed 3-layer verification |
| `S03` | `DAMAGE` | Case A Headband Damage (Clip-A) | 1 | 0 | 0.00 | 0.00 | 🔒 BLOCKED | null | needs real filmed clip (synthetic media cannot show cracked headband) |
| `S04` | `MISMATCH` | Case B Wrong Color Delivered (Clip-B) | 5 | 4 | 0.80 | 0.00 | ❌ FAIL | `gemini-3.5-flash-lite` | DB: Case state WAITING_CUSTOMER not in expected ['WAITING_SELLER', 'HUMAN_REVIEW', 'PROCESSING'] |
| `S05` | `UNCLEAR` | Case C Dim Lighting + Excess Amount | 5 | 5 | 1.00 | 1.00 | ✅ PASS | `gemini-3.5-flash-lite` | All 5 trial(s) passed 3-layer verification |
| `S06` | `LATE` | Return Window Exceeded (>7 Days) | 5 | 5 | 1.00 | 1.00 | ✅ PASS | *rule-gate* | All 5 trial(s) passed 3-layer verification |
| `S07` | `NDR` | Courier NDR Address Correction (COD) | 5 | 5 | 1.00 | 1.00 | ✅ PASS | *rule-gate* | All 5 trial(s) passed 3-layer verification |
| `S08` | `MISMATCH` | Voice Note Claim with Video (VN-HI) | 5 | 5 | 1.00 | 1.00 | ✅ PASS | `gemini-3.5-flash-lite` | All 5 trial(s) passed 3-layer verification |
| `S09` | `UNCLEAR` | Customer Return After Server Restart | 5 | 5 | 1.00 | 1.00 | ✅ PASS | `gemini-3.5-flash-lite` | All 5 trial(s) passed 3-layer verification |
| `S10` | `DAMAGE` | Cumulative Daily Velocity Limit Gate | 5 | 5 | 1.00 | 1.00 | ✅ PASS | *rule-gate* | All 5 trial(s) passed 3-layer verification |

**Benchmark Summary:**
- **8 / 10 scenarios passed at $k=5$ ($pass^5 = 1.00$)**
- **1 honestly blocked** (`S03` awaiting real filmed damage clip; synthetic media cannot show physical cracks)
- **1 measured failure at $k=5$** (`S04`: 4/5 passed, $pass@1 = 0.80$, $pass^5 = 0.00$ on `gemini-3.5-flash-lite` due to real-world vision model variance across multi-turn clarification). Because $pass^5 < 1.00$, the Earned Autonomy gate safely locks Case B (`MISMATCH`) to human seller review.

---

## 7. System Architecture

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

### The 5 Architectural Differentiators:
1. **Earned Autonomy Staircase:** No blanket auto-approvals. Level progression is gated mathematically by the reliability harness.
2. **Deterministic Financial Ledger:** All calculations operate strictly in integer minor units (paise). Over-refunds are prevented by database constraints.
3. **Tool Isolation:** AI models analyze evidence and generate text proposals only. Mutations require merchant authorization or verified L2/L3 policy execution.
4. **Stateful Cross-Session Recovery:** Workflows persist in durable SQLite tables, surviving unexpected crashes or restarts.
5. **Real-Time Courier Hooks:** Webhooks reactively trigger customer reach-out for NDRs before parcels are returned to origin.

---

## 8. Local Setup & Reproduction (≤ 3 Commands)

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

## 9. Honest Limitations & Staged Data Disclosure

1. **Scenario S03 Status:** Scenario S03 (Case A Headband Damage) is recorded as `BLOCKED`. The synthetic solid-color video clip used in early development cannot visually demonstrate a cracked headband to a real vision model. The system correctly refuses to hallucinate damage, keeping the scenario blocked until real unboxing footage is filmed.
2. **Scenario S04 Model Variance:** In the live benchmark against `gemini-3.5-flash-lite`, S04 achieved 4/5 passes ($pass@1 = 0.80$, $pass^5 = 0.00$). In 1 trial the model requested box label clarification rather than immediately transitioning to seller review. Because $pass^5 < 1.00$, the system honestly keeps `MISMATCH` autonomy locked to human review per the Earned Autonomy gate.
3. **Synthetic Voice Audio:** Voice notes (`synthetic_voice_*.ogg`) were generated using offline Windows System.Speech text-to-speech to enable deterministic, zero-cost unit testing without consuming paid cloud API calls.
4. **Demo Orders & Store Data:** Order fixtures for store *Dhun Audio* are pre-seeded relative to `DEMO_TODAY = 2026-11-11` per the hackathon prototype specification.

---

## 10. Technology Stack, Credits & Team

### Built With:
- **Language & Runtime:** Python 3.12, Node.js 20, TypeScript 5.9
- **Backend Framework:** FastAPI, Uvicorn, SQLite3, Pydantic v2, Python-Dotenv
- **AI / LLM Integration:** Google GenAI SDK (`google-genai`), Gemini 3.5 Flash Lite (`gemini-3.5-flash-lite`), Gemini 3.6 Flash fallback (`gemini-3.6-flash`)
- **Frontend Console:** React 18, Vite 5.4, Vanilla CSS (Design Tokens inspired by Indian botanical aesthetics)
- **Testing & Verification:** Pytest, Vitest, Microsoft Edge Headless Automation

### Media Credits (Pexels License):
Stock footage utilized for unboxing evidence is credited to the following creators via Pexels (free commercial use, modification permitted):
- *Black Headphones Unboxing Video:* Created by **Dario Fernandez Ruz** via [Pexels](https://www.pexels.com/video/person-getting-headphones-9130360/)
- *Dim Lighting Unboxing Video:* Created by **Tom Shutkin** via [Pexels](https://www.pexels.com/video/unboxing-gear-in-a-dimly-lit-room-40423563/)
- *Wireless Earbuds Case Video:* Created by **Nothing Ahead (ian-panelo)** via [Pexels](https://www.pexels.com/video/unboxing-wireless-earbuds-with-charging-case-40558520/)

### Team Members:
- **Role A:** Backend Workflow, API Contracts & Packaging
- **Role B:** Gemini Model Adapter, Multimodal Evidence & Autonomy Gate
- **Role C:** Reliability Benchmark Harness & Evaluation
- **Role D:** Web Console (Customer, Seller, Operator), UI Deep Linking & Documentation

---

### Integrity Statement:
> *"Ideas and design were planned before the event, as allowed; all code was written during the 24-hour window."*
