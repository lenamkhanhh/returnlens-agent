"""Harness data models for Card B11.

Supports 3-layer scoring (DB, Process, Message), trial results,
and scenario summaries per 18 §1, 15 B11, and 02 §2.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field

from app.backend.contracts import CaseType


class LayerResult(BaseModel):
    """Result of one scoring layer in a scenario trial."""
    layer: str  # "db", "process", "message"
    passed: bool
    reason: str = ""
    details: Dict[str, Any] = Field(default_factory=dict)


class TrialResult(BaseModel):
    """Execution result of a single trial for a scenario."""
    scenario_id: str
    trial_no: int
    passed: bool
    status: str  # "passed", "failed", "blocked"
    reason: str = ""
    db_layer: Optional[LayerResult] = None
    process_layer: Optional[LayerResult] = None
    message_layer: Optional[LayerResult] = None
    duration_ms: float = 0.0
    error: Optional[str] = None


class ScenarioRunSummary(BaseModel):
    """Aggregated summary of k trials for a scenario per 17 §2 and 18 §1."""
    scenario_id: str
    case_type: CaseType
    k: int
    passes: int
    pass_at_1: float
    pass_pow_k: float
    agent_version: str
    model_id: Optional[str] = None
    ran_at: str
    synthetic: bool = False
    status: str = "blocked"  # "passed", "failed", "blocked"
    reason: str = ""
    trials: List[TrialResult] = Field(default_factory=list)
