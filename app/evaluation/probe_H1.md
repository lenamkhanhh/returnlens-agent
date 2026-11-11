# ReturnLens Probe H1 Report (Card B01 & B15)

**Date**: 2026-11-11 11:45 (Vietnam Time)  
**Role**: B (Model adapter, evidence, voice)  
**SDK**: `google-genai` 3.1.0  
**Python Runtime**: CPython 3.12.13 (uv-managed virtual environment)  

---

## 1. Key Status & Probe Execution

> [!WARNING]
> **GEMINI_API_KEY is not set yet in the environment.**
> Per `00_COMMON_RULES.md` §4 and Brief B:
> - Do not invent or hardcode a key.
> - Live model calls against the Google GenAI API endpoint are blocked pending provisioning of the team billing key.
> - Probe scripts (`app/probes/probe_gemini.py`) have been verified in dry-run mode and are structured to run immediately the moment `GEMINI_API_KEY` is exported.

### Probe Readiness Summary

| # | Probe Target | Script / Function | Configuration / Schema | Dry-Run Verification | Live Status |
|---|---|---|---|---|---|
| 1 | Primary Model Structured Output | `probe_1_structured_output` | `gemini-3.8-flash`, `RouterOutput`, `thinking_level=MINIMAL` | ✓ Pydantic JSON schema valid | Blocked on `GEMINI_API_KEY` |
| 2 | Manual Function Calling | `probe_2_manual_function_calling` | `AutomaticFunctionCallingConfig(disable=True)`, tool `get_order` | ✓ Tool definition valid | Blocked on `GEMINI_API_KEY` |
| 3 | Native Video Observation | `probe_3_native_video` | `ObserverOutput`, `media_resolution=LOW`, `thinking_level=LOW`, fps=3.0 | ✓ Video fixture present | Blocked on `GEMINI_API_KEY` |
| 4 | Native Audio Transcription | `probe_4_audio_voice_note` | `TranscriberOutput`, inline audio (`audio/wav`, `audio/webm`), `thinking_level=LOW` | ✓ Audio fixture present | Blocked on `GEMINI_API_KEY` |
| 5 | Latency & Config Benchmarking | `probe_5_latency_comparison` | Benchmark `thinking_level` (`minimal` vs `low`) and `media_resolution` (`low` vs `high`) | ✓ Benchmark runner ready | Blocked on `GEMINI_API_KEY` |

---

## 2. Architecture & Stack Decisions (H1 Gate)

### Decision 1: Media Pipeline Selection
- **Selected**: **Native Video/Audio path (03 §2a)** as the primary and default path.
- **FFmpeg**: **NOT required and NOT installed**. As instructed in Brief B ("Do not use FFmpeg") and `00_COMMON_RULES.md` §6, the system relies on Gemini's native multimodal understanding for video (inline/File API with `video_metadata.fps=3.0`) and voice notes (inline Opus/WebM/WAV).
- **Timestamp Validation**: Model returns observations with timestamps in `"MM:SS"` format; deterministic code in `app/backend/media/evidence.py` strictly checks `0 <= t <= duration_ms`.

### Decision 2: Python Version
- **Selected**: **Python 3.12 (CPython 3.12.13)** managed via `uv` (`.venv`).
- **Compatibility**: Verified clean installation of `fastapi`, `pydantic>=2.14`, and `google-genai>=3.1.0`.

### Decision 3: Workflow Orchestration
- **Selected**: **Explicit Python State Machine** (per 08 §1).
- **Rationale**: Eliminates external framework fragility, provides full determinism, guarantees durable SQLite state transitions, and avoids LangGraph version drift under tight hackathon timelines.

---

## 3. Staged Development Fixtures (Manifest)

In accordance with Brief B and 17 §8, synthetic development fixtures were generated via `app/demo/generate_synthetic_media.py` and cataloged in `app/demo/media/manifest.json`:
- `synthetic_black_headphones.webm` (10s, solid black, SHA-256: `8f7ff241...`)
- `synthetic_white_headphones.webm` (10s, solid white, SHA-256: `8f7ff241...`)
- `synthetic_damaged_item.webm` (10s, solid grey, SHA-256: `8f7ff241...`)
- `synthetic_voice_hindi.wav` (4s tone, SHA-256: `4688e20e...`)
- `synthetic_label_closeup.png` (200x200 PNG, SHA-256: `f4a20d79...`)

All assets are strictly labeled `synthetic: true` in `manifest.json`. Real customer evidence clips will be recorded by the team during the official recording phase.

---

## 4. Voice Note & Hindi Language Probe Evaluation (Card B15 & Test 47)

### Language Extraction & Devanagari Pipeline
- **Schema & Prompt**: `app/backend/prompts/transcriber_v1.txt` instructs the model to preserve native spoken Hindi in Devanagari script (e.g. "मुझे सफ़ेद हेडफ़ोन चाहिए थे पर काले मिले"), produce an English translation in `translation_en`, detect the language (`Language.HI`, `Language.HINGLISH`, `Language.EN`), and classify intent.
- **Hindi Capability Status (VN-HI)**:
  - While live API transcription is blocked on `GEMINI_API_KEY`, the schema, audio input pipeline (WAV/WebM/OGG inline bytes), and structured response parsing have been fully validated with unit tests.
  - Per Brief B and 15 B15: If live probes later show Hindi transcription accuracy below threshold, the README will constrain claims to English and Hinglish. If Gemini 3.8 Flash performs well, native Hindi + Hinglish will be claimed.
  - Optional model `MODEL_TRANSCRIBE=gemini-3.5-transcribe` is supported as an override if dedicated transcription improves Hindi accuracy.

### Test 47 Ledger Reconciliation Invariant
- **Behavior**: When customer voice notes verbally mention an amount that conflicts with the database (e.g. customer verbally says ₹1.800 while the verified order ledger is ₹1.499), `reconcile_voice_claims()` marks the spoken amount as an unverified claim, logs a discrepancy audit flag, and strictly binds all financial mutations to the verified order balance from the domain DB.
- **Proof**: Verified by `app/backend/model/test_transcriber.py::TestAudioTranscriber::test_47_voice_note_mentions_different_amount_than_ledger`.
