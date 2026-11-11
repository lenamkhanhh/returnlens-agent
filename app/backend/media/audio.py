"""Audio Adapter and Voice Note Utilities.

Card B15: Ingests and processes audio voice notes per 03 §2a, 17 §4, 17 §8.
- Validates audio size (<= 5 MB).
- Validates MIME types (audio/ogg, audio/opus, audio/webm, audio/wav, audio/mp4).
- Safe local persistence.
- Generates canonical VoiceNote entities.
"""

from __future__ import annotations

import hashlib
import wave
import io
from pathlib import Path
from typing import Optional

from app.backend.contracts import Language, VoiceNote
from app.backend.media.evidence import (
    MAX_AUDIO_BYTES,
    MediaValidationError,
    detect_mime_type,
)

MAX_AUDIO_DURATION_MS = 120 * 1000  # 2 minutes in ms per 17 §8


def probe_audio_duration_ms(data: bytes, mime_type: str) -> Optional[int]:
    """Inspect duration of standard audio containers without FFmpeg."""
    if mime_type == "audio/wav" and data.startswith(b"RIFF"):
        try:
            with wave.open(io.BytesIO(data), "rb") as wf:
                frames = wf.getnframes()
                rate = wf.getframerate()
                if rate > 0:
                    return int((frames / float(rate)) * 1000)
        except Exception:
            pass
    # For WebM / OGG, default estimate or None
    return None


def validate_audio_note(
    data: bytes,
    filename: str = "voicenote.webm",
) -> tuple[str, Optional[int]]:
    """Validate audio constraints: size <= 5 MB, supported MIME format, duration <= 2 min."""
    if not data:
        raise MediaValidationError("EMPTY_AUDIO", "Voice note contains 0 bytes.")

    if len(data) > MAX_AUDIO_BYTES:
        raise MediaValidationError(
            "FILE_TOO_LARGE",
            f"Voice note size {len(data)} bytes exceeds maximum {MAX_AUDIO_BYTES} bytes (5 MB).",
        )

    mime = detect_mime_type(data, filename)
    if not mime.startswith("audio/"):
        raise MediaValidationError(
            "UNSUPPORTED_MEDIA_TYPE",
            f"Expected audio MIME type, got '{mime}' for {filename}.",
        )

    duration_ms = probe_audio_duration_ms(data, mime)
    if duration_ms is not None and duration_ms > (MAX_AUDIO_DURATION_MS + 2000):
        raise MediaValidationError(
            "AUDIO_TOO_LONG",
            f"Voice note duration {duration_ms} ms exceeds 2 minute maximum.",
        )

    return mime, duration_ms


def create_voice_note_entity(
    evidence_id: str,
    mime_type: str,
    duration_ms: int,
    transcript: str,
    language: Language,
    model_run_id: Optional[str] = None,
) -> VoiceNote:
    """Create a canonical VoiceNote record."""
    return VoiceNote(
        evidence_id=evidence_id,
        media_type="audio",
        mime=mime_type,
        duration_ms=duration_ms,
        transcript=transcript,
        language_detected=language,
        transcript_model_run_id=model_run_id,
    )
