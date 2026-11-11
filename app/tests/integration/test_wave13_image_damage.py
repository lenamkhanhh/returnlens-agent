"""Integration tests for Wave 13 S03 real CC photo & DAMAGE image workflow."""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

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
from app.backend.model.provenance import ModelRun


@pytest.mark.asyncio
async def test_wave13_jpeg_damage_photo_flow_and_customer_confirmations():
    """Real JPEG photo with visible damage + ColorClass.OTHER stays on DAMAGE path and surfaces ₹1,299 & label ID."""
    photo_path = (
        Path(__file__).resolve().parents[2]
        / "demo"
        / "media"
        / "stock"
        / "flickr_broken_headphones_gabrielsaldana_4728001748.jpg"
    )
    assert photo_path.exists(), f"Missing stock damage photo at {photo_path}"
    photo_bytes = photo_path.read_bytes()

    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)

        # Ensure new seed row ORD-1043 exists alongside untouched ORD-1042
        assert app.state.repo.get_order("ORD-1042") is not None
        ord_1043 = app.state.repo.get_order("ORD-1043")
        assert ord_1043 is not None
        assert ord_1043.customer_id == "CUS-06"
        assert ord_1043.line_item.sku == "HEAD-BLK-01"

        mock_observer = MagicMock()
        mock_observer.observe.return_value = (
            ObserverOutput(
                observations=[
                    ObservationItem(
                        id="OBS-DMG-01",
                        evidence_id="EVI-01",
                        t=None,
                        attribute=ObservationAttribute.DAMAGE,
                        value="broken headband patched with white tape",
                        visibility=Visibility.VISIBLE,
                    ),
                    ObservationItem(
                        id="OBS-COL-01",
                        evidence_id="EVI-01",
                        t=None,
                        attribute=ObservationAttribute.COLOR,
                        value="black and silver",
                        color_class=ColorClass.OTHER,
                        visibility=Visibility.VISIBLE,
                    ),
                ],
                unknowns=["barcode", "exact_model"],
                ignored_instructions=False,
            ),
            ModelRun(
                run_id="RUN-WAVE13-01",
                model_id="gemini-3.5-flash-lite",
            ),
        )
        app.state.engine.observer_runner = mock_observer

        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            res_case = await client.post(
                "/api/cases",
                json={
                    "order_id": "ORD-1043",
                    "initial_message": "The headband cracked during normal use.",
                },
                headers={"X-Customer-Id": "CUS-06"},
            )
            assert res_case.status_code == 202
            case_id = res_case.json()["case_id"]

            res_evi = await client.post(
                f"/api/cases/{case_id}/evidence",
                files={"file": (photo_path.name, photo_bytes, "image/jpeg")},
                headers={"X-Customer-Id": "CUS-06"},
            )
            assert res_evi.status_code == 201

            # Verify engine passed true image/jpeg MIME type to observer (not hardcoded image/png)
            assert mock_observer.observe.called
            assert mock_observer.observe.call_args.kwargs["mime_type"] == "image/jpeg"

            # Verify UNCLEAR (ColorClass.OTHER) + visible damage stays on DAMAGE path to PROPOSE_RETURN
            snap_ret = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-06"})
            assert snap_ret.status_code == 200
            snap_data = snap_ret.json()
            assert snap_data["case_type"] == CaseType.DAMAGE.value
            assert snap_data["state"] == CaseState.WAITING_SELLER.value

            proposals = app.state.repo.list_case_proposals(case_id)
            ret_prop = next(p for p in proposals if p.action_type == NextStep.PROPOSE_RETURN)
            assert not any(p.action_type == NextStep.PROPOSE_REFUND for p in proposals)

            # Approve return
            res_ret = await client.post(
                f"/api/proposals/{ret_prop.proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": ret_prop.payload_hash},
                headers={"Idempotency-Key": f"DEC-RET-{case_id}"},
            )
            assert res_ret.status_code == 200

            with app.state.repo.db.cursor() as cur:
                cur.execute("SELECT label_id FROM returns WHERE order_id = ?", ("ORD-1043",))
                ret_row = cur.fetchone()
            assert ret_row is not None
            label_id = ret_row["label_id"]

            # Fire RETURN_RECEIVED
            res_rcv = await client.post(
                "/api/operator/courier-events",
                json={"shipment_id": "SHP-1043", "type": "RETURN_RECEIVED"},
            )
            assert res_rcv.status_code == 200

            proposals_v2 = app.state.repo.list_case_proposals(case_id)
            ref_prop = next(p for p in proposals_v2 if p.action_type == NextStep.PROPOSE_REFUND)

            # Approve refund and verify idempotent replay
            res_ref = await client.post(
                f"/api/proposals/{ref_prop.proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": ref_prop.payload_hash},
                headers={"Idempotency-Key": f"DEC-REF-{case_id}"},
            )
            assert res_ref.status_code == 200

            res_replay = await client.post(
                f"/api/proposals/{ref_prop.proposal_id}/decisions",
                json={"decision": "approve", "payload_hash": ref_prop.payload_hash},
                headers={"Idempotency-Key": f"DEC-REF-{case_id}"},
            )
            assert res_replay.status_code == 200
            assert res_replay.json().get("action_id") == res_ref.json().get("action_id")
            assert res_replay.json().get("status") == "succeeded"

            with app.state.repo.db.cursor() as cur:
                cur.execute("SELECT count(*) AS cnt FROM refunds WHERE order_id = ?", ("ORD-1043",))
                assert cur.fetchone()["cnt"] == 1

            # Verify customer-visible messages include both return label ID and comma-formatted ₹1,299.00
            snap_final = await client.get(f"/api/cases/{case_id}", headers={"X-Customer-Id": "CUS-06"})
            assert snap_final.status_code == 200
            final_data = snap_final.json()
            assert final_data["state"] == CaseState.RESOLVED.value
            combined_outbound = " ".join(
                m["text"] for m in final_data["messages"] if m["role"] in ("agent", "seller")
            )
            assert label_id in combined_outbound
            assert "1,299.00" in combined_outbound

            updated_order = app.state.repo.get_order("ORD-1043")
            assert updated_order is not None
            assert updated_order.refunded_minor == 129900
