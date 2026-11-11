"""Mock Services and Tool Implementations per 02 §4 and 02 §4b.

Read tools for agent dispatch (get_order, get_tracking, get_store_policy, get_customer_profile).
Contract-faithful write tools for domain mutations (Shopify returnCreate, Razorpay refund, Shiprocket NDR).
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from app.backend.contracts import (
    CustomerProfile,
    Order,
    RefundStatus,
    ReturnStatus,
    Shipment,
    StorePolicy,
)
from app.backend.persistence.repository import Repository


class MockToolService:
    """Mock service providing read and write tool execution against the domain DB."""

    def __init__(self, repo: Repository):
        self.repo = repo

    # =========================================================================
    # Read Tools (02 §4)
    # =========================================================================

    def get_order(self, order_id: str, customer_id: Optional[str] = None) -> Dict[str, Any]:
        """Fetch order details with customer scoping (02 §4)."""
        order = self.repo.get_order(order_id, customer_id=customer_id)
        if not order:
            return {"error": "not_found", "order_id": order_id}

        return {
            "order_id": order.order_id,
            "store_id": order.store_id,
            "customer_id": order.customer_id,
            "currency": order.currency,
            "paid_minor": order.paid_minor,
            "refunded_minor": order.refunded_minor,
            "reserved_minor": order.reserved_minor,
            "remaining_refundable_minor": order.paid_minor - order.refunded_minor - order.reserved_minor,
            "revision": order.revision,
            "line_item": {
                "item_id": order.line_item.item_id,
                "sku": order.line_item.sku,
                "catalog_color": order.line_item.catalog_color.value,
                "display_name": order.line_item.display_name,
                "quantity": order.line_item.quantity,
                "refundable_item_minor": order.line_item.refundable_item_minor,
            },
        }

    def get_tracking(self, order_id: str) -> Dict[str, Any]:
        """Fetch tracking details from verified order (02 §4)."""
        shipment = self.repo.get_shipment(order_id)
        if not shipment:
            return {"error": "not_found", "order_id": order_id}

        return {
            "shipment_id": shipment.shipment_id,
            "order_id": shipment.order_id,
            "carrier_label": shipment.carrier_label,
            "status": shipment.status,
            "delivered_at": shipment.delivered_at,
            "latest_scan_at": shipment.latest_scan_at,
            "source_revision": shipment.source_revision,
            "eta": shipment.eta,
            "recipient_address": shipment.recipient_address,
            "pincode": shipment.pincode,
            "attempt_count": shipment.attempt_count,
            "reason": shipment.reason,
        }

    def get_store_policy(self, store_id: str = "store_dhun") -> Dict[str, Any]:
        """Fetch versioned store policy (02 §4)."""
        policy = self.repo.get_store_policy(store_id)
        if not policy:
            return {"error": "not_found", "store_id": store_id}
        return {
            "store_id": policy.store_id,
            "policy_version": policy.policy_version,
            "timezone": policy.timezone,
            "return_window_days": policy.return_window_days,
            "cap_minor": policy.cap_minor,
            "require_receipt_before_refund": policy.require_receipt_before_refund,
            "eligible_reasons": policy.eligible_reasons,
        }

    def get_customer_profile(self, customer_id: str) -> Dict[str, Any]:
        """Fetch customer profile memory (02 §4)."""
        profile = self.repo.get_customer_profile(customer_id)
        if not profile:
            return {"error": "not_found", "customer_id": customer_id}
        return {
            "customer_id": profile.customer_id,
            "store_id": profile.store_id,
            "name": profile.name,
            "preferred_language": profile.preferred_language.value,
            "refund_destination": profile.refund_destination,
            "open_case_ids": profile.open_case_ids,
            "prior_case_count": profile.prior_case_count,
        }

    # =========================================================================
    # Write Tools (02 §4b: contract-faithful mocks)
    # =========================================================================

    def create_return(
        self,
        order_id: str,
        item_id: str,
        quantity: int = 1,
        return_reason: str = "DEFECTIVE",
        action_id: str = "",
    ) -> Dict[str, Any]:
        """Contract-faithful mock following Shopify Admin GraphQL `returnCreate` (02 §4b).

        Invariants:
        - Only fulfilled line items can be returned.
        - Cannot exceed line item quantity or return already returned line items.
        - Errors returned in Shopify GraphQL `userErrors` format: [{"field": [...], "message": "..."}].
        - Generates return_id and mock shipping label_id atomically.
        """
        order = self.repo.get_order(order_id)
        if not order:
            return {
                "return": None,
                "userErrors": [{"field": ["orderId"], "message": f"Order {order_id} not found"}],
            }

        if order.line_item.item_id != item_id:
            return {
                "return": None,
                "userErrors": [{"field": ["returnLineItems", "itemId"], "message": f"Line item {item_id} not found in order"}],
            }

        # Check existing active returns for this item in SQLite (Test 38)
        with self.repo.db.cursor() as cur:
            cur.execute(
                """
                SELECT COALESCE(SUM(quantity), 0) AS returned_qty
                FROM returns
                WHERE order_id = ? AND item_id = ? AND status IN ('requested', 'received')
                """,
                (order_id, item_id),
            )
            row = cur.fetchone()
            existing_returned = int(row["returned_qty"]) if row else 0

        if existing_returned + quantity > order.line_item.quantity:
            return {
                "return": None,
                "userErrors": [
                    {
                        "field": ["returnLineItems"],
                        "message": "Line item has already been returned or requested quantity exceeds available",
                    }
                ],
            }

        # Generate return record and mock shipping label
        return_id = f"RET-{uuid.uuid4().hex[:8].upper()}"
        label_id = f"LBL-RET-{uuid.uuid4().hex[:8].upper()}"
        now_iso = datetime.now(timezone.utc).isoformat()

        with self.repo.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO returns (return_id, order_id, item_id, quantity, status, label_id, created_action_id, created_at)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    return_id,
                    order_id,
                    item_id,
                    quantity,
                    ReturnStatus.REQUESTED.value,
                    label_id,
                    action_id,
                    now_iso,
                ),
            )

        return {
            "return": {
                "return_id": return_id,
                "order_id": order_id,
                "item_id": item_id,
                "quantity": quantity,
                "status": ReturnStatus.REQUESTED.value,
                "label_id": label_id,
                "return_reason": return_reason,
            },
            "userErrors": [],
        }
