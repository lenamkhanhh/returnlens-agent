"""Integration tests for Card B03 Status Slice (Tests 01, 02, 03).

Validates:
- Test 01: WISMO chat queries live mock tools, replies with verified facts and emits timeline events.
- Test 02: Tracking counterfactual updates backend state; subsequent query reflects latest revision.
- Test 03: Customer boundary enforcement: unauthorized access to other customers' orders or cases is denied without leaking data.
"""

from datetime import date, timedelta
from pathlib import Path
import tempfile
import pytest
from httpx import ASGITransport, AsyncClient

from app.backend.main import create_app


@pytest.mark.asyncio
async def test_01_wismo_chat_returns_real_tool_facts_and_timeline():
    """Test 01: Chat hỏi tracking -> Facts khớp mock backend, trace có tool result."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        demo_today = "2026-11-11"
        app = create_app(data_dir=tmp_dir, demo_today=demo_today, harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Customer CUS-01 asks about ORD-2030
            create_payload = {
                "order_id": "ORD-2030",
                "initial_message": "Where is my order? When will it arrive?",
                "client_message_id": "client-msg-101",
            }
            res = await client.post(
                "/api/cases",
                json=create_payload,
                headers={"X-Customer-Id": "CUS-01"},
            )
            assert res.status_code == 202
            case_info = res.json()
            case_id = case_info["case_id"]
            assert case_id.startswith("CASE-")
            assert case_info["accepted_revision"] == 1

            # 2. Inspect Case Snapshot
            res = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-01"})
            assert res.status_code == 200
            snapshot = res.json()
            assert snapshot["case_id"] == case_id
            assert snapshot["case_type"] == "WISMO"
            assert snapshot["state"] == "RESOLVED"  # WISMO status reply resolves case (18 §2 S01)
            assert snapshot["facts"]["order"]["order_id"] == "ORD-2030"
            assert snapshot["facts"]["shipment"]["status"] == "IN_TRANSIT"

            expected_eta = (date.fromisoformat(demo_today) + timedelta(days=2)).isoformat()
            assert snapshot["facts"]["shipment"]["eta"] == expected_eta

            # 3. Check Audit Events / Timeline trace (02 §8, 17 §7)
            res = await client.get(f"/api/cases/{case_id}/events")
            assert res.status_code == 200
            events = res.json()
            event_types = [e["event_type"] for e in events]

            # Invariant: trace has message_received, tool_call_succeeded, customer_reply_delivered
            assert "message_received" in event_types
            assert "tool_call_succeeded" in event_types
            assert "customer_reply_delivered" in event_types

            # Verify human-readable labels from 17 §7
            outcomes = [e["outcome"] for e in events]
            assert "Checked order ORD-2030" in outcomes
            assert "Checked tracking" in outcomes

            # 4. Check Messages in database
            repo = app.state.repo
            messages = repo.get_case_messages(case_id)
            assert len(messages) == 2  # 1 customer inbound + 1 agent reply
            customer_msg = messages[0]
            agent_reply = messages[1]

            assert customer_msg.role.value == "customer"
            assert agent_reply.role.value == "agent"
            assert "ORD-2030" in agent_reply.text
            assert "in transit" in agent_reply.text.lower()
            assert expected_eta in agent_reply.text


@pytest.mark.asyncio
async def test_02_wismo_counterfactual_reflects_updated_backend():
    """Test 02: Đổi tracking ở backend, hỏi lại -> Reply lấy revision mới, không lặp cache cũ."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        demo_today = "2026-11-11"
        app = create_app(data_dir=tmp_dir, demo_today=demo_today, harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. First inquiry: In transit
            res = await client.post(
                "/api/cases",
                json={"order_id": "ORD-2030", "initial_message": "Where is my package?"},
                headers={"X-Customer-Id": "CUS-01"},
            )
            assert res.status_code == 202
            case_id = res.json()["case_id"]

            repo = app.state.repo
            messages_v1 = repo.get_case_messages(case_id)
            reply_v1 = messages_v1[1].text
            assert "in transit" in reply_v1.lower()

            # 2. Counterfactual mutation: Backend shipment status changes to OUT_FOR_DELIVERY
            updated = repo.update_shipment_status("SHP-2030", status="OUT_FOR_DELIVERY", scan_at=demo_today)
            assert updated is True

            # 3. Customer asks again on the same case
            res = await client.post(
                f"/api/cases/{case_id}/messages",
                json={"text": "Any updates on my delivery today?"},
                headers={"X-Customer-Id": "CUS-01"},
            )
            assert res.status_code == 202

            # 4. Verify new reply reflects latest backend state without stale caching
            messages_v2 = repo.get_case_messages(case_id)
            assert len(messages_v2) == 4  # 2 customer + 2 agent
            reply_v2 = messages_v2[3].text

            assert "out for delivery" in reply_v2.lower()
            assert reply_v2 != reply_v1


@pytest.mark.asyncio
async def test_03_customer_isolation_and_access_denial():
    """Test 03: Customer truy cập đơn/case khác -> Không lộ dữ liệu; server deny (404)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        demo_today = "2026-11-11"
        app = create_app(data_dir=tmp_dir, demo_today=demo_today, harness_mode=True)
        transport = ASGITransport(app=app)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # ORD-2030 belongs to CUS-01. Customer CUS-02 attempts to initiate a case on it.
            res = await client.post(
                "/api/cases",
                json={"order_id": "ORD-2030", "initial_message": "Check status of ORD-2030"},
                headers={"X-Customer-Id": "CUS-02"},
            )
            assert res.status_code == 404
            err = res.json()
            assert err["code"] == "NOT_FOUND"

            # Valid case created by CUS-01
            res = await client.post(
                "/api/cases",
                json={"order_id": "ORD-2030", "initial_message": "Status update please"},
                headers={"X-Customer-Id": "CUS-01"},
            )
            assert res.status_code == 202
            case_id = res.json()["case_id"]

            # CUS-02 attempts to inspect CUS-01's case snapshot
            res = await client.get(
                f"/api/cases/{case_id}",
                headers={"X-Customer-Id": "CUS-02"},
            )
            assert res.status_code == 404
            assert res.json()["code"] == "NOT_FOUND"
