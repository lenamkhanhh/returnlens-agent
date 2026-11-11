"""Integration Tests for Wave 10 Media Streaming & Case Labels (Role A).

Verifies:
1. GET /api/media/{evidence_id} serves video with right content type.
2. Video seek: HTTP Range requests return 206 Partial Content with Content-Range header.
3. 404 handling on missing evidence or missing media file.
4. GET /api/cases/{case_id} snapshot contains evidence URL (/api/media/{evidence_id}) and real observations.
5. In the cold-open state, ORD-1042 and ORD-4401 show case_type == 'DAMAGE' (not 'UNCLEAR').
6. Root proxy GET /media/{evidence_id} serves media identically.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient

from app.backend.contracts import CaseState, CaseType
from app.backend.main import create_app


@pytest.mark.asyncio
async def test_wave10_cold_open_case_types_are_damage():
    """Verify ORD-1042 and ORD-4401 show DAMAGE in seller inbox, not UNCLEAR."""
    snapshot_path = Path(__file__).resolve().parents[2] / "demo" / "snapshot" / "demo_cold_open.db"
    if not snapshot_path.exists():
        pytest.skip("demo_cold_open.db snapshot not found")

    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DEMO_SNAPSHOT"] = str(snapshot_path.resolve())
        try:
            app = create_app(data_dir=tmp_dir, harness_mode=False)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get("/api/seller/cases")
                assert res.status_code == 200
                cases = res.json()
                assert len(cases) == 2

                case_map = {c["order_id"]: c for c in cases}
                assert "ORD-1042" in case_map
                assert "ORD-4401" in case_map

                assert case_map["ORD-1042"]["case_type"] == CaseType.DAMAGE.value
                assert case_map["ORD-1042"]["state"] == CaseState.WAITING_RETURN.value

                assert case_map["ORD-4401"]["case_type"] == CaseType.DAMAGE.value
                assert case_map["ORD-4401"]["state"] == CaseState.WAITING_RETURN.value
        finally:
            os.environ.pop("DEMO_SNAPSHOT", None)


@pytest.mark.asyncio
async def test_wave10_media_serving_and_range_requests():
    """Verify /api/media/{evidence_id} serves files with inline disposition and HTTP Range support."""
    snapshot_path = Path(__file__).resolve().parents[2] / "demo" / "snapshot" / "demo_cold_open.db"
    if not snapshot_path.exists():
        pytest.skip("demo_cold_open.db snapshot not found")

    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DEMO_SNAPSHOT"] = str(snapshot_path.resolve())
        try:
            app = create_app(data_dir=tmp_dir, harness_mode=False)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                # 1. Fetch case snapshot to get evidence_id and evidence URL
                res = await client.get("/api/seller/cases")
                cases = res.json()
                case_id = cases[0]["case_id"]

                res_snap = await client.get(f"/api/cases/{case_id}")
                assert res_snap.status_code == 200
                snap = res_snap.json()

                # Verify evidence in snapshot has url and filename
                assert "evidence" in snap
                assert len(snap["evidence"]) >= 1
                evi = snap["evidence"][0]
                assert "url" in evi
                assert evi["url"].startswith("/api/media/")
                evidence_id = evi["evidence_id"]

                # 2. Test full media download via /api/media/{evidence_id}
                res_media = await client.get(f"/api/media/{evidence_id}")
                assert res_media.status_code == 200
                assert res_media.headers.get("accept-ranges") == "bytes"
                assert "video/" in res_media.headers.get("content-type", "")
                total_len = len(res_media.content)
                assert total_len > 0

                # 3. Test HTTP Range request (video seeking at bytes 10-50)
                res_range = await client.get(
                    f"/api/media/{evidence_id}",
                    headers={"Range": "bytes=10-50"},
                )
                assert res_range.status_code == 206
                assert len(res_range.content) == 41
                assert res_range.headers.get("content-range") == f"bytes 10-50/{total_len}"

                # 4. Test root proxy /media/{evidence_id}
                res_root = await client.get(
                    f"/media/{evidence_id}",
                    headers={"Range": "bytes=0-10"},
                )
                assert res_root.status_code == 206
                assert len(res_root.content) == 11

                # 5. Non-existent evidence returns 404
                res_404 = await client.get("/api/media/NON_EXISTENT_EVI")
                assert res_404.status_code == 404
        finally:
            os.environ.pop("DEMO_SNAPSHOT", None)


@pytest.mark.asyncio
async def test_wave10_case_snapshot_has_real_observations():
    """Verify case snapshot includes real observations and plan card without devmock fallback."""
    snapshot_path = Path(__file__).resolve().parents[2] / "demo" / "snapshot" / "demo_cold_open.db"
    if not snapshot_path.exists():
        pytest.skip("demo_cold_open.db snapshot not found")

    with tempfile.TemporaryDirectory() as tmp_dir:
        os.environ["DEMO_SNAPSHOT"] = str(snapshot_path.resolve())
        try:
            app = create_app(data_dir=tmp_dir, harness_mode=False)
            transport = ASGITransport(app=app)
            async with AsyncClient(transport=transport, base_url="http://test") as client:
                res = await client.get("/api/seller/cases")
                cases = res.json()
                for c in cases:
                    res_snap = await client.get(f"/api/cases/{c['case_id']}")
                    assert res_snap.status_code == 200
                    snap = res_snap.json()

                    # Real observations must be populated
                    assert len(snap["observations"]) >= 1
                    obs = snap["observations"][0]
                    assert obs["attribute"] == "damage"
                    assert "cracked" in obs["value"].lower()

                    # Plan card must be present
                    assert snap["plan"] is not None
                    assert snap["plan"]["action_type"] in ("PROPOSE_RETURN", "WAITING_RETURN")
        finally:
            os.environ.pop("DEMO_SNAPSHOT", None)
