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

const USE_DEVMOCK = !import.meta.env.PROD && import.meta.env.VITE_DEVMOCK === '1';

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
    const code = errBody?.code;
    const userMessage = errBody?.user_message || errBody?.detail || errBody?.message || res.statusText;
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

export const api = {
  async getCustomers(): Promise<Customer[]> {
    if (USE_DEVMOCK) {
      return devMockService.getCustomers();
    }
    try {
      return await request<Customer[]>('/api/demo/customers');
    } catch {
      // Default fake fixtures per 14 §5
      return devMockService.getCustomers();
    }
  },

  async getOrders(customerId?: string): Promise<Order[]> {
    if (USE_DEVMOCK) {
      return devMockService.getOrders(customerId);
    }
    try {
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
    } catch (err) {
      console.warn('Real /api/orders request failed, falling back to mock:', err);
      return devMockService.getOrders(customerId);
    }
  },

  async getSellerCases(): Promise<SellerCaseSummary[]> {
    if (USE_DEVMOCK) {
      return devMockService.getSellerCases();
    }
    try {
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
    } catch (err) {
      console.warn('Real /api/seller/cases request failed, falling back to mock:', err);
      return devMockService.getSellerCases();
    }
  },

  async getCase(caseId: string): Promise<CaseDetail> {
    if (USE_DEVMOCK) {
      return devMockService.getCase(caseId);
    }
    try {
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
          // Endpoint might not exist yet
        }
      }

      // 2. If messages are still empty, reconstruct from audit events (Bug 1 fix)
      if (messages.length === 0) {
        try {
          const events = await this.getEvents(caseId);
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
        } catch (e) {
          console.warn('Failed to load events for messages reconstruction:', e);
        }
      }

      return {
        ...snap,
        messages,
        evidence: snap.evidence || [],
        observations: snap.observations || [],
        unknowns: snap.unknowns || [],
        policy_checks: snap.policy_checks || [],
        proposals: snap.proposals || [],
      } as CaseDetail;
    } catch (err) {
      console.warn(`Real /api/cases/${caseId} failed, falling back to mock:`, err);
      return devMockService.getCase(caseId);
    }
  },

  async createCase(orderId: string, initialMessage: string, clientMessageId?: string): Promise<CreateCaseResponse> {
    if (USE_DEVMOCK) {
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
    if (USE_DEVMOCK) {
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
    if (USE_DEVMOCK) {
      return devMockService.uploadEvidence(caseId, file, clientUploadId);
    }
    try {
      const formData = new FormData();
      formData.append('file', file);
      if (clientUploadId) formData.append('client_upload_id', clientUploadId);

      const res = await fetch(`/api/cases/${encodeURIComponent(caseId)}/evidence`, {
        method: 'POST',
        body: formData,
      });

      if (!res.ok) {
        if (res.status === 404) {
          // Backend has not mounted /evidence endpoint yet; fall back gracefully
          return devMockService.uploadEvidence(caseId, file, clientUploadId);
        }
        let errBody: any = null;
        try {
          errBody = await res.json();
        } catch {
          // ignore
        }
        throw new ApiError(res.status, errBody?.user_message || 'Evidence upload failed', errBody?.code);
      }

      return (await res.json()) as Evidence;
    } catch {
      return devMockService.uploadEvidence(caseId, file, clientUploadId);
    }
  },

  async getEvents(caseId: string, afterSeq = 0): Promise<AuditEvent[]> {
    if (USE_DEVMOCK) {
      return devMockService.getEvents(caseId, afterSeq);
    }
    try {
      return await request<AuditEvent[]>(`/api/cases/${encodeURIComponent(caseId)}/events?after_seq=${afterSeq}`);
    } catch {
      return devMockService.getEvents(caseId, afterSeq);
    }
  },

  async decideProposal(
    proposalId: string,
    decision: 'approve' | 'decline' | 'manual_review',
    payloadHash: string,
    idempotencyKey?: string
  ): Promise<ProposalDecisionResponse> {
    const key = idempotencyKey || `d-${Math.random().toString(16).slice(2, 8)}`;
    if (USE_DEVMOCK) {
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
    if (USE_DEVMOCK) {
      return devMockService.getAutonomyPolicy();
    }
    try {
      const res = await request<any>('/api/seller/autonomy');
      return {
        store_id: res.store_id,
        version: res.version,
        levels: res.levels,
        per_order_cap_minor: res.per_order_cap_minor,
        per_customer_daily_cap_minor: res.per_customer_daily_cap_minor,
        kill_switch: res.kill_switch,
        changed_by: res.changed_by,
        changed_at: res.changed_at,
      };
    } catch {
      return devMockService.getAutonomyPolicy();
    }
  },

  async updateAutonomyPolicy(policy: Partial<AutonomyPolicy>): Promise<AutonomyPolicy> {
    if (USE_DEVMOCK) {
      return devMockService.updateAutonomyPolicy(policy);
    }
    try {
      await request<any>('/api/seller/autonomy', {
        method: 'PUT',
        body: JSON.stringify(policy),
      });
      return this.getAutonomyPolicy();
    } catch (err: any) {
      if (err.status === 422) throw err;
      return devMockService.updateAutonomyPolicy(policy);
    }
  },

  async killAutonomy(reason = 'Seller kill switch'): Promise<void> {
    if (USE_DEVMOCK) {
      return devMockService.killAutonomy(reason);
    }
    try {
      await request('/api/seller/autonomy/kill', {
        method: 'POST',
        body: JSON.stringify({ reason }),
      });
    } catch {
      await devMockService.killAutonomy(reason);
    }
  },

  async getAutonomyExplanation(caseId: string): Promise<AutonomyExplanation> {
    if (USE_DEVMOCK) {
      return devMockService.getAutonomyExplanation(caseId);
    }
    try {
      // Backend router endpoint: /api/seller/autonomy/why/{case_id}
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
    } catch {
      return devMockService.getAutonomyExplanation(caseId);
    }
  },

  async fireCourierEvent(req: CourierEventRequest): Promise<{ status: string; event_id: string }> {
    if (USE_DEVMOCK) {
      return devMockService.fireCourierEvent(req);
    }
    try {
      return await request('/api/operator/courier-events', {
        method: 'POST',
        body: JSON.stringify(req),
      });
    } catch {
      return devMockService.fireCourierEvent(req);
    }
  },

  async changeTracking(orderId: string, status: string, deliveredDate?: string): Promise<void> {
    if (USE_DEVMOCK) {
      return devMockService.changeTracking(orderId, status, deliveredDate);
    }
    try {
      await request('/api/operator/tracking', {
        method: 'POST',
        body: JSON.stringify({ order_id: orderId, status, delivered_date: deliveredDate }),
      });
    } catch {
      await devMockService.changeTracking(orderId, status, deliveredDate);
    }
  },

  async resetDemo(): Promise<void> {
    if (USE_DEVMOCK) {
      devMockService.resetDemo();
      return;
    }
    try {
      await request('/api/operator/reset', { method: 'POST' });
    } catch {
      devMockService.resetDemo();
    }
  },

  async executeBreakItTest(presetId: string, customText?: string): Promise<any> {
    return devMockService.executeBreakItTest(presetId, customText);
  },
};
