"""Case and Chat API Endpoints per 17 §5 and 02 §3.

Exposes REST routes for case creation, role-scoped snapshot queries,
message dispatch, and event stream timelines.
"""

from __future__ import annotations

import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, File, Form, Header, HTTPException, Query, Request, UploadFile
from fastapi.responses import FileResponse

from app.backend.contracts import (
    ActorRole,
    CaseSnapshotResponse,
    CaseState,
    CaseType,
    CreateCaseRequest,
    CreateCaseResponse,
    Message,
)
from app.backend.media.evidence import ingest_evidence
from app.backend.persistence.repository import Repository
from app.backend.workflow.engine import WorkflowEngine

router = APIRouter(prefix="/api", tags=["cases"])


@router.post("/cases", status_code=202, response_model=CreateCaseResponse)
async def create_case(
    payload: CreateCaseRequest,
    request: Request,
    x_customer_id: Optional[str] = Header(None, alias="X-Customer-Id"),
    customer_id_query: Optional[str] = Query(None, alias="customer_id"),
):
    """Create a case from customer inquiry, initialize durable job, and return 202."""
    repo: Repository = request.app.state.repo
    engine: WorkflowEngine = request.app.state.engine

    # Resolve customer ID (header or query or look up from order)
    customer_id = x_customer_id or customer_id_query
    order = repo.get_order(payload.order_id)
    if not order:
        raise HTTPException(status_code=404, detail=f"Order {payload.order_id} not found")

    # Inaccessible/scoped check (02 §1, Test 03: if customer_id supplied, it must match order)
    if customer_id and order.customer_id != customer_id:
        raise HTTPException(status_code=404, detail=f"Order {payload.order_id} not found for customer")

    effective_customer_id = customer_id or order.customer_id

    result = engine.create_case_with_job(
        order_id=payload.order_id,
        customer_id=effective_customer_id,
        initial_message=payload.initial_message,
        client_message_id=payload.client_message_id,
    )

    return CreateCaseResponse(
        case_id=result["case_id"],
        accepted_revision=result["accepted_revision"],
        job_id=result["job_id"],
    )


@router.get("/cases/{case_id}", response_model=CaseSnapshotResponse)
async def get_case_snapshot(
    case_id: str,
    request: Request,
    x_customer_id: Optional[str] = Header(None, alias="X-Customer-Id"),
    customer_id_query: Optional[str] = Query(None, alias="customer_id"),
):
    """Retrieve full case snapshot for customer or seller console (17 §5)."""
    repo: Repository = request.app.state.repo
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    # Access boundary check
    customer_id = x_customer_id or customer_id_query
    if customer_id and case.customer_id != customer_id:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not accessible")

    order = repo.get_order(case.order_id)
    shipment = repo.get_shipment(case.order_id)
    messages = repo.get_case_messages(case_id)
    proposals = repo.list_case_proposals(case_id)
    events = repo.list_case_audit_events(case_id)
    autonomy_policy = repo.get_autonomy_policy()

    facts = {
        "order": order.model_dump() if order else None,
        "shipment": shipment.model_dump() if shipment else None,
    }

    autonomy_info = {
        "case_type_level": autonomy_policy.levels.get(case.case_type, "L0"),
        "kill_switch": autonomy_policy.kill_switch,
        "per_order_cap_minor": autonomy_policy.per_order_cap_minor,
        "per_customer_daily_cap_minor": autonomy_policy.per_customer_daily_cap_minor,
    }

    latest_event_seq = events[-1].seq if events else 0

    visible_messages = [
        m.model_dump() for m in messages
        if m.role in (ActorRole.CUSTOMER, ActorRole.AGENT)
    ]

    with repo.db.cursor() as cur:
        cur.execute("SELECT * FROM evidence WHERE case_id = ? ORDER BY created_at ASC", (case_id,))
        evidence_list = []
        for row in cur.fetchall():
            row_dict = dict(row)
            row_dict["url"] = f"/api/media/{row_dict['evidence_id']}"
            row_dict["filename"] = row_dict.get("storage_key", "")
            if row_dict.get("duration_ms"):
                row_dict["duration_s"] = round(row_dict["duration_ms"] / 1000.0, 1)
            evidence_list.append(row_dict)

    # Observations & unknowns extraction from table or audit events
    observations_list = []
    unknowns_list = []
    with repo.db.cursor() as cur:
        cur.execute("SELECT * FROM observations WHERE case_id = ? ORDER BY t ASC", (case_id,))
        for r in cur.fetchall():
            observations_list.append(dict(r))

    # Reconstruct or supplement from audit events
    for ev in events:
        if ev.event_type == "observation_validated" and ev.safe_payload:
            if not observations_list:
                obs = ev.safe_payload.get("observations") or []
                if isinstance(obs, list):
                    observations_list.extend(obs)
            if not unknowns_list:
                unk = ev.safe_payload.get("unknowns") or []
                if isinstance(unk, list):
                    unknowns_list.extend(unk)

    # Policy checks
    policy_checks_list = []
    with repo.db.cursor() as cur:
        cur.execute("SELECT * FROM policy_checks WHERE case_id = ? ORDER BY created_at ASC", (case_id,))
        for r in cur.fetchall():
            policy_checks_list.append(dict(r))

    if not policy_checks_list:
        for ev in events:
            if ev.event_type == "policy_checked" and ev.safe_payload:
                policy_checks_list.append({
                    "rule_id": ev.safe_payload.get("rule_id", "POL-DEF"),
                    "result": ev.safe_payload.get("result", "PASS"),
                    "reason_code": ev.safe_payload.get("reason_code", "OK"),
                })

    # Plan card synthesis
    plan = None
    if proposals:
        latest_prop = proposals[-1]
        action_val = latest_prop.action_type.value if hasattr(latest_prop.action_type, "value") else str(latest_prop.action_type)
        plan = {
            "action_type": action_val,
            "summary": f"Proposed {action_val} for order {case.order_id}",
            "requires_approval": True,
            "proposal_id": latest_prop.proposal_id,
        }
    elif case.state == CaseState.WAITING_CUSTOMER:
        plan = {
            "action_type": "REQUEST_CLARIFICATION",
            "summary": case.summary or "Awaiting additional evidence from customer",
            "requires_approval": False,
        }
    elif case.state in (CaseState.RESOLVED, CaseState.WAITING_RETURN):
        plan = {
            "action_type": case.state.value,
            "summary": case.summary or f"Case in {case.state.value}",
            "requires_approval": False,
        }

    return CaseSnapshotResponse(
        case_id=case.case_id,
        case_type=case.case_type,
        state=case.state,
        facts=facts,
        observations=observations_list,
        unknowns=unknowns_list,
        policy_checks=policy_checks_list,
        plan=plan,
        clarification_count=case.clarification_count,
        proposals=[p.model_dump() for p in proposals],
        autonomy=autonomy_info,
        event_cursor=latest_event_seq,
        messages=visible_messages,
        evidence=evidence_list,
    )


@router.post("/cases/{case_id}/evidence", status_code=201)
async def upload_evidence(
    case_id: str,
    request: Request,
    file: UploadFile = File(...),
    client_upload_id: Optional[str] = Form(None),
):
    """Upload media evidence (image, video, audio) for a case (17 §5, 02 §3)."""
    repo: Repository = request.app.state.repo
    engine: WorkflowEngine = request.app.state.engine
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    file_bytes = await file.read()
    if not file_bytes:
        raise HTTPException(status_code=400, detail="Uploaded file contains 0 bytes")

    # Enforce IP rate limit and daily budget stop (21 P3, B16) outside harness mode
    if not getattr(request.app.state, "harness_mode", False):
        from app.backend.autonomy.budget_limiter import budget_tracker, ip_rate_limiter
        client_ip = request.client.host if request.client else "127.0.0.1"
        if not ip_rate_limiter.check_and_record(client_ip):
            raise HTTPException(status_code=429, detail="Model analysis rate limit exceeded (10 calls/hour per IP)")
        if budget_tracker.is_budget_exceeded(getattr(request.app.state, "demo_today", "2026-11-11")):
            raise HTTPException(status_code=429, detail="Daily model analysis budget reached ($3.00 stop per 21 P3)")
        budget_tracker.record_call(getattr(request.app.state, "demo_today", "2026-11-11"))

    media_dir = getattr(request.app.state, "data_dir", Path("data")) / "media"
    try:
        evi = ingest_evidence(
            file_bytes=file_bytes,
            filename=file.filename or "upload.bin",
            case_id=case_id,
            media_dir=media_dir,
        )
    except Exception as exc:
        raise HTTPException(status_code=400, detail=str(exc))

    now_iso = datetime.now(timezone.utc).isoformat()
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO evidence (
                evidence_id, case_id, media_type, storage_key, content_sha256,
                bytes, duration_ms, width, height, ingest_status, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, 'ingested', ?)
            """,
            (
                evi.evidence_id,
                case_id,
                evi.media_type,
                evi.storage_key,
                evi.content_sha256,
                evi.bytes,
                evi.duration_ms,
                evi.width,
                evi.height,
                now_iso,
            ),
        )

    repo.append_audit_event(
        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
        actor=f"customer:{case.customer_id}",
        event_type="evidence_uploaded",
        outcome=f"Uploaded {evi.media_type} evidence ({evi.bytes} bytes)",
        case_id=case_id,
        refs=[f"evidence:{evi.evidence_id}"],
        safe_payload={"evidence_id": evi.evidence_id, "media_type": evi.media_type},
    )

    # Trigger job to re-evaluate case with new evidence
    job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, case_id, input_revision, status, attempts, trigger_type, created_at, updated_at)
            VALUES (?, ?, ?, 'pending', 0, 'evidence', ?, ?)
            """,
            (job_id, case_id, case.input_revision + 1, now_iso, now_iso),
        )
    engine.process_job(job_id)

    return evi.model_dump()


@router.get("/cases/{case_id}/evidence")
async def list_case_evidence(
    case_id: str,
    request: Request,
):
    """List uploaded evidence assets for a case (17 §5)."""
    repo: Repository = request.app.state.repo
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    with repo.db.cursor() as cur:
        cur.execute("SELECT * FROM evidence WHERE case_id = ? ORDER BY created_at ASC", (case_id,))
        evidence = []
        for row in cur.fetchall():
            row_dict = dict(row)
            row_dict["url"] = f"/api/media/{row_dict['evidence_id']}"
            row_dict["filename"] = row_dict.get("storage_key", "")
            if row_dict.get("duration_ms"):
                row_dict["duration_s"] = round(row_dict["duration_ms"] / 1000.0, 1)
            evidence.append(row_dict)
        return evidence


@router.get("/media/{evidence_id}")
async def get_media_evidence(
    evidence_id: str,
    request: Request,
):
    """Serve uploaded media file with HTTP Range support for video seeking (Wave 10)."""
    repo: Repository = request.app.state.repo
    with repo.db.cursor() as cur:
        cur.execute("SELECT * FROM evidence WHERE evidence_id = ?", (evidence_id,))
        row = cur.fetchone()

    if not row:
        raise HTTPException(status_code=404, detail=f"Evidence {evidence_id} not found")

    storage_key = row["storage_key"]
    media_type = row["media_type"]

    # Search media locations
    media_dir = getattr(request.app.state, "data_dir", Path("data")) / "media"
    candidates = [
        media_dir / storage_key,
        Path(repo.db.db_path).parent / "media" / storage_key,
        Path("data/media") / storage_key,
        Path("app/demo/snapshot/media") / storage_key,
        Path("app/demo/media/stock") / storage_key,
        Path("app/demo/media") / storage_key,
        Path(storage_key),
    ]
    media_path = next((p for p in candidates if p.exists() and p.is_file()), None)

    if not media_path:
        filename = Path(storage_key).name
        for search_dir in [
            Path("app/demo/snapshot/media"),
            Path("app/demo/media/stock"),
            Path("app/demo/media"),
            media_dir,
            Path("data/media"),
        ]:
            if search_dir.exists():
                candidate = search_dir / filename
                if candidate.exists() and candidate.is_file():
                    media_path = candidate
                    break
    if not media_path:
        raise HTTPException(status_code=404, detail=f"Media file for {evidence_id} not found on disk")

    ext = media_path.suffix.lower()
    mime_map = {
        ".mp4": "video/mp4",
        ".webm": "video/webm",
        ".ogg": "audio/ogg",
        ".wav": "audio/wav",
        ".png": "image/png",
        ".jpg": "image/jpeg",
        ".jpeg": "image/jpeg",
    }
    content_type = mime_map.get(ext)
    if not content_type:
        if media_type == "video":
            content_type = "video/mp4"
        elif media_type == "audio":
            content_type = "audio/ogg"
        elif media_type == "image":
            content_type = "image/png"
        else:
            content_type = "application/octet-stream"

    return FileResponse(
        path=media_path,
        media_type=content_type,
        content_disposition_type="inline",
        headers={"Accept-Ranges": "bytes"},
    )


@router.get("/cases/{case_id}/messages")
async def get_case_messages(
    case_id: str,
    request: Request,
    x_customer_id: Optional[str] = Header(None, alias="X-Customer-Id"),
    customer_id_query: Optional[str] = Query(None, alias="customer_id"),
):
    """Retrieve messages for a case, role-filtered for customer view (17 §5, 17 §8)."""
    repo: Repository = request.app.state.repo
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    customer_id = x_customer_id or customer_id_query
    if customer_id and case.customer_id != customer_id:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not accessible")

    messages = repo.get_case_messages(case_id)
    visible_messages = [
        m.model_dump() for m in messages
        if m.role in (ActorRole.CUSTOMER, ActorRole.AGENT)
    ]
    return visible_messages


@router.post("/cases/{case_id}/messages", status_code=202)
async def add_case_message(
    case_id: str,
    payload: Dict[str, Any],
    request: Request,
    x_customer_id: Optional[str] = Header(None, alias="X-Customer-Id"),
):
    """Add message to existing case and trigger subsequent workflow job."""
    repo: Repository = request.app.state.repo
    engine: WorkflowEngine = request.app.state.engine

    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    text = payload.get("text", "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="Message text is required")

    client_msg_id = payload.get("client_message_id")
    msg_id = f"MSG-{case_id}-{uuid.uuid4().hex[:6]}"

    # Save inbound customer message
    repo.add_message(
        message_id=msg_id,
        case_id=case_id,
        actor_id=case.customer_id,
        role=ActorRole.CUSTOMER,
        text=text,
        client_message_id=client_msg_id,
    )

    # Append audit event
    repo.append_audit_event(
        event_id=f"EVT-{uuid.uuid4().hex[:8]}",
        actor=f"customer:{case.customer_id}",
        event_type="message_received",
        outcome="Inbound customer message received",
        case_id=case_id,
        safe_payload={"text": text, "client_message_id": client_msg_id},
    )

    # Enqueue new job
    job_id = f"JOB-{uuid.uuid4().hex[:8].upper()}"
    now_iso = datetime.now(timezone.utc).isoformat()
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, case_id, input_revision, status, attempts, trigger_type, created_at, updated_at)
            VALUES (?, ?, ?, 'pending', 0, 'message', ?, ?)
            """,
            (job_id, case_id, case.input_revision + 1, now_iso, now_iso),
        )

    # Process job synchronously
    engine.process_job(job_id)

    return {"status": "accepted", "job_id": job_id}


@router.get("/cases/{case_id}/events")
async def get_case_events(
    case_id: str,
    request: Request,
    after_seq: int = Query(0, ge=0),
):
    """Stream or poll case audit events for timeline drawer (17 §6, 02 §8)."""
    repo: Repository = request.app.state.repo
    case = repo.get_case(case_id)
    if not case:
        raise HTTPException(status_code=404, detail=f"Case {case_id} not found")

    events = repo.list_case_audit_events(case_id, after_seq=after_seq)
    return [e.model_dump() for e in events]


@router.get("/seller/cases")
async def list_seller_cases(
    request: Request,
    state: Optional[str] = None,
):
    """List all cases for seller inbox (02 §3)."""
    repo: Repository = request.app.state.repo
    with repo.db.cursor() as cur:
        if state:
            cur.execute("SELECT * FROM cases WHERE state = ? ORDER BY updated_at DESC", (state,))
        else:
            cur.execute("SELECT * FROM cases ORDER BY updated_at DESC")
        cases = []
        for row in cur.fetchall():
            cases.append(
                {
                    "case_id": row["case_id"],
                    "order_id": row["order_id"],
                    "customer_id": row["customer_id"],
                    "case_type": row["case_type"],
                    "state": row["state"],
                    "clarification_count": row["clarification_count"],
                    "summary": row["summary"],
                    "updated_at": row["updated_at"],
                }
            )
        return cases
