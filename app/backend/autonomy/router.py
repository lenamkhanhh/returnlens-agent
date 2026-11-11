"""Autonomy REST API Router.

Card B12: Provides FastAPI endpoints per 17 §3, 17 §5, 02 §5b, 23 W4:
- GET /api/seller/autonomy: Current policy, active levels, lock status per case type.
- PUT /api/seller/autonomy: Update policy levels/caps; rejects L2/L3 with 422 if reliability gate fails (Test 40).
- POST /api/seller/autonomy/kill: Engage kill switch immediately (Test 44).
- GET /api/seller/autonomy/why/{case_id}: 7-step decision checklist for the UI 'Why?' button.
"""

from __future__ import annotations

import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, HTTPException, Query, Response, status
from pydantic import BaseModel

from app.backend.contracts import (
    AutonomyLevel,
    AutonomyPolicy,
    CaseType,
    UpdateAutonomyRequest,
)
from app.backend.autonomy.decision import (
    AutonomyEvaluationResult,
    evaluate_autonomy_decision,
)
from app.backend.autonomy.reliability import (
    check_case_type_reliability,
    load_reliability_results,
)
from app.backend.autonomy.version import compute_agent_version
from app.backend.persistence.db import Database
from app.backend.persistence.repository import Repository

router = APIRouter(tags=["autonomy"])


def get_repository() -> Repository:
    """Dependency injecting repository backed by active database."""
    data_dir = os.environ.get("DATA_DIR", "./data")
    db_path = Path(data_dir) / "returnlens.db"
    return Repository(Database(db_path))


class AutonomyPolicyResponse(BaseModel):
    store_id: str
    version: str
    levels: Dict[str, str]
    per_order_cap_minor: int
    per_customer_daily_cap_minor: int
    kill_switch: bool
    changed_by: str
    changed_at: str
    agent_version: str
    model_id: str
    lock_status: Dict[str, Dict[str, Any]]


@router.get("/api/seller/autonomy", response_model=AutonomyPolicyResponse)
def get_autonomy_policy(
    store_id: str = "store_dhun",
    repo: Repository = Depends(get_repository),
) -> AutonomyPolicyResponse:
    """Fetch current autonomy policy and reliability status for all CaseTypes."""
    policy = repo.get_autonomy_policy(store_id=store_id)
    agent_ver = compute_agent_version()
    model_id = os.environ.get("MODEL_PRIMARY", "gemini-3.8-flash")
    rel_data = load_reliability_results()

    lock_status: Dict[str, Dict[str, Any]] = {}
    for ct in CaseType:
        passed, reason, metrics = check_case_type_reliability(
            case_type=ct,
            current_agent_version=agent_ver,
            current_model_id=model_id,
            reliability_data=rel_data,
        )
        lock_status[ct.value] = {
            "eligible_for_l2_l3": passed,
            "status_message": reason,
            "metrics": metrics,
        }

    return AutonomyPolicyResponse(
        store_id=policy.store_id,
        version=policy.version,
        levels={k.value: v.value for k, v in policy.levels.items()},
        per_order_cap_minor=policy.per_order_cap_minor,
        per_customer_daily_cap_minor=policy.per_customer_daily_cap_minor,
        kill_switch=policy.kill_switch,
        changed_by=policy.changed_by,
        changed_at=policy.changed_at,
        agent_version=agent_ver,
        model_id=model_id,
        lock_status=lock_status,
    )


@router.put("/api/seller/autonomy")
def update_autonomy_policy(
    payload: UpdateAutonomyRequest,
    store_id: str = "store_dhun",
    repo: Repository = Depends(get_repository),
) -> Dict[str, Any]:
    """Update autonomy policy levels and thresholds.

    Test 40: Rejects L2 or L3 with HTTP 422 if reliability gate is not met.
    """
    agent_ver = compute_agent_version()
    model_id = os.environ.get("MODEL_PRIMARY", "gemini-3.8-flash")
    rel_data = load_reliability_results()

    # Validate that requested L2/L3 levels pass the reliability gate
    for ct, lvl in payload.levels.items():
        if lvl in (AutonomyLevel.L2, AutonomyLevel.L3):
            passed, reason, metrics = check_case_type_reliability(
                case_type=ct,
                current_agent_version=agent_ver,
                current_model_id=model_id,
                reliability_data=rel_data,
            )
            if not passed:
                # Find metrics for the failed scenario if available
                scenarios = metrics.values()
                first_metric = next(iter(scenarios), {}) if scenarios else {}
                pass_pow_k = first_metric.get("pass_pow_k", 0.0)
                k = first_metric.get("k", 5)

                raise HTTPException(
                    status_code=422,
                    detail={
                        "code": "reliability_locked",
                        "case_type": ct.value,
                        "pass_pow_k": pass_pow_k,
                        "k": k,
                        "user_message": (
                            f"Cannot unlock {lvl.value} for {ct.value}: "
                            f"reliability requirement not met. {reason}"
                        ),
                    },
                )

    # Persist policy in SQLite
    now_iso = datetime.now(timezone.utc).isoformat()
    levels_json = json.dumps({k.value: v.value for k, v in payload.levels.items()})

    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO autonomy_policies (
                store_id, version, levels_json, per_order_cap_minor,
                per_customer_daily_cap_minor, kill_switch, changed_by, changed_at
            ) VALUES (?, '1.0', ?, ?, ?, 0, 'seller', ?)
            ON CONFLICT(store_id) DO UPDATE SET
                levels_json = excluded.levels_json,
                per_order_cap_minor = excluded.per_order_cap_minor,
                per_customer_daily_cap_minor = excluded.per_customer_daily_cap_minor,
                changed_at = excluded.changed_at
            """,
            (
                store_id,
                levels_json,
                payload.per_order_cap_minor,
                payload.per_customer_daily_cap_minor,
                now_iso,
            ),
        )

    # Log audit event
    repo.append_audit_event(
        event_id=f"EVT-AUTONOMY-{datetime.now().timestamp()}",
        actor="seller",
        event_type="autonomy_changed",
        outcome="updated",
        safe_payload={
            "levels": {k.value: v.value for k, v in payload.levels.items()},
            "per_order_cap_minor": payload.per_order_cap_minor,
            "per_customer_daily_cap_minor": payload.per_customer_daily_cap_minor,
        },
    )

    return {
        "status": "success",
        "message": "Autonomy policy updated successfully.",
        "updated_at": now_iso,
    }


@router.post("/api/seller/autonomy/kill")
def engage_kill_switch(
    store_id: str = "store_dhun",
    repo: Repository = Depends(get_repository),
) -> Dict[str, Any]:
    """Test 44: Engage kill switch, instantly reverting all autonomy to L0."""
    now_iso = datetime.now(timezone.utc).isoformat()
    repo.set_kill_switch(store_id=store_id, kill=True)

    repo.append_audit_event(
        event_id=f"EVT-KILL-{datetime.now().timestamp()}",
        actor="seller",
        event_type="kill_switch_engaged",
        outcome="autonomy_suspended",
        safe_payload={"kill_switch": True, "reason": "emergency_seller_stop"},
    )

    return {
        "status": "success",
        "kill_switch": True,
        "message": "Kill switch engaged. All automated actions suspended.",
        "changed_at": now_iso,
    }


@router.get("/api/seller/autonomy/why/{case_id}", response_model=AutonomyEvaluationResult)
def get_autonomy_why_checklist(
    case_id: str,
    proposal_id: Optional[str] = None,
    repo: Repository = Depends(get_repository),
) -> AutonomyEvaluationResult:
    """Evaluate and return the 7-step checklist for the 'Why?' button (23 W4)."""
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found.")

    order = repo.get_order(case.order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {case.order_id} not found.")

    policy = repo.get_autonomy_policy(order.store_id)
    agent_ver = compute_agent_version()
    model_id = os.environ.get("MODEL_PRIMARY", "gemini-3.8-flash")
    rel_data = load_reliability_results()

    # Find proposal or default to return proposal for evaluation
    proposals = repo.list_case_proposals(case_id)
    target_proposal = None
    if proposal_id:
        target_proposal = next((p for p in proposals if p.proposal_id == proposal_id), None)
    if not target_proposal and proposals:
        target_proposal = proposals[-1]

    action_type = target_proposal.action_type.value if target_proposal else "PROPOSE_RETURN"
    amount_minor = target_proposal.amount_minor if target_proposal else None

    # Load observations for grounding check
    observations = repo.list_case_observations(case_id)

    # Check cumulative totals
    demo_today = os.environ.get("DEMO_TODAY", datetime.now().strftime("%Y-%m-%d"))
    customer_daily_total = repo.get_customer_daily_refund_total(order.customer_id, demo_today)

    # Check courier status for receipt requirement
    shipment = repo.get_shipment(order.order_id)
    is_receipt_received = (shipment.status == "RETURN_RECEIVED") if shipment else False

    result = evaluate_autonomy_decision(
        action_type=action_type,
        case_type=case.case_type,
        policy=policy,
        amount_minor=amount_minor,
        order_paid_minor=order.paid_minor,
        order_refunded_minor=order.refunded_minor,
        order_reserved_minor=order.reserved_minor,
        customer_daily_refund_total_minor=customer_daily_total,
        order_cumulative_refund_minor=order.refunded_minor + order.reserved_minor,
        observations=observations,
        reliability_data=rel_data,
        current_agent_version=agent_ver,
        current_model_id=model_id,
        is_receipt_received=is_receipt_received,
    )

    return result
