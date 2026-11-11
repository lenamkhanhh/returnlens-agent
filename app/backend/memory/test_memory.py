"""Unit tests for Customer Memory and PlanRecord (Card B13).

Verifies:
- Test 48: Returning customer profile persists language and preferences across session boundaries.
- PlanRecord (goal, tools, outcome) + memory_used persistence and retrieval.
- Memory chip formatting for seller console.
"""

from __future__ import annotations

import tempfile
import unittest
from pathlib import Path

from app.backend.contracts import CaseType, Language
from app.backend.memory.plan import get_case_plan, record_case_plan
from app.backend.memory.profile import (
    format_memory_chips,
    get_or_create_customer_profile,
    update_customer_memory,
)
from app.backend.persistence.db import Database
from app.backend.persistence.repository import Repository
from app.backend.persistence.seed import seed_database


class TestCustomerMemory(unittest.TestCase):
    def setUp(self):
        self.temp_dir = tempfile.TemporaryDirectory()
        self.db_path = Path(self.temp_dir.name) / "test.db"
        self.db = Database(self.db_path)
        seed_database(self.db)
        self.repo = Repository(self.db)

    def tearDown(self):
        self.temp_dir.cleanup()

    def test_48_returning_customer_memory_persists(self):
        """Test 48: Customer memory remembers preferred language and prior interactions across session restarts."""
        # 1. Customer CUS-02 interacts, updates language preference to Hindi
        profile1 = update_customer_memory(
            repo=self.repo,
            customer_id="CUS-02",
            preferred_language=Language.HI,
            refund_destination="UPI",
            increment_prior_case_count=True,
        )
        self.assertEqual(profile1.preferred_language, Language.HI)
        self.assertEqual(profile1.refund_destination, "UPI")
        self.assertGreater(profile1.prior_case_count, 0)

        # 2. Simulate worker restart / new session: reload fresh repository connection
        restarted_repo = Repository(Database(self.db_path))
        profile2 = get_or_create_customer_profile(restarted_repo, "CUS-02")

        # 3. Assert profile is fully retained
        self.assertEqual(profile2.customer_id, "CUS-02")
        self.assertEqual(profile2.preferred_language, Language.HI)
        self.assertEqual(profile2.refund_destination, "UPI")
        self.assertEqual(profile2.prior_case_count, profile1.prior_case_count)

        # 4. Check memory chips for seller UI
        chips = format_memory_chips(profile2)
        self.assertIn("preferred_language=hi", chips)
        self.assertIn("refund_destination=UPI", chips)

    def test_plan_record_persistence_and_retrieval(self):
        """PlanRecord correctly saves and retrieves 3 fields (goal, tools, outcome) + memory_used."""
        case_id = "CASE-1042"
        job_id = "JOB-001"
        self.repo.create_case(
            case_id=case_id,
            order_id="ORD-1042",
            customer_id="CUS-03",
            case_type=CaseType.DAMAGE,
        )
        goal = "Resolve damaged goods claim for ORD-1042"
        tools_planned = ["get_order", "get_tracking", "observe_video"]
        tools_called = ["get_order", "get_tracking", "observe_video"]
        outcome = "Proposed replacement return; awaiting seller approval"
        memory_used = ["preferred_language=hi", "prior_cases=1"]

        # Record plan
        plan = record_case_plan(
            repo=self.repo,
            case_id=case_id,
            job_id=job_id,
            goal=goal,
            tools_planned=tools_planned,
            tools_called=tools_called,
            outcome=outcome,
            memory_used=memory_used,
        )

        self.assertEqual(plan.case_id, case_id)
        self.assertEqual(plan.goal, goal)

        # Retrieve plan from DB
        retrieved = get_case_plan(self.repo, case_id)
        self.assertIsNotNone(retrieved)
        self.assertEqual(retrieved.plan_id, plan.plan_id)
        self.assertEqual(retrieved.goal, goal)
        self.assertEqual(retrieved.tools_planned, tools_planned)
        self.assertEqual(retrieved.tools_called, tools_called)
        self.assertEqual(retrieved.outcome, outcome)
        self.assertEqual(retrieved.memory_used, memory_used)


if __name__ == "__main__":
    unittest.main()
