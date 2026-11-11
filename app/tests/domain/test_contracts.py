"""Unit test for app/backend/contracts.py (Card B00 proof)."""

import pytest
from app.backend.contracts import (
    CaseType,
    CaseState,
    NextStep,
    ColorClass,
    Visibility,
    ObservationAttribute,
    Intent,
    Language,
    AutonomyLevel,
    AutonomyDecision,
    RefundStatus,
    ReturnStatus,
    PolicyRuleId,
    PolicyCheckResult,
    CourierEventType,
    ActionType,
    ActionStatus,
    JobStatus,
    JobTrigger,
    ActorRole,
    ErrorShape,
    StorePolicy,
    LineItem,
    Order,
    Shipment,
    Message,
    Case,
    Evidence,
    EvidenceRef,
    VoiceNote,
    Observation,
    FactSnapshot,
    PolicyCheck,
    ProposalBasis,
    Proposal,
    Approval,
    Action,
    ReturnRecord,
    RefundRecord,
    AuditEvent,
    Job,
    CustomerProfile,
    CourierEvent,
    AutonomyPolicy,
    ReliabilityResult,
    PlanRecord,
    RouterOutput,
    ObserverOutput,
    TranscriberOutput,
    PlannerOutput,
)


def test_enums_completeness():
    assert len(CaseType) == 6
    assert set(c.value for c in CaseType) == {"WISMO", "DAMAGE", "MISMATCH", "UNCLEAR", "LATE", "NDR"}
    assert len(AutonomyLevel) == 4
    assert len(ColorClass) == 5
    assert len(PolicyRuleId) == 9


def test_order_and_line_item():
    item = LineItem(
        item_id="item_01",
        sku="HEAD-WHT-02",
        catalog_color=ColorClass.WHITE,
        display_name="Dhun Wave Headphones",
        quantity=1,
        refundable_item_minor=149900,
    )
    order = Order(
        order_id="ORD-7729",
        store_id="store_dhun",
        customer_id="CUS-02",
        currency="INR",
        paid_minor=149900,
        refunded_minor=0,
        reserved_minor=0,
        revision=1,
        line_item=item,
    )
    assert order.paid_minor == 149900
    assert order.line_item.catalog_color == ColorClass.WHITE


def test_autonomy_policy_default():
    policy = AutonomyPolicy(store_id="store_dhun")
    assert policy.levels[CaseType.WISMO] == AutonomyLevel.L1
    assert policy.levels[CaseType.DAMAGE] == AutonomyLevel.L0
    assert policy.per_order_cap_minor == 150000
    assert policy.per_customer_daily_cap_minor == 200000
    assert not policy.kill_switch


def test_model_outputs_schemas():
    router = RouterOutput(
        intent=Intent.WISMO,
        read_tools=[{"name": "get_order", "args": {"order_id": "ORD-2030"}}],
    )
    assert router.intent == Intent.WISMO
    assert len(router.read_tools) == 1

    planner = PlannerOutput(
        goal="Provide tracking update for customer",
        recommended_next_step=NextStep.SEND_STATUS,
        alternatives=[],
        customer_reply_draft="Your order is in transit.",
    )
    assert planner.recommended_next_step == NextStep.SEND_STATUS
