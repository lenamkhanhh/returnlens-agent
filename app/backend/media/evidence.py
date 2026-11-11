"""Evidence Ingest, Timestamp Grounding, and Semantic Observation Validation.

Card B05: Media evidence processing backend per 03 §2a, 03 §4, 17 §2, 17 §4, 17 §8.
- Upload size and MIME limits enforcement.
- Safe local persistence under DATA_DIR/media.
- Deterministic timestamp validation (0 <= t <= duration_ms).
- Observation grounding and unknown preservation (CLIP-B observed black + barcode unverified).
- Color mismatch evaluation in code (17 §2).
"""

from __future__ import annotations

import datetime
import hashlib
import os
import re
from pathlib import Path
from typing import List, Optional, Tuple

from app.backend.contracts import (
    ColorClass,
    Evidence,
    ObservationAttribute,
    ObservationItem,
    Visibility,
)

# Size limits per 17 §8 and 02 §9
MAX_VIDEO_BYTES = 20 * 1024 * 1024  # 20 MB
MAX_IMAGE_BYTES = 10 * 1024 * 1024  # 10 MB
MAX_AUDIO_BYTES = 5 * 1024 * 1024   # 5 MB

# Allowed MIME types
ALLOWED_VIDEO_MIMES = {"video/webm", "video/mp4", "video/quicktime"}
ALLOWED_IMAGE_MIMES = {"image/jpeg", "image/png", "image/webp"}
ALLOWED_AUDIO_MIMES = {"audio/ogg", "audio/opus", "audio/webm", "audio/wav", "audio/mp4"}

TIMESTAMP_REGEX = re.compile(r"^(?:(\d{1,2}):)?([0-5]?\d):([0-5]\d)$")


class MediaValidationError(Exception):
    """Raised when uploaded media fails size, format, or grounding validation."""
    def __init__(self, code: str, message: str) -> None:
        super().__init__(message)
        self.code = code
        self.message = message


def parse_timestamp_ms(t_str: Optional[str]) -> Optional[int]:
    """Parse 'MM:SS' or 'HH:MM:SS' timestamp into integer milliseconds."""
    if not t_str:
        return None
    match = TIMESTAMP_REGEX.match(t_str.strip())
    if not match:
        return None
    h_str, m_str, s_str = match.groups()
    hours = int(h_str) if h_str else 0
    minutes = int(m_str)
    seconds = int(s_str)
    return ((hours * 3600) + (minutes * 60) + seconds) * 1000


def validate_timestamp(t_str: Optional[str], duration_ms: Optional[int]) -> bool:
    """Validate that timestamp t is formatted correctly and falls within clip duration.

    Per 03 §2a: 0 <= t <= duration, with 1000ms buffer for rounding.
    """
    if t_str is None:
        return True  # Valid for images or timeless observations
    t_ms = parse_timestamp_ms(t_str)
    if t_ms is None:
        return False
    if t_ms < 0:
        return False
    if duration_ms is not None:
        # Allow 1000ms tolerance for fractional second rounding
        if t_ms > (duration_ms + 1000):
            return False
    return True


def detect_mime_type(data: bytes, filename: str = "") -> str:
    """Detect MIME type by magic byte header with extension fallback."""
    if len(data) >= 4:
        # WebM / Matroska (EBML)
        if data.startswith(b"\x1a\x45\xdf\xa3"):
            # Can be video/webm or audio/webm depending on extension
            if filename.endswith(".opus") or filename.endswith(".ogg") or filename.endswith(".weba"):
                return "audio/webm"
            return "video/webm"
        # PNG
        if data.startswith(b"\x89PNG\r\n\x1a\n"):
            return "image/png"
        # JPEG
        if data.startswith(b"\xff\xd8\xff"):
            return "image/jpeg"
        # WAV (RIFF .... WAVE)
        if data.startswith(b"RIFF") and len(data) >= 12 and data[8:12] == b"WAVE":
            return "audio/wav"
        # OGG (OggS)
        if data.startswith(b"OggS"):
            return "audio/ogg"
        # MP4 / QuickTime (ftyp box)
        if len(data) >= 12 and data[4:8] == b"ftyp":
            return "video/mp4"

    # Extension fallback
    ext = Path(filename).suffix.lower()
    if ext in (".webm", ".mkv"):
        return "video/webm"
    elif ext in (".mp4", ".m4v"):
        return "video/mp4"
    elif ext in (".jpg", ".jpeg"):
        return "image/jpeg"
    elif ext == ".png":
        return "image/png"
    elif ext in (".ogg", ".opus"):
        return "audio/ogg"
    elif ext == ".wav":
        return "audio/wav"

    return "application/octet-stream"


def ingest_evidence(
    file_bytes: bytes,
    filename: str,
    case_id: str,
    media_dir: Path,
    duration_ms: Optional[int] = None,
) -> Evidence:
    """Ingest, validate, and persist media asset.

    Enforces size limits and MIME rules. Returns Evidence entity.
    """
    if not file_bytes:
        raise MediaValidationError("EMPTY_FILE", "Uploaded file contains 0 bytes.")

    mime_type = detect_mime_type(file_bytes, filename)

    # Classify media category
    if mime_type in ALLOWED_VIDEO_MIMES:
        media_type = "video"
        max_bytes = MAX_VIDEO_BYTES
    elif mime_type in ALLOWED_IMAGE_MIMES:
        media_type = "image"
        max_bytes = MAX_IMAGE_BYTES
    elif mime_type in ALLOWED_AUDIO_MIMES:
        media_type = "audio"
        max_bytes = MAX_AUDIO_BYTES
    else:
        raise MediaValidationError(
            "UNSUPPORTED_MEDIA_TYPE",
            f"Unsupported file format '{mime_type}' for {filename}. "
            f"Allowed: WebM, MP4, JPEG, PNG, WAV, OGG.",
        )

    # Size limit check (Test 30)
    if len(file_bytes) > max_bytes:
        raise MediaValidationError(
            "FILE_TOO_LARGE",
            f"File size {len(file_bytes)} bytes exceeds maximum {max_bytes} bytes for {media_type}.",
        )

    # Compute SHA-256
    content_sha256 = hashlib.sha256(file_bytes).hexdigest()
    evidence_id = f"EVI-{content_sha256[:12]}"

    # Save to storage
    media_dir.mkdir(parents=True, exist_ok=True)
    ext = Path(filename).suffix.lower() or f".{mime_type.split('/')[-1]}"
    storage_key = f"{evidence_id}_{content_sha256[:8]}{ext}"
    storage_path = media_dir / storage_key

    with open(storage_path, "wb") as f:
        f.write(file_bytes)

    now_iso = datetime.datetime.now(datetime.timezone.utc).isoformat()
    return Evidence(
        evidence_id=evidence_id,
        case_id=case_id,
        media_type=media_type,
        storage_key=storage_key,
        content_sha256=content_sha256,
        bytes=len(file_bytes),
        duration_ms=duration_ms,
        ingest_status="ingested",
        created_at=now_iso,
    )


def validate_observations_grounding(
    observations: List[ObservationItem],
    evidence_id: str,
    duration_ms: Optional[int] = None,
) -> Tuple[List[ObservationItem], List[str]]:
    """Validate that observations are grounded in the evidence and timestamps are within bounds.

    Returns:
        (valid_observations, rejection_reasons)
    """
    valid: List[ObservationItem] = []
    rejections: List[str] = []

    for obs in observations:
        # 1. Evidence ID binding
        if obs.evidence_id != evidence_id:
            rejections.append(
                f"Observation {obs.id} references evidence '{obs.evidence_id}', expected '{evidence_id}'."
            )
            continue

        # 2. Timestamp within clip duration (Test 11)
        if obs.t is not None:
            if not validate_timestamp(obs.t, duration_ms):
                rejections.append(
                    f"Observation {obs.id} timestamp '{obs.t}' is outside valid clip duration ({duration_ms} ms)."
                )
                continue

        valid.append(obs)

    return valid, rejections


def evaluate_color_match(
    observed_color: Optional[ColorClass],
    catalog_color: ColorClass,
    visibility: Visibility = Visibility.VISIBLE,
) -> Tuple[str, str]:
    """Deterministic color comparison in code per 17 §2.

    Returns:
        (status, reason_code) where status is 'MATCH', 'MISMATCH', or 'UNCLEAR'.
    """
    if visibility != Visibility.VISIBLE:
        return "UNCLEAR", "visibility_not_visible"

    if observed_color is None or observed_color == ColorClass.UNKNOWN:
        return "UNCLEAR", "observed_color_unknown"

    if catalog_color == ColorClass.UNKNOWN:
        return "UNCLEAR", "catalog_color_unknown"

    if observed_color != catalog_color:
        return "MISMATCH", f"observed_{observed_color.value}_catalog_{catalog_color.value}"

    return "MATCH", f"color_match_{observed_color.value}"
