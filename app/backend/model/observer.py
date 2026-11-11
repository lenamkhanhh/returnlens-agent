"""Visual Evidence Observer Module.

Card B05: Runs vision observer pipeline on uploaded evidence:
- Loads versioned observer prompt (observer_v1.txt).
- Dispatches model call via GeminiModelAdapter with ObserverOutput schema.
- Uses low media resolution for video/overview, high for label close-ups (17 §8).
- Performs deterministic timestamp validation in code (0 <= t <= duration_ms).
- Preserves unknowns (e.g. barcode unverified) per 03 §4 and Case B.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any, List, Optional, Tuple

from pydantic import ValidationError

from app.backend.contracts import (
    Evidence,
    ObservationAttribute,
    ObserverOutput,
    Visibility,
)
from app.backend.media.evidence import validate_observations_grounding
from app.backend.model.client import GeminiModelAdapter
from app.backend.model.provenance import ModelRun

try:
    from google.genai import types
except ImportError:
    types = None  # type: ignore

PROMPT_FILE = Path(__file__).resolve().parent.parent / "prompts" / "observer_v1.txt"


def load_observer_prompt() -> str:
    """Load the versioned neutral observer prompt text."""
    if PROMPT_FILE.exists():
        with open(PROMPT_FILE, "r", encoding="utf-8") as f:
            return f.read().strip()
    return (
        "Observe this customer return evidence neutrally. "
        "Classify observed color, visible damage, and note timestamps in MM:SS format. "
        "If shipping label, barcode, or exact model is not visible or verified, list them in unknowns."
    )


def _normalize_raw_observer_json(raw_text: str) -> str:
    """Normalize model variance in enum values to match Visibility contract (17 §2)."""
    # Map non-standard visibility tokens to contract schema values
    normalized = re.sub(
        r'("visibility"\s*:\s*)"(partial|occluded)"',
        r'\1"unclear"',
        raw_text,
        flags=re.IGNORECASE,
    )
    normalized = re.sub(
        r'("visibility"\s*:\s*)"not_visible"',
        r'\1"not_observed"',
        normalized,
        flags=re.IGNORECASE,
    )
    return normalized


class VisionObserverRunner:
    """Orchestrates visual evidence analysis with strict schema validation and grounding."""

    def __init__(self, adapter: Optional[GeminiModelAdapter] = None) -> None:
        self.adapter = adapter or GeminiModelAdapter()
        self.prompt_text = load_observer_prompt()
        self.prompt_version = "observer_v1.0"
        self.schema_version = "v1.0"

    def observe(
        self,
        evidence: Evidence,
        media_bytes: bytes,
        mime_type: str,
        is_closeup_label: bool = False,
        correlation_id: str = "",
    ) -> Tuple[ObserverOutput, ModelRun]:
        """Analyze evidence with Gemini vision model and validate grounded observations."""
        contents: List[Any] = []

        if types is not None:
            media_part = types.Part.from_bytes(
                data=media_bytes,
                mime_type=mime_type,
            )
            contents.append(media_part)
        else:
            contents.append({"mime_type": mime_type, "data_bytes_len": len(media_bytes)})

        prompt_with_context = (
            f"{self.prompt_text}\n\n"
            f"Target evidence_id: '{evidence.evidence_id}'. "
            f"Set evidence_id to '{evidence.evidence_id}' for all observations."
        )
        contents.append(prompt_with_context)

        # Call model adapter
        response, model_run = self.adapter.generate(
            contents=contents,
            stage="observer",
            response_schema=ObserverOutput,
            is_closeup_label=is_closeup_label,
            prompt_version=self.prompt_version,
            schema_version=self.schema_version,
            correlation_id=correlation_id,
        )

        # Parse response into ObserverOutput
        raw_text = getattr(response, "text", "")
        if isinstance(raw_text, str) and raw_text:
            cleaned_json = _normalize_raw_observer_json(raw_text)
            try:
                parsed_output = ObserverOutput.model_validate_json(cleaned_json)
            except ValidationError as err:
                # Return safe fallback with unverified state
                parsed_output = ObserverOutput(
                    observations=[],
                    unknowns=["model_schema_validation_failed"],
                    ignored_instructions=False,
                )
        else:
            parsed_output = ObserverOutput(
                observations=[],
                unknowns=["empty_model_response"],
                ignored_instructions=False,
            )

        # Code grounding validation: check timestamps and evidence IDs
        valid_obs, rejections = validate_observations_grounding(
            parsed_output.observations,
            evidence_id=evidence.evidence_id,
            duration_ms=evidence.duration_ms,
        )

        # If any observation was rejected, record in unknowns
        unknowns = list(parsed_output.unknowns)
        for r in rejections:
            unknowns.append(f"unverified_observation: {r}")

        # Ensure unverified fields are listed in unknowns when label/packaging is not observed (Wave 11)
        has_verified_label = any(
            o.attribute in (ObservationAttribute.LABEL_TEXT, "label_text")
            and getattr(o.visibility, "value", o.visibility) in (Visibility.VISIBLE, "visible")
            for o in valid_obs
        )
        if not has_verified_label:
            for required_unk in ["barcode", "exact_model", "shipping_label"]:
                if required_unk not in unknowns:
                    unknowns.append(required_unk)

        final_output = ObserverOutput(
            observations=valid_obs,
            unknowns=unknowns,
            ignored_instructions=parsed_output.ignored_instructions,
        )

        return final_output, model_run
