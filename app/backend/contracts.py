"""ReturnLens Canonical Contracts and Domain Schemas.

Card B00: Single source of truth for enums, data contracts, model output schemas,
and API payloads as specified in 17 §2, 17 §4, 17 §5, and 02 §1–§5b.
All monetary amounts are integer paise (minor units).
"""

from __future__ import annotations

from enum import Enum
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, ConfigDict, Field


# ==============================================================================
# 1. Enums (17 §2, 02 §2)
# ==============================================================================

class CaseType(str, Enum):
    """Case type determining routing, evidence handling, and autonomy eligibility."""
    WISMO = "WISMO"
    DAMAGE = "DAMAGE"
    MISMATCH = "MISMATCH"
    UNCLEAR = "UNCLEAR"
    LATE = "LATE"
    NDR = "NDR"


class CaseState(str, Enum):
    """Case lifecycle state (01 §5, 17 §2)."""
    NEW = "NEW"
    PROCESSING = "PROCESSING"
    WAITING_CUSTOMER = "WAITING_CUSTOMER"
    WAITING_SELLER = "WAITING_SELLER"
    ACTION_PENDING = "ACTION_PENDING"
    WAITING_RETURN = "WAITING_RETURN"
    HUMAN_REVIEW = "HUMAN_REVIEW"
    RECONCILIATION = "RECONCILIATION"
    RESOLVED = "RESOLVED"


class NextStep(str, Enum):
    """Recommended or planned next step in case resolution (17 §2)."""
    SEND_STATUS = "SEND_STATUS"
    REQUEST_EVIDENCE = "REQUEST_EVIDENCE"
    PROPOSE_RETURN = "PROPOSE_RETURN"
    PROPOSE_REFUND = "PROPOSE_REFUND"
    PROPOSE_NDR_REATTEMPT = "PROPOSE_NDR_REATTEMPT"
    HANDOFF = "HANDOFF"


class ColorClass(str, Enum):
    """Standardized color classification for observation comparison (17 §2)."""
    WHITE = "white"
    BLACK = "black"
    GREY = "grey"
    OTHER = "other"
    UNKNOWN = "unknown"


class Visibility(str, Enum):
    """Observation visibility assessment (17 §2)."""
    VISIBLE = "visible"
    UNCLEAR = "unclear"
    NOT_OBSERVED = "not_observed"


class ObservationAttribute(str, Enum):
    """Target attribute evaluated in video or image evidence (17 §2)."""
    COLOR = "color"
    DAMAGE = "damage"
    LABEL_TEXT = "label_text"
    ITEM_TYPE = "item_type"
    OTHER = "other"


class Intent(str, Enum):
    """Customer intent extracted by router or transcriber (17 §2)."""
    WISMO = "WISMO"
    RETURN = "RETURN"
    REFUND = "REFUND"
    ADDRESS_UPDATE = "ADDRESS_UPDATE"
    OTHER = "OTHER"


class Language(str, Enum):
    """Customer message or voice note language (17 §2)."""
    EN = "en"
    HI = "hi"
    HINGLISH = "hinglish"
    OTHER = "other"


class AutonomyLevel(str, Enum):
    """Earned autonomy ladder levels L0–L3 (17 §2, 02 §5b)."""
    L0 = "L0"  # Draft only (default for financial actions)
    L1 = "L1"  # Inform (status, clarification <=1, NDR notice)
    L2 = "L2"  # Act (no money: create_return, ndr_action reattempt)
    L3 = "L3"  # Small refund (after RETURN_RECEIVED, under cumulative cap)


class AutonomyDecision(str, Enum):
    """Decision produced by the 7-step autonomy evaluation algorithm (17 §2, 17 §3)."""
    AUTO = "AUTO"
    DEFER_TO_SELLER = "DEFER_TO_SELLER"
    BLOCK = "BLOCK"


class RefundStatus(str, Enum):
    """Status of a refund transaction (17 §2, 02 §4b)."""
    PENDING = "pending"
    PROCESSED = "processed"
    FAILED = "failed"


class ReturnStatus(str, Enum):
    """Status of a return record (02 §2, 02 §4b)."""
    REQUESTED = "requested"
    IN_TRANSIT = "in_transit"
    RECEIVED = "received"
    CANCELLED = "cancelled"


class PolicyRuleId(str, Enum):
    """Deterministic policy rules evaluated by code (17 §2, 02 §5)."""
    P_OWNERSHIP = "P_OWNERSHIP"
    P_WINDOW = "P_WINDOW"  # 0 <= DEMO_TODAY - delivered_date <= 7 days
    P_RECEIPT = "P_RECEIPT"  # Refund requires RETURN_RECEIVED
    P_CAP = "P_CAP"  # <= ₹3.000 per transaction (300000 paise)
    P_BALANCE = "P_BALANCE"  # <= paid_minor - refunded_minor - reserved_minor
    P_CUMULATIVE = "P_CUMULATIVE"  # Autonomy limits per order / per customer daily
    P_CLARIFY_BUDGET = "P_CLARIFY_BUDGET"  # <= 1 clarification request per case
    P_NDR = "P_NDR"  # Attempt <= 3, cannot change pincode/city/state
    P_UNVERIFIED = "P_UNVERIFIED"  # Unclear/conflicting observations block auto


class PolicyCheckResult(str, Enum):
    """Result of evaluating a deterministic policy rule (17 §2)."""
    PASS = "PASS"
    FAIL = "FAIL"
    UNKNOWN = "UNKNOWN"


class CourierEventType(str, Enum):
    """Types of mock courier events ingested by operator or system (17 §2, 02 §2)."""
    NDR = "NDR"
    DELAYED = "DELAYED"
    RETURN_RECEIVED = "RETURN_RECEIVED"


class ActionType(str, Enum):
    """Executor action types for domain side effects (02 §4)."""
    REQUEST_EVIDENCE = "request_evidence"
    SEND_STATUS_REPLY = "send_status_reply"
    HANDOFF_CASE = "handoff_case"
    CREATE_RETURN = "create_return"
    ISSUE_REFUND = "issue_refund"
    NDR_ACTION = "ndr_action"
    SEND_RESOLUTION_REPLY = "send_resolution_reply"


class ActionStatus(str, Enum):
    """Execution status of a domain action (02 §2)."""
    PENDING = "pending"
    SUCCEEDED = "succeeded"
    FAILED = "failed"
    BLOCKED = "blocked"
    UNKNOWN = "unknown"


class JobStatus(str, Enum):
    """Durable job processing status (02 §2)."""
    PENDING = "pending"
    LEASED = "leased"
    COMPLETED = "completed"
    FAILED = "failed"


class JobTrigger(str, Enum):
    """Event that triggered a background job (02 §2, 17 §2)."""
    MESSAGE = "message"
    COURIER_EVENT = "courier_event"
    HARNESS = "harness"


class ActorRole(str, Enum):
    """Security role of an actor in conversations and audits (02 §2)."""
    CUSTOMER = "customer"
    SELLER = "seller"
    AGENT = "agent"
    OPERATOR = "operator"
    COURIER = "courier"


# ==============================================================================
# 2. Base Models & Error Shape (02 §1, 02 §2)
# ==============================================================================

class AppBaseModel(BaseModel):
    """Base model with strict configuration."""
    model_config = ConfigDict(extra="forbid", populate_by_name=True)


class ErrorShape(AppBaseModel):
    """Structured error contract returned across all HTTP and domain failures (02 §1)."""
    code: str
    user_message: str
    retryable: bool = False
    correlation_id: str = ""


# ==============================================================================
# 3. Domain Entities & Value Objects (02 §2)
# ==============================================================================

class StorePolicy(AppBaseModel):
    """Store-level configuration and policy limits (02 §2)."""
    store_id: str
    policy_version: str = "1.0"
    timezone: str = "Asia/Kolkata"
    return_window_days: int = 7
    eligible_reasons: List[str] = Field(default_factory=lambda: ["damaged", "wrong_item", "defective"])
    cap_minor: int = 300000  # ₹3.000 max single refund in paise
    require_receipt_before_refund: bool = True
    approved_template_ids: List[str] = Field(default_factory=list)


class LineItem(AppBaseModel):
    """Line item within an order (single item per order in core prototype) (02 §2)."""
    item_id: str
    sku: str
    catalog_color: ColorClass
    display_name: str
    quantity: int = 1
    refundable_item_minor: int  # Price in paise (e.g. 149900 for ₹1.499)


class Order(AppBaseModel):
    """Order record from mock backend; ledger is balance authority (02 §2)."""
    order_id: str
    store_id: str
    customer_id: str
    currency: str = "INR"
    paid_minor: int  # Total paid in paise
    refunded_minor: int = 0  # Processed refunds in paise
    reserved_minor: int = 0  # In-flight refund reservations in paise
    revision: int = 1
    line_item: LineItem


class Shipment(AppBaseModel):
    """Shipment record from courier mock (02 §2)."""
    shipment_id: str
    order_id: str
    carrier_label: str = "Delhivery"
    status: str  # e.g. DELIVERED, IN_TRANSIT, OUT_FOR_DELIVERY, NDR
    delivered_at: Optional[str] = None  # ISO-8601 date string e.g. "2026-11-07"
    latest_scan_at: Optional[str] = None
    source_revision: int = 1
    eta: Optional[str] = None
    recipient_address: Optional[str] = None
    pincode: Optional[str] = None
    attempt_count: int = 0
    reason: Optional[str] = None


class Message(AppBaseModel):
    """Immutable chat message record (02 §2)."""
    message_id: str
    client_message_id: Optional[str] = None
    case_id: str
    actor_id: str
    role: ActorRole
    text: str
    language: Language = Language.EN
    attachment_ids: List[str] = Field(default_factory=list)
    created_at: str


class Case(AppBaseModel):
    """Case entity tracking overall customer issue (02 §2)."""
    case_id: str
    order_id: str
    customer_id: str
    case_type: CaseType
    state: CaseState = CaseState.NEW
    input_revision: int = 1
    clarification_count: int = 0
    summary: str = ""
    last_error: Optional[str] = None


class Evidence(AppBaseModel):
    """Uploaded media asset record (02 §2)."""
    evidence_id: str
    case_id: str
    media_type: str  # "video", "image", "audio"
    storage_key: str
    content_sha256: str
    bytes: int
    duration_ms: Optional[int] = None
    width: Optional[int] = None
    height: Optional[int] = None
    ingest_status: str = "ingested"
    created_at: str


class EvidenceRef(AppBaseModel):
    """Reference to a specific timestamp/frame in evidence (02 §2)."""
    ref_id: str
    evidence_id: str
    timestamp_ms: Optional[int] = None
    source: str = "model_native"  # "model_native" or "decoder_fallback"
    content_hash: Optional[str] = None


class VoiceNote(AppBaseModel):
    """Voice note audio metadata and transcribed observation (02 §2)."""
    evidence_id: str
    media_type: str = "audio"
    mime: str  # "audio/ogg", "audio/webm", "audio/opus", "audio/mp4"
    duration_ms: int
    transcript: str
    language_detected: Language
    transcript_model_run_id: Optional[str] = None


class Observation(AppBaseModel):
    """Ground-truth observation extracted from evidence (02 §2, 17 §4)."""
    observation_id: str
    evidence_id: str
    evidence_ref_ids: List[str] = Field(default_factory=list)
    t: Optional[str] = None  # "MM:SS" for video timestamp, None for photo
    attribute: ObservationAttribute
    value: str
    color_class: Optional[ColorClass] = None
    visibility: Visibility = Visibility.VISIBLE
    uncertainty_reason: Optional[str] = None
    model_run_id: Optional[str] = None


class FactSnapshot(AppBaseModel):
    """Point-in-time snapshot of verified facts (02 §2)."""
    order_revision: int
    shipment_revision: int
    policy_version: str
    fetched_at: str
    source_tool_call_ids: List[str] = Field(default_factory=list)


class PolicyCheck(AppBaseModel):
    """Deterministic evaluation outcome for a single policy rule (02 §2)."""
    rule_id: PolicyRuleId
    result: PolicyCheckResult
    reason_code: str
    source_refs: List[str] = Field(default_factory=list)

    @property
    def reason(self) -> str:
        return self.reason_code


class ProposalBasis(AppBaseModel):
    """Immutable state snapshot on which a proposal was generated (02 §2, 02 §7)."""
    evidence_revision: int = 1
    observation_set_revision: int = 1
    order_revision: int = 1
    shipment_revision: int = 1
    policy_version: str = "1.0"
    action_fields: Dict[str, Any] = Field(default_factory=dict)
    amount_minor: Optional[int] = None


class Proposal(AppBaseModel):
    """Immutable action recommendation requiring approval or autonomy grant (02 §2)."""
    proposal_id: str
    case_id: str
    action_type: NextStep
    item_id: Optional[str] = None
    amount_minor: Optional[int] = None
    currency: str = "INR"
    customer_reply_draft: str = ""
    rationale_refs: List[str] = Field(default_factory=list)
    basis: ProposalBasis
    status: str = "pending"  # "pending", "approved", "declined", "stale"
    payload_hash: str = ""
    created_at: str = ""


class Approval(AppBaseModel):
    """Explicit seller or autonomy authorization for a specific proposal (02 §2)."""
    approval_id: str
    proposal_id: str
    seller_id: str  # User ID or "policy:autonomy@<policy_version>"
    decision: str = "approve"  # "approve", "decline", "manual_review"
    approved_payload_hash: str
    approved_at: str


class Action(AppBaseModel):
    """Executed mutation command tracked by domain executor (02 §2)."""
    action_id: str
    type: ActionType
    order_id: str
    proposal_id: str
    approval_id: Optional[str] = None
    idempotency_key: str
    payload_hash: str
    status: ActionStatus = ActionStatus.PENDING
    result_ref: Optional[str] = None
    attempt_count: int = 0
    created_at: str = ""


class ReturnRecord(AppBaseModel):
    """Return entity created via mock Shopify returnCreate (02 §2, 02 §4b)."""
    return_id: str
    order_id: str
    item_id: str
    quantity: int = 1
    status: ReturnStatus = ReturnStatus.REQUESTED
    label_id: Optional[str] = None
    created_action_id: str
    created_at: str = ""


class RefundRecord(AppBaseModel):
    """Refund entity created via mock Razorpay refund (02 §2, 02 §4b)."""
    refund_id: str
    order_id: str
    amount_minor: int  # in paise
    currency: str = "INR"
    status: RefundStatus = RefundStatus.PROCESSED
    created_action_id: str
    created_at: str = ""


class AuditEvent(AppBaseModel):
    """Append-only audit and timeline event (02 §2, 02 §8)."""
    event_id: str
    seq: int
    actor: str
    event_type: str
    outcome: str
    refs: List[str] = Field(default_factory=list)
    safe_payload: Dict[str, Any] = Field(default_factory=dict)
    recorded_at: str


class Job(AppBaseModel):
    """Durable worker queue job (02 §2)."""
    job_id: str
    case_id: str
    input_revision: int = 1
    status: JobStatus = JobStatus.PENDING
    lease_until: Optional[str] = None
    attempts: int = 0
    resume_reason: Optional[str] = None
    trigger: JobTrigger = JobTrigger.MESSAGE


class CustomerProfile(AppBaseModel):
    """Customer memory persisting across chat sessions (02 §2, 17 §2)."""
    customer_id: str
    store_id: str
    name: str = ""
    phone: str = ""
    preferred_language: Language = Language.EN
    refund_destination: str = "original"  # "UPI", "store_credit", "original"
    open_case_ids: List[str] = Field(default_factory=list)
    prior_case_count: int = 0
    updated_at: str = ""


class CourierEvent(AppBaseModel):
    """Inbound webhook or mock courier status event (02 §2, 17 §2)."""
    event_id: str
    shipment_id: str
    type: CourierEventType
    attempt_no: int = 1
    reason: Optional[str] = None
    received_at: str = ""
    simulated: bool = True


class AutonomyPolicy(AppBaseModel):
    """Seller-configurable autonomy levels and cumulative gates (02 §2, 17 §2)."""
    store_id: str
    version: str = "1.0"
    levels: Dict[CaseType, AutonomyLevel] = Field(
        default_factory=lambda: {
            CaseType.WISMO: AutonomyLevel.L1,
            CaseType.DAMAGE: AutonomyLevel.L0,
            CaseType.MISMATCH: AutonomyLevel.L0,
            CaseType.UNCLEAR: AutonomyLevel.L0,
            CaseType.LATE: AutonomyLevel.L0,
            CaseType.NDR: AutonomyLevel.L1,
        }
    )
    per_order_cap_minor: int = 150000  # ₹1.500 in paise
    per_customer_daily_cap_minor: int = 200000  # ₹2.000 in paise
    kill_switch: bool = False
    changed_by: str = "seller"
    changed_at: str = ""


class ReliabilityResult(AppBaseModel):
    """Harness reliability execution result gating L2/L3 autonomy (02 §2, 17 §2)."""
    run_id: str
    scenario_id: str
    case_type: CaseType
    k: int = 5
    passes: int = 5
    pass_at_1: float = 1.0
    pass_pow_k: float = 1.0
    agent_version: str
    model_id: Optional[str] = None
    ran_at: str
    synthetic: bool = False
    status: str = "passed"
    reason: Optional[str] = None


class PlanRecord(AppBaseModel):
    """Structured plan record displayed in seller console (02 §2, 17 §2)."""
    plan_id: str
    case_id: str
    job_id: str
    goal: str
    tools_planned: List[str] = Field(default_factory=list)
    tools_called: List[str] = Field(default_factory=list)
    outcome: str
    memory_used: List[str] = Field(default_factory=list)


# ==============================================================================
# 4. Model Output Schemas (17 §4)
# ==============================================================================

class ToolCallProposal(AppBaseModel):
    """Tool invocation selected by router or planner."""
    name: str
    args: Dict[str, Any] = Field(default_factory=dict)


class RouterOutput(AppBaseModel):
    """Structured output schema for Router stage (17 §4)."""
    intent: Intent
    read_tools: List[ToolCallProposal] = Field(default_factory=list)
    missing_inputs: List[str] = Field(default_factory=list)
    handoff_reason: Optional[str] = None


class ObservationItem(AppBaseModel):
    """Individual observation item from video or image (17 §4)."""
    id: str
    evidence_id: str
    t: Optional[str] = None  # "MM:SS" for video, None for image
    attribute: ObservationAttribute
    value: str
    color_class: Optional[ColorClass] = None
    visibility: Visibility = Visibility.VISIBLE
    limitation: Optional[str] = None


class ObserverOutput(AppBaseModel):
    """Structured output schema for Observer stage (17 §4)."""
    observations: List[ObservationItem] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    ignored_instructions: bool = False


class MentionedFacts(AppBaseModel):
    """Unverified entities mentioned in customer audio (17 §4)."""
    order_ids: List[str] = Field(default_factory=list)
    amounts_minor: List[int] = Field(default_factory=list)


class TranscriberOutput(AppBaseModel):
    """Structured output schema for Transcriber stage (17 §4)."""
    transcript: str
    language: Language
    translation_en: str = ""
    intent: Intent = Intent.OTHER
    mentioned: MentionedFacts = Field(default_factory=MentionedFacts)
    inaudible: bool = False


class PlanAlternative(AppBaseModel):
    """Alternative next step considered by planner (17 §4)."""
    next_step: NextStep
    reason: str


class PlannerOutput(AppBaseModel):
    """Structured output schema for Planner stage (17 §4)."""
    goal: str
    recommended_next_step: NextStep
    alternatives: List[PlanAlternative] = Field(default_factory=list)
    facts_used: List[str] = Field(default_factory=list)
    observations_used: List[str] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    customer_reply_draft: str = ""
    handoff_summary: Optional[str] = None


# ==============================================================================
# 5. API Request & Response Payloads (17 §5)
# ==============================================================================

class CreateCaseRequest(AppBaseModel):
    """Request payload to create a new case (17 §5)."""
    order_id: str
    initial_message: str
    client_message_id: Optional[str] = None


class CreateCaseResponse(AppBaseModel):
    """Response payload when a case is created/accepted (17 §5)."""
    case_id: str
    accepted_revision: int
    job_id: str


class CaseSnapshotResponse(AppBaseModel):
    """Full snapshot of a case for the seller console (17 §5) and customer chat."""
    case_id: str
    case_type: CaseType
    state: CaseState
    facts: Dict[str, Any] = Field(default_factory=dict)
    observations: List[Dict[str, Any]] = Field(default_factory=list)
    unknowns: List[str] = Field(default_factory=list)
    policy_checks: List[Dict[str, Any]] = Field(default_factory=list)
    plan: Optional[Dict[str, Any]] = None
    clarification_count: int = 0
    proposals: List[Dict[str, Any]] = Field(default_factory=list)
    autonomy: Dict[str, Any] = Field(default_factory=dict)
    event_cursor: int = 0
    messages: List[Dict[str, Any]] = Field(default_factory=list)
    evidence: List[Dict[str, Any]] = Field(default_factory=list)


class ProposalDecisionRequest(AppBaseModel):
    """Seller decision on a proposal (17 §5)."""
    decision: str  # "approve", "decline", "manual_review"
    payload_hash: str


class ProposalDecisionResponse(AppBaseModel):
    """Result of seller proposal decision (17 §5)."""
    action_id: str
    status: str


class UpdateAutonomyRequest(AppBaseModel):
    """Update autonomy configuration payload (17 §5)."""
    levels: Dict[CaseType, AutonomyLevel]
    per_order_cap_minor: int
    per_customer_daily_cap_minor: int


class CourierEventRequest(AppBaseModel):
    """Operator mock courier event payload (17 §5)."""
    shipment_id: str
    type: CourierEventType
    attempt_no: int = 1
    reason: Optional[str] = None
