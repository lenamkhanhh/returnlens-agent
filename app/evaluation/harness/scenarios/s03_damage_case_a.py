"""S03 — Case A, Damage (CaseType: DAMAGE).

Per 18 §2 & Wave 13:
- Setup: CUS-06, ORD-1043 HEAD-BLK-01 ₹1,299, delivered -4 days.
- Steps: customer sends "The headband cracked during normal use." + real CC damage photo ->
  (harness-seller) approve PROPOSE_RETURN -> operator RETURN_RECEIVED ->
  (harness-seller) approve PROPOSE_REFUND ₹1,299 -> replay idempotent refund decision.
- DB: 1 return status received; 1 refund 129900 paise processed; order refunded_minor = 129900; case RESOLVED.
- Process: observation damage visible; P_WINDOW PASS; refund only after RETURN_RECEIVED;
  replay decision with same Idempotency-Key does not create second refund.
- Message: confirmation has return label ID; refund confirmation ₹1,299 only after processed.
"""

from __future__ import annotations

import os
import time
from pathlib import Path
from typing import Optional

from app.backend.contracts import CaseState, CaseType
from app.evaluation.harness.assertions import (
    verify_db_layer,
    verify_process_layer,
    verify_message_layer,
)
from app.evaluation.harness.environment import TrialEnvironment
from app.evaluation.harness.models import TrialResult
from app.evaluation.harness.scenarios.base import BaseScenario


class Scenario03DamageCaseA(BaseScenario):
    scenario_id = "S03"
    case_type = CaseType.DAMAGE
    title = "S03 — Case A, Damage"
    requires_model = True

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()

        # Check model prerequisite
        prereq = self.check_prerequisites(trial_no=trial_no)
        if prereq:
            return prereq

        assert env.client is not None
        assert env.repo is not None

        photo_path = Path("app/demo/media/stock/flickr_broken_headphones_gabrielsaldana_4728001748.jpg")
        if not photo_path.exists():
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="BLOCKED",
                reason=f"Media file {photo_path} not found",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 1. Customer initiates damage claim with real CC photo (Wave 13 / 18 §2)
        res = await env.client.post(
            "/api/cases",
            json={
                "order_id": "ORD-1043",
                "initial_message": "The headband cracked during normal use.",
            },
            headers={"X-Customer-Id": "CUS-06"},
        )
        if res.status_code != 202:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Case creation failed: {res.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        case_id = res.json()["case_id"]

        # Upload real broken-headphones JPEG photo
        with open(photo_path, "rb") as f:
            res_evi = await env.client.post(
                f"/api/cases/{case_id}/evidence",
                files={"file": (photo_path.name, f, "image/jpeg")},
                headers={"X-Customer-Id": "CUS-06"},
            )
        if res_evi.status_code != 201:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Evidence upload failed: {res_evi.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 2. Harness acting as seller: approve return proposal
        proposals = env.repo.list_case_proposals(case_id)
        return_prop = next(
            (p for p in proposals if str(p.action_type.value).lower() == "propose_return"),
            None,
        )
        if not return_prop:
            cur_case = env.repo.get_case(case_id)
            detail = f" (state={cur_case.state.value}, summary={cur_case.summary})" if cur_case else ""
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Return proposal not created by agent{detail}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        res_app = await env.client.post(
            f"/api/proposals/{return_prop.proposal_id}/decisions",
            json={"decision": "approve", "payload_hash": return_prop.payload_hash},
            headers={"Idempotency-Key": f"DEC-RET-{case_id}"},
        )
        if res_app.status_code != 200:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Seller approval for return failed: {res_app.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        with env.repo.db.cursor() as cur:
            cur.execute("SELECT label_id FROM returns WHERE order_id = ?", ("ORD-1043",))
            ret_row = cur.fetchone()
            cur.execute("SELECT count(*) AS cnt FROM refunds WHERE order_id = ?", ("ORD-1043",))
            pre_refund_cnt = cur.fetchone()["cnt"]
        label_id = ret_row["label_id"] if ret_row else ""

        # 3. Operator fires RETURN_RECEIVED courier event (18 §2)
        res_courier = await env.client.post(
            "/api/operator/courier-events",
            json={
                "shipment_id": "SHP-1043",
                "type": "RETURN_RECEIVED",
            },
        )
        if res_courier.status_code != 200:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Operator RETURN_RECEIVED event failed: {res_courier.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 4. Harness acting as seller: approve refund proposal
        proposals_v2 = env.repo.list_case_proposals(case_id)
        refund_prop = next(
            (p for p in proposals_v2 if str(p.action_type.value).lower() == "propose_refund"),
            None,
        )
        if not refund_prop:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason="Refund proposal not generated after RETURN_RECEIVED",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        refund_idem_key = f"DEC-REF-{case_id}"
        res_ref = await env.client.post(
            f"/api/proposals/{refund_prop.proposal_id}/decisions",
            json={"decision": "approve", "payload_hash": refund_prop.payload_hash},
            headers={"Idempotency-Key": refund_idem_key},
        )
        if res_ref.status_code != 200:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Refund decision approval failed: {res_ref.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        # 5. Replay decision with same Idempotency-Key (must not duplicate refund)
        res_replay = await env.client.post(
            f"/api/proposals/{refund_prop.proposal_id}/decisions",
            json={"decision": "approve", "payload_hash": refund_prop.payload_hash},
            headers={"Idempotency-Key": refund_idem_key},
        )

        # 6. Layer 1: DB assertion
        db_res = verify_db_layer(
            env=env,
            case_id=case_id,
            expected_case_state=CaseState.RESOLVED,
            expected_return_count=1,
            expected_return_status="received",
            expected_refund_count=1,
            expected_refund_status="processed",
            expected_refund_minor=129900,
        )

        # 7. Layer 2: Process assertion
        process_res = verify_process_layer(
            env=env,
            case_id=case_id,
            max_clarifications=1,
            check_no_premature_write=True,
            expected_event_types=["policy_checked", "courier_event_received", "return_created", "refund_posted"],
            require_model_observation=True,
        )

        # 8. Layer 3: Message assertion
        required_subs = ["1,299"]
        if label_id:
            required_subs.append(label_id)
        msg_res = verify_message_layer(
            env=env,
            case_id=case_id,
            required_substrings=required_subs,
            forbidden_substrings=["fraud", "scam"],
            include_seller_messages=True,
        )

        extra_failures = []
        if pre_refund_cnt != 0:
            extra_failures.append(f"Refund existed before RETURN_RECEIVED (count={pre_refund_cnt})")
        if not label_id:
            extra_failures.append("Return label_id missing after return approval")
        if res_replay.status_code != 200 or res_replay.json().get("action_id") != res_ref.json().get("action_id"):
            extra_failures.append(
                f"Idempotent replay returned unexpected payload: {res_replay.status_code} {res_replay.text} (expected action_id {res_ref.json().get('action_id')})"
            )

        updated_order = env.repo.get_order("ORD-1043")
        if not updated_order or updated_order.refunded_minor != 129900:
            extra_failures.append(
                f"Expected ORD-1043 refunded_minor=129900, got {updated_order.refunded_minor if updated_order else None}"
            )

        with env.repo.db.cursor() as cur:
            cur.execute(
                "SELECT attribute, value, visibility FROM observations WHERE case_id = ?",
                (case_id,),
            )
            obs_rows = cur.fetchall()
            cur.execute(
                "SELECT event_type FROM audit_events WHERE case_id = ? ORDER BY seq ASC",
                (case_id,),
            )
            ordered_events = [r["event_type"] for r in cur.fetchall()]

        audit_events = env.repo.list_case_audit_events(case_id)
        p_window_pass = any(
            e.event_type == "policy_checked"
            and (
                (
                    isinstance(e.safe_payload, dict)
                    and e.safe_payload.get("rule_id") == "P_WINDOW"
                    and str(e.safe_payload.get("result", "")).upper() == "PASS"
                )
                or "p_window pass" in (e.outcome or "").lower()
            )
            for e in audit_events
        )

        no_damage_vals = {"none", "none observed", "no damage", "no visible damage", "not visible", ""}
        if not any(
            str(r["attribute"]).lower() == "damage"
            and str(r["visibility"]).lower() == "visible"
            and str(r["value"] or "").strip().lower() not in no_damage_vals
            for r in obs_rows
        ):
            extra_failures.append("Expected at least one visible concrete damage observation in DB")

        if not p_window_pass:
            extra_failures.append("Expected P_WINDOW PASS in policy audit trace")

        if "courier_event_received" in ordered_events and "refund_posted" in ordered_events:
            if ordered_events.index("refund_posted") <= ordered_events.index("courier_event_received"):
                extra_failures.append("refund_posted occurred before courier_event_received")

        passed = db_res.passed and process_res.passed and msg_res.passed and not extra_failures
        duration_ms = (time.perf_counter() - start_time) * 1000

        reasons = []
        if not db_res.passed:
            reasons.append(f"DB: {db_res.reason}")
        if not process_res.passed:
            reasons.append(f"Process: {process_res.reason}")
        if not msg_res.passed:
            reasons.append(f"Message: {msg_res.reason}")
        reasons.extend(extra_failures)

        return TrialResult(
            scenario_id=self.scenario_id,
            trial_no=trial_no,
            passed=passed,
            status="PASS" if passed else "FAIL",
            reason="All 3 layers verified" if passed else " | ".join(reasons),
            db_layer=db_res,
            process_layer=process_res,
            message_layer=msg_res,
            duration_ms=duration_ms,
        )
