"""SQLite Database Connection and Schema Management.

Manages tables, WAL mode, foreign keys, and atomic write transactions (BEGIN IMMEDIATE).
"""

from __future__ import annotations

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

SCHEMA_SQL = """
PRAGMA foreign_keys = ON;

CREATE TABLE IF NOT EXISTS stores (
    store_id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    policy_version TEXT NOT NULL DEFAULT '1.0',
    timezone TEXT NOT NULL DEFAULT 'Asia/Kolkata',
    return_window_days INTEGER NOT NULL DEFAULT 7,
    cap_minor INTEGER NOT NULL DEFAULT 300000,
    require_receipt_before_refund INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS customers (
    customer_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    name TEXT NOT NULL,
    phone TEXT NOT NULL,
    preferred_language TEXT NOT NULL DEFAULT 'en',
    refund_destination TEXT NOT NULL DEFAULT 'original',
    prior_case_count INTEGER NOT NULL DEFAULT 0,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS products (
    sku TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    name TEXT NOT NULL,
    color TEXT NOT NULL,
    price_minor INTEGER NOT NULL
);

CREATE TABLE IF NOT EXISTS orders (
    order_id TEXT PRIMARY KEY,
    store_id TEXT NOT NULL REFERENCES stores(store_id),
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    currency TEXT NOT NULL DEFAULT 'INR',
    paid_minor INTEGER NOT NULL,
    refunded_minor INTEGER NOT NULL DEFAULT 0,
    reserved_minor INTEGER NOT NULL DEFAULT 0,
    revision INTEGER NOT NULL DEFAULT 1,
    item_id TEXT NOT NULL,
    sku TEXT NOT NULL REFERENCES products(sku),
    catalog_color TEXT NOT NULL,
    display_name TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    refundable_item_minor INTEGER NOT NULL,
    payment_method TEXT NOT NULL DEFAULT 'Prepaid'
);

CREATE TABLE IF NOT EXISTS shipments (
    shipment_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    carrier_label TEXT NOT NULL DEFAULT 'Delhivery',
    status TEXT NOT NULL,
    delivered_at TEXT,
    latest_scan_at TEXT,
    source_revision INTEGER NOT NULL DEFAULT 1,
    eta TEXT,
    recipient_address TEXT,
    pincode TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    reason TEXT
);

CREATE TABLE IF NOT EXISTS cases (
    case_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    customer_id TEXT NOT NULL REFERENCES customers(customer_id),
    case_type TEXT NOT NULL,
    state TEXT NOT NULL DEFAULT 'NEW',
    input_revision INTEGER NOT NULL DEFAULT 1,
    clarification_count INTEGER NOT NULL DEFAULT 0,
    summary TEXT NOT NULL DEFAULT '',
    last_error TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS messages (
    message_id TEXT PRIMARY KEY,
    client_message_id TEXT,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    actor_id TEXT NOT NULL,
    role TEXT NOT NULL,
    text TEXT NOT NULL,
    language TEXT NOT NULL DEFAULT 'en',
    attachment_ids_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS evidence (
    evidence_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    media_type TEXT NOT NULL,
    storage_key TEXT NOT NULL,
    content_sha256 TEXT NOT NULL,
    bytes INTEGER NOT NULL,
    duration_ms INTEGER,
    width INTEGER,
    height INTEGER,
    ingest_status TEXT NOT NULL DEFAULT 'ingested',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS observations (
    observation_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    evidence_id TEXT NOT NULL REFERENCES evidence(evidence_id),
    evidence_ref_ids_json TEXT NOT NULL DEFAULT '[]',
    t TEXT,
    attribute TEXT NOT NULL,
    value TEXT NOT NULL,
    color_class TEXT,
    visibility TEXT NOT NULL DEFAULT 'visible',
    uncertainty_reason TEXT,
    model_run_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS policy_checks (
    check_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    rule_id TEXT NOT NULL,
    result TEXT NOT NULL,
    reason_code TEXT NOT NULL,
    source_refs_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS proposals (
    proposal_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    action_type TEXT NOT NULL,
    item_id TEXT,
    amount_minor INTEGER,
    currency TEXT NOT NULL DEFAULT 'INR',
    customer_reply_draft TEXT NOT NULL DEFAULT '',
    rationale_refs_json TEXT NOT NULL DEFAULT '[]',
    basis_json TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    payload_hash TEXT NOT NULL,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS approvals (
    approval_id TEXT PRIMARY KEY,
    proposal_id TEXT NOT NULL REFERENCES proposals(proposal_id),
    seller_id TEXT NOT NULL,
    decision TEXT NOT NULL DEFAULT 'approve',
    approved_payload_hash TEXT NOT NULL,
    approved_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS actions (
    action_id TEXT PRIMARY KEY,
    type TEXT NOT NULL,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    proposal_id TEXT NOT NULL REFERENCES proposals(proposal_id),
    approval_id TEXT,
    idempotency_key TEXT UNIQUE NOT NULL,
    payload_hash TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'pending',
    result_ref TEXT,
    attempt_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS returns (
    return_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    item_id TEXT NOT NULL,
    quantity INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'requested',
    label_id TEXT,
    created_action_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS refunds (
    refund_id TEXT PRIMARY KEY,
    order_id TEXT NOT NULL REFERENCES orders(order_id),
    amount_minor INTEGER NOT NULL,
    currency TEXT NOT NULL DEFAULT 'INR',
    status TEXT NOT NULL DEFAULT 'processed',
    created_action_id TEXT,
    created_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS audit_events (
    seq INTEGER PRIMARY KEY AUTOINCREMENT,
    event_id TEXT UNIQUE NOT NULL,
    case_id TEXT,
    actor TEXT NOT NULL,
    event_type TEXT NOT NULL,
    outcome TEXT NOT NULL,
    refs_json TEXT NOT NULL DEFAULT '[]',
    safe_payload_json TEXT NOT NULL DEFAULT '{}',
    recorded_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS jobs (
    job_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    input_revision INTEGER NOT NULL DEFAULT 1,
    status TEXT NOT NULL DEFAULT 'pending',
    lease_until TEXT,
    attempts INTEGER NOT NULL DEFAULT 0,
    resume_reason TEXT,
    trigger_type TEXT NOT NULL DEFAULT 'message',
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS autonomy_policies (
    store_id TEXT PRIMARY KEY REFERENCES stores(store_id),
    version TEXT NOT NULL DEFAULT '1.0',
    levels_json TEXT NOT NULL,
    per_order_cap_minor INTEGER NOT NULL DEFAULT 150000,
    per_customer_daily_cap_minor INTEGER NOT NULL DEFAULT 200000,
    kill_switch INTEGER NOT NULL DEFAULT 0,
    changed_by TEXT NOT NULL DEFAULT 'seller',
    changed_at TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS courier_events (
    event_id TEXT PRIMARY KEY,
    shipment_id TEXT NOT NULL,
    type TEXT NOT NULL,
    attempt_no INTEGER NOT NULL DEFAULT 1,
    reason TEXT,
    received_at TEXT NOT NULL,
    simulated INTEGER NOT NULL DEFAULT 1
);

CREATE TABLE IF NOT EXISTS plan_records (
    plan_id TEXT PRIMARY KEY,
    case_id TEXT NOT NULL REFERENCES cases(case_id),
    job_id TEXT NOT NULL,
    goal TEXT NOT NULL,
    tools_planned_json TEXT NOT NULL DEFAULT '[]',
    tools_called_json TEXT NOT NULL DEFAULT '[]',
    outcome TEXT NOT NULL,
    memory_used_json TEXT NOT NULL DEFAULT '[]',
    created_at TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_orders_customer ON orders(customer_id);
CREATE INDEX IF NOT EXISTS idx_cases_order ON cases(order_id);
CREATE INDEX IF NOT EXISTS idx_cases_state ON cases(state);
CREATE INDEX IF NOT EXISTS idx_messages_case ON messages(case_id);
CREATE INDEX IF NOT EXISTS idx_audit_case ON audit_events(case_id);
CREATE INDEX IF NOT EXISTS idx_jobs_status ON jobs(status);
"""


class Database:
    """SQLite wrapper with WAL mode and row-factory support."""

    def __init__(self, db_path: str | Path):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self.init_schema()

    def get_connection(self) -> sqlite3.Connection:
        conn = sqlite3.connect(
            str(self.db_path),
            timeout=30.0,
            check_same_thread=False,
            isolation_level=None,  # Autocommit mode; we manage transactions explicitly
        )
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode = WAL;")
        conn.execute("PRAGMA busy_timeout = 5000;")
        conn.execute("PRAGMA foreign_keys = ON;")
        return conn

    def init_schema(self) -> None:
        conn = self.get_connection()
        try:
            conn.executescript(SCHEMA_SQL)
        finally:
            conn.close()

    @contextmanager
    def transaction(self) -> Generator[sqlite3.Connection, None, None]:
        """Atomic write transaction using BEGIN IMMEDIATE (17 §3)."""
        conn = self.get_connection()
        try:
            conn.execute("BEGIN IMMEDIATE;")
            yield conn
            conn.execute("COMMIT;")
        except Exception:
            conn.execute("ROLLBACK;")
            raise
        finally:
            conn.close()

    @contextmanager
    def cursor(self) -> Generator[sqlite3.Cursor, None, None]:
        """Read-only or single-query context."""
        conn = self.get_connection()
        try:
            cur = conn.cursor()
            yield cur
        finally:
            conn.close()
