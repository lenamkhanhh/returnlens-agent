"""Integration Tests for Wave 11 Case B Flow & Plan Records (Role A).

Verifies per Wave 11 dispatch:
1. A.1: Case B Flow - Customer sends text + unboxing clip. Agent does NOT send generic
   no-evidence reply. Grounded observation (black vs catalog white) triggers exactly ONE
   request for the outer-box label photo. After label photo, creates PROPOSE_RETURN proposal.
2. A.2: Plan Records - Every processed turn writes a PlanRecord (goal, tools, outcome, memory_used)
   to SQLite plan_records, and GET /api/cases/{case_id} retrieves and returns it.
3. A.3: Unknowns List - Still unverified / unknowns lists barcode, exact_model, shipping_label
   whenever packaging label / barcode was not observed.
4. A.4: Policy Checks Deduplication - policy_checks in case snapshot deduplicates per rule_id
   (latest result wins, no duplicate P_WINDOW).
"""

from __future__ import annotations

import tempfile
from pathlib import Path
import pytest
from httpx import ASGITransport, AsyncClient

from app.backend.contracts import (
    CaseState,
    CaseType,
    ColorClass,
    NextStep,
    ObservationAttribute,
    ObservationItem,
    ObserverOutput,
    Visibility,
)
from app.backend.main import create_app
from app.backend.memory.plan import get_case_plan
from app.backend.model.provenance import ModelRun
from unittest.mock import MagicMock


@pytest.mark.asyncio
async def test_wave11_a1_case_b_flow_with_clip_and_label():
    """A.1 & A.2: Case B unboxing clip -> outer box label request -> label provided -> PROPOSE_RETURN with PlanRecord."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)

        mock_observer = MagicMock()
        mock_observer.observe.return_value = (
            ObserverOutput(
                observations=[
                    ObservationItem(
                        id="OBS-BLK-01",
                        evidence_id="EVI-01",
                        t="00:07",
                        attribute=ObservationAttribute.COLOR,
                        value="black headphones",
                        color_class=ColorClass.BLACK,
                        visibility=Visibility.VISIBLE,
                    )
                ],
                unknowns=["barcode", "exact_model", "shipping_label"],
                ignored_instructions=False,
            ),
            ModelRun(
                run_id="RUN-TEST-01",
                model_id="gemini-3.5-flash-lite",
            ),
        )
        app.state.engine.observer_runner = mock_observer

        transport = ASGITransport(app=app, raise_app_exceptions=False)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Create case with message indicating unboxing clip attached
            res1 = await client.post(
                "/api/cases",
                json={
                    "order_id": "ORD-7729",
                    "initial_message": "I ordered white headphones but received black ones. Here is the unboxing clip.",
                    "has_attachment": True,
                },
                headers={"X-Customer-Id": "CUS-02"},
            )
            assert res1.status_code == 202
            case_id = res1.json()["case_id"]

            # 2. Upload video evidence (stock clip or synthetic test bytes)
            stock_video = (
                Path(__file__).resolve().parents[2]
                / "demo"
                / "media"
                / "stock"
                / "stock_black_headphones_pexels_9130360.mp4"
            )
            video_bytes = stock_video.read_bytes() if stock_video.exists() else b"FAKE_MP4_BYTES"

            files = {"file": ("stock_black_headphones_pexels_9130360.mp4", video_bytes, "video/mp4")}
            res2 = await client.post(f"/api/cases/{case_id}/evidence", files=files)
            assert res2.status_code == 201

            # 3. Check snapshot after video analysis
            snap1 = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-02"})
            assert snap1.status_code == 200
            data1 = snap1.json()

            # Verify NO premature generic no-evidence prompt was left
            for m in data1.get("messages", []):
                if m.get("role") == "agent":
                    assert "provide a clear photo or unboxing video" not in m.get("text", "").lower()

            # Verify Case Type is MISMATCH
            assert data1["case_type"] == CaseType.MISMATCH.value

            # Verify exactly ONE clarification requested for outer box label
            assert data1["state"] == CaseState.WAITING_CUSTOMER.value
            assert data1["clarification_count"] == 1
            last_agent_msg = [m for m in data1["messages"] if m["role"] == "agent"][-1]["text"]
            assert "outer box label" in last_agent_msg.lower() or "barcode" in last_agent_msg.lower()

            # Verify PlanRecord exists in snapshot
            plan1 = data1.get("plan")
            assert plan1 is not None
            assert "goal" in plan1 and plan1["goal"]
            assert "tools" in plan1 and len(plan1["tools"]) > 0
            assert "outcome" in plan1 and plan1["outcome"]

            # 4. Customer provides outer box label
            res3 = await client.post(
                f"/api/cases/{case_id}/messages",
                json={"text": "Here is the photo of the outer box label showing barcode for ORD-7729."},
                headers={"X-Customer-Id": "CUS-02"},
            )
            assert res3.status_code == 202

            # 5. Snapshot after label verification: PROPOSE_RETURN created, awaiting seller
            snap2 = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-02"})
            assert snap2.status_code == 200
            data2 = snap2.json()

            assert data2["state"] == CaseState.WAITING_SELLER.value
            assert len(data2["proposals"]) >= 1
            proposal = data2["proposals"][0]
            assert proposal["action_type"] == NextStep.PROPOSE_RETURN.value

            # Verify PlanRecord updated
            plan2 = data2.get("plan")
            assert plan2 is not None
            assert plan2["goal"]
            assert NextStep.PROPOSE_RETURN.value in plan2["action_type"] or "return" in plan2["outcome"].lower()


@pytest.mark.asyncio
async def test_wave11_a3_unknowns_list_includes_barcode_and_model():
    """A.3: Unknowns list in Triad Facts includes barcode, exact_model, shipping_label when unverified."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app, raise_app_exceptions=False)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res1 = await client.post(
                "/api/cases",
                json={
                    "order_id": "ORD-7729",
                    "initial_message": "Received wrong color headphones.",
                },
                headers={"X-Customer-Id": "CUS-02"},
            )
            case_id = res1.json()["case_id"]

            snap = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-02"})
            data = snap.json()
            unknowns = data.get("unknowns", [])

            # When packaging/barcode has not been verified, must list barcode, exact_model, shipping_label
            assert "barcode" in unknowns
            assert "exact_model" in unknowns
            assert "shipping_label" in unknowns


@pytest.mark.asyncio
async def test_wave11_a4_policy_checks_deduplication():
    """A.4: Case snapshot policy_checks list deduplicates per rule_id (latest result wins)."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app, raise_app_exceptions=False)

        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res1 = await client.post(
                "/api/cases",
                json={
                    "order_id": "ORD-7729",
                    "initial_message": "I received black headphones instead of white. Here is the unboxing clip.",
                    "has_attachment": True,
                },
                headers={"X-Customer-Id": "CUS-02"},
            )
            case_id = res1.json()["case_id"]

            # Trigger a couple turns
            await client.post(
                f"/api/cases/{case_id}/messages",
                json={"text": "Still checking on this order."},
                headers={"X-Customer-Id": "CUS-02"},
            )

            snap = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-02"})
            data = snap.json()
            policy_checks = data.get("policy_checks", [])

            # Rule IDs must be unique
            rule_ids = [p["rule_id"] for p in policy_checks]
            assert len(rule_ids) == len(set(rule_ids)), f"Duplicate policy checks found: {rule_ids}"
            assert "P_WINDOW" in rule_ids
