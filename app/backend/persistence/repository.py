"""Domain and Persistence Repositories for ReturnLens.

Provides type-safe, scoped CRUD operations and enforces store/customer boundaries.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.backend.contracts import (
    Action,
    ActionStatus,
    ActionType,
    ActorRole,
    Approval,
    AuditEvent,
    AutonomyLevel,
    AutonomyPolicy,
    Case,
    CaseState,
    CaseType,
    ColorClass,
    CustomerProfile,
    Evidence,
    Language,
    LineItem,
    Message,
    Observation,
    ObservationAttribute,
    Order,
    PolicyCheck,
    PolicyCheckResult,
    PolicyRuleId,
    Proposal,
    ProposalBasis,
    RefundRecord,
    RefundStatus,
    ReturnRecord,
    ReturnStatus,
    Shipment,
    StorePolicy,
    Visibility,
)
from app.backend.persistence.db import Database


class Repository:
    """Consolidated repository interfacing with SQLite."""

    def __init__(self, db: Database):
        self.db = db

    # =========================================================================
    # Stores & Policies
    # =========================================================================

    def get_store_policy(self, store_id: str) -> Optional[StorePolicy]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM stores WHERE store_id = ?", (store_id,))
            row = cur.fetchone()
            if not row:
                return None
            return StorePolicy(
                store_id=row["store_id"],
                policy_version=row["policy_version"],
                timezone=row["timezone"],
                return_window_days=row["return_window_days"],
                eligible_reasons=["damaged", "wrong_item", "defective"],
                cap_minor=row["cap_minor"],
                require_receipt_before_refund=bool(row["require_receipt_before_refund"]),
            )

    # =========================================================================
    # Customers & Profiles
    # =========================================================================

    def get_customer_profile(self, customer_id: str) -> Optional[CustomerProfile]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM customers WHERE customer_id = ?", (customer_id,))
            row = cur.fetchone()
            if not row:
                return None

            # Get open case IDs
            cur.execute(
                "SELECT case_id FROM cases WHERE customer_id = ? AND state NOT IN ('RESOLVED')",
                (customer_id,),
            )
            open_cases = [r["case_id"] for r in cur.fetchall()]

            return CustomerProfile(
                customer_id=row["customer_id"],
                store_id=row["store_id"],
                name=row["name"],
                phone=row["phone"],
                preferred_language=Language(row["preferred_language"]),
                refund_destination=row["refund_destination"],
                open_case_ids=open_cases,
                prior_case_count=row["prior_case_count"],
                updated_at=row["updated_at"],
            )

    def update_customer_language(self, customer_id: str, language: Language) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE customers SET preferred_language = ?, updated_at = ? WHERE customer_id = ?",
                (language.value, now_iso, customer_id),
            )

    # =========================================================================
    # Orders & Shipments
    # =========================================================================

    def get_order(self, order_id: str, customer_id: Optional[str] = None) -> Optional[Order]:
        """Fetch order, enforcing customer binding if customer_id is provided (02 §1)."""
        with self.db.cursor() as cur:
            if customer_id:
                cur.execute(
                    "SELECT * FROM orders WHERE order_id = ? AND customer_id = ?",
                    (order_id, customer_id),
                )
            else:
                cur.execute("SELECT * FROM orders WHERE order_id = ?", (order_id,))
            row = cur.fetchone()
            if not row:
                return None

            item = LineItem(
                item_id=row["item_id"],
                sku=row["sku"],
                catalog_color=ColorClass(row["catalog_color"]),
                display_name=row["display_name"],
                quantity=row["quantity"],
                refundable_item_minor=row["refundable_item_minor"],
            )

            return Order(
                order_id=row["order_id"],
                store_id=row["store_id"],
                customer_id=row["customer_id"],
                currency=row["currency"],
                paid_minor=row["paid_minor"],
                refunded_minor=row["refunded_minor"],
                reserved_minor=row["reserved_minor"],
                revision=row["revision"],
                line_item=item,
            )

    def list_customer_orders(self, customer_id: str) -> List[Order]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM orders WHERE customer_id = ?", (customer_id,))
            results = []
            for row in cur.fetchall():
                item = LineItem(
                    item_id=row["item_id"],
                    sku=row["sku"],
                    catalog_color=ColorClass(row["catalog_color"]),
                    display_name=row["display_name"],
                    quantity=row["quantity"],
                    refundable_item_minor=row["refundable_item_minor"],
                )
                results.append(
                    Order(
                        order_id=row["order_id"],
                        store_id=row["store_id"],
                        customer_id=row["customer_id"],
                        currency=row["currency"],
                        paid_minor=row["paid_minor"],
                        refunded_minor=row["refunded_minor"],
                        reserved_minor=row["reserved_minor"],
                        revision=row["revision"],
                        line_item=item,
                    )
                )
            return results

    def get_shipment(self, order_id: str) -> Optional[Shipment]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM shipments WHERE order_id = ?", (order_id,))
            row = cur.fetchone()
            if not row:
                return None
            return Shipment(
                shipment_id=row["shipment_id"],
                order_id=row["order_id"],
                carrier_label=row["carrier_label"],
                status=row["status"],
                delivered_at=row["delivered_at"],
                latest_scan_at=row["latest_scan_at"],
                source_revision=row["source_revision"],
                eta=row["eta"],
                recipient_address=row["recipient_address"],
                pincode=row["pincode"],
                attempt_count=row["attempt_count"],
                reason=row["reason"],
            )

    def update_shipment_status(
        self,
        shipment_id: str,
        status: str,
        scan_at: Optional[str] = None,
        recipient_address: Optional[str] = None,
    ) -> bool:
        with self.db.transaction() as conn:
            cur = conn.cursor()
            cur.execute("SELECT source_revision FROM shipments WHERE shipment_id = ?", (shipment_id,))
            row = cur.fetchone()
            if not row:
                return False
            new_rev = row["source_revision"] + 1

            if recipient_address:
                conn.execute(
                    """
                    UPDATE shipments
                    SET status = ?, latest_scan_at = ?, recipient_address = ?, source_revision = ?
                    WHERE shipment_id = ?
                    """,
                    (status, scan_at, recipient_address, new_rev, shipment_id),
                )
            else:
                conn.execute(
                    """
                    UPDATE shipments
                    SET status = ?, latest_scan_at = ?, source_revision = ?
                    WHERE shipment_id = ?
                    """,
                    (status, scan_at, new_rev, shipment_id),
                )
            return True

    # =========================================================================
    # Cases & Messages
    # =========================================================================

    def create_case(
        self,
        case_id: str,
        order_id: str,
        customer_id: str,
        case_type: CaseType,
        initial_message: Optional[str] = None,
        client_message_id: Optional[str] = None,
    ) -> Case:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO cases (
                    case_id, order_id, customer_id, case_type, state, input_revision,
                    clarification_count, summary, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, 1, 0, '', ?, ?)
                """,
                (case_id, order_id, customer_id, case_type.value, CaseState.NEW.value, now_iso, now_iso),
            )

            if initial_message:
                msg_id = f"MSG-{case_id}-001"
                conn.execute(
                    """
                    INSERT INTO messages (
                        message_id, client_message_id, case_id, actor_id, role, text, language, created_at
                    ) VALUES (?, ?, ?, ?, ?, ?, 'en', ?)
                    """,
                    (msg_id, client_message_id, case_id, customer_id, ActorRole.CUSTOMER.value, initial_message, now_iso),
                )

        return Case(
            case_id=case_id,
            order_id=order_id,
            customer_id=customer_id,
            case_type=case_type,
            state=CaseState.NEW,
            input_revision=1,
            clarification_count=0,
            summary="",
        )

    def get_case(self, case_id: str) -> Optional[Case]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM cases WHERE case_id = ?", (case_id,))
            row = cur.fetchone()
            if not row:
                return None
            return Case(
                case_id=row["case_id"],
                order_id=row["order_id"],
                customer_id=row["customer_id"],
                case_type=CaseType(row["case_type"]),
                state=CaseState(row["state"]),
                input_revision=row["input_revision"],
                clarification_count=row["clarification_count"],
                summary=row["summary"],
                last_error=row["last_error"],
            )

    def update_case_state(
        self,
        case_id: str,
        state: CaseState,
        summary: Optional[str] = None,
        increment_clarification: bool = False,
    ) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            sql = "UPDATE cases SET state = ?, updated_at = ?"
            params: List[Any] = [state.value, now_iso]
            if summary is not None:
                sql += ", summary = ?"
                params.append(summary)
            if increment_clarification:
                sql += ", clarification_count = clarification_count + 1"
            sql += " WHERE case_id = ?"
            params.append(case_id)
            conn.execute(sql, tuple(params))

    def add_message(
        self,
        message_id: str,
        case_id: str,
        actor_id: str,
        role: ActorRole,
        text: str,
        language: Language = Language.EN,
        attachment_ids: Optional[List[str]] = None,
        client_message_id: Optional[str] = None,
    ) -> Message:
        now_iso = datetime.now(timezone.utc).isoformat()
        attachments_json = json.dumps(attachment_ids or [])
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO messages (
                    message_id, client_message_id, case_id, actor_id, role, text, language, attachment_ids_json, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (message_id, client_message_id, case_id, actor_id, role.value, text, language.value, attachments_json, now_iso),
            )
        return Message(
            message_id=message_id,
            client_message_id=client_message_id,
            case_id=case_id,
            actor_id=actor_id,
            role=role,
            text=text,
            language=language,
            attachment_ids=attachment_ids or [],
            created_at=now_iso,
        )

    def get_case_messages(self, case_id: str) -> List[Message]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM messages WHERE case_id = ? ORDER BY created_at ASC", (case_id,))
            messages = []
            for row in cur.fetchall():
                messages.append(
                    Message(
                        message_id=row["message_id"],
                        client_message_id=row["client_message_id"],
                        case_id=row["case_id"],
                        actor_id=row["actor_id"],
                        role=ActorRole(row["role"]),
                        text=row["text"],
                        language=Language(row["language"]),
                        attachment_ids=json.loads(row["attachment_ids_json"]),
                        created_at=row["created_at"],
                    )
                )
            return messages

    # =========================================================================
    # Proposals, Approvals, & Actions (02 §2, 02 §7)
    # =========================================================================

    def create_proposal(self, proposal: Proposal) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        basis_json = proposal.basis.model_dump_json()
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO proposals (
                    proposal_id, case_id, action_type, item_id, amount_minor, currency,
                    customer_reply_draft, rationale_refs_json, basis_json, status, payload_hash, created_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    proposal.proposal_id,
                    proposal.case_id,
                    proposal.action_type.value,
                    proposal.item_id,
                    proposal.amount_minor,
                    proposal.currency,
                    proposal.customer_reply_draft,
                    json.dumps(proposal.rationale_refs),
                    basis_json,
                    proposal.status,
                    proposal.payload_hash,
                    now_iso,
                ),
            )

    def get_proposal(self, proposal_id: str) -> Optional[Proposal]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM proposals WHERE proposal_id = ?", (proposal_id,))
            row = cur.fetchone()
            if not row:
                return None
            basis_dict = json.loads(row["basis_json"])
            basis = ProposalBasis(**basis_dict)
            return Proposal(
                proposal_id=row["proposal_id"],
                case_id=row["case_id"],
                action_type=row["action_type"],
                item_id=row["item_id"],
                amount_minor=row["amount_minor"],
                currency=row["currency"],
                customer_reply_draft=row["customer_reply_draft"],
                rationale_refs=json.loads(row["rationale_refs_json"]),
                basis=basis,
                status=row["status"],
                payload_hash=row["payload_hash"],
                created_at=row["created_at"],
            )

    def list_case_proposals(self, case_id: str) -> List[Proposal]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM proposals WHERE case_id = ? ORDER BY created_at ASC", (case_id,))
            proposals = []
            for row in cur.fetchall():
                basis = ProposalBasis(**json.loads(row["basis_json"]))
                proposals.append(
                    Proposal(
                        proposal_id=row["proposal_id"],
                        case_id=row["case_id"],
                        action_type=row["action_type"],
                        item_id=row["item_id"],
                        amount_minor=row["amount_minor"],
                        currency=row["currency"],
                        customer_reply_draft=row["customer_reply_draft"],
                        rationale_refs=json.loads(row["rationale_refs_json"]),
                        basis=basis,
                        status=row["status"],
                        payload_hash=row["payload_hash"],
                        created_at=row["created_at"],
                    )
                )
            return proposals

    def record_approval(self, approval: Approval) -> None:
        with self.db.transaction() as conn:
            conn.execute(
                """
                INSERT OR REPLACE INTO approvals (
                    approval_id, proposal_id, seller_id, decision, approved_payload_hash, approved_at
                ) VALUES (?, ?, ?, ?, ?, ?)
                """,
                (
                    approval.approval_id,
                    approval.proposal_id,
                    approval.seller_id,
                    approval.decision,
                    approval.approved_payload_hash,
                    approval.approved_at,
                ),
            )
            # Update proposal status to approved
            conn.execute(
                "UPDATE proposals SET status = 'approved' WHERE proposal_id = ?",
                (approval.proposal_id,),
            )

    def get_approval(self, approval_id: str) -> Optional[Approval]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM approvals WHERE approval_id = ?", (approval_id,))
            row = cur.fetchone()
            if not row:
                return None
            return Approval(
                approval_id=row["approval_id"],
                proposal_id=row["proposal_id"],
                seller_id=row["seller_id"],
                decision=row["decision"],
                approved_payload_hash=row["approved_payload_hash"],
                approved_at=row["approved_at"],
            )

    def get_action_by_idempotency_key(self, idempotency_key: str) -> Optional[Action]:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM actions WHERE idempotency_key = ?", (idempotency_key,))
            row = cur.fetchone()
            if not row:
                return None
            return Action(
                action_id=row["action_id"],
                type=ActionType(row["type"]),
                order_id=row["order_id"],
                proposal_id=row["proposal_id"],
                approval_id=row["approval_id"],
                idempotency_key=row["idempotency_key"],
                payload_hash=row["payload_hash"],
                status=ActionStatus(row["status"]),
                result_ref=row["result_ref"],
                attempt_count=row["attempt_count"],
                created_at=row["created_at"],
            )

    # =========================================================================
    # Audit Events & Timeline (02 §8)
    # =========================================================================

    def append_audit_event(
        self,
        event_id: str,
        actor: str,
        event_type: str,
        outcome: str,
        case_id: Optional[str] = None,
        refs: Optional[List[str]] = None,
        safe_payload: Optional[Dict[str, Any]] = None,
    ) -> AuditEvent:
        now_iso = datetime.now(timezone.utc).isoformat()
        refs_json = json.dumps(refs or [])
        payload_json = json.dumps(safe_payload or {})
        with self.db.transaction() as conn:
            cur = conn.cursor()
            cur.execute(
                """
                INSERT INTO audit_events (
                    event_id, case_id, actor, event_type, outcome, refs_json, safe_payload_json, recorded_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (event_id, case_id, actor, event_type, outcome, refs_json, payload_json, now_iso),
            )
            seq = cur.lastrowid or 0

        return AuditEvent(
            event_id=event_id,
            seq=seq,
            actor=actor,
            event_type=event_type,
            outcome=outcome,
            refs=refs or [],
            safe_payload=safe_payload or {},
            recorded_at=now_iso,
        )

    def list_case_audit_events(self, case_id: str, after_seq: int = 0) -> List[AuditEvent]:
        with self.db.cursor() as cur:
            cur.execute(
                "SELECT * FROM audit_events WHERE case_id = ? AND seq > ? ORDER BY seq ASC",
                (case_id, after_seq),
            )
            events = []
            for row in cur.fetchall():
                events.append(
                    AuditEvent(
                        event_id=row["event_id"],
                        seq=row["seq"],
                        actor=row["actor"],
                        event_type=row["event_type"],
                        outcome=row["outcome"],
                        refs=json.loads(row["refs_json"]),
                        safe_payload=json.loads(row["safe_payload_json"]),
                        recorded_at=row["recorded_at"],
                    )
                )
            return events

    # =========================================================================
    # Autonomy Policy & Cumulative Gate (17 §3, 02 §5b)
    # =========================================================================

    def get_autonomy_policy(self, store_id: str = "store_dhun") -> AutonomyPolicy:
        with self.db.cursor() as cur:
            cur.execute("SELECT * FROM autonomy_policies WHERE store_id = ?", (store_id,))
            row = cur.fetchone()
            if not row:
                return AutonomyPolicy(store_id=store_id)
            levels_dict = json.loads(row["levels_json"])
            levels = {CaseType(k): AutonomyLevel(v) for k, v in levels_dict.items()}
            return AutonomyPolicy(
                store_id=row["store_id"],
                version=row["version"],
                levels=levels,
                per_order_cap_minor=row["per_order_cap_minor"],
                per_customer_daily_cap_minor=row["per_customer_daily_cap_minor"],
                kill_switch=bool(row["kill_switch"]),
                changed_by=row["changed_by"],
                changed_at=row["changed_at"],
            )

    def set_kill_switch(self, store_id: str = "store_dhun", kill: bool = True) -> None:
        now_iso = datetime.now(timezone.utc).isoformat()
        with self.db.transaction() as conn:
            conn.execute(
                "UPDATE autonomy_policies SET kill_switch = ?, changed_at = ? WHERE store_id = ?",
                (1 if kill else 0, now_iso, store_id),
            )

    def get_customer_daily_refund_total(self, customer_id: str, date_str: str) -> int:
        """Calculate total refunds processed or reserved for a customer on a given calendar date."""
        with self.db.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(r.amount_minor), 0) AS total
                FROM refunds r
                JOIN orders o ON r.order_id = o.order_id
                WHERE o.customer_id = ? AND r.status IN ('processed', 'pending')
                  AND r.created_at LIKE ?
                """,
                (customer_id, f"{date_str}%"),
            )
            row = cur.fetchone()
            return int(row["total"]) if row else 0
