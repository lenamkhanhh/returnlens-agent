"""Reliability Gate Evaluator.

Per 17 §2, 17 §3, 02 §5b:
Evaluates reliability results from app/evaluation/reliability.json to gate L2 and L3 autonomy.
A CaseType is only unlocked for L2/L3 when every scenario mapped to it achieves
pass^5 = 1.0 (5 out of 5 passes) on the matching agent_version and model_id.
Synthetic results are accepted ONLY when HARNESS_MODE=1.
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from app.backend.contracts import CaseType, ReliabilityResult

# Mapping of scenarios to CaseType per 17 §2
SCENARIO_MAPPING: Dict[CaseType, List[str]] = {
    CaseType.WISMO: ["S01", "S02"],
    CaseType.DAMAGE: ["S03", "S10"],
    CaseType.MISMATCH: ["S04", "S08"],
    CaseType.UNCLEAR: ["S05", "S09"],
    CaseType.LATE: ["S06"],
    CaseType.NDR: ["S07"],
}

DEFAULT_RELIABILITY_PATH = (
    Path(__file__).resolve().parent.parent.parent / "evaluation" / "reliability.json"
)


def load_reliability_results(
    file_path: Optional[Path] = None,
    harness_mode: Optional[bool] = None,
) -> Dict[str, ReliabilityResult]:
    """Load reliability results indexed by scenario_id.

    Filters out synthetic results if HARNESS_MODE != '1'.
    """
    path = file_path or DEFAULT_RELIABILITY_PATH
    if harness_mode is None:
        harness_mode = os.environ.get("HARNESS_MODE", "0") == "1"

    if not path.exists():
        return {}

    try:
        with open(path, "r", encoding="utf-8") as f:
            data = json.load(f)
    except Exception:
        return {}

    # Handle both list of results and dict format {"results": [...]}
    raw_list: List[Dict[str, Any]] = []
    if isinstance(data, list):
        raw_list = data
    elif isinstance(data, dict):
        raw_list = data.get("results", [])

    results_by_scenario: Dict[str, ReliabilityResult] = {}
    for item in raw_list:
        try:
            # Handle item with ReliabilityResult schema
            res = ReliabilityResult.model_validate(item)
            if res.synthetic and not harness_mode:
                continue

            results_by_scenario[res.scenario_id] = res
        except Exception:
            continue

    return results_by_scenario


def check_case_type_reliability(
    case_type: CaseType,
    current_agent_version: str,
    current_model_id: str,
    reliability_data: Optional[Dict[str, ReliabilityResult]] = None,
    required_k: int = 5,
) -> Tuple[bool, str, Dict[str, Any]]:
    """Check if all scenarios for a CaseType pass the reliability gate.

    Returns:
        (passed: bool, reason: str, metrics: dict)
    """
    if reliability_data is None:
        reliability_data = load_reliability_results()

    scenarios = SCENARIO_MAPPING.get(case_type, [])
    if not scenarios:
        return False, f"No scenarios configured for CaseType {case_type.value}", {}

    scenario_metrics: Dict[str, Any] = {}
    all_passed = True
    failure_reasons: List[str] = []

    for sid in scenarios:
        res = reliability_data.get(sid)
        if not res:
            all_passed = False
            failure_reasons.append(f"Missing run for scenario {sid}")
            scenario_metrics[sid] = {"status": "MISSING"}
            continue

        status_val = res.status.lower() if res.status else "passed"
        reason_val = res.reason or ""

        scenario_metrics[sid] = {
            "k": res.k,
            "passes": res.passes,
            "pass_pow_k": res.pass_pow_k,
            "agent_version": res.agent_version,
            "model_id": res.model_id,
            "synthetic": res.synthetic,
            "status": status_val,
            "reason": reason_val,
        }

        # Wave 3 Bug 4: Autonomy must treat 'blocked' as not passed
        if status_val in ("blocked", "failed"):
            all_passed = False
            msg = f"{sid} is {status_val}"
            if reason_val:
                msg += f" ({reason_val})"
            failure_reasons.append(msg)
            continue

        # Validate trial count k >= 5
        if res.k < required_k:
            all_passed = False
            failure_reasons.append(
                f"{sid} ran with k={res.k} < required {required_k}"
            )

        # Validate 100% pass power (pass^k == 1.0)
        if res.pass_pow_k < 1.0 or res.passes < res.k:
            all_passed = False
            failure_reasons.append(
                f"{sid} passed {res.passes}/{res.k} (pass^{res.k}={res.pass_pow_k:.2f} < 1.0)"
            )

        # Validate agent_version
        if res.agent_version != current_agent_version:
            all_passed = False
            failure_reasons.append(
                f"{sid} agent_version '{res.agent_version[:8]}' != current '{current_agent_version[:8]}'"
            )

        # Validate model_id: if model was used, it must match current_model_id
        if res.model_id and res.model_id != current_model_id:
            all_passed = False
            failure_reasons.append(
                f"{sid} model_id '{res.model_id}' != current '{current_model_id}'"
            )

    if all_passed:
        return True, f"{case_type.value} passed reliability gate (all scenarios pass^{required_k} = 1.0)", scenario_metrics
    else:
        return False, f"Reliability locked for {case_type.value}: " + "; ".join(failure_reasons), scenario_metrics
