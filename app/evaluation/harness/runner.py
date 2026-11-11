"""Reliability Harness Runner for Card B11.

Executes all 10 scenarios across k trials in isolated environments,
computes 3-layer verification metrics, writes app/evaluation/reliability.json,
and renders a Markdown table for documentation per 18 §1–§2 and 17 §2–§3.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from app.backend.autonomy.version import compute_agent_version
from app.backend.contracts import CaseType, ReliabilityResult
from app.evaluation.harness.environment import TrialEnvironment
from app.evaluation.harness.models import ScenarioRunSummary, TrialResult
from app.evaluation.harness.scenarios import ALL_SCENARIOS

DEFAULT_RELIABILITY_JSON = (
    Path(__file__).resolve().parent.parent / "reliability.json"
)


class HarnessRunner:
    """Orchestrates multi-scenario, multi-trial reliability evaluation."""

    def __init__(
        self,
        k: int = 1,
        output_path: Optional[Path] = None,
        model_id: Optional[str] = None,
    ) -> None:
        self.k = k
        self.output_path = output_path or DEFAULT_RELIABILITY_JSON
        self.model_id = (
            model_id
            or os.environ.get("MODEL_PRIMARY")
            or "gemini-3.8-flash"
        )
        self.agent_version = compute_agent_version()

    async def run_scenario(
        self,
        scenario_id: str,
        k: Optional[int] = None,
    ) -> ScenarioRunSummary:
        """Execute k trials for a single scenario with full trial isolation."""
        num_trials = k or self.k
        scenario_cls = ALL_SCENARIOS.get(scenario_id)
        if not scenario_cls:
            raise ValueError(f"Unknown scenario ID: {scenario_id}")

        scenario = scenario_cls()
        trials: List[TrialResult] = []
        now_iso = datetime.now(timezone.utc).isoformat()

        # Check static prerequisites (e.g. GEMINI_API_KEY)
        prereq = scenario.check_prerequisites(trial_no=1)
        if prereq:
            summary = ScenarioRunSummary(
                scenario_id=scenario.scenario_id,
                case_type=scenario.case_type,
                k=num_trials,
                passes=0,
                pass_at_1=0.0,
                pass_pow_k=0.0,
                agent_version=self.agent_version,
                model_id=self.model_id,
                ran_at=now_iso,
                synthetic=(scenario.scenario_id == "S10"),
                status=prereq.status,
                reason=prereq.reason,
                trials=[prereq],
            )
            return summary

        # Run each trial in an isolated environment (17 §9)
        for trial_no in range(1, num_trials + 1):
            async with TrialEnvironment() as env:
                try:
                    trial_res = await scenario.run_trial(env, trial_no=trial_no)
                except Exception as ex:
                    trial_res = TrialResult(
                        scenario_id=scenario.scenario_id,
                        trial_no=trial_no,
                        passed=False,
                        status="FAIL",
                        reason=f"Unhandled exception: {str(ex)}",
                        error=str(ex),
                    )
                trials.append(trial_res)

        passes = sum(1 for t in trials if t.passed)
        pass_at_1 = float(passes) / float(num_trials) if num_trials > 0 else 0.0
        pass_pow_k = 1.0 if (passes == num_trials and num_trials > 0) else 0.0

        # Determine overall scenario status
        if passes == num_trials:
            overall_status = "PASS"
            overall_reason = f"All {num_trials} trial(s) passed 3-layer verification"
        elif any(t.status == "BLOCKED" for t in trials):
            overall_status = "BLOCKED"
            blocked_t = next(t for t in trials if t.status == "BLOCKED")
            overall_reason = blocked_t.reason
        elif any(t.status == "PENDING" for t in trials):
            overall_status = "PENDING"
            pending_t = next(t for t in trials if t.status == "PENDING")
            overall_reason = pending_t.reason
        else:
            overall_status = "FAIL"
            failed_reasons = [t.reason for t in trials if not t.passed]
            overall_reason = failed_reasons[0] if failed_reasons else f"{passes}/{num_trials} passed"

        return ScenarioRunSummary(
            scenario_id=scenario.scenario_id,
            case_type=scenario.case_type,
            k=num_trials,
            passes=passes,
            pass_at_1=round(pass_at_1, 4),
            pass_pow_k=round(pass_pow_k, 4),
            agent_version=self.agent_version,
            model_id=self.model_id,
            ran_at=now_iso,
            synthetic=(scenario.scenario_id == "S10"),
            status=overall_status,
            reason=overall_reason,
            trials=trials,
        )

    async def run_all(
        self,
        scenario_ids: Optional[List[str]] = None,
        k: Optional[int] = None,
    ) -> List[ScenarioRunSummary]:
        """Execute all configured scenarios and write reliability.json."""
        targets = scenario_ids or list(ALL_SCENARIOS.keys())
        summaries: List[ScenarioRunSummary] = []

        for sid in targets:
            summary = await self.run_scenario(sid, k=k)
            summaries.append(summary)

        # Output reliability.json
        self.save_reliability_json(summaries)
        return summaries

    def save_reliability_json(self, summaries: List[ScenarioRunSummary]) -> None:
        """Write reliability results matching ReliabilityResult contract."""
        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        results_list: List[Dict[str, Any]] = []
        for s in summaries:
            # Map into strict ReliabilityResult format (02 §2, 17 §2)
            res = ReliabilityResult(
                run_id=f"RUN-{s.scenario_id}-{int(time.time())}",
                scenario_id=s.scenario_id,
                case_type=s.case_type,
                k=s.k,
                passes=s.passes,
                pass_at_1=s.pass_at_1,
                pass_pow_k=s.pass_pow_k,
                agent_version=s.agent_version,
                model_id=s.model_id,
                ran_at=s.ran_at,
                synthetic=s.synthetic,
            )
            results_list.append(res.model_dump())

        output_payload = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "agent_version": self.agent_version,
                "model_id": self.model_id,
                "k": self.k,
            },
            "results": results_list,
            "scenario_metadata": {
                s.scenario_id: {
                    "status": s.status,
                    "reason": s.reason,
                    "case_type": s.case_type.value,
                    "synthetic": s.synthetic,
                }
                for s in summaries
            },
        }

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, indent=2)

    def render_markdown_table(self, summaries: List[ScenarioRunSummary]) -> str:
        """Generate formatted Markdown results table per 15 B11."""
        lines = [
            f"### Reliability Benchmark (k={self.k}, agent_version: `{self.agent_version[:8]}`)",
            "",
            "| Scenario | Case Type | Name | k | Passes | Pass@1 | Pass^k | Status | Reason / Details |",
            "|:---:|:---:|:---|:---:|:---:|:---:|:---:|:---:|:---|",
        ]

        scenario_names = {
            "S01": "WISMO Inquiry",
            "S02": "WISMO Counterfactual",
            "S03": "Case A Damage (Clip-A)",
            "S04": "Case B Mismatch (Clip-B)",
            "S05": "Case C Unclear (Clip-C)",
            "S06": "Late Return Window Check",
            "S07": "NDR Reattempt (COD)",
            "S08": "Voice Note Hindi (VN-HI)",
            "S09": "Customer Return After Restart",
            "S10": "Cumulative Daily Limit Gate",
        }

        status_badges = {
            "PASS": "✅ PASS",
            "FAIL": "❌ FAIL",
            "BLOCKED": "🔒 BLOCKED",
            "PENDING": "⏳ PENDING",
        }

        for s in summaries:
            name = scenario_names.get(s.scenario_id, s.scenario_id)
            badge = status_badges.get(s.status, s.status)
            synthetic_tag = " *(synthetic)*" if s.synthetic else ""
            lines.append(
                f"| `{s.scenario_id}` | `{s.case_type.value}` | {name}{synthetic_tag} | {s.k} | {s.passes} | {s.pass_at_1:.2f} | {s.pass_pow_k:.2f} | {badge} | {s.reason} |"
            )

        lines.append("")
        total_pass = sum(1 for s in summaries if s.status == "PASS")
        lines.append(f"**Total Passing**: {total_pass}/{len(summaries)} scenarios (k={self.k})")
        return "\n".join(lines)


async def _main():
    parser = argparse.ArgumentParser(description="ReturnLens Reliability Harness Runner")
    parser.add_argument("-k", "--trials", type=int, default=1, help="Number of trials per scenario (k)")
    parser.add_argument("-s", "--scenario", type=str, default=None, help="Run specific scenario ID (e.g. S01)")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output path for reliability.json")
    args = parser.parse_args()

    out_path = Path(args.output) if args.output else DEFAULT_RELIABILITY_JSON
    runner = HarnessRunner(k=args.trials, output_path=out_path)

    targets = [args.scenario.upper()] if args.scenario else None
    print(f"Running Reliability Harness (k={args.trials}, agent_version={runner.agent_version[:8]})...")
    summaries = await runner.run_all(scenario_ids=targets)

    table = runner.render_markdown_table(summaries)
    print("\n" + table)
    print(f"\nWrote results to {runner.output_path}")


if __name__ == "__main__":
    asyncio.run(_main())
