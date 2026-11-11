export type CaseType = 'WISMO' | 'DAMAGE' | 'MISMATCH' | 'UNCLEAR' | 'LATE' | 'NDR';

export type CaseState =
  | 'NEW'
  | 'PROCESSING'
  | 'WAITING_CUSTOMER'
  | 'WAITING_SELLER'
  | 'ACTION_PENDING'
  | 'WAITING_RETURN'
  | 'HUMAN_REVIEW'
  | 'RECONCILIATION'
  | 'RESOLVED';

export type CustomerFacingStatus =
  | 'new conversation'
  | 'sending'
  | 'processing'
  | 'waiting for you'
  | 'waiting for seller'
  | 'done'
  | 'error';

export type NextStep =
  | 'SEND_STATUS'
  | 'REQUEST_EVIDENCE'
  | 'PROPOSE_RETURN'
  | 'PROPOSE_REFUND'
  | 'PROPOSE_NDR_REATTEMPT'
  | 'HANDOFF';

export type AutonomyLevel = 'L0' | 'L1' | 'L2' | 'L3';

export type AutonomyDecision = 'AUTO' | 'DEFER_TO_SELLER' | 'BLOCK';

export type ColorClass = 'white' | 'black' | 'grey' | 'other' | 'unknown';

export type Visibility = 'visible' | 'unclear' | 'not_observed';

export type ObservationAttribute = 'color' | 'damage' | 'label_text' | 'item_type' | 'other';

export type PolicyCheckResult = 'PASS' | 'FAIL' | 'UNKNOWN';

export interface Customer {
  customer_id: string;
  name: string;
  language: string;
  city_pin: string;
  phone: string;
}

export interface LineItem {
  item_id: string;
  sku: string;
  catalog_color: ColorClass | string;
  display_name: string;
  quantity: number;
  refundable_item_minor: number;
}

export interface Order {
  order_id: string;
  customer_id: string;
  sku: string;
  item_name: string;
  catalog_color: string;
  paid_minor: number; // Integer paise (e.g. 149900 = ₹1,499)
  currency: 'INR' | string;
  payment_method: 'Prepaid' | 'COD' | string;
  shipping_status: 'Delivered' | 'In transit' | 'NDR attempt 1' | string;
  delivered_date?: string; // YYYY-MM-DD
  eta_days_relative?: number; // e.g. +2
  scenario_tag: string;
  line_item?: LineItem;
}

export interface Message {
  message_id: string;
  client_message_id?: string;
  case_id: string;
  role: 'customer' | 'agent' | 'seller';
  text: string;
  attachment_ids?: string[];
  created_at: string;
}

export interface Evidence {
  evidence_id: string;
  case_id: string;
  media_type: 'video' | 'image' | 'audio';
  url: string;
  filename: string;
  duration_s?: number;
  transcript?: string;
  language_detected?: string;
  created_at: string;
}

export interface Observation {
  id: string;
  evidence_id: string;
  t: string | null; // "MM:SS" for video or null for photo
  attribute: ObservationAttribute | string;
  value: string;
  color_class?: ColorClass;
  visibility: Visibility;
  limitation?: string | null;
}

export interface PolicyCheck {
  rule_id: string;
  result: PolicyCheckResult;
  reason_code: string;
  source_refs?: string[];
}

export interface PlanRecord {
  goal: string;
  tools: string[];
  outcome: string;
  memory_used?: string[];
}

export interface Proposal {
  proposal_id: string;
  case_id: string;
  action_type: NextStep | string;
  payload_hash: string;
  item_id?: string;
  amount_minor?: number;
  currency?: string;
  reply_preview: string;
  status: 'pending' | 'approved' | 'declined' | 'stale';
}

export interface AutonomyInfo {
  case_type_level: string; // e.g. "L1", "L0"
  locked_reason: string | null;
  kill_switch?: boolean;
  per_order_cap_minor?: number;
  per_customer_daily_cap_minor?: number;
}

export interface AutonomyPolicy {
  store_id: string;
  version: string;
  levels: Record<CaseType, AutonomyLevel>;
  per_order_cap_minor: number;
  per_customer_daily_cap_minor: number;
  kill_switch: boolean;
  changed_by?: string;
  changed_at?: string;
}

export interface AutonomyStepCheck {
  step: number;
  title: string;
  passed: boolean;
  detail: string;
}

export interface AutonomyExplanation {
  case_id: string;
  case_type: CaseType;
  action_type: string;
  decision: AutonomyDecision;
  reason_code: string;
  checks: AutonomyStepCheck[];
}

export interface CaseDetail {
  case_id: string;
  order_id: string;
  customer_id: string;
  case_type: CaseType;
  state: CaseState;
  facts: {
    order: {
      order_id: string;
      sku: string;
      catalog_color: string;
      item_name?: string;
      paid_minor: number;
      currency: string;
      customer_name?: string;
    };
    shipment: {
      status: string;
      delivered_date?: string;
      carrier_label?: string;
      tracking_number?: string;
      attempt_no?: number;
      failure_reason?: string;
    };
  };
  messages: Message[];
  evidence: Evidence[];
  observations: Observation[];
  unknowns: string[];
  policy_checks: PolicyCheck[];
  plan: PlanRecord | null;
  clarification_count: number;
  proposals: Proposal[];
  autonomy?: AutonomyInfo;
  event_cursor: number;
}

export interface SellerCaseSummary {
  case_id: string;
  order_id: string;
  customer_name: string;
  case_type: CaseType;
  state: CaseState;
  pending_amount_minor: number;
  currency: string;
  last_updated: string;
  summary: string;
}

export interface AuditEvent {
  event_id: string;
  seq: number;
  event_type: string;
  actor: string;
  outcome: string;
  safe_payload: Record<string, any>;
  recorded_at: string;
}

export interface CreateCaseResponse {
  case_id: string;
  accepted_revision: number;
  job_id: string;
}

export interface ProposalDecisionResponse {
  action_id?: string;
  status?: string;
  code?: string;
  user_message?: string;
}

export interface CourierEventRequest {
  shipment_id: string;
  type: 'NDR' | 'RETURN_RECEIVED' | 'DELAYED';
  attempt_no: number;
  reason?: string;
}

export interface BreakItPreset {
  id: string;
  title: string;
  description: string;
  attackVector: string;
  expectedResult: string;
}
