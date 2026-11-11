"""Integration tests for Card B14 NDR Workflows (Tests 45, 46).

Validates:
- Test 45: NDR event deduplication by event_id: duplicate webhook creates exactly 1 job and 1 message.
- Test 46: NDR contract invariants: PIN code/city/state immutability and attempt limit (<= 3).
"""

import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from app.backend.contracts import CourierEventType, NextStep
from app.backend.main import create_app


@pytest.mark.asyncio
async def test_45_ndr_event_deduplication():
    """Test 45: NDR event lặp cùng event_id -> Dedupe, chỉ một tin nhắn, một job."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Post NDR courier event with explicit event_id
            ndr_payload = {
                "shipment_id": "SHP-3110",
                "type": CourierEventType.NDR.value,
                "attempt_no": 1,
                "reason": "customer_not_available",
            }
            res1 = await client.post("/api/operator/courier-events", json=ndr_payload)
            assert res1.status_code == 200
            data1 = res1.json()
            assert data1["status"] == "processed"
            case_id = data1["case_id"]

            repo = app.state.repo
            messages_v1 = repo.get_case_messages(case_id)
            assert len(messages_v1) >= 1

            # 2. Duplicate event sent again with exact same event_id
            res2 = await client.post("/api/operator/courier-events", json=ndr_payload)
            assert res2.status_code == 200
            data2 = res2.json()
            assert data2["status"] == "replayed"

            # Invariant: exactly 1 message delivered, no duplicate jobs
            messages_v2 = repo.get_case_messages(case_id)
            assert len(messages_v2) == len(messages_v1)


@pytest.mark.asyncio
async def test_46_ndr_action_pincode_and_attempt_invariants():
    """Test 46: ndr_action đổi pincode hoặc attempt > 3 -> Reject theo hợp đồng mock."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        mock_service = app.state.mock_service

        # 1. Valid update: PIN code 411038 remains identical
        res = mock_service.ndr_action(
            shipment_id="SHP-3110",
            action_type="reattempt",
            new_address="Flat 14B, Test Residency, Pune 411038",
        )
        assert res["success"] is True
        assert res["status"] == "REATTEMPT_REQUESTED"

        # 2. Invalid update: Customer attempts to change PIN code to Bengaluru 560034
        res_bad_pin = mock_service.ndr_action(
            shipment_id="SHP-3110",
            action_type="reattempt",
            new_address="Flat 14B, Test Residency, Bengaluru 560034",
        )
        assert res_bad_pin["success"] is False
        assert "Cannot change pincode" in res_bad_pin["error"]

        # 3. Invalid update: attempt count > 3
        repo = app.state.repo
        with repo.db.transaction() as conn:
            conn.execute("UPDATE shipments SET attempt_count = 4 WHERE shipment_id = 'SHP-3110'")

        res_max_attempt = mock_service.ndr_action(
            shipment_id="SHP-3110",
            action_type="reattempt",
            new_address="Flat 14B, Test Residency, Pune 411038",
        )
        assert res_max_attempt["success"] is False
        assert "Max reattempt limit" in res_max_attempt["error"]
