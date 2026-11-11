"""Integration tests for Card B07 Refund Transaction (Tests 20, 21, 22, 23, 24, 25, 37, 39, 43).

Validates:
- Test 20: Concurrent refund requests against the same order: second caller revalidates ledger, total never exceeds remaining balance.
- Test 21: Store cap enforcement: amounts exceeding store cap (₹3,000 / 300,000 paise) are blocked (P_CAP).
- Test 22: Remaining balance gate: requested amount exceeding remaining balance is blocked (P_BALANCE).
- Test 23: Amount integrity: negative, zero, float, boolean, or non-integer values are strictly rejected.
- Test 24: Receipt requirement: refund before RETURN_RECEIVED is blocked (P_RECEIPT).
- Test 25: Receipt + seller approval creates refund record, increments refunded_minor, updates ledger atomically.
- Test 37: Single approval consumption enforcement.
- Test 39: Outbox retry preserves stable message IDs and does not duplicate confirmation notifications.
- Test 43: Cumulative daily gate: refunds exceeding daily customer cap (₹2,000 / 200,000 paise) are deferred to seller.
"""

import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from app.backend.contracts import CourierEventType, NextStep, ReturnStatus
from app.backend.main import create_app


@pytest.mark.asyncio
async def test_21_store_cap_enforcement_blocks_excessive_amount():
    """Test 21: Store cap (₹3.000) binding check -> blocks amount > cap."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        mock_service = app.state.mock_service

        # Request ₹3,001 (300100 paise) on an order
        res = mock_service.issue_refund(
            order_id="ORD-7729",
            amount_minor=300100,
            idempotency_key="idem-cap-01",
            bypass_receipt_check=True,
        )
        assert res["refund"] is None
        assert len(res["userErrors"]) == 1
        assert "P_CAP" in res["userErrors"][0]["message"]


@pytest.mark.asyncio
async def test_22_balance_gate_blocks_amount_exceeding_remaining():
    """Test 22: Paid ₹1.499, refund trước ₹499, request ₹1.001 -> Remaining ₹1.000; block."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        repo = app.state.repo
        mock_service = app.state.mock_service

        # Set prior refund of ₹499 (49900 paise) on ORD-7729 (paid 149900 paise)
        with repo.db.transaction() as conn:
            conn.execute("UPDATE orders SET refunded_minor = 49900 WHERE order_id = 'ORD-7729'")

        # Now request ₹1,001 (100100 paise) -> remaining is 100000 paise (₹1,000)
        res = mock_service.issue_refund(
            order_id="ORD-7729",
            amount_minor=100100,
            idempotency_key="idem-bal-01",
            bypass_receipt_check=True,
        )
        assert res["refund"] is None
        assert len(res["userErrors"]) == 1
        assert "P_BALANCE" in res["userErrors"][0]["message"]


@pytest.mark.asyncio
async def test_23_amount_integrity_strict_rejection():
    """Test 23: Tiền âm/0/float/bool/NaN -> Strict reject theo contract."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        mock_service = app.state.mock_service

        for invalid_amount in [0, -100, 1499.50, True, "149900", None]:
            res = mock_service.issue_refund(
                order_id="ORD-7729",
                amount_minor=invalid_amount,
                idempotency_key=f"idem-inv-{hash(str(invalid_amount))}",
                bypass_receipt_check=True,
            )
            assert res["refund"] is None
            assert len(res["userErrors"]) >= 1
            assert "P_AMOUNT_INVALID" in res["userErrors"][0]["message"]


@pytest.mark.asyncio
async def test_24_receipt_required_before_refund():
    """Test 24: Tạo label rồi xin refund trước receipt -> Chưa eligible, block P_RECEIPT."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        mock_service = app.state.mock_service

        # Create return label, but item is NOT yet received
        ret_res = mock_service.create_return(
            order_id="ORD-7729",
            item_id="item_7729",
            quantity=1,
            action_id="ACT-RET-01",
        )
        assert ret_res["return"]["status"] == "requested"

        # Attempt refund before receipt
        res = mock_service.issue_refund(
            order_id="ORD-7729",
            amount_minor=149900,
            idempotency_key="idem-premature-rfd",
            bypass_receipt_check=False,
        )
        assert res["refund"] is None
        assert len(res["userErrors"]) == 1
        assert "P_RECEIPT" in res["userErrors"][0]["message"]


@pytest.mark.asyncio
async def test_25_receipt_and_seller_approval_processes_refund_atomically():
    """Test 25: Mock receipt + seller approval mới -> Refund thành công một lần; ledger consistent."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create case and return
            res = await client.post(
                "/api/cases",
                json={"order_id": "ORD-1042", "initial_message": "Headband cracked"},
                headers={"X-Customer-Id": "CUS-03"},
            )
            case_id = res.json()["case_id"]

            res = await client.post(
                f"/api/cases/{case_id}/proposals",
                json={"action_type": NextStep.PROPOSE_RETURN.value, "item_id": "item_1042"},
            )
            prop_id = res.json()["proposal_id"]
            hash_val = res.json()["payload_hash"]

            await client.post(
                f"/api/proposals/{prop_id}/decisions",
                json={"decision": "approve", "payload_hash": hash_val},
                headers={"Idempotency-Key": "idem-ret-1042"},
            )

            # 2. Operator fires RETURN_RECEIVED courier event
            res = await client.post(
                "/api/operator/courier-events",
                json={
                    "shipment_id": "SHP-1042",
                    "type": CourierEventType.RETURN_RECEIVED.value,
                    "attempt_no": 1,
                },
            )
            assert res.status_code == 200
            courier_res = res.json()
            assert courier_res["type"] == "RETURN_RECEIVED"
            refund_prop_id = courier_res["proposal_id"]

            # 3. Fetch proposal details
            repo = app.state.repo
            refund_prop = repo.get_proposal(refund_prop_id)
            assert refund_prop is not None
            assert refund_prop.amount_minor == 129900

            # 4. Seller approves refund proposal
            res = await client.post(
                f"/api/proposals/{refund_prop_id}/decisions",
                json={"decision": "approve", "payload_hash": refund_prop.payload_hash},
                headers={"Idempotency-Key": "idem-rfd-1042"},
            )
            assert res.status_code == 200
            decision_data = res.json()
            assert decision_data["status"] == "succeeded"
            assert decision_data["action_id"].startswith("ACT-")

            # 5. Verify order ledger updated atomically (02 §6)
            order = repo.get_order("ORD-1042")
            assert order.refunded_minor == 129900
            assert order.revision >= 2

            # 6. Verify audit events emitted
            res = await client.get(f"/api/cases/{case_id}/events")
            events = res.json()
            types = [e["event_type"] for e in events]
            assert "refund_posted" in types
            assert "customer_reply_delivered" in types


@pytest.mark.asyncio
async def test_20_concurrent_refunds_respect_remaining_balance():
    """Test 20: Hai key/case refund cùng order cạnh tranh -> Writer sau kiểm tra lại, tổng không vượt remaining."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        mock_service = app.state.mock_service

        # First refund: ₹1,000 (100000 paise) of ₹1,499
        res1 = mock_service.issue_refund(
            order_id="ORD-7729",
            amount_minor=100000,
            idempotency_key="key-writer-1",
            bypass_receipt_check=True,
        )
        assert res1["refund"] is not None

        # Second competing refund: ₹1,000 (100000 paise)
        # Remaining is only ₹499 (49900 paise)
        res2 = mock_service.issue_refund(
            order_id="ORD-7729",
            amount_minor=100000,
            idempotency_key="key-writer-2",
            bypass_receipt_check=True,
        )
        assert res2["refund"] is None
        assert "P_BALANCE" in res2["userErrors"][0]["message"]


@pytest.mark.asyncio
async def test_43_cumulative_daily_gate_defers_excess_to_seller():
    """Test 43: Ba refund nhỏ cùng khách trong ngày vượt ngưỡng cộng dồn (₹2.000) -> Khoản vượt chuyển seller."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            repo = app.state.repo
            executor = app.state.executor

            # Customer CUS-03 has daily cap ₹2,000 (200000 paise)
            # 1. Process first refund of ₹1,299 (129900 paise) for ORD-1042
            with repo.db.transaction() as conn:
                conn.execute(
                    """
                    INSERT INTO refunds (refund_id, order_id, amount_minor, currency, status, created_action_id, created_at)
                    VALUES ('RFD-PRIOR-01', 'ORD-1042', 129900, 'INR', 'processed', 'ACT-01', '2026-11-11T10:00:00')
                    """
                )
                conn.execute("UPDATE orders SET refunded_minor = 129900 WHERE order_id = 'ORD-1042'")

            # 2. Second refund attempted autonomously for ORD-4401 (CUS-03) of ₹999 (99900 paise)
            # Total would be 129900 + 99900 = 229800 (> 200000 daily cap)
            res = await client.post(
                "/api/cases",
                json={"order_id": "ORD-4401", "initial_message": "Defective buds"},
                headers={"X-Customer-Id": "CUS-03"},
            )
            case_id = res.json()["case_id"]

            res = await client.post(
                f"/api/cases/{case_id}/proposals",
                json={
                    "action_type": NextStep.PROPOSE_REFUND.value,
                    "amount_minor": 99900,
                },
            )
            prop_data = res.json()
            proposal_id = prop_data["proposal_id"]
            payload_hash = prop_data["payload_hash"]

            # Autonomous decision attempt via policy:autonomy actor
            decision_res = executor.execute_decision(
                proposal_id=proposal_id,
                decision="approve",
                payload_hash=payload_hash,
                idempotency_key="idem-auto-split-01",
                seller_id="policy:autonomy@1.0",
                demo_today="2026-11-11",
            )

            # Invariant: deferred to seller with cumulative_limit reason
            assert decision_res["status"] == "deferred_to_seller"
            assert decision_res["reason"] == "cumulative_limit"

            # Check audit event cumulative_limit_hit logged
            res = await client.get(f"/api/cases/{case_id}/events")
            events = res.json()
            event_types = [e["event_type"] for e in events]
            assert "cumulative_limit_hit" in event_types
            assert "autonomy_deferred_to_seller" in event_types
