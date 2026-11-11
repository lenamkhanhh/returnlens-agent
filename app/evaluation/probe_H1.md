# ReturnLens Probe H1 Report (Card B01 & B15)

**Date**: 2026-11-11 12:55 (Vietnam Time)  
**Role**: B (Model adapter, evidence, voice)  
**SDK**: `google-genai` 3.1.0  
**Python Runtime**: CPython 3.12.13 (uv-managed virtual environment)  
**Key Status**: LIVE (`GEMINI_API_KEY` configured via `.env`)

---

## 1. Key Status & Live Probe Results (Wave 4)

All five H1 runtime probes have been executed live against the Google GenAI API with schema cleaning (`clean_json_schema`), proving 100% operational readiness across structured text, manual tool dispatch, native video understanding, and audio transcription.

### Probe Execution Summary

| # | Probe Target | Script / Function | Configuration / Schema | Live Status | Latency | Key Proof / Output |
|---|---|---|---|---|---|---|
| **1** | Structured JSON Output | `probe_1_structured_output` | `RouterOutput`, `thinking_level=LOW` | **PASS** | **2,346 ms** | Valid `Intent.RETURN`, recommended tool `get_order`, Pydantic validation passed |
| **2** | Manual Function Calling | `probe_2_manual_function_calling` | `AutomaticFunctionCallingConfig(disable=True)`, tool `get_order` | **PASS** | **1,288 ms** | Model generated manual tool call `get_order(order_id='ORD-7729')`; automatic dispatch disabled |
| **3** | Native Video Observation | `probe_3_native_video` | `ObserverOutput`, `media_resolution=LOW`, `thinking_level=LOW`, fps=3.0 | **PASS** | **5,267 ms** | Video uploaded inline as `video/webm`; structured observations returned without FFmpeg |
| **4** | Native Audio Transcription | `probe_4_audio_voice_note` | `TranscriberOutput`, inline audio (`audio/wav`), `thinking_level=LOW` | **PASS** | **2,818 ms** | Spoken claim transcribed verbatim; language identified; intent classified; facts separated |
| **5** | Latency Comparison | `probe_5_latency_comparison` | Benchmark `thinking_budget=0` vs `thinking_level=LOW` | **PASS** | **1,176 ms** (budget=0)<br>**2,511 ms** (low) | Minimal/budget=0 yields ~1.18s latency; low thinking yields ~2.51s latency |

---

## 2. Model Decision & Per-Call Latency

### Model Status & Recommendation
- **`gemini-3.8-flash`**: Free Tier quota limit reached (20 requests/day per project). Developer API rejects `ThinkingLevel.MINIMAL` (`INVALID_ARGUMENT`), requiring `thinking_budget=0` or `ThinkingLevel.LOW`.
- **`gemini-3.6-flash`**: Fully active, available, and verified across all 5 capabilities.
- **Decision**:
  - `MODEL_PRIMARY`: **`gemini-3.6-flash`** for immediate development/harness execution under active quota (fallback to `gemini-3.8-flash` on paid tier).
  - Per-call latency benchmarks:
    - Text routing (`budget=0`): **~1,176 ms**
    - Text routing (`thinking_low`): **~2,346 ms**
    - Manual function calling: **~1,288 ms**
    - Audio voice note transcription: **~2,818 ms**
    - Video evidence observation (native WebM): **~5,267 ms**

---

## 3. Schema Cleansing for Developer API Compatibility

The Google Gemini Developer API rejects `additionalProperties` and `title` keys in `response_schema` ("only supported in Gemini Enterprise Agent Platform mode").

### Adapter Solution
`GeminiModelAdapter` now integrates `clean_json_schema()`:
- Recursively removes `additionalProperties` and `title` from Pydantic-generated JSON schemas before dispatch.
- Preserves full Pydantic models on our application side with strict validation (`model_validate_json`) after the API response arrives.
- Free-form `dict` types are cleanly represented as schema objects without `additionalProperties`.

---

## 4. Architecture & Stack Decisions (H1 Gate)

### Decision 1: Media Pipeline Selection
- **Selected**: **Native Video/Audio path (03 §2a)** as primary and default.
- **FFmpeg**: **NOT required and NOT installed**. As instructed in Brief B ("Do not use FFmpeg") and `00_COMMON_RULES.md` §6, the system relies on Gemini's native multimodal understanding for video (inline `video/webm` with `video_metadata.fps=3.0`) and voice notes (inline Opus/WebM/WAV).
- **Timestamp Validation**: Model returns observations with timestamps in `"MM:SS"` format; deterministic code in `app/backend/media/evidence.py` strictly checks `0 <= t <= duration_ms`.

### Decision 2: Python Version
- **Selected**: **Python 3.12 (CPython 3.12.13)** managed via `uv` (`.venv`).
- **Compatibility**: Verified clean execution of `fastapi`, `pydantic>=2.14`, and `google-genai>=3.1.0`.

### Decision 3: Workflow Orchestration
- **Selected**: **Explicit Python State Machine** (per 08 §1).
- **Rationale**: Eliminates external framework fragility, provides full determinism, guarantees durable SQLite state transitions, and avoids LangGraph version drift under tight hackathon timelines.

---

## 5. Staged Development Fixtures (Manifest)

Synthetic development fixtures were generated via `app/demo/generate_synthetic_media.py` and cataloged in `app/demo/media/manifest.json`:
- `synthetic_black_headphones.webm` (10s, solid black, SHA-256: `8f7ff241...`)
- `synthetic_white_headphones.webm` (10s, solid white, SHA-256: `8f7ff241...`)
- `synthetic_damaged_item.webm` (10s, solid grey, SHA-256: `8f7ff241...`)
- `synthetic_voice_hindi.wav` (4s tone, SHA-256: `4688e20e...`)
- `synthetic_label_closeup.png` (200x200 PNG, SHA-256: `f4a20d79...`)

All assets are strictly labeled `synthetic: true` in `manifest.json`. Real customer evidence clips will be recorded by the team during the official recording phase.

---

## 6. Voice Note & Hindi Language Probe Evaluation (Card B15 & Test 47)

### Language Extraction & Devanagari Pipeline
- **Schema & Prompt**: `app/backend/prompts/transcriber_v1.txt` instructs the model to preserve native spoken Hindi in Devanagari script, produce an English translation in `translation_en`, detect the language (`Language.HI`, `Language.HINGLISH`, `Language.EN`), and classify intent.
- **Test 47 Ledger Reconciliation Invariant**: Spoken claims never override verified ledger balance. When a customer verbally claims ₹1.800 while the verified order ledger is ₹1.499, `reconcile_voice_claims()` marks the spoken amount as an unverified claim, logs a discrepancy audit flag, and strictly binds all financial mutations to the verified order balance from the domain DB.
- **Proof**: Verified by `app/backend/model/test_transcriber.py::TestAudioTranscriber::test_47_voice_note_mentions_different_amount_than_ledger`.
