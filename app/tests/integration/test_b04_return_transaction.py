"""Integration tests for Card B04 Return Transaction (Tests 16, 17, 18, 19, 37, 38).

Validates:
- Test 16: Exact seller approval executes proposal, creates return + mock label, links audit, moves state to WAITING_RETURN.
- Test 17: Proposal freshness / stale rejection (409) if order revision or payload hash changes prior to approval.
- Test 18: Idempotent replay: identical key and payload returns prior result without duplicate mutation.
- Test 19: Conflict rejection (409): identical idempotency key with conflicting payload.
- Test 37: Single approval consumption: an approval cannot be consumed across multiple actions.
- Test 38: Quantity and active-return concurrency gate: Shopify returnCreate userErrors if item already returned.
"""

import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from app.backend.contracts import CaseState, NextStep
from app.backend.main import create_app


@pytest.mark.asyncio
async def test_16_seller_exact_approval_creates_return_and_emits_audit():
    """Test 16: Seller approval chính xác -> Action đúng proposal/payload, audit liên kết."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create case for ORD-1042 (Customer CUS-03)
            res = await client.post(
                "/api/cases",
                json={"order_id": "ORD-1042", "initial_message": "The headband is cracked"},
                headers={"X-Customer-Id": "CUS-03"},
            )
            assert res.status_code == 202
            case_id = res.json()["case_id"]

            # 2. Agent creates PROPOSE_RETURN proposal
            res = await client.post(
                f"/api/cases/{case_id}/proposals",
                json={
                    "action_type": NextStep.PROPOSE_RETURN.value,
                    "item_id": "item_1042",
                    "customer_reply_draft": "Your return for ORD-1042 has been authorized.",
                },
            )
            assert res.status_code == 201
            prop_data = res.json()
            proposal_id = prop_data["proposal_id"]
            payload_hash = prop_data["payload_hash"]

            # 3. Seller approves proposal with exact payload_hash and unique Idempotency-Key
            idempotency_key = "idem-approve-001"
            res = await client.post(
                f"/api/proposals/{proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": payload_hash},
                headers={"Idempotency-Key": idempotency_key, "X-Seller-Id": "seller_dhun"},
            )
            assert res.status_code == 200
            decision_res = res.json()
            action_id = decision_res["action_id"]
            assert decision_res["status"] == "succeeded"

            # 4. Verify Case State transitioned to WAITING_RETURN (01 §5, 17 §2)
            res = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-03"})
            assert res.status_code == 200
            snapshot = res.json()
            assert snapshot["state"] == CaseState.WAITING_RETURN.value

            # 5. Verify Return record created with mock label in DB
            repo = app.state.repo
            with repo.db.cursor() as cur:
                cur.execute("SELECT * FROM returns WHERE order_id = 'ORD-1042'")
                ret_row = cur.fetchone()
                assert ret_row is not None
                assert ret_row["status"] == "requested"
                assert ret_row["label_id"].startswith("LBL-RET-")
                assert ret_row["created_action_id"] == action_id

            # 6. Verify Audit Events emitted and linked (02 §8, 17 §7)
            res = await client.get(f"/api/cases/{case_id}/events")
            assert res.status_code == 200
            events = res.json()
            event_types = [e["event_type"] for e in events]
            assert "approval_recorded" in event_types
            assert "return_created" in event_types
            assert "customer_reply_delivered" in event_types

            # 7. Verify Customer receives outbound notification message with label ID
            messages = repo.get_case_messages(case_id)
            latest_msg = messages[-1]
            assert latest_msg.role.value == "seller"
            assert "approved" in latest_msg.text.lower()
            assert ret_row["label_id"] in latest_msg.text


@pytest.mark.asyncio
async def test_17_stale_basis_or_payload_hash_mismatch_rejected_with_409():
    """Test 17: Evidence/policy/balance đổi trước approve -> Stale reject (409), cần review lại."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
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
            proposal_id = res.json()["proposal_id"]
            valid_payload_hash = res.json()["payload_hash"]

            # Scenario A: Payload hash mismatch (e.g. stale client modal)
            tampered_hash = "0" * 64
            res = await client.post(
                f"/api/proposals/{proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": tampered_hash},
                headers={"Idempotency-Key": "idem-stale-001"},
            )
            assert res.status_code == 409
            assert res.json()["code"] == "CONFLICT"

            # Scenario B: Order revision mutated before approval (e.g. balance or status changed)
            repo = app.state.repo
            with repo.db.transaction() as conn:
                conn.execute("UPDATE orders SET revision = revision + 1 WHERE order_id = 'ORD-1042'")

            res = await client.post(
                f"/api/proposals/{proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": valid_payload_hash},
                headers={"Idempotency-Key": "idem-stale-002"},
            )
            assert res.status_code == 409
            assert "stale" in res.json()["user_message"].lower()


@pytest.mark.asyncio
async def test_18_idempotent_retry_returns_prior_result_without_duplicate():
    """Test 18: Retry cùng key và cùng payload -> Cùng result ID, một mutation."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/cases",
                json={"order_id": "ORD-1042", "initial_message": "Return request"},
                headers={"X-Customer-Id": "CUS-03"},
            )
            case_id = res.json()["case_id"]

            res = await client.post(
                f"/api/cases/{case_id}/proposals",
                json={"action_type": NextStep.PROPOSE_RETURN.value, "item_id": "item_1042"},
            )
            proposal_id = res.json()["proposal_id"]
            payload_hash = res.json()["payload_hash"]

            idem_key = "idem-replay-test-01"

            # 1. First execution
            res1 = await client.post(
                f"/api/proposals/{proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": payload_hash},
                headers={"Idempotency-Key": idem_key},
            )
            assert res1.status_code == 200
            data1 = res1.json()
            action_id_1 = data1["action_id"]

            # 2. Second execution (replay with same key and same payload)
            res2 = await client.post(
                f"/api/proposals/{proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": payload_hash},
                headers={"Idempotency-Key": idem_key},
            )
            assert res2.status_code == 200
            data2 = res2.json()
            action_id_2 = data2["action_id"]

            # Invariant: identical action ID returned, exactly ONE return in DB
            assert action_id_1 == action_id_2

            repo = app.state.repo
            with repo.db.cursor() as cur:
                cur.execute("SELECT COUNT(*) AS c FROM returns WHERE order_id = 'ORD-1042'")
                count = cur.fetchone()["c"]
                assert count == 1


@pytest.mark.asyncio
async def test_19_same_key_different_payload_returns_409_conflict():
    """Test 19: Cùng key, payload khác -> Conflict (409), không mutation thêm."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/cases",
                json={"order_id": "ORD-1042", "initial_message": "First case"},
                headers={"X-Customer-Id": "CUS-03"},
            )
            case_id = res.json()["case_id"]

            res = await client.post(
                f"/api/cases/{case_id}/proposals",
                json={"action_type": NextStep.PROPOSE_RETURN.value, "item_id": "item_1042"},
            )
            proposal_id = res.json()["proposal_id"]
            payload_hash = res.json()["payload_hash"]

            shared_key = "reused-idempotency-key-001"

            # 1. Success on original payload
            res = await client.post(
                f"/api/proposals/{proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": payload_hash},
                headers={"Idempotency-Key": shared_key},
            )
            assert res.status_code == 200

            # 2. Reuse same key with conflicting/different payload hash
            res = await client.post(
                f"/api/proposals/{proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": "a" * 64},
                headers={"Idempotency-Key": shared_key},
            )
            assert res.status_code == 409
            assert res.json()["code"] == "CONFLICT"


@pytest.mark.asyncio
async def test_37_single_approval_cannot_be_consumed_by_two_action_keys():
    """Test 37: Một approval bị dùng qua hai action keys -> Chỉ một action được consume approval."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/cases",
                json={"order_id": "ORD-1042", "initial_message": "Return claim"},
                headers={"X-Customer-Id": "CUS-03"},
            )
            case_id = res.json()["case_id"]

            res = await client.post(
                f"/api/cases/{case_id}/proposals",
                json={"action_type": NextStep.PROPOSE_RETURN.value, "item_id": "item_1042"},
            )
            proposal_id = res.json()["proposal_id"]
            payload_hash = res.json()["payload_hash"]

            # First action consumes approval
            res1 = await client.post(
                f"/api/proposals/{proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": payload_hash},
                headers={"Idempotency-Key": "action-key-alpha"},
            )
            assert res1.status_code == 200

            # Second distinct action key attempts to consume the same proposal/approval
            res2 = await client.post(
                f"/api/proposals/{proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": payload_hash},
                headers={"Idempotency-Key": "action-key-beta"},
            )
            assert res2.status_code == 409
            assert "already been consumed" in res2.json()["user_message"].lower()


@pytest.mark.asyncio
async def test_38_two_competing_create_returns_respect_line_item_quantity():
    """Test 38: Hai create-return cạnh tranh cho cùng item -> Chỉ một active return cho quantity=1."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        mock_service = app.state.mock_service

        # 1. First return for ORD-7729 (item quantity=1)
        res1 = mock_service.create_return(
            order_id="ORD-7729",
            item_id="item_7729",
            quantity=1,
            return_reason="COLOR_MISMATCH",
            action_id="ACT-FIRST",
        )
        assert res1["return"] is not None
        assert len(res1["userErrors"]) == 0

        # 2. Competing return creation on same item
        res2 = mock_service.create_return(
            order_id="ORD-7729",
            item_id="item_7729",
            quantity=1,
            return_reason="COLOR_MISMATCH",
            action_id="ACT-SECOND",
        )
        assert res2["return"] is None
        assert len(res2["userErrors"]) == 1
        assert "already been returned" in res2["userErrors"][0]["message"].lower()
