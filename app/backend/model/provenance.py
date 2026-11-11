"""ModelRun provenance record.

Per 02 §2 and 02 §8:
ModelRun provenance tracks provider, model ID/version, API family, SDK version,
prompt/schema versions, input reference hashes, output validated status,
cache hit, latency, token usage, and replay flag.
Does not log raw secrets or chain-of-thought.
"""

from __future__ import annotations

import uuid
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


class ModelRun(BaseModel):
    """ModelRun provenance record for auditing and reproducibility."""
    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(default_factory=lambda: f"RUN-{uuid.uuid4().hex[:12]}")
    provider: str = "google"
    model_id: str
    api_family: str = "generate_content"
    sdk_version: str = "3.1.0"
    prompt_version: str = "v1"
    schema_version: str = "v1"
    input_ref_hashes: List[str] = Field(default_factory=list)
    output_validated: bool = True
    cache_hit: bool = False
    latency_ms: int = 0
    token_usage: Dict[str, Optional[int]] = Field(
        default_factory=lambda: {
            "prompt_tokens": None,
            "completion_tokens": None,
            "total_tokens": None,
        }
    )
    replay_flag: bool = False
    error_code: Optional[str] = None
