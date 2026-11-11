"""Integration tests for app factory, isolation, and seed endpoints (Card B02)."""

import pytest
import tempfile
from pathlib import Path
from httpx import AsyncClient, ASGITransport

from app.backend.main import create_app


@pytest.mark.asyncio
async def test_app_factory_and_endpoints():
    with tempfile.TemporaryDirectory() as tmp_dir:
        app = create_app(data_dir=tmp_dir, demo_today="2026-11-11", harness_mode=True)
        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            # 1. Health endpoint
            res = await client.get("/api/health")
            assert res.status_code == 200
            data = res.json()
            assert data["status"] == "healthy"
            assert data["demo_today"] == "2026-11-11"
            assert data["harness_mode"] is True

            # 2. Store policy endpoint
            res = await client.get("/api/store/policy")
            assert res.status_code == 200
            policy = res.json()
            assert policy["return_window_days"] == 7
            assert policy["cap_minor"] == 300000

            # 3. Customer orders
            res = await client.get("/api/orders?customer_id=CUS-01")
            assert res.status_code == 200
            orders = res.json()
            order_ids = [o["order_id"] for o in orders]
            assert "ORD-2030" in order_ids
            assert "ORD-0915" in order_ids

            # 4. Single order with shipment
            res = await client.get("/api/orders/ORD-2030")
            assert res.status_code == 200
            ord_data = res.json()
            assert ord_data["order"]["order_id"] == "ORD-2030"
            assert ord_data["shipment"]["status"] == "IN_TRANSIT"

            # 5. Customer isolation check (02 §1: inaccessible/not found, no cross-customer leak)
            res = await client.get("/api/orders/ORD-2030?customer_id=CUS-02")
            assert res.status_code == 404

            # 6. Reset endpoint
            res = await client.post("/api/operator/reset")
            assert res.status_code == 200
            assert res.json()["status"] == "reset_successful"
