"""Base scenario class for Card B11."""

from __future__ import annotations

import abc
import os
import time
from typing import List, Optional

from app.backend.contracts import CaseType
from app.evaluation.harness.environment import TrialEnvironment
from app.evaluation.harness.models import TrialResult


class BaseScenario(abc.ABC):
    """Abstract base class for all 10 harness scenarios per 18 §2."""

    scenario_id: str
    case_type: CaseType
    title: str
    requires_model: bool = False
    requires_features: List[str] = []

    def check_prerequisites(self, trial_no: int = 1) -> Optional[TrialResult]:
        """Check prerequisites. If blocked/pending, return immediate TrialResult."""
        if self.requires_model and not os.environ.get("GEMINI_API_KEY"):
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="blocked",
                reason="blocked: GEMINI_API_KEY not set",
            )
        return None

    @abc.abstractmethod
    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        """Execute one isolated trial of this scenario and return 3-layer results."""
        raise NotImplementedError
