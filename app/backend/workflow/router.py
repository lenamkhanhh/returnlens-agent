"""Router and Intent Classifier per 17 §4.

Provides intent classification, read-tool selection, and deterministic fast-path routing.
"""

from __future__ import annotations

import re
from typing import List

from app.backend.contracts import CaseType, Intent, RouterOutput, ToolCallProposal


class Router:
    """Classifies inbound requests and dispatches allowlisted read tools."""

    @staticmethod
    def classify_and_route(text: str, order_id: str) -> RouterOutput:
        clean_text = text.lower().strip()

        # 1. WISMO fast path
        wismo_keywords = [
            "where", "status", "track", "tracking", "when", "delivery",
            "kahan", "kab", "shipment", "eta", "in transit", "arrive"
        ]
        is_wismo = any(kw in clean_text for kw in wismo_keywords) and not any(
            kw in clean_text for kw in ["damaged", "broken", "cracked", "wrong", "color", "refund", "return"]
        )

        if is_wismo:
            return RouterOutput(
                intent=Intent.WISMO,
                read_tools=[
                    ToolCallProposal(name="get_order", args={"order_id": order_id}),
                    ToolCallProposal(name="get_tracking", args={"order_id": order_id}),
                ],
                missing_inputs=[],
            )

        # 2. Address Update (NDR)
        if any(kw in clean_text for kw in ["flat", "address", "pata", "gali", "colony", "road"]):
            return RouterOutput(
                intent=Intent.ADDRESS_UPDATE,
                read_tools=[
                    ToolCallProposal(name="get_order", args={"order_id": order_id}),
                    ToolCallProposal(name="get_tracking", args={"order_id": order_id}),
                ],
                missing_inputs=[],
            )

        # 3. Return / Refund
        if any(kw in clean_text for kw in ["refund", "return", "broken", "damage", "crack", "wrong", "black", "white", "color"]):
            return RouterOutput(
                intent=Intent.RETURN,
                read_tools=[
                    ToolCallProposal(name="get_order", args={"order_id": order_id}),
                    ToolCallProposal(name="get_tracking", args={"order_id": order_id}),
                    ToolCallProposal(name="get_store_policy", args={"store_id": "store_dhun"}),
                ],
                missing_inputs=[],
            )

        # Fallback default
        return RouterOutput(
            intent=Intent.OTHER,
            read_tools=[
                ToolCallProposal(name="get_order", args={"order_id": order_id}),
                ToolCallProposal(name="get_tracking", args={"order_id": order_id}),
            ],
            missing_inputs=[],
        )

    @staticmethod
    def infer_case_type(text: str, tracking_status: str, is_outside_window: bool) -> CaseType:
        """Map initial conditions to canonical CaseType (17 §2)."""
        clean = text.lower()
        if is_outside_window:
            return CaseType.LATE
        if tracking_status == "NDR":
            return CaseType.NDR
        if any(w in clean for w in ["damage", "broken", "crack", "tuta"]):
            return CaseType.DAMAGE
        if any(w in clean for w in ["wrong", "black", "color", "mismatch", "different"]):
            return CaseType.MISMATCH
        if any(w in clean for w in ["unclear", "dark", "blur", "room"]):
            return CaseType.UNCLEAR
        if any(w in clean for w in ["where", "track", "status", "shipment"]):
            return CaseType.WISMO
        return CaseType.WISMO
