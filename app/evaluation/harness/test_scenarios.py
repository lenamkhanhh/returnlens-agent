"""Pytest integration for Card B11 Reliability Harness.

Per 17 §1 & 18 §1–§2:
- Runs scenarios in isolated trials.
- Emits app/evaluation/reliability.json and Markdown table.
- Model-dependent scenarios report 'blocked: no GEMINI_API_KEY' when key is missing.
"""

from __future__ import annotations

import json
from pathlib import Path
import pytest

from app.backend.autonomy.reliability import load_reliability_results
from app.evaluation.harness.runner import HarnessRunner
from app.evaluation.harness.scenarios import ALL_SCENARIOS


@pytest.fixture(autouse=True)
def clean_model_key(monkeypatch):
    """Ensure harness tests evaluate honesty in reproducible no-key mode."""
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)


@pytest.fixture(scope="function")
def harness_runner(tmp_path: Path):
    """Harness runner instance configured for k=1 evaluation in isolated tmp directory."""
    return HarnessRunner(k=1, output_path=tmp_path / "test_reliability.json")


@pytest.mark.asyncio
@pytest.mark.parametrize("scenario_id", list(ALL_SCENARIOS.keys()))
async def test_scenario_trial(scenario_id: str, harness_runner: HarnessRunner):
    """Execute a single scenario trial."""
    summary = await harness_runner.run_scenario(scenario_id, k=1)

    if summary.status.lower() == "blocked":
        pytest.skip(f"{scenario_id} blocked: {summary.reason}")
    elif summary.status.lower() == "pending":
        pytest.skip(f"{scenario_id} pending: {summary.reason}")

    assert summary.status.lower() in ("pass", "passed"), f"{scenario_id} failed: {summary.reason}"
    assert summary.passes >= 1
    assert summary.pass_pow_k == 1.0


@pytest.mark.asyncio
async def test_generate_reliability_json_and_markdown(harness_runner: HarnessRunner):
    """Execute all 10 scenarios, save reliability.json, and verify schema."""
    summaries = await harness_runner.run_all(k=1)
    assert len(summaries) == 10

    # 1. Verify reliability.json exists
    rel_path = harness_runner.output_path
    assert rel_path.exists(), f"Expected {rel_path} to exist"

    with open(rel_path, "r", encoding="utf-8") as f:
        data = json.load(f)

    assert "metadata" in data
    assert "results" in data
    assert len(data["results"]) == 10

    # 2. Verify load_reliability_results loads cleanly
    loaded = load_reliability_results(file_path=rel_path, harness_mode=True)
    assert len(loaded) == 10

    # Wave 3 Bug 4: Verify harness honesty across loaded results
    for sid, res in loaded.items():
        assert res.status in ("passed", "failed", "blocked")
        if res.status == "blocked":
            assert res.reason == "blocked: GEMINI_API_KEY not set"
            assert res.model_id is None
            assert res.passes == 0
            assert res.pass_pow_k == 0.0

    # 3. Verify Markdown table renders
    md = harness_runner.render_markdown_table(summaries)
    assert "Reliability Benchmark" in md
    assert "S01" in md
    assert "S10" in md
    assert "Reason / Details" in md
    assert "blocked: GEMINI_API_KEY not set" in md
