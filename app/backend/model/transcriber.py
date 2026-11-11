"""Audio Voice Note Transcriber and Reconciliation Module.

Card B15: Transcribes customer voice notes and reconciles mentioned claims:
- Loads versioned transcriber prompt (transcriber_v1.txt).
- Dispatches model call via GeminiModelAdapter with TranscriberOutput schema.
- Handles Hindi (Devanagari), Hinglish, and English audio.
- Test 47: Reconciles mentioned customer claims against verified order/ledger facts.
  Customer-stated amounts are untrusted claims and never override ledger values.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from pydantic import ValidationError

from app.backend.contracts import (
    Language,
    MentionedFacts,
    Order,
    TranscriberOutput,
    VoiceNote,
)
from app.backend.media.audio import create_voice_note_entity, validate_audio_note
from app.backend.model.client import GeminiModelAdapter
from app.backend.model.provenance import ModelRun

try:
    from google.genai import types
except ImportError:
    types = None  # type: ignore

PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "transcriber_v1.txt"


def load_transcriber_prompt() -> str:
    """Load the versioned transcriber prompt text."""
    if PROMPT_FILE.exists():
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return (
        "Transcribe this voice note verbatim. Detect language (hi, en, hinglish), "
        "provide English translation if non-English, extract customer intent, "
        "and list any mentioned order IDs or amounts."
    )


class AudioTranscriberRunner:
    """Transcribes customer voice notes with structured output and entity extraction."""

    def __init__(self, adapter: Optional[GeminiModelAdapter] = None) -> None:
        self.adapter = adapter or GeminiModelAdapter()
        self.prompt_text = load_transcriber_prompt()
        self.prompt_version = "transcriber_v1.0"
        self.schema_version = "v1.0"

    def transcribe(
        self,
        audio_bytes: bytes,
        mime_type: str = "audio/webm",
        evidence_id: str = "EVI-AUDIO-01",
        duration_ms: Optional[int] = None,
        correlation_id: str = "",
    ) -> Tuple[TranscriberOutput, ModelRun, VoiceNote]:
        """Transcribe audio using inline Gemini audio processing."""
        # Validate audio constraints
        validated_mime, probed_dur = validate_audio_note(audio_bytes, f"audio.{mime_type.split('/')[-1]}")
        actual_duration_ms = duration_ms or probed_dur or 5000

        contents: List[Any] = []
        if types is not None:
            audio_part = types.Part.from_bytes(
                data=audio_bytes,
                mime_type=validated_mime,
            )
            contents.append(audio_part)
        else:
            contents.append({"mime_type": validated_mime, "data_bytes_len": len(audio_bytes)})

        contents.append(self.prompt_text)

        # Call model adapter with TranscriberOutput schema
        response, model_run = self.adapter.generate(
            contents=contents,
            stage="transcriber",
            response_schema=TranscriberOutput,
            prompt_version=self.prompt_version,
            schema_version=self.schema_version,
            correlation_id=correlation_id,
        )

        raw_text = getattr(response, "text", "")
        if isinstance(raw_text, str) and raw_text:
            try:
                parsed_output = TranscriberOutput.model_validate_json(raw_text)
            except ValidationError:
                parsed_output = TranscriberOutput(
                    transcript="[transcription_schema_validation_failed]",
                    language=Language.OTHER,
                    inaudible=True,
                )
        else:
            parsed_output = TranscriberOutput(
                transcript="[empty_audio_response]",
                language=Language.OTHER,
                inaudible=True,
            )

        voice_note = create_voice_note_entity(
            evidence_id=evidence_id,
            mime_type=validated_mime,
            duration_ms=actual_duration_ms,
            transcript=parsed_output.transcript,
            language=parsed_output.language,
            model_run_id=model_run.run_id,
        )

        return parsed_output, model_run, voice_note


def reconcile_voice_claims(
    mentioned: MentionedFacts,
    verified_order: Order,
) -> Dict[str, Any]:
    """Reconcile unverified facts mentioned in customer voice note against domain DB.

    Test 47: When customer states an amount different from ledger (e.g. ₹1.800 instead of ₹1.499),
    the system explicitly flags the discrepancy as an unverified claim and binds resolution
    exclusively to verified ledger facts.
    """
    discrepancies: List[str] = []
    amount_mismatch = False

    # Check order IDs
    if mentioned.order_ids:
        if verified_order.order_id not in mentioned.order_ids:
            discrepancies.append(
                f"Spoken order ID(s) {mentioned.order_ids} do not match active order {verified_order.order_id}."
            )

    # Check amounts (Test 47)
    verified_amount_minor = verified_order.paid_minor
    claimed_amounts = mentioned.amounts_minor

    if claimed_amounts:
        for claimed in claimed_amounts:
            if claimed != verified_amount_minor:
                amount_mismatch = True
                discrepancies.append(
                    f"Customer verbally claimed amount {claimed} paise (₹{claimed / 100:.2f}), "
                    f"which differs from verified ledger paid amount {verified_amount_minor} paise (₹{verified_amount_minor / 100:.2f})."
                )

    return {
        "verified_order_id": verified_order.order_id,
        "verified_paid_minor": verified_amount_minor,
        "spoken_order_ids": mentioned.order_ids,
        "spoken_amounts_minor": claimed_amounts,
        "amount_mismatch": amount_mismatch,
        "discrepancies": discrepancies,
        "enforced_amount_minor": verified_amount_minor,  # Truth always comes from domain DB
        "status": "DISCREPANCY_FLAGGED" if discrepancies else "RECONCILED",
    }
