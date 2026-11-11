"""PlanRecord Memory Persistence and Retrieval.

Card B13: Manages structured plan records displayed on the seller console per 02 §2, 17 §2:
- 3 core fields: goal, tools (tools_planned, tools_called), outcome.
- memory_used list highlighting which customer profile attributes were leveraged.
- Persisted to SQLite plan_records table.
- Does NOT store raw chain-of-thought (02 §2).
"""

from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from typing import List, Optional

from app.backend.contracts import PlanRecord
from app.backend.persistence.repository import Repository


def record_case_plan(
    repo: Repository,
    case_id: str,
    job_id: str,
    goal: str,
    tools_planned: List[str],
    tools_called: List[str],
    outcome: str,
    memory_used: List[str],
) -> PlanRecord:
    """Persist a new PlanRecord for a case execution."""
    plan_id = f"PLAN-{uuid.uuid4().hex[:8]}"
    now_iso = datetime.now(timezone.utc).isoformat()

    plan = PlanRecord(
        plan_id=plan_id,
        case_id=case_id,
        job_id=job_id,
        goal=goal,
        tools_planned=tools_planned,
        tools_called=tools_called,
        outcome=outcome,
        memory_used=memory_used,
    )

    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO plan_records (
                plan_id, case_id, job_id, goal, tools_planned_json,
                tools_called_json, outcome, memory_used_json, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                plan_id,
                case_id,
                job_id,
                goal,
                json.dumps(tools_planned),
                json.dumps(tools_called),
                outcome,
                json.dumps(memory_used),
                now_iso,
            ),
        )

    return plan


def get_case_plan(repo: Repository, case_id: str) -> Optional[PlanRecord]:
    """Retrieve the latest PlanRecord for a case."""
    with repo.db.cursor() as cur:
        cur.execute(
            """
            SELECT * FROM plan_records
            WHERE case_id = ?
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (case_id,),
        )
        row = cur.fetchone()
        if not row:
            return None

        return PlanRecord(
            plan_id=row["plan_id"],
            case_id=row["case_id"],
            job_id=row["job_id"],
            goal=row["goal"],
            tools_planned=json.loads(row["tools_planned_json"]),
            tools_called=json.loads(row["tools_called_json"]),
            outcome=row["outcome"],
            memory_used=json.loads(row["memory_used_json"]),
        )
