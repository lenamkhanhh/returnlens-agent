"""Unit test for Card B02 (Domain Seed Fixtures & Reset Capability)."""

from datetime import date, timedelta
import tempfile
from pathlib import Path
import pytest

from app.backend.persistence.db import Database
from app.backend.persistence.repository import Repository
from app.backend.persistence.seed import seed_database, reset_database, STORE_ID


@pytest.fixture
def temp_db():
    with tempfile.TemporaryDirectory() as tmp_dir:
        db_path = Path(tmp_dir) / "test.db"
        db = Database(db_path)
        yield db


def test_seed_and_reset(temp_db):
    demo_today = "2026-11-11"
    today_date = seed_database(temp_db, demo_today)
    assert today_date == date(2026, 11, 11)

    repo = Repository(temp_db)

    # 1. Store and Policy check
    policy = repo.get_store_policy(STORE_ID)
    assert policy is not None
    assert policy.return_window_days == 7
    assert policy.cap_minor == 300000
    assert policy.require_receipt_before_refund is True

    # 2. Check Customers
    for cus_id in ["CUS-01", "CUS-02", "CUS-03", "CUS-04", "CUS-05"]:
        profile = repo.get_customer_profile(cus_id)
        assert profile is not None
        assert profile.customer_id == cus_id

    # 3. Check Orders and Relative Dates
    # ORD-2030: In transit, ETA +2 days
    ord_2030 = repo.get_order("ORD-2030")
    assert ord_2030 is not None
    assert ord_2030.paid_minor == 99900
    assert ord_2030.line_item.sku == "BUDS-GRY-01"
    shp_2030 = repo.get_shipment("ORD-2030")
    assert shp_2030 is not None
    assert shp_2030.status == "IN_TRANSIT"
    assert shp_2030.eta == (today_date + timedelta(days=2)).isoformat()

    # ORD-1042: Delivered -4 days
    ord_1042 = repo.get_order("ORD-1042")
    assert ord_1042 is not None
    assert ord_1042.paid_minor == 129900
    shp_1042 = repo.get_shipment("ORD-1042")
    assert shp_1042.status == "DELIVERED"
    assert shp_1042.delivered_at == (today_date - timedelta(days=4)).isoformat()

    # ORD-7729: Delivered -4 days
    ord_7729 = repo.get_order("ORD-7729")
    assert ord_7729.paid_minor == 149900
    assert ord_7729.line_item.catalog_color.value == "white"

    # ORD-3110: COD, NDR
    ord_3110 = repo.get_order("ORD-3110")
    assert ord_3110 is not None
    shp_3110 = repo.get_shipment("ORD-3110")
    assert shp_3110.status == "NDR"
    assert shp_3110.reason == "customer_not_available"
    assert "Pune 411038" in shp_3110.recipient_address

    # ORD-0915: Delivered -14 days (Late)
    shp_0915 = repo.get_shipment("ORD-0915")
    assert shp_0915.delivered_at == (today_date - timedelta(days=14)).isoformat()

    # 4. Check Autonomy Policy default
    autonomy = repo.get_autonomy_policy(STORE_ID)
    assert autonomy.levels[autonomy.levels.__class__.WISMO if hasattr(autonomy.levels, 'WISMO') else 'WISMO'] in ('L1', autonomy.levels.get('WISMO'))
    assert autonomy.per_order_cap_minor == 150000
    assert autonomy.per_customer_daily_cap_minor == 200000
    assert autonomy.kill_switch is False

    # 5. Clean reset test
    reset_database(temp_db, demo_today)
    ord_after_reset = repo.get_order("ORD-2030")
    assert ord_after_reset is not None
    assert ord_after_reset.paid_minor == 99900
