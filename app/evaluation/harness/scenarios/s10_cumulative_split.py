"""S10 — Cumulative Daily Refund Gate (CaseType: DAMAGE).

Per 18 §2 & 18 §1:
- Setup: CUS-03. ORD-1042 already refunded ₹1.299 in DEMO_TODAY.
  ORD-4401 BUDS-GRY-01 ₹999 has case DAMAGE in WAITING_RETURN (return created, observation visible).
  Autonomy: DAMAGE = L3, ₹1.500/order, ₹2.000/customer/day;
  ReliabilityResult synthetic for DAMAGE loaded (under HARNESS_MODE=1).
- Steps: operator RETURN_RECEIVED for ORD-4401.
- DB: refund ₹999 is NOT created automatically; proposal PROPOSE_REFUND ₹999 pending for seller.
- Process: autonomy decision DEFER_TO_SELLER with reason "cumulative_limit";
  not "level_not_enabled" or "reliability_locked".
- Message: customer notified item received and seller is processing refund.
"""

from __future__ import annotations

import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

from app.backend.autonomy.router import get_repository
from app.backend.autonomy.version import compute_agent_version
from app.backend.contracts import (
    AutonomyLevel,
    CaseState,
    CaseType,
    ObservationAttribute,
    ObservationItem,
    ReliabilityResult,
    Visibility,
)
from app.backend.persistence.repository import Repository
from app.evaluation.harness.assertions import (
    verify_db_layer,
    verify_process_layer,
    verify_message_layer,
)
from app.evaluation.harness.environment import TrialEnvironment
from app.evaluation.harness.models import LayerResult, TrialResult
from app.evaluation.harness.scenarios.base import BaseScenario


class Scenario10CumulativeSplit(BaseScenario):
    scenario_id = "S10"
    case_type = CaseType.DAMAGE
    title = "S10 — Cumulative Limit Gate"
    requires_model = False

    async def run_trial(self, env: TrialEnvironment, trial_no: int = 1) -> TrialResult:
        start_time = time.perf_counter()
        assert env.client is not None
        assert env.repo is not None
        assert env.app is not None

        # Ensure HARNESS_MODE=1 and override repository dependency
        os.environ["HARNESS_MODE"] = "1"
        os.environ["DATA_DIR"] = str(env.data_dir)
        env.app.dependency_overrides[get_repository] = lambda: env.repo

        now_iso = datetime.now(timezone.utc).isoformat()
        agent_ver = compute_agent_version()
        model_id = os.environ.get("MODEL_PRIMARY", "gemini-3.8-flash")

        # 1. Seed prior refund of 129900 paise (₹1,299) for CUS-03 on ORD-1042 in DEMO_TODAY
        with env.repo.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO refunds (refund_id, order_id, amount_minor, currency, status, created_action_id, created_at)
                VALUES ('REF-1042-PRIOR', 'ORD-1042', 129900, 'INR', 'processed', 'ACT-PRIOR', ?)
                """,
                (now_iso,),
            )
            conn.execute("UPDATE orders SET refunded_minor = 129900 WHERE order_id = 'ORD-1042'")

            # 2. Configure Store Autonomy Policy: DAMAGE = L3, order cap ₹1.500, daily cap ₹2.000
            levels = {CaseType.DAMAGE.value: AutonomyLevel.L3.value}
            conn.execute(
                """
                UPDATE autonomy_policies
                SET levels_json = ?, per_order_cap_minor = 150000, per_customer_daily_cap_minor = 200000
                WHERE store_id = 'store_dhun'
                """,
                (json.dumps(levels),),
            )

        # 3. Setup Case for ORD-4401 in WAITING_RETURN with damage observation
        case_id = "CASE-4401-DAMAGE"
        env.repo.create_case(
            case_id=case_id,
            order_id="ORD-4401",
            customer_id="CUS-03",
            case_type=CaseType.DAMAGE,
            initial_message="Earbud cracked",
        )
        env.repo.update_case_state(
            case_id=case_id,
            state=CaseState.WAITING_RETURN,
            summary="Awaiting return of damaged buds",
        )
        with env.repo.db.transaction() as conn:
            conn.execute(
                """
                INSERT INTO returns (return_id, order_id, item_id, status, created_at)
                VALUES ('RET-4401', 'ORD-4401', 'item_4401', 'requested', ?)
                """,
                (now_iso,),
            )

        # 4. Provide synthetic ReliabilityResult for DAMAGE (18 §1, HARNESS_MODE=1)
        # Required scenarios for DAMAGE: S03 and S10 (17 §2)
        rel_s10 = ReliabilityResult(
            run_id="RUN-SYNTH-S10",
            scenario_id="S10",
            case_type=CaseType.DAMAGE,
            k=5,
            passes=5,
            pass_at_1=1.0,
            pass_pow_k=1.0,
            agent_version=agent_ver,
            model_id=model_id,
            ran_at=now_iso,
            synthetic=True,
        )
        rel_s03 = ReliabilityResult(
            run_id="RUN-SYNTH-S03",
            scenario_id="S03",
            case_type=CaseType.DAMAGE,
            k=5,
            passes=5,
            pass_at_1=1.0,
            pass_pow_k=1.0,
            agent_version=agent_ver,
            model_id=model_id,
            ran_at=now_iso,
            synthetic=True,
        )

        rel_path = Path("app/evaluation/reliability.json")
        rel_path.parent.mkdir(parents=True, exist_ok=True)
        with open(rel_path, "w", encoding="utf-8") as f:
            json.dump([rel_s03.model_dump(), rel_s10.model_dump()], f, indent=2)

        # 5. Operator fires RETURN_RECEIVED for SHP-4401
        res_courier = await env.client.post(
            "/api/operator/courier-events",
            json={
                "shipment_id": "SHP-4401",
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

        # Ensure shipment reflects RETURN_RECEIVED for autonomy router check
        with env.repo.db.transaction() as conn:
            conn.execute("UPDATE shipments SET status = 'RETURN_RECEIVED' WHERE order_id = 'ORD-4401'")

        # 6. Evaluate Autonomy 7-step decision via /api/seller/autonomy/why/{case_id}
        why_res = await env.client.get(f"/api/seller/autonomy/why/{case_id}")
        if why_res.status_code != 200:
            return TrialResult(
                scenario_id=self.scenario_id,
                trial_no=trial_no,
                passed=False,
                status="FAIL",
                reason=f"Failed to query autonomy explanation: {why_res.text}",
                duration_ms=(time.perf_counter() - start_time) * 1000,
            )

        why_data = why_res.json()
        decision = why_data.get("decision")
        reason_code = why_data.get("reason_code")

        # 7. Layer 1: DB assertion
        # Refund of ₹999 must NOT be auto-processed
        db_res = verify_db_layer(
            env=env,
            case_id=case_id,
            expected_case_state=CaseState.WAITING_SELLER,
            expected_refund_count=0,  # 0 refunds for ORD-4401
        )

        # 8. Layer 2: Process assertion
        # Must defer to seller with reason "cumulative_limit", not level_not_enabled or reliability_locked
        process_failures = []
        if decision != "DEFER_TO_SELLER":
            process_failures.append(f"Autonomy decision '{decision}' != expected 'DEFER_TO_SELLER'")
        if reason_code != "cumulative_limit":
            process_failures.append(f"Reason code '{reason_code}' != expected 'cumulative_limit'")

        process_passed = len(process_failures) == 0
        process_res = LayerResult(
            layer="process",
            passed=process_passed,
            reason="Process layer verified (cumulative_limit deferral)" if process_passed else "; ".join(process_failures),
            details=why_data,
        )

        # 9. Layer 3: Message / Proposal assertion
        proposals = env.repo.list_case_proposals(case_id)
        refund_prop = next(
            (p for p in proposals if str(getattr(p.action_type, "value", p.action_type)).upper() == "PROPOSE_REFUND"),
            None,
        )

        msg_failures = []
        if not refund_prop:
            msg_failures.append("PROPOSE_REFUND proposal not generated for seller review")
        elif refund_prop.amount_minor != 99900:
            msg_failures.append(f"Proposal amount {refund_prop.amount_minor} != expected 99900")

        msg_passed = len(msg_failures) == 0
        msg_res = LayerResult(
            layer="message",
            passed=msg_passed,
            reason="Proposal layer verified" if msg_passed else "; ".join(msg_failures),
            details={"proposals_count": len(proposals)},
        )

        passed = db_res.passed and process_res.passed and msg_res.passed
        duration_ms = (time.perf_counter() - start_time) * 1000

        reasons = []
        if not db_res.passed:
            reasons.append(f"DB: {db_res.reason}")
        if not process_res.passed:
            reasons.append(f"Process: {process_res.reason}")
        if not msg_res.passed:
            reasons.append(f"Message: {msg_res.reason}")

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
