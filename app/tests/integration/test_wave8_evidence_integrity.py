"""Wave 8: Evidence Integrity & Model-Grounded Decisions.

Per WAVE8_EVIDENCE_INTEGRITY.md:
1. Every evidence-based decision (MISMATCH, DAMAGE, UNCLEAR, request close-up, propose return)
   must come from validated observations compared with order facts in code (17 §2 colour rule).
2. When the model is unavailable or returns nothing valid: the case goes to HUMAN_REVIEW
   with reason model_unavailable and verified facts.
3. Keyword shortcuts removed: with observer stubbed to return color_class=white for ORD-7729 (catalog white),
   customer text "got black" must NOT produce a mismatch request.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest
from httpx import ASGITransport, AsyncClient

from app.backend.contracts import (
    CaseState,
    ColorClass,
    ObservationAttribute,
    ObservationItem,
    ObserverOutput,
    Visibility,
)
from app.backend.main import create_app
from app.backend.model.exceptions import ModelUnavailableError
from app.backend.model.observer import VisionObserverRunner
from app.backend.model.provenance import ModelRun


@pytest.mark.asyncio
async def test_wave8_no_keyword_shortcut_when_observer_sees_white():
    """Test Wave 8.3: Observer returns color_class=white for ORD-7729 (catalog white).

    Customer text claiming 'got black' must NOT produce a mismatch clarification request.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)

        # Mock observer runner to return white headphones
        mock_runner = MagicMock(spec=VisionObserverRunner)
        mock_runner.observe.return_value = (
            ObserverOutput(
                observations=[
                    ObservationItem(
                        id="OBS-WHT-1",
                        evidence_id="EVI-TEST-01",
                        t="00:05",
                        attribute=ObservationAttribute.COLOR,
                        value="white",
                        color_class=ColorClass.WHITE,
                        visibility=Visibility.VISIBLE,
                    )
                ],
                unknowns=[],
                ignored_instructions=False,
            ),
            ModelRun(
                run_id="RUN-TEST-01",
                model_id="gemini-3.8-flash",
            ),
        )
        app.state.engine.observer_runner = mock_runner

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Customer initiates claim with keyword "got black" on white catalog item
            res = await client.post(
                "/api/cases",
                json={
                    "order_id": "ORD-7729",
                    "initial_message": "I ordered white headphones but got black ones instead.",
                },
                headers={"X-Customer-Id": "CUS-02"},
            )
            assert res.status_code == 202
            case_id = res.json()["case_id"]

            # 2. Upload video evidence (observed as white by mock runner)
            dummy_bytes = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 200
            res_upload = await client.post(
                f"/api/cases/{case_id}/evidence",
                files={"file": ("test_clip.mp4", dummy_bytes, "video/mp4")},
                headers={"X-Customer-Id": "CUS-02"},
            )
            assert res_upload.status_code == 201

            # 3. Verify case state and audit trail: NO mismatch clarification sent!
            res_snap = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-02"})
            assert res_snap.status_code == 200
            snap = res_snap.json()

            # Must NOT take the colour-mismatch path (label-photo request) on the claim text alone.
            # The evidence shows white and no damage, so the agent may ask once for a close-up.
            assert snap["clarification_count"] <= 1

            res_events = await client.get(f"/api/cases/{case_id}/events")
            events = res_events.json()
            event_types = [e["event_type"] for e in events]
            assert "observation_validated" in event_types
            clar_outcomes = [str(e.get("outcome", "")).lower() for e in events if e["event_type"] == "clarification_sent"]
            assert not any("label" in o for o in clar_outcomes)
            agent_text = " ".join(m["text"].lower() for m in snap.get("messages", []) if m.get("role") == "agent")
            assert "label" not in agent_text
            # No return proposal on unsupported evidence
            assert not snap.get("proposals")


@pytest.mark.asyncio
async def test_wave8_grounded_mismatch_when_observer_sees_black():
    """Test Wave 8.1: Observer returns color_class=black for ORD-7729 (catalog white).

    Grounded mismatch correctly requests box label photo with clarification_sent.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)

        # Mock observer runner to return black headphones
        mock_runner = MagicMock(spec=VisionObserverRunner)
        mock_runner.observe.return_value = (
            ObserverOutput(
                observations=[
                    ObservationItem(
                        id="OBS-BLK-1",
                        evidence_id="EVI-TEST-02",
                        t="00:07",
                        attribute=ObservationAttribute.COLOR,
                        value="black",
                        color_class=ColorClass.BLACK,
                        visibility=Visibility.VISIBLE,
                    )
                ],
                unknowns=["barcode_unverified"],
                ignored_instructions=False,
            ),
            ModelRun(
                run_id="RUN-TEST-02",
                model_id="gemini-3.8-flash",
            ),
        )
        app.state.engine.observer_runner = mock_runner

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/cases",
                json={
                    "order_id": "ORD-7729",
                    "initial_message": "I received the wrong item, please check.",
                },
                headers={"X-Customer-Id": "CUS-02"},
            )
            case_id = res.json()["case_id"]

            # Upload video evidence (observed as black)
            dummy_bytes = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 200
            res_upload = await client.post(
                f"/api/cases/{case_id}/evidence",
                files={"file": ("test_clip.mp4", dummy_bytes, "video/mp4")},
                headers={"X-Customer-Id": "CUS-02"},
            )
            assert res_upload.status_code == 201

            # Case must transition to WAITING_CUSTOMER, clarification_count=1
            res_snap = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-02"})
            snap = res_snap.json()
            assert snap["state"] == CaseState.WAITING_CUSTOMER.value
            assert snap["clarification_count"] == 1

            # Audit events must have observation_validated AND clarification_sent
            res_events = await client.get(f"/api/cases/{case_id}/events")
            events = res_events.json()
            event_types = [e["event_type"] for e in events]
            assert "observation_validated" in event_types
            assert "clarification_sent" in event_types


@pytest.mark.asyncio
async def test_wave8_model_unavailable_routes_to_human_review():
    """Test Wave 8.2: When model adapter raises ModelUnavailableError.

    Case must transition to HUMAN_REVIEW with model_unavailable event, never fake pass.
    """
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)

        mock_runner = MagicMock(spec=VisionObserverRunner)
        mock_runner.observe.side_effect = ModelUnavailableError("API key invalid")
        app.state.engine.observer_runner = mock_runner

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res = await client.post(
                "/api/cases",
                json={
                    "order_id": "ORD-7729",
                    "initial_message": "I got black headphones instead of white.",
                },
                headers={"X-Customer-Id": "CUS-02"},
            )
            case_id = res.json()["case_id"]

            dummy_bytes = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 200
            res_upload = await client.post(
                f"/api/cases/{case_id}/evidence",
                files={"file": ("test_clip.mp4", dummy_bytes, "video/mp4")},
                headers={"X-Customer-Id": "CUS-02"},
            )
            assert res_upload.status_code == 201

            # Snapshot must be HUMAN_REVIEW
            res_snap = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-02"})
            snap = res_snap.json()
            assert snap["state"] == CaseState.HUMAN_REVIEW.value
            case_entity = app.state.repo.get_case(case_id)
            assert "model unavailable" in case_entity.summary.lower()

            # Audit events must record model_unavailable
            res_events = await client.get(f"/api/cases/{case_id}/events")
            events = res_events.json()
            event_types = [e["event_type"] for e in events]
            assert "model_unavailable" in event_types
            assert "clarification_sent" not in event_types
