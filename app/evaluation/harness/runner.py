"""Reliability Harness Runner for Card B11.

Executes all 10 scenarios across k trials in isolated environments,
computes 3-layer verification metrics, writes app/evaluation/reliability.json,
and renders a Markdown table for documentation per 18 §1–§2 and 17 §2–§3.
"""

from __future__ import annotations

import os
# Per 17 §1 & 18 §1: HARNESS_MODE=1 disables dev cache and auto-dotenv in app factory
os.environ["HARNESS_MODE"] = "1"

from pathlib import Path
# Explicit absolute path to returnlens-agent/.env (Wave 7 per WAVE7.md)
ROOT_DIR = Path(__file__).resolve().parents[3]
ENV_PATH = ROOT_DIR / ".env"
from dotenv import load_dotenv
if ENV_PATH.exists():
    load_dotenv(dotenv_path=ENV_PATH, override=True)
else:
    load_dotenv()

import argparse
import asyncio
import json
import sys
import time
from datetime import datetime, timezone
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
        invalid_key_mode: bool = False,
    ) -> None:
        self.k = k
        self.output_path = output_path or DEFAULT_RELIABILITY_JSON
        self.invalid_key_mode = invalid_key_mode
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
                model_id=None,  # Wave 3 Bug 4: null when no model call happened
                ran_at=now_iso,
                synthetic=(scenario.scenario_id == "S10"),
                status="blocked",
                reason=prereq.reason,
                trials=[prereq],
            )
            return summary

        # Run each trial in an isolated environment (17 §9)
        for trial_no in range(1, num_trials + 1):
            async with TrialEnvironment() as env:
                try:
                    trial_res = await scenario.run_trial(env, trial_no=trial_no)
                    if self.invalid_key_mode and scenario.requires_model:
                        # Wave 8 Negative Control assertion:
                        if trial_res.status.lower() == "blocked":
                            pass  # Keep blocked if e.g. S03 prerequisite
                        else:
                            with env.repo.db.cursor() as cur:
                                cur.execute("SELECT case_id, state FROM cases ORDER BY created_at DESC LIMIT 1")
                                case_row = cur.fetchone()
                                if case_row:
                                    c_state = str(case_row["state"]).upper()
                                    cur.execute("SELECT event_type FROM audit_events WHERE case_id = ?", (case_row["case_id"],))
                                    c_evts = [r["event_type"] for r in cur.fetchall()]
                                else:
                                    c_state = ""
                                    c_evts = []

                            if case_row:
                                if c_state == "HUMAN_REVIEW" or "model_unavailable" in c_evts:
                                    trial_res = TrialResult(
                                        scenario_id=scenario.scenario_id,
                                        trial_no=trial_no,
                                        passed=False,
                                        status="human_review",
                                        reason="ended in HUMAN_REVIEW (expected behaviour under invalid key)",
                                        duration_ms=trial_res.duration_ms,
                                    )
                                else:
                                    trial_res = TrialResult(
                                        scenario_id=scenario.scenario_id,
                                        trial_no=trial_no,
                                        passed=False,
                                        status="failed",
                                        reason=f"Negative control violation: ended in {c_state} instead of HUMAN_REVIEW",
                                        duration_ms=trial_res.duration_ms,
                                    )
                except Exception as ex:
                    trial_res = TrialResult(
                        scenario_id=scenario.scenario_id,
                        trial_no=trial_no,
                        passed=False,
                        status="failed",
                        reason=f"Unhandled exception: {str(ex)}",
                        error=str(ex),
                    )
                trials.append(trial_res)

        passes = sum(1 for t in trials if t.passed)
        pass_at_1 = float(passes) / float(num_trials) if num_trials > 0 else 0.0
        pass_pow_k = 1.0 if (passes == num_trials and num_trials > 0) else 0.0

        if self.invalid_key_mode and scenario.requires_model:
            passes = 0
            pass_at_1 = 0.0
            pass_pow_k = 0.0
            scenario_model_id = None
            if all(t.status.lower() == "human_review" for t in trials):
                overall_status = "human_review"
                overall_reason = "ended in HUMAN_REVIEW (expected behaviour under invalid key)"
            elif any(t.status.lower() == "blocked" for t in trials):
                overall_status = "blocked"
                blocked_t = next(t for t in trials if t.status.lower() == "blocked")
                overall_reason = blocked_t.reason
            else:
                overall_status = "failed"
                failed_t = next((t for t in trials if t.status.lower() == "failed"), trials[0])
                overall_reason = failed_t.reason
        else:
            # Determine overall scenario status per Wave 3: "passed", "failed", "blocked"
            if passes == num_trials:
                overall_status = "passed"
                overall_reason = f"All {num_trials} trial(s) passed 3-layer verification"
            elif any(t.status.lower() == "blocked" for t in trials):
                overall_status = "blocked"
                blocked_t = next(t for t in trials if t.status.lower() == "blocked")
                overall_reason = blocked_t.reason
            else:
                overall_status = "failed"
                failed_reasons = [t.reason for t in trials if not t.passed]
                overall_reason = failed_reasons[0] if failed_reasons else f"{passes}/{num_trials} passed"

            # Wave 3 Bug 4: record model_id: null when no model call happened
            if overall_status == "blocked" or not scenario.requires_model:
                scenario_model_id = None
            else:
                scenario_model_id = self.model_id

        return ScenarioRunSummary(
            scenario_id=scenario.scenario_id,
            case_type=scenario.case_type,
            k=num_trials,
            passes=passes,
            pass_at_1=round(pass_at_1, 4),
            pass_pow_k=round(pass_pow_k, 4),
            agent_version=self.agent_version,
            model_id=scenario_model_id,
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
        """Write reliability results matching ReliabilityResult contract, merging with existing entries."""
        if self.invalid_key_mode and self.output_path.resolve() == DEFAULT_RELIABILITY_JSON.resolve():
            # Wave 8: In negative control mode, do not overwrite production reliability.json
            return

        self.output_path.parent.mkdir(parents=True, exist_ok=True)

        existing_results: Dict[str, Dict[str, Any]] = {}
        existing_meta: Dict[str, Dict[str, Any]] = {}
        if self.output_path.exists():
            try:
                with open(self.output_path, "r", encoding="utf-8") as f:
                    old_data = json.load(f)
                    for r in old_data.get("results", []):
                        existing_results[r["scenario_id"]] = r
                    existing_meta = old_data.get("scenario_metadata", {})
            except Exception:
                pass

        for s in summaries:
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
                status=s.status,
                reason=s.reason,
            )
            existing_results[s.scenario_id] = res.model_dump()
            existing_meta[s.scenario_id] = {
                "status": s.status,
                "reason": s.reason,
                "case_type": s.case_type.value,
                "synthetic": s.synthetic,
                "model_id": s.model_id,
            }

        sorted_keys = sorted(
            existing_results.keys(),
            key=lambda x: int(x[1:]) if x[1:].isdigit() else x,
        )
        sorted_results = [existing_results[k] for k in sorted_keys]

        output_payload = {
            "metadata": {
                "generated_at": datetime.now(timezone.utc).isoformat(),
                "agent_version": self.agent_version,
                "model_id": self.model_id,
                "k": self.k,
            },
            "results": sorted_results,
            "scenario_metadata": existing_meta,
        }

        with open(self.output_path, "w", encoding="utf-8") as f:
            json.dump(output_payload, f, indent=2)

    def render_markdown_table(self, summaries: List[ScenarioRunSummary]) -> str:
        """Generate formatted Markdown results table per 15 B11."""
        lines = [
            f"### Reliability Benchmark (agent_version: `{self.agent_version[:8]}`, model: `{self.model_id}`)",
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
            "passed": "✅ PASS",
            "failed": "❌ FAIL",
            "blocked": "🔒 BLOCKED",
            "human_review": "🛡️ HUMAN_REVIEW",
            "pass": "✅ PASS",
            "fail": "❌ FAIL",
        }

        for s in summaries:
            name = scenario_names.get(s.scenario_id, s.scenario_id)
            badge = status_badges.get(s.status.lower(), s.status.upper())
            synthetic_tag = " *(synthetic)*" if s.synthetic else ""
            lines.append(
                f"| `{s.scenario_id}` | `{s.case_type.value}` | {name}{synthetic_tag} | {s.k} | {s.passes} | {s.pass_at_1:.2f} | {s.pass_pow_k:.2f} | {badge} | {s.reason} |"
            )

        lines.append("")
        total_pass = sum(1 for s in summaries if s.status.lower() in ("pass", "passed"))
        total_blocked = sum(1 for s in summaries if s.status.lower() in ("blocked",))
        total_hr = sum(1 for s in summaries if s.status.lower() in ("human_review",))
        total_failed = len(summaries) - total_pass - total_blocked - total_hr

        summary_line = f"**Total Passing**: {total_pass}/{len(summaries)} scenarios — {total_blocked} blocked, {total_failed} failed"
        if total_hr > 0:
            summary_line += f", {total_hr} ended in HUMAN_REVIEW (negative control)"
        lines.append(summary_line)
        return "\n".join(lines)


async def _main():
    parser = argparse.ArgumentParser(description="ReturnLens Reliability Harness Runner")
    parser.add_argument("-k", "--k", "--trials", dest="trials", type=int, default=1, help="Number of trials per scenario (k)")
    parser.add_argument("-s", "--scenario", type=str, default=None, help="Run specific scenario ID(s), e.g. S01 or S01,S02")
    parser.add_argument("-o", "--output", type=str, default=None, help="Output path for reliability.json")
    parser.add_argument("--k5-passed", action="store_true", help="Run k=1 for all scenarios, then k=5 for all scenarios that pass k=1")
    parser.add_argument("--invalid-key", action="store_true", help="Negative control mode: run with invalid GEMINI_API_KEY to verify model scenarios end in HUMAN_REVIEW")
    args = parser.parse_args()

    targets = [s.strip().upper() for s in args.scenario.split(",") if s.strip()] if args.scenario else None

    # Wave 8: If invalid-key negative control mode is selected, set invalid key
    if args.invalid_key:
        os.environ["GEMINI_API_KEY"] = "invalid-key-negative-control"

    # Wave 7 per WAVE7.md: Fail loudly at start if key is missing for model scenarios
    target_sids = targets or list(ALL_SCENARIOS.keys())
    model_sids = [sid for sid in target_sids if ALL_SCENARIOS.get(sid) and ALL_SCENARIOS[sid].requires_model]
    if not args.invalid_key and model_sids and not os.environ.get("GEMINI_API_KEY"):
        raise RuntimeError(
            f"FATAL: GEMINI_API_KEY is not set in {ENV_PATH}! "
            f"Model scenarios {model_sids} require a live GEMINI_API_KEY. "
            "Aborting evaluation immediately without generating unmeasured results."
        )

    out_path = Path(args.output) if args.output else DEFAULT_RELIABILITY_JSON
    runner = HarnessRunner(k=args.trials, output_path=out_path, invalid_key_mode=args.invalid_key)

    if args.k5_passed:
        print(f"Phase 1: Running all 10 scenarios with k=1 (agent_version={runner.agent_version[:8]})...")
        k1_summaries = await runner.run_all(k=1)
        passed_sids = [s.scenario_id for s in k1_summaries if s.status.lower() in ("pass", "passed")]
        print(f"\nPhase 1 complete: {len(passed_sids)}/10 passed ({', '.join(passed_sids)}).")

        final_summaries_map = {s.scenario_id: s for s in k1_summaries}
        if passed_sids:
            print(f"\nPhase 2: Running k=5 for passing scenarios ({', '.join(passed_sids)})...")
            runner_k5 = HarnessRunner(k=5, output_path=out_path, invalid_key_mode=args.invalid_key)
            for sid in passed_sids:
                print(f"  -> Running {sid} (k=5)...")
                summary_k5 = await runner_k5.run_scenario(sid, k=5)
                final_summaries_map[sid] = summary_k5

            # Save full merged results
            ordered_summaries = [
                final_summaries_map[sid]
                for sid in ALL_SCENARIOS.keys()
                if sid in final_summaries_map
            ]
            runner_k5.save_reliability_json(ordered_summaries)
            table = runner_k5.render_markdown_table(ordered_summaries)
        else:
            table = runner.render_markdown_table(k1_summaries)

        print("\n" + table)
        print(f"\nWrote results to {runner.output_path}")
        return

    targets = [s.strip().upper() for s in args.scenario.split(",") if s.strip()] if args.scenario else None
    print(f"Running Reliability Harness (k={args.trials}, agent_version={runner.agent_version[:8]})...")
    summaries = await runner.run_all(scenario_ids=targets, k=args.trials)

    table = runner.render_markdown_table(summaries)
    print("\n" + table)
    print(f"\nWrote results to {runner.output_path}")


if __name__ == "__main__":
    asyncio.run(_main())
