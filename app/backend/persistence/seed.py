"""Domain Seed Fixtures per 14 §5 and 17 §8.

Populates store Dhun Audio, 5 customers, 4 products, 7 orders with shipments
relative to DEMO_TODAY, default autonomy policy, and supports clean multi-run reset.
"""

from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Optional

from app.backend.contracts import AutonomyLevel, CaseType
from app.backend.persistence.db import Database


DEFAULT_DEMO_TODAY = "2026-11-11"
STORE_ID = "store_dhun"


def seed_database(db: Database, demo_today_str: Optional[str] = None) -> date:
    """Seed the database with canonical prototype fixtures (14 §5)."""
    if not demo_today_str:
        demo_today_str = DEFAULT_DEMO_TODAY

    demo_today = date.fromisoformat(demo_today_str)
    now_iso = datetime.now(timezone.utc).isoformat()

    with db.transaction() as conn:
        # 1. Store
        conn.execute(
            """
            INSERT OR REPLACE INTO stores (
                store_id, name, policy_version, timezone, return_window_days, cap_minor, require_receipt_before_refund
            ) VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (STORE_ID, "Dhun Audio", "1.0", "Asia/Kolkata", 7, 300000, 1),
        )

        # 2. Customers (14 §5)
        customers = [
            ("CUS-01", STORE_ID, "Priya Sharma", "+91 90000 00001", "en", "original", 0, now_iso),
            ("CUS-02", STORE_ID, "Arjun Mehta", "+91 90000 00002", "hi", "original", 0, now_iso),
            ("CUS-03", STORE_ID, "Kavya Iyer", "+91 90000 00003", "en", "original", 0, now_iso),
            ("CUS-04", STORE_ID, "Rohan Das", "+91 90000 00004", "hinglish", "original", 0, now_iso),
            ("CUS-05", STORE_ID, "Sneha Patil", "+91 90000 00005", "hinglish", "original", 0, now_iso),
        ]
        conn.executemany(
            """
            INSERT OR REPLACE INTO customers (
                customer_id, store_id, name, phone, preferred_language, refund_destination, prior_case_count, updated_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            customers,
        )

        # 3. Products / SKUs (14 §5)
        products = [
            ("HEAD-WHT-02", STORE_ID, "Dhun Wave Headphones", "white", 149900),
            ("HEAD-BLK-02", STORE_ID, "Dhun Wave Headphones", "black", 149900),
            ("HEAD-WHT-01", STORE_ID, "Dhun Lite Headphones", "white", 129900),
            ("BUDS-GRY-01", STORE_ID, "Dhun Buds", "grey", 99900),
        ]
        conn.executemany(
            """
            INSERT OR REPLACE INTO products (
                sku, store_id, name, color, price_minor
            ) VALUES (?, ?, ?, ?, ?)
            """,
            products,
        )

        # 4. Orders & Shipments (14 §5, relative to demo_today)
        # ORD-2030: In transit, ETA +2 days
        # ORD-1042: Delivered -4 days
        # ORD-7729: Delivered -4 days
        # ORD-5150: Delivered -3 days
        # ORD-3110: COD, NDR attempt 1
        # ORD-0915: Delivered -14 days (Late)
        # ORD-4401: Delivered -2 days
        orders_data = [
            (
                "ORD-2030", STORE_ID, "CUS-01", "INR", 99900, 0, 0, 1,
                "item_2030", "BUDS-GRY-01", "grey", "Dhun Buds", 1, 99900, "Prepaid",
                "SHP-2030", "IN_TRANSIT", None, (demo_today - timedelta(days=1)).isoformat(), 1,
                (demo_today + timedelta(days=2)).isoformat(), "Flat 12B, Test Residency, Bengaluru 560034", "560034", 0, None,
            ),
            (
                "ORD-1042", STORE_ID, "CUS-03", "INR", 129900, 0, 0, 1,
                "item_1042", "HEAD-WHT-01", "white", "Dhun Lite Headphones", 1, 129900, "Prepaid",
                "SHP-1042", "DELIVERED", (demo_today - timedelta(days=4)).isoformat(), (demo_today - timedelta(days=4)).isoformat(), 1,
                (demo_today - timedelta(days=4)).isoformat(), "Flat 12B, Test Residency, Chennai 600020", "600020", 1, None,
            ),
            (
                "ORD-7729", STORE_ID, "CUS-02", "INR", 149900, 0, 0, 1,
                "item_7729", "HEAD-WHT-02", "white", "Dhun Wave Headphones", 1, 149900, "Prepaid",
                "SHP-7729", "DELIVERED", (demo_today - timedelta(days=4)).isoformat(), (demo_today - timedelta(days=4)).isoformat(), 1,
                (demo_today - timedelta(days=4)).isoformat(), "Flat 12B, Test Residency, Mumbai 400053", "400053", 1, None,
            ),
            (
                "ORD-5150", STORE_ID, "CUS-04", "INR", 149900, 0, 0, 1,
                "item_5150", "HEAD-WHT-02", "white", "Dhun Wave Headphones", 1, 149900, "Prepaid",
                "SHP-5150", "DELIVERED", (demo_today - timedelta(days=3)).isoformat(), (demo_today - timedelta(days=3)).isoformat(), 1,
                (demo_today - timedelta(days=3)).isoformat(), "Flat 12B, Test Residency, Delhi 110017", "110017", 1, None,
            ),
            (
                "ORD-3110", STORE_ID, "CUS-05", "INR", 149900, 0, 0, 1,
                "item_3110", "HEAD-BLK-02", "black", "Dhun Wave Headphones", 1, 149900, "COD",
                "SHP-3110", "NDR", None, (demo_today - timedelta(days=1)).isoformat(), 1,
                demo_today.isoformat(), "Flat 12B, Test Residency, Pune 411038", "411038", 1, "customer_not_available",
            ),
            (
                "ORD-0915", STORE_ID, "CUS-01", "INR", 129900, 0, 0, 1,
                "item_0915", "HEAD-WHT-01", "white", "Dhun Lite Headphones", 1, 129900, "Prepaid",
                "SHP-0915", "DELIVERED", (demo_today - timedelta(days=14)).isoformat(), (demo_today - timedelta(days=14)).isoformat(), 1,
                (demo_today - timedelta(days=14)).isoformat(), "Flat 12B, Test Residency, Bengaluru 560034", "560034", 1, None,
            ),
            (
                "ORD-4401", STORE_ID, "CUS-03", "INR", 99900, 0, 0, 1,
                "item_4401", "BUDS-GRY-01", "grey", "Dhun Buds", 1, 99900, "Prepaid",
                "SHP-4401", "DELIVERED", (demo_today - timedelta(days=2)).isoformat(), (demo_today - timedelta(days=2)).isoformat(), 1,
                (demo_today - timedelta(days=2)).isoformat(), "Flat 12B, Test Residency, Chennai 600020", "600020", 1, None,
            ),
        ]

        for item in orders_data:
            (
                order_id, store_id, customer_id, currency, paid, refunded, reserved, rev,
                item_id, sku, color, name, qty, refundable_minor, pay_method,
                shp_id, shp_status, delivered_at, scan_at, shp_rev, eta, addr, pincode, attempts, reason
            ) = item

            conn.execute(
                """
                INSERT OR REPLACE INTO orders (
                    order_id, store_id, customer_id, currency, paid_minor, refunded_minor, reserved_minor,
                    revision, item_id, sku, catalog_color, display_name, quantity, refundable_item_minor, payment_method
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (order_id, store_id, customer_id, currency, paid, refunded, reserved, rev,
                 item_id, sku, color, name, qty, refundable_minor, pay_method),
            )

            conn.execute(
                """
                INSERT OR REPLACE INTO shipments (
                    shipment_id, order_id, carrier_label, status, delivered_at, latest_scan_at,
                    source_revision, eta, recipient_address, pincode, attempt_count, reason
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (shp_id, order_id, "Delhivery", shp_status, delivered_at, scan_at,
                 shp_rev, eta, addr, pincode, attempts, reason),
            )

        # 5. Default Autonomy Policy (17 §8, 02 §5b)
        levels_map = {
            CaseType.WISMO.value: AutonomyLevel.L1.value,
            CaseType.DAMAGE.value: AutonomyLevel.L0.value,
            CaseType.MISMATCH.value: AutonomyLevel.L0.value,
            CaseType.UNCLEAR.value: AutonomyLevel.L0.value,
            CaseType.LATE.value: AutonomyLevel.L0.value,
            CaseType.NDR.value: AutonomyLevel.L1.value,
        }
        conn.execute(
            """
            INSERT OR REPLACE INTO autonomy_policies (
                store_id, version, levels_json, per_order_cap_minor, per_customer_daily_cap_minor, kill_switch, changed_by, changed_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (STORE_ID, "1.0", json.dumps(levels_map), 150000, 200000, 0, "seller", now_iso),
        )

    return demo_today


def reset_database(db: Database, demo_today_str: Optional[str] = None) -> date:
    """Clear all dynamic case data and re-seed clean baseline."""
    # Temporarily disable foreign keys for clean truncation
    conn = db.get_connection()
    try:
        conn.execute("PRAGMA foreign_keys = OFF;")
        tables = [
            "refunds", "returns", "actions", "approvals", "proposals",
            "policy_checks", "observations", "evidence", "messages",
            "plan_records", "jobs", "cases", "shipments", "orders",
            "products", "customers", "autonomy_policies", "stores",
            "courier_events", "audit_events"
        ]
        for t in tables:
            conn.execute(f"DELETE FROM {t};")
        conn.execute("PRAGMA foreign_keys = ON;")
    finally:
        conn.close()

    return seed_database(db, demo_today_str)
