"""ReturnLens Reliability Harness Package (Card B11).

Exposes HarnessRunner, TrialEnvironment, LayerResult, TrialResult,
and all 10 scenario definitions per 18 §1–§2 and 17 §2–§3.
"""

from __future__ import annotations

from app.evaluation.harness.environment import TrialEnvironment
from app.evaluation.harness.models import (
    LayerResult,
    ScenarioRunSummary,
    TrialResult,
)
from app.evaluation.harness.runner import HarnessRunner
from app.evaluation.harness.scenarios import ALL_SCENARIOS

__all__ = [
    "ALL_SCENARIOS",
    "HarnessRunner",
    "LayerResult",
    "ScenarioRunSummary",
    "TrialEnvironment",
    "TrialResult",
]
