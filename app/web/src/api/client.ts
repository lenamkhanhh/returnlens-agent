import {
  CaseDetail,
  SellerCaseSummary,
  AuditEvent,
  CreateCaseResponse,
  Evidence,
  ProposalDecisionResponse,
  Customer,
  Order,
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
    const userMessage = errBody?.user_message || errBody?.message || res.statusText;
    throw new ApiError(res.status, userMessage, code, userMessage);
  }

  return (await res.json()) as T;
}

export const api = {
  async getCustomers(): Promise<Customer[]> {
    if (USE_DEVMOCK) {
      return devMockService.getCustomers();
    }
    return request<Customer[]>('/api/demo/customers');
  },

  async getOrders(customerId?: string): Promise<Order[]> {
    if (USE_DEVMOCK) {
      return devMockService.getOrders(customerId);
    }
    const url = customerId ? `/api/orders?customer_id=${encodeURIComponent(customerId)}` : '/api/orders';
    return request<Order[]>(url);
  },

  async getSellerCases(): Promise<SellerCaseSummary[]> {
    if (USE_DEVMOCK) {
      return devMockService.getSellerCases();
    }
    return request<SellerCaseSummary[]>('/api/seller/cases');
  },

  async getCase(caseId: string): Promise<CaseDetail> {
    if (USE_DEVMOCK) {
      return devMockService.getCase(caseId);
    }
    return request<CaseDetail>(`/api/cases/${encodeURIComponent(caseId)}`);
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

    return (await res.json()) as Evidence;
  },

  async getEvents(caseId: string, afterSeq = 0): Promise<AuditEvent[]> {
    if (USE_DEVMOCK) {
      return devMockService.getEvents(caseId, afterSeq);
    }
    return request<AuditEvent[]>(`/api/cases/${encodeURIComponent(caseId)}/events?after_seq=${afterSeq}`);
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
};
