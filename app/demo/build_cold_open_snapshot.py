"""Build Cold-Open DB Snapshot (17 §9, 18 §3).

Runs real flows to bring:
1. ORD-1042 (CUS-03) to WAITING_RETURN with approved return.
2. ORD-4401 (CUS-03) to WAITING_RETURN with approved return.
Saves the DB snapshot with pinned DEMO_TODAY ("2026-11-11").
"""

from __future__ import annotations

import json
import os
import shutil
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import MagicMock

from app.backend.contracts import (
    CaseState,
    ColorClass,
    NextStep,
    ObservationAttribute,
    ObservationItem,
    ObserverOutput,
    Visibility,
)
from app.backend.main import create_app
from app.backend.model.observer import VisionObserverRunner
from app.backend.model.provenance import ModelRun
from app.backend.persistence.repository import Repository
from app.backend.persistence.seed import STORE_ID, reset_database, seed_database


def build_cold_open_snapshot(
    output_db_path: Path,
    demo_today: str = "2026-11-11",
) -> None:
    output_db_path = Path(output_db_path)
    output_db_path.parent.mkdir(parents=True, exist_ok=True)
    if output_db_path.exists():
        output_db_path.unlink()

    # Create isolated app on target directory
    target_data_dir = output_db_path.parent
    app = create_app(data_dir=target_data_dir, demo_today=demo_today, harness_mode=True)
    repo: Repository = app.state.repo

    # Reset and seed database cleanly
    reset_database(app.state.db, demo_today)

    engine = app.state.engine
    executor = app.state.executor

    # --------------------------------------------------------------------------
    # Flow 1: ORD-1042 (CUS-03) -> Case A Damage -> WAITING_RETURN
    # --------------------------------------------------------------------------
    print("Building Flow 1: ORD-1042...")
    res_c1 = engine.create_case_with_job(
        order_id="ORD-1042",
        customer_id="CUS-03",
        initial_message="The headband cracked. I want to return it.",
    )
    case_id_1042 = res_c1["case_id"]

    # Ingest synthetic/mock damage evidence
    dummy_bytes = b"\x00\x00\x00\x20ftypisom" + b"\x00" * 200
    from app.backend.media.evidence import ingest_evidence
    evi_1042 = ingest_evidence(
        file_bytes=dummy_bytes,
        filename="damage_clip.mp4",
        case_id=case_id_1042,
        media_dir=target_data_dir / "media",
    )
    now_iso = datetime.now(timezone.utc).isoformat()
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO evidence (evidence_id, case_id, media_type, storage_key, content_sha256, bytes, duration_ms, ingest_status, created_at)
            VALUES (?, ?, 'video', ?, ?, ?, 12000, 'ingested', ?)
            """,
            (evi_1042.evidence_id, case_id_1042, evi_1042.storage_key, evi_1042.content_sha256, len(dummy_bytes), now_iso),
        )

    # Provide grounded damage observation
    mock_runner = MagicMock(spec=VisionObserverRunner)
    mock_runner.observe.return_value = (
        ObserverOutput(
            observations=[
                ObservationItem(
                    id="OBS-DMG-1",
                    evidence_id=evi_1042.evidence_id,
                    t="00:04",
                    attribute=ObservationAttribute.DAMAGE,
                    value="cracked headband",
                    visibility=Visibility.VISIBLE,
                )
            ],
            unknowns=[],
            ignored_instructions=False,
        ),
        ModelRun(run_id="RUN-1042", model_id="gemini-3.8-flash"),
    )
    engine.observer_runner = mock_runner

    # Process evidence job
    job_id_evi_1 = f"JOB-EVI-1042"
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, case_id, input_revision, status, attempts, trigger_type, created_at, updated_at)
            VALUES (?, ?, 2, 'pending', 0, 'evidence', ?, ?)
            """,
            (job_id_evi_1, case_id_1042, now_iso, now_iso),
        )
    engine.process_job(job_id_evi_1)

    # Verify proposal exists and approve it
    props_1042 = repo.list_case_proposals(case_id_1042)
    assert len(props_1042) >= 1, "Expected proposal for ORD-1042"
    prop_1042 = props_1042[0]

    executor.execute_decision(
        proposal_id=prop_1042.proposal_id,
        decision="approved",
        payload_hash=prop_1042.payload_hash,
        idempotency_key=f"IDEMP-{prop_1042.proposal_id}",
    )

    case_1042 = repo.get_case(case_id_1042)
    print(f"ORD-1042 final state: {case_1042.state.value}")
    assert case_1042.state == CaseState.WAITING_RETURN

    # --------------------------------------------------------------------------
    # Flow 2: ORD-4401 (CUS-03) -> Damage Claim -> WAITING_RETURN
    # --------------------------------------------------------------------------
    print("Building Flow 2: ORD-4401...")
    res_c2 = engine.create_case_with_job(
        order_id="ORD-4401",
        customer_id="CUS-03",
        initial_message="Dhun Buds cracked and stopped working.",
    )
    case_id_4401 = res_c2["case_id"]

    dummy_bytes_2 = b"\x00\x00\x00\x20ftypisom_buds" + b"\x01" * 200
    evi_4401 = ingest_evidence(
        file_bytes=dummy_bytes_2,
        filename="buds_damage.mp4",
        case_id=case_id_4401,
        media_dir=target_data_dir / "media",
    )
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO evidence (evidence_id, case_id, media_type, storage_key, content_sha256, bytes, duration_ms, ingest_status, created_at)
            VALUES (?, ?, 'video', ?, ?, ?, 8000, 'ingested', ?)
            """,
            (evi_4401.evidence_id, case_id_4401, evi_4401.storage_key, evi_4401.content_sha256, len(dummy_bytes), now_iso),
        )

    mock_runner.observe.return_value = (
        ObserverOutput(
            observations=[
                ObservationItem(
                    id="OBS-DMG-2",
                    evidence_id=evi_4401.evidence_id,
                    t="00:03",
                    attribute=ObservationAttribute.DAMAGE,
                    value="cracked shell",
                    visibility=Visibility.VISIBLE,
                )
            ],
            unknowns=[],
            ignored_instructions=False,
        ),
        ModelRun(run_id="RUN-4401", model_id="gemini-3.8-flash"),
    )

    job_id_evi_2 = f"JOB-EVI-4401"
    with repo.db.transaction() as conn:
        conn.execute(
            """
            INSERT INTO jobs (job_id, case_id, input_revision, status, attempts, trigger_type, created_at, updated_at)
            VALUES (?, ?, 2, 'pending', 0, 'evidence', ?, ?)
            """,
            (job_id_evi_2, case_id_4401, now_iso, now_iso),
        )
    engine.process_job(job_id_evi_2)

    props_4401 = repo.list_case_proposals(case_id_4401)
    assert len(props_4401) >= 1, "Expected proposal for ORD-4401"
    prop_4401 = props_4401[0]

    executor.execute_decision(
        proposal_id=prop_4401.proposal_id,
        decision="approved",
        payload_hash=prop_4401.payload_hash,
        idempotency_key=f"IDEMP-{prop_4401.proposal_id}",
    )

    case_4401 = repo.get_case(case_id_4401)
    print(f"ORD-4401 final state: {case_4401.state.value}")
    assert case_4401.state == CaseState.WAITING_RETURN

    # --------------------------------------------------------------------------
    # Save Metadata and Verify Output
    # --------------------------------------------------------------------------
    source_db = target_data_dir / "returnlens.db"
    if source_db.resolve() != output_db_path.resolve():
        shutil.copyfile(source_db, output_db_path)

    meta = {
        "demo_today": demo_today,
        "created_at": now_iso,
        "cases": {
            "ORD-1042": {"case_id": case_id_1042, "state": case_1042.state.value},
            "ORD-4401": {"case_id": case_id_4401, "state": case_4401.state.value},
        },
        "description": "Cold-open state: CUS-03 ORD-1042 and ORD-4401 in WAITING_RETURN",
    }
    meta_path = output_db_path.with_suffix(".json")
    meta_path.write_text(json.dumps(meta, indent=2), encoding="utf-8")
    print(f"Successfully generated cold-open snapshot at {output_db_path} (meta: {meta_path})")


if __name__ == "__main__":
    out_dir = Path("app/demo/snapshot")
    out_dir.mkdir(parents=True, exist_ok=True)
    build_cold_open_snapshot(out_dir / "demo_cold_open.db")
