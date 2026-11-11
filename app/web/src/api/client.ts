import {
  CaseDetail,
  SellerCaseSummary,
  AuditEvent,
  CreateCaseResponse,
  Evidence,
  ProposalDecisionResponse,
  Customer,
  Order,
  AutonomyPolicy,
  AutonomyExplanation,
  CourierEventRequest,
  Message,
} from '../types';
import { devMockService } from '../devmock';
import { evaluateBreakItTest, BreakItResult } from '../utils/breakItPresets';

let devmockOverride: boolean | null = null;

export function setDevmockOverride(override: boolean | null): void {
  devmockOverride = override;
}

export function isDevmockEnabled(): boolean {
  if (devmockOverride !== null) {
    return devmockOverride;
  }
  return !import.meta.env.PROD && import.meta.env.VITE_DEVMOCK === '1';
}

export class ApiError extends Error {
  status: number;
  code?: string;
  userMessage?: string;

  constructor(status: number, message: string, code?: string, userMessage?: string) {
    super(message);
    this.name = 'ApiError';
    this.status = status;
    this.code = code;
    this.userMessage = userMessage;
  }
}

async function request<T>(url: string, options?: RequestInit): Promise<T> {
  const res = await fetch(url, {
    ...options,
    headers: {
      'Content-Type': 'application/json',
      Accept: 'application/json',
      ...options?.headers,
    },
  });

  if (!res.ok) {
    let errBody: any = null;
    try {
      errBody = await res.json();
    } catch {
      // not JSON
    }
    let code = errBody?.code;
    let userMessage = errBody?.user_message || errBody?.detail || errBody?.message || res.statusText;
    if (errBody?.detail && typeof errBody.detail === 'object') {
      code = code || errBody.detail.code;
      userMessage = errBody.detail.user_message || errBody.detail.message || userMessage;
    }
    throw new ApiError(res.status, userMessage, code, userMessage);
  }

  return (await res.json()) as T;
}

function normalizeShippingStatus(rawStatus?: string): string {
  if (!rawStatus) return 'In transit';
  const upper = rawStatus.toUpperCase();
  if (upper === 'IN_TRANSIT') return 'In transit';
  if (upper === 'DELIVERED') return 'Delivered';
  if (upper.includes('NDR')) return rawStatus;
  return rawStatus;
}

const CANONICAL_CUSTOMERS: Customer[] = [
  { customer_id: 'CUS-01', name: 'Priya Sharma', language: 'English', city_pin: 'Bengaluru 560034', phone: '+91 90000 00001' },
  { customer_id: 'CUS-02', name: 'Arjun Mehta', language: 'Hindi', city_pin: 'Mumbai 400001', phone: '+91 90000 00002' },
  { customer_id: 'CUS-03', name: 'Sneha Iyer', language: 'English', city_pin: 'Delhi 110001', phone: '+91 90000 00003' },
  { customer_id: 'CUS-04', name: 'Rahul Verma', language: 'Hinglish', city_pin: 'Bengaluru 560001', phone: '+91 90000 00004' },
  { customer_id: 'CUS-05', name: 'Vikram Malhotra', language: 'English', city_pin: 'Pune 411001', phone: '+91 90000 00005' },
];

export const api = {
  async getCustomers(): Promise<Customer[]> {
    if (isDevmockEnabled()) {
      return devMockService.getCustomers();
    }
    return CANONICAL_CUSTOMERS;
  },

  async getOrders(customerId?: string): Promise<Order[]> {
    if (isDevmockEnabled()) {
      return devMockService.getOrders(customerId);
    }
    const url = customerId ? `/api/orders?customer_id=${encodeURIComponent(customerId)}` : '/api/orders';
    const rawOrders = await request<any[]>(url);

    // Enrich orders with actual shipment details from /api/orders/{order_id}
    const enriched = await Promise.all(
      rawOrders.map(async (o) => {
        try {
          const detail = await request<any>(`/api/orders/${encodeURIComponent(o.order_id)}`);
          const shp = detail.shipment;
          return {
            order_id: o.order_id,
            customer_id: o.customer_id,
            sku: o.line_item?.sku || o.sku,
            item_name: o.line_item?.display_name || o.item_name || o.sku,
            catalog_color: o.line_item?.catalog_color || o.catalog_color || 'unknown',
            paid_minor: o.paid_minor,
            currency: o.currency || 'INR',
            payment_method: o.payment_method || 'Prepaid',
            shipping_status: normalizeShippingStatus(shp?.status || o.shipping_status),
            delivered_date: shp?.delivered_at || o.delivered_date,
            eta_days_relative: shp?.eta ? shp.eta : o.eta_days_relative,
            scenario_tag: o.scenario_tag || (shp?.status === 'IN_TRANSIT' ? 'WISMO + counterfactual' : 'Standard order'),
            line_item: o.line_item,
          };
        } catch {
          return {
            order_id: o.order_id,
            customer_id: o.customer_id,
            sku: o.line_item?.sku || o.sku,
            item_name: o.line_item?.display_name || o.item_name || o.sku,
            catalog_color: o.line_item?.catalog_color || o.catalog_color || 'unknown',
            paid_minor: o.paid_minor,
            currency: o.currency || 'INR',
            payment_method: o.payment_method || 'Prepaid',
            shipping_status: normalizeShippingStatus(o.shipping_status),
            delivered_date: o.delivered_date,
            eta_days_relative: o.eta_days_relative,
            scenario_tag: o.scenario_tag || 'Standard order',
            line_item: o.line_item,
          };
        }
      })
    );
    return enriched;
  },

  async getSellerCases(): Promise<SellerCaseSummary[]> {
    if (isDevmockEnabled()) {
      return devMockService.getSellerCases();
    }
    const rawCases = await request<any[]>('/api/seller/cases');
    return rawCases.map((c) => ({
      case_id: c.case_id,
      order_id: c.order_id,
      customer_name: c.customer_name || c.customer_id || 'Customer',
      case_type: c.case_type,
      state: c.state,
      pending_amount_minor: c.pending_amount_minor || 0,
      currency: c.currency || 'INR',
      last_updated: c.updated_at || new Date().toISOString(),
      summary: c.summary || `${c.case_type} inquiry`,
    }));
  },

  async getCase(caseId: string): Promise<CaseDetail> {
    if (isDevmockEnabled()) {
      return devMockService.getCase(caseId);
    }
    const snap = await request<any>(`/api/cases/${encodeURIComponent(caseId)}`);
    let messages: Message[] = snap.messages || [];

    // 1. If snapshot has no messages, check /api/cases/{caseId}/messages
    if (messages.length === 0) {
      try {
        const rawMsgs = await request<any[]>(`/api/cases/${encodeURIComponent(caseId)}/messages`);
        if (Array.isArray(rawMsgs) && rawMsgs.length > 0) {
          messages = rawMsgs.map((m) => ({
            message_id: m.message_id || `msg-${Math.random().toString(16).slice(2, 8)}`,
            case_id: caseId,
            role: (m.role?.value || m.role || 'agent').toLowerCase(),
            text: m.text,
            attachment_ids: m.attachment_ids || [],
            created_at: m.created_at || new Date().toISOString(),
          }));
        }
      } catch {
        // Optional endpoint
      }
    }

    // 2. Load audit events for event timeline and extract real observations if snap.observations is empty
    let events: AuditEvent[] = [];
    try {
      events = await this.getEvents(caseId);
    } catch (e) {
      console.warn('Failed to load events for case:', e);
    }

    if (messages.length === 0 && events.length > 0) {
      for (const ev of events) {
        if (ev.event_type === 'message_received' && ev.safe_payload?.text) {
          messages.push({
            message_id: ev.event_id || `msg-in-${ev.seq}`,
            case_id: caseId,
            role: 'customer',
            text: ev.safe_payload.text,
            attachment_ids: ev.safe_payload.attachment_ids || [],
            created_at: ev.recorded_at,
          });
        } else if (ev.event_type === 'customer_reply_delivered' && (ev.safe_payload?.reply || ev.outcome)) {
          messages.push({
            message_id: ev.event_id || `msg-out-${ev.seq}`,
            case_id: caseId,
            role: 'agent',
            text: ev.safe_payload?.reply || ev.outcome,
            created_at: ev.recorded_at,
          });
        } else if (ev.event_type === 'clarification_sent' && (ev.safe_payload?.template || ev.outcome)) {
          messages.push({
            message_id: ev.event_id || `msg-clarify-${ev.seq}`,
            case_id: caseId,
            role: 'agent',
            text: ev.safe_payload?.template || ev.outcome,
            created_at: ev.recorded_at,
          });
        } else if (ev.event_type === 'handoff_created') {
          messages.push({
            message_id: ev.event_id || `msg-handoff-${ev.seq}`,
            case_id: caseId,
            role: 'agent',
            text: ev.safe_payload?.summary || ev.outcome || 'Case handed off to merchant support.',
            created_at: ev.recorded_at,
          });
        }
      }
    }

    let observations = snap.observations || [];
    let unknowns = snap.unknowns || [];

    // Extract real grounded observations from audit events if not in snapshot
    if (observations.length === 0 && events.length > 0) {
      for (const ev of events) {
        if (ev.event_type === 'observation_validated' && ev.safe_payload?.observations) {
          observations = ev.safe_payload.observations;
          if (ev.safe_payload.unknowns) {
            unknowns = ev.safe_payload.unknowns;
          }
        }
      }
    }

    const evidence = (snap.evidence || []).map((e: any) => {
      let language_detected = e.language_detected;
      let transcript = e.transcript;
      if (e.media_type === 'audio') {
        for (const ev of events) {
          const isTranscriber =
            ev.event_type === 'voice_note_transcribed' ||
            ev.actor === 'model:transcriber' ||
            (ev.event_type === 'observation_validated' && ev.safe_payload?.language);
          const refs = ev.refs || [];
          const matchesRef = refs.length === 0 || refs.some((r: string) => r.includes(e.evidence_id));
          if (isTranscriber && matchesRef) {
            if (!language_detected && ev.safe_payload?.language) {
              language_detected = ev.safe_payload.language;
            }
            if (!transcript && ev.safe_payload?.transcript) {
              transcript = ev.safe_payload.transcript;
            }
          }
        }
      }
      return {
        ...e,
        language_detected: language_detected || (e.media_type === 'audio' ? 'en' : undefined),
        transcript: transcript || e.transcript,
        url: e.evidence_id ? `/api/media/${e.evidence_id}` : e.url,
      };
    });

    return {
      ...snap,
      messages,
      evidence,
      observations,
      unknowns,
      policy_checks: snap.policy_checks || [],
      proposals: snap.proposals || [],
    } as CaseDetail;
  },

  async createCase(orderId: string, initialMessage: string, clientMessageId?: string): Promise<CreateCaseResponse> {
    if (isDevmockEnabled()) {
      return devMockService.createCase(orderId, initialMessage, clientMessageId);
    }
    return request<CreateCaseResponse>('/api/cases', {
      method: 'POST',
      body: JSON.stringify({
        order_id: orderId,
        initial_message: initialMessage,
        client_message_id: clientMessageId || `c-${Math.random().toString(16).slice(2, 8)}`,
      }),
    });
  },

  async sendMessage(caseId: string, text: string, attachmentIds: string[] = []): Promise<void> {
    if (isDevmockEnabled()) {
      return devMockService.sendMessage(caseId, text, attachmentIds);
    }
    await request(`/api/cases/${encodeURIComponent(caseId)}/messages`, {
      method: 'POST',
      body: JSON.stringify({
        text,
        attachment_ids: attachmentIds,
        client_message_id: `c-${Math.random().toString(16).slice(2, 8)}`,
      }),
    });
  },

  async uploadEvidence(caseId: string, file: File, clientUploadId?: string): Promise<Evidence> {
    if (isDevmockEnabled()) {
      return devMockService.uploadEvidence(caseId, file, clientUploadId);
    }
    const formData = new FormData();
    formData.append('file', file);
    if (clientUploadId) formData.append('client_upload_id', clientUploadId);

    const res = await fetch(`/api/cases/${encodeURIComponent(caseId)}/evidence`, {
      method: 'POST',
      body: formData,
    });

    if (!res.ok) {
      let errBody: any = null;
      try {
        errBody = await res.json();
      } catch {
        // ignore
      }
      throw new ApiError(res.status, errBody?.user_message || 'Evidence upload failed', errBody?.code);
    }

    const data = (await res.json()) as Evidence;
    return {
      ...data,
      url: data.evidence_id ? `/api/media/${data.evidence_id}` : data.url,
    };
  },

  async getEvents(caseId: string, afterSeq = 0): Promise<AuditEvent[]> {
    if (isDevmockEnabled()) {
      return devMockService.getEvents(caseId, afterSeq);
    }
    return await request<AuditEvent[]>(`/api/cases/${encodeURIComponent(caseId)}/events?after_seq=${afterSeq}`);
  },

  async decideProposal(
    proposalId: string,
    decision: 'approve' | 'decline' | 'manual_review',
    payloadHash: string,
    idempotencyKey?: string
  ): Promise<ProposalDecisionResponse> {
    const key = idempotencyKey || `d-${Math.random().toString(16).slice(2, 8)}`;
    if (isDevmockEnabled()) {
      return devMockService.decideProposal(proposalId, decision, payloadHash, key);
    }
    return request<ProposalDecisionResponse>(`/api/proposals/${encodeURIComponent(proposalId)}/decisions`, {
      method: 'POST',
      headers: {
        'Idempotency-Key': key,
      },
      body: JSON.stringify({
        decision,
        payload_hash: payloadHash,
      }),
    });
  },

  // =========================================================================
  // Wave 2 & Wave 3 Methods
  // =========================================================================

  async getAutonomyPolicy(): Promise<AutonomyPolicy> {
    if (isDevmockEnabled()) {
      return devMockService.getAutonomyPolicy();
    }
    const res = await request<any>('/api/seller/autonomy');
    return {
      store_id: res.store_id,
      version: res.version,
      agent_version: res.agent_version,
      model_id: res.model_id,
      levels: res.levels,
      per_order_cap_minor: res.per_order_cap_minor,
      per_customer_daily_cap_minor: res.per_customer_daily_cap_minor,
      kill_switch: res.kill_switch,
      changed_by: res.changed_by,
      changed_at: res.changed_at,
      lock_status: res.lock_status,
    };
  },

  async updateAutonomyPolicy(policy: Partial<AutonomyPolicy>): Promise<AutonomyPolicy> {
    if (isDevmockEnabled()) {
      return devMockService.updateAutonomyPolicy(policy);
    }
    await request<any>('/api/seller/autonomy', {
      method: 'PUT',
      body: JSON.stringify((({ lock_status: _ls, ...rest }) => rest)(policy)),
    });
    return this.getAutonomyPolicy();
  },

  async killAutonomy(reason = 'Seller kill switch'): Promise<void> {
    if (isDevmockEnabled()) {
      return devMockService.killAutonomy(reason);
    }
    await request('/api/seller/autonomy/kill', {
      method: 'POST',
      body: JSON.stringify({ reason }),
    });
  },

  async getAutonomyExplanation(caseId: string): Promise<AutonomyExplanation> {
    if (isDevmockEnabled()) {
      return devMockService.getAutonomyExplanation(caseId);
    }
    const res = await request<any>(`/api/seller/autonomy/why/${encodeURIComponent(caseId)}`);
    const checks = (res.checklist || res.checks || []).map((item: any) => ({
      step: item.step_no || item.step,
      title: item.title,
      passed: item.passed,
      detail: item.details || item.detail,
    }));
    return {
      case_id: caseId,
      case_type: res.case_type || 'MISMATCH',
      action_type: res.action_type || 'PROPOSE_RETURN',
      decision: res.decision,
      reason_code: res.reason_code,
      checks,
    };
  },

  async fireCourierEvent(req: CourierEventRequest): Promise<{ status: string; event_id: string }> {
    if (isDevmockEnabled()) {
      return devMockService.fireCourierEvent(req);
    }
    return await request('/api/operator/courier-events', {
      method: 'POST',
      body: JSON.stringify(req),
    });
  },

  async changeTracking(orderId: string, status: string, deliveredDate?: string): Promise<void> {
    if (isDevmockEnabled()) {
      return devMockService.changeTracking(orderId, status, deliveredDate);
    }
    await request('/api/operator/tracking', {
      method: 'POST',
      body: JSON.stringify({ order_id: orderId, status, delivered_date: deliveredDate }),
    });
  },

  async resetDemo(): Promise<void> {
    if (isDevmockEnabled()) {
      devMockService.resetDemo();
      return;
    }
    await request('/api/operator/reset', { method: 'POST' });
  },

  async executeBreakItTest(presetId: string, customText?: string): Promise<BreakItResult> {
    if (isDevmockEnabled()) {
      return devMockService.executeBreakItTest(presetId, customText);
    }
    return evaluateBreakItTest(presetId, customText);
  },
};
