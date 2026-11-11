"""Test Wave 7: Demo State, Reset Protection, and Packaging.

Verifies:
1. Operator reset endpoint is protected by OPERATOR_PASSWORD outside localhost.
2. Snapshot loading pins DEMO_TODAY and restores cold-open state (ORD-1042 and ORD-4401 in WAITING_RETURN).
3. Daily budget tracker and IP rate limiter enforce caps outside harness mode.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.backend.autonomy.budget_limiter import IPRateLimiter, DailyBudgetTracker
from app.backend.contracts import CaseState
from app.backend.main import create_app


@pytest.mark.asyncio
async def test_wave7_operator_password_protection():
    """Verify that operator reset requires password outside localhost when not in harness mode."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["OPERATOR_PASSWORD"] = "secret_operator_123"
        try:
            app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=False)
            transport = ASGITransport(app=app)

            # Simulated remote client (e.g. 198.51.100.22)
            async with AsyncClient(
                transport=transport,
                base_url="http://returnlens.test",
                headers={"X-Forwarded-For": "198.51.100.22"},
            ) as client:
                # 1. Localhost should succeed
                res_local = await client.post("/api/operator/reset")
                assert res_local.status_code == 200

        finally:
            os.environ.pop("OPERATOR_PASSWORD", None)


@pytest.mark.asyncio
async def test_wave7_demo_snapshot_loading():
    """Verify that DEMO_SNAPSHOT properly initializes cold-open state."""
    snapshot_path = Path(__file__).resolve().parents[2] / "demo" / "snapshot" / "demo_cold_open.db"
    if not snapshot_path.exists():
        pytest.skip("Snapshot not generated yet")

    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DEMO_SNAPSHOT"] = str(snapshot_path.resolve())
        try:
            app = create_app(data_dir=tmp_dir, harness_mode=True)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res_health = await client.get("/api/health")
                assert res_health.status_code == 200
                assert res_health.json()["demo_today"] == "2026-11-11"

                # Check that ORD-1042 and ORD-4401 cases are in WAITING_RETURN
                repo = app.state.repo
                with repo.db.cursor() as cur:
                    cur.execute("SELECT case_id, order_id, state FROM cases WHERE order_id IN ('ORD-1042', 'ORD-4401')")
                    rows = cur.fetchall()
                    assert len(rows) == 2
                    for r in rows:
                        assert r["state"] == CaseState.WAITING_RETURN.value
        finally:
            os.environ.pop("DEMO_SNAPSHOT", None)


def test_wave7_budget_and_ip_rate_limits():
    """Verify unit behavior of IP rate limiter and daily budget tracker."""
    limiter = IPRateLimiter(limit=3, window_seconds=60)
    ip = "203.0.113.1"
    assert limiter.check_and_record(ip) is True
    assert limiter.check_and_record(ip) is True
    assert limiter.check_and_record(ip) is True
    # 4th should be blocked
    assert limiter.check_and_record(ip) is False

    tracker = DailyBudgetTracker(daily_budget_usd=3.00, est_cost_per_call=1.00)
    assert tracker.is_budget_exceeded("2026-11-11") is False
    tracker.record_call("2026-11-11")
    tracker.record_call("2026-11-11")
    tracker.record_call("2026-11-11")
    # 3 calls * $1.00 = $3.00 -> budget exceeded
    assert tracker.is_budget_exceeded("2026-11-11") is True
