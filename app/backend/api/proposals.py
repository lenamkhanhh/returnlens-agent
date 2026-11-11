"""Proposals and Seller Decisions API Endpoints per 17 §5 and 02 §3.

Exposes routes for proposal creation, decision recording (approve/decline),
and action execution via ActionExecutor.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from fastapi import APIRouter, Header, HTTPException, Request

from app.backend.contracts import (
    NextStep,
    Proposal,
    ProposalBasis,
    ProposalDecisionRequest,
    ProposalDecisionResponse,
)
from app.backend.domain.executor import ActionExecutor, compute_payload_hash
from app.backend.persistence.repository import Repository

router = APIRouter(prefix="/api", tags=["proposals"])


@router.post("/proposals/{proposal_id}/decisions", response_model=ProposalDecisionResponse)
async def decide_proposal(
    proposal_id: str,
    payload: ProposalDecisionRequest,
    request: Request,
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
    x_seller_id: Optional[str] = Header(None, alias="X-Seller-Id"),
):
    """Record seller decision (approve/decline) on an immutable proposal (17 §5, 02 §3)."""
    executor: ActionExecutor = request.app.state.executor
    seller_id = x_seller_id or "seller_dhun"

    result = executor.execute_decision(
        proposal_id=proposal_id,
        decision=payload.decision,
        payload_hash=payload.payload_hash,
        idempotency_key=idempotency_key,
        seller_id=seller_id,
    )

    return ProposalDecisionResponse(
        action_id=result.get("action_id", ""),
        status=result.get("status", "succeeded"),
    )


@router.post("/cases/{case_id}/proposals", status_code=201)
async def create_case_proposal(
    case_id: str,
    payload: Dict[str, Any],
    request: Request,
):
    """Helper to create and persist an immutable proposal with computed payload hash."""
    repo: Repository = request.app.state.repo
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    order = repo.get_order(case.order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {case.order_id} not found")

    action_type = NextStep(payload.get("action_type", NextStep.PROPOSE_RETURN.value))
    item_id = payload.get("item_id", order.line_item.item_id)
    amount_minor = payload.get("amount_minor")
    currency = payload.get("currency", "INR")
    draft = payload.get("customer_reply_draft", f"Your return for {order.order_id} is approved.")

    proposal_id = f"PRP-{uuid.uuid4().hex[:8].upper()}"

    # Compute canonical payload hash
    payload_dict = {
        "case_id": case_id,
        "action_type": action_type.value,
        "item_id": item_id,
        "amount_minor": amount_minor,
        "currency": currency,
    }
    payload_hash = compute_payload_hash(payload_dict)

    # Build immutable basis
    basis = ProposalBasis(
        evidence_revision=1,
        observation_set_revision=1,
        order_revision=order.revision,
        shipment_revision=1,
        policy_version="1.0",
        action_fields={"order_id": order.order_id, "item_id": item_id},
        amount_minor=amount_minor,
    )

    proposal = Proposal(
        proposal_id=proposal_id,
        case_id=case_id,
        action_type=action_type,
        item_id=item_id,
        amount_minor=amount_minor,
        currency=currency,
        customer_reply_draft=draft,
        rationale_refs=payload.get("rationale_refs", []),
        basis=basis,
        status="pending",
        payload_hash=payload_hash,
    )

    repo.create_proposal(proposal)

    # Append proposal_created audit event (17 §7)
    repo.append_audit_event(
        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
        actor="agent:returnlens",
        event_type="proposal_created",
        outcome=f"Created proposal for {action_type.value}",
        case_id=case_id,
        refs=[f"proposal:{proposal_id}", f"order:{order.order_id}"],
        safe_payload={"payload_hash": payload_hash, "action_type": action_type.value},
    )

    return {
        "proposal_id": proposal_id,
        "payload_hash": payload_hash,
        "action_type": action_type.value,
    }
