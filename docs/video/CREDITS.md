# ReturnLens Video Demo — Credits & Asset Licenses

This document lists all media assets, voices, music, and tools used in the production of the official **ReturnLens** demo video (AgentX Hackathon 2026, Track PS-04). All assets are free, open-source, or public domain, with permissive licenses allowing inclusion in a public repository and public video distribution.

---

## 1. Narration & Voice-Over (Synthetic)

- **Voice**: `en-IN-NeerjaNeural` (Indian English neural voice)
- **Engine**: Microsoft Edge Neural TTS via open-source `edge-tts` 7.3.1
- **License**: Generated output for educational/competition demonstration.
- **Notice**: In accordance with competition rules, the narration voice-over is **synthetic**. Zero paid APIs, zero human voice actors, and zero unauthorized third-party recordings were used.

---

## 2. Background Music

- **Title**: *Gymnopédie No. 1: Lent et douloureux*
- **Composer**: Erik Satie (1888, Public Domain)
- **Performer**: Robin Alciatore (Piano)
- **Publisher**: Musopen (https://musopen.org/)
- **Repository**: Wikimedia Commons ([File:Erik_Satie_-_gymnopedies_-_la_1_ere._lent_et_douloureux.ogg](https://commons.wikimedia.org/wiki/File:Erik_Satie_-_gymnopedies_-_la_1_ere._lent_et_douloureux.ogg))
- **License**: **Public Domain (CC0 / PD 1.0 Universal)**
- **Usage**: Mixed at approximately −24 dB under narration voice with smooth dynamic sidechain ducking, gentle intro fade-in, and outro fade-out.

---

## 3. Subtitles & Typography

- **Subtitles**: Arial / sans-serif, rendered at 32 px on 1080p canvas with semi-transparent dark backing box (`BorderStyle=3`, `MarginV=60`).
- **Formatting**: Max two lines per cue, maximum 42 characters per line, positioned at screen bottom to keep UI and ink annotations fully visible.

---

## 4. Software & Assembly Pipeline

- **Assembly Engine**: `docs/video/assemble.py` (FFmpeg-based automated pipeline)
- **FFmpeg & FFprobe**: Open-source multimedia framework (LGPL / GPL)
- **Audio Processing**: Python standard library `wave` module for microsecond-precise, non-overlapping PCM voice compilation; FFmpeg `sidechaincompress`, `amix`, and `loudnorm` (EBU R128 / −16 LUFS) for audio mastering.
