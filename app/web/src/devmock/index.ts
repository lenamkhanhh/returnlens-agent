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
import { FAKE_CUSTOMERS, FAKE_ORDERS, INITIAL_DEV_CASES, INITIAL_DEV_EVENTS } from './fixtureData';

class DevMockService {
  private cases: Map<string, CaseDetail> = new Map();
  private events: Map<string, AuditEvent[]> = new Map();
  private counter: number = 20;

  constructor() {
    // Clone initial fixtures
    for (const [id, c] of Object.entries(INITIAL_DEV_CASES)) {
      this.cases.set(id, JSON.parse(JSON.stringify(c)));
    }
    for (const [id, evts] of Object.entries(INITIAL_DEV_EVENTS)) {
      this.events.set(id, JSON.parse(JSON.stringify(evts)));
    }
  }

  async getCustomers(): Promise<Customer[]> {
    return FAKE_CUSTOMERS;
  }

  async getOrders(customerId?: string): Promise<Order[]> {
    if (!customerId) return FAKE_ORDERS;
    return FAKE_ORDERS.filter((o) => o.customer_id === customerId);
  }

  async getSellerCases(): Promise<SellerCaseSummary[]> {
    const list: SellerCaseSummary[] = [];
    for (const c of this.cases.values()) {
      let pendingAmount = 0;
      for (const p of c.proposals) {
        if (p.status === 'pending' && p.amount_minor) {
          pendingAmount += p.amount_minor;
        }
      }
      list.push({
        case_id: c.case_id,
        order_id: c.order_id,
        customer_name: c.facts.order.customer_name || 'Customer',
        case_type: c.case_type,
        state: c.state,
        pending_amount_minor: pendingAmount || c.facts.order.paid_minor,
        currency: 'INR',
        last_updated: c.messages[c.messages.length - 1]?.created_at || new Date().toISOString(),
        summary: c.plan?.goal || c.messages[0]?.text || 'Customer inquiry',
      });
    }
    return list;
  }

  async getCase(caseId: string): Promise<CaseDetail> {
    const c = this.cases.get(caseId);
    if (!c) {
      throw new Error(`Case ${caseId} not found`);
    }
    return JSON.parse(JSON.stringify(c));
  }

  async getEvents(caseId: string, afterSeq = 0): Promise<AuditEvent[]> {
    const evts = this.events.get(caseId) || [];
    return evts.filter((e) => e.seq > afterSeq);
  }

  async createCase(orderId: string, initialMessage: string, clientMessageId?: string): Promise<CreateCaseResponse> {
    this.counter += 1;
    const caseId = `CASE-00${this.counter}`;
    const jobId = `JOB-00${this.counter + 10}`;
    const order = FAKE_ORDERS.find((o) => o.order_id === orderId) || FAKE_ORDERS[0];
    const customer = FAKE_CUSTOMERS.find((c) => c.customer_id === order.customer_id) || FAKE_CUSTOMERS[0];

    // Determine CaseType
    let caseType = 'MISMATCH' as any;
    if (order.shipping_status === 'In transit') caseType = 'WISMO';
    else if (order.shipping_status.includes('NDR')) caseType = 'NDR';
    else if (initialMessage.toLowerCase().includes('crack') || initialMessage.toLowerCase().includes('damage')) {
      caseType = 'DAMAGE';
    }

    const newCase: CaseDetail = {
      case_id: caseId,
      order_id: order.order_id,
      customer_id: customer.customer_id,
      case_type: caseType,
      state: 'PROCESSING', // Starts in processing
      facts: {
        order: {
          order_id: order.order_id,
          sku: order.sku,
          catalog_color: order.catalog_color,
          item_name: order.item_name,
          paid_minor: order.paid_minor,
          currency: order.currency,
          customer_name: customer.name,
        },
        shipment: {
          status: order.shipping_status,
          delivered_date: order.delivered_date,
          carrier_label: 'Bluedart Express',
          tracking_number: `TRK-${Math.floor(Math.random() * 899999 + 100000)}`,
        },
      },
      messages: [
        {
          message_id: `MSG-${Date.now()}-1`,
          client_message_id: clientMessageId,
          case_id: caseId,
          role: 'customer',
          text: initialMessage,
          created_at: new Date().toISOString(),
        },
      ],
      evidence: [],
      observations: [],
      unknowns: [],
      policy_checks: [
        { rule_id: 'P_WINDOW', result: 'PASS', reason_code: 'within_7_days' },
      ],
      plan: {
        goal: `Process ${caseType} claim for ${order.order_id}`,
        tools: ['get_order', 'get_tracking'],
        outcome: 'Analyzing customer request and verifying order facts',
        memory_used: [`preferred_language=${customer.language.toLowerCase().slice(0, 2)}`],
      },
      clarification_count: 0,
      proposals: [],
      event_cursor: 1,
    };

    const initialEvents: AuditEvent[] = [
      {
        event_id: `EVT-${Date.now()}-1`,
        seq: 1,
        event_type: 'tool_call_succeeded',
        actor: 'system',
        outcome: 'success',
        safe_payload: { tool: 'get_order', order_id: order.order_id },
        recorded_at: new Date().toISOString(),
      },
    ];

    this.cases.set(caseId, newCase);
    this.events.set(caseId, initialEvents);

    // Simulate async agent processing (transitions state after 2.5s)
    setTimeout(() => {
      const live = this.cases.get(caseId);
      if (!live) return;

      if (caseType === 'WISMO') {
        live.state = 'RESOLVED';
        live.messages.push({
          message_id: `MSG-${Date.now()}-2`,
          case_id: caseId,
          role: 'agent',
          text: `Your order ${order.order_id} (${order.item_name}) is currently in transit with Bluedart Express. Estimated delivery date is in ${order.eta_days_relative || 2} days.`,
          created_at: new Date().toISOString(),
        });
        const evts = this.events.get(caseId) || [];
        evts.push({
          event_id: `EVT-${Date.now()}-2`,
          seq: evts.length + 1,
          event_type: 'tool_call_succeeded',
          actor: 'system',
          outcome: 'success',
          safe_payload: { tool: 'get_tracking', status: 'IN_TRANSIT' },
          recorded_at: new Date().toISOString(),
        });
      } else {
        live.state = 'WAITING_SELLER';
        live.messages.push({
          message_id: `MSG-${Date.now()}-2`,
          case_id: caseId,
          role: 'agent',
          text: `We have reviewed your inquiry regarding ${order.item_name}. A return authorization proposal has been created and sent to the store seller for final approval.`,
          created_at: new Date().toISOString(),
        });

        const proposalId = `PRP-00${this.counter + 5}`;
        live.proposals.push({
          proposal_id: proposalId,
          case_id: caseId,
          action_type: 'PROPOSE_RETURN',
          payload_hash: 'hash_' + Date.now().toString(16),
          item_id: order.sku,
          amount_minor: order.paid_minor,
          currency: 'INR',
          reply_preview: `Your return request for order ${order.order_id} is approved. Pickup will be arranged.`,
          status: 'pending',
        });

        const evts = this.events.get(caseId) || [];
        evts.push({
          event_id: `EVT-${Date.now()}-3`,
          seq: evts.length + 1,
          event_type: 'proposal_created',
          actor: 'planner',
          outcome: 'success',
          safe_payload: { action_type: 'PROPOSE_RETURN', amount_minor: order.paid_minor },
          recorded_at: new Date().toISOString(),
        });
      }
    }, 2500);

    return {
      case_id: caseId,
      accepted_revision: 1,
      job_id: jobId,
    };
  }

  async sendMessage(caseId: string, text: string, attachmentIds: string[] = []): Promise<void> {
    const c = this.cases.get(caseId);
    if (!c) throw new Error(`Case ${caseId} not found`);

    c.messages.push({
      message_id: `MSG-${Date.now()}`,
      case_id: caseId,
      role: 'customer',
      text,
      attachment_ids: attachmentIds,
      created_at: new Date().toISOString(),
    });

    c.state = 'PROCESSING';

    setTimeout(() => {
      const live = this.cases.get(caseId);
      if (!live) return;
      live.state = 'WAITING_SELLER';
      live.messages.push({
        message_id: `MSG-${Date.now()}-reply`,
        case_id: caseId,
        role: 'agent',
        text: 'Thank you for the update. Our team has received your message and updated the case notes.',
        created_at: new Date().toISOString(),
      });
    }, 2000);
  }

  async uploadEvidence(caseId: string, file: File, _clientUploadId?: string): Promise<Evidence> {
    const c = this.cases.get(caseId);
    if (!c) throw new Error(`Case ${caseId} not found`);

    const evidenceId = `EVI-00${Date.now().toString().slice(-4)}`;
    const isVideo = file.type.startsWith('video');
    const isAudio = file.type.startsWith('audio');
    const mediaType = isVideo ? 'video' : isAudio ? 'audio' : 'image';
    const objectUrl = URL.createObjectURL(file);

    const newEvidence: Evidence = {
      evidence_id: evidenceId,
      case_id: caseId,
      media_type: mediaType,
      url: objectUrl,
      filename: file.name,
      duration_s: isVideo ? 15 : isAudio ? 8 : undefined,
      transcript: isAudio ? 'नमस्ते, मैंने सफ़ेद हेडफ़ोन ऑर्डर किए थे, लेकिन डिब्बे में काले हेडफ़ोन आए हैं। ऑर्डर ORD-7729.' : undefined,
      language_detected: isAudio ? 'Hindi' : undefined,
      created_at: new Date().toISOString(),
    };

    c.evidence.push(newEvidence);

    // If audio voice note, add observation and timeline
    if (isAudio) {
      c.observations.push({
        id: `OBS-${Date.now().toString().slice(-3)}`,
        evidence_id: evidenceId,
        t: null,
        attribute: 'color',
        value: 'customer states black received, ordered white',
        visibility: 'visible',
      });

      const evts = this.events.get(caseId) || [];
      evts.push({
        event_id: `EVT-${Date.now()}`,
        seq: evts.length + 1,
        event_type: 'voice_note_transcribed',
        actor: 'transcriber',
        outcome: 'success',
        safe_payload: { language: 'Hindi', transcript: newEvidence.transcript },
        recorded_at: new Date().toISOString(),
      });
    } else if (isVideo) {
      // Add video observation with timestamp
      c.observations.push({
        id: `OBS-${Date.now().toString().slice(-3)}`,
        evidence_id: evidenceId,
        t: '00:07',
        attribute: 'color',
        value: 'black headphones observed',
        color_class: 'black',
        visibility: 'visible',
      });

      const evts = this.events.get(caseId) || [];
      evts.push({
        event_id: `EVT-${Date.now()}`,
        seq: evts.length + 1,
        event_type: 'observation_validated',
        actor: 'observer',
        outcome: 'success',
        safe_payload: { attribute: 'color', value: 'black', t: '00:07' },
        recorded_at: new Date().toISOString(),
      });
    }

    return newEvidence;
  }

  async decideProposal(
    proposalId: string,
    decision: 'approve' | 'decline' | 'manual_review',
    payloadHash: string,
    idempotencyKey: string
  ): Promise<ProposalDecisionResponse> {
    // Find proposal across cases
    let foundCase: CaseDetail | null = null;
    let foundPropIndex = -1;

    for (const c of this.cases.values()) {
      const idx = c.proposals.findIndex((p) => p.proposal_id === proposalId);
      if (idx !== -1) {
        foundCase = c;
        foundPropIndex = idx;
        break;
      }
    }

    if (!foundCase || foundPropIndex === -1) {
      throw new Error(`Proposal ${proposalId} not found`);
    }

    const prop = foundCase.proposals[foundPropIndex];

    // Demo triggers for 422 Blocked
    if (prop.amount_minor && prop.amount_minor > foundCase.facts.order.paid_minor) {
      const err: any = new Error('Refund exceeds remaining refundable balance');
      err.status = 422;
      err.code = 'P_BALANCE';
      err.user_message = `Refund ₹${(prop.amount_minor / 100).toLocaleString('en-IN')} exceeds remaining refundable balance ₹${(foundCase.facts.order.paid_minor / 100).toLocaleString('en-IN')}.`;
      throw err;
    }

    // Demo trigger for 409 Stale (if hash is "stale" or begins with "stale")
    if (payloadHash === 'stale' || prop.payload_hash === 'stale') {
      const err: any = new Error('Proposal is stale');
      err.status = 409;
      err.code = 'stale_proposal';
      err.user_message = 'Proposal is stale. Order shipment or policy basis has changed since this proposal was created. Please refresh.';
      throw err;
    }

    if (decision === 'approve') {
      prop.status = 'approved';
      foundCase.state = prop.action_type === 'PROPOSE_RETURN' ? 'WAITING_RETURN' : 'RESOLVED';

      const evts = this.events.get(foundCase.case_id) || [];
      evts.push({
        event_id: `EVT-${Date.now()}`,
        seq: evts.length + 1,
        event_type: 'approval_recorded',
        actor: 'seller',
        outcome: 'approved',
        safe_payload: { proposal_id: proposalId, action_type: prop.action_type, idempotency_key: idempotencyKey },
        recorded_at: new Date().toISOString(),
      });

      return {
        action_id: `ACT-00${Math.floor(Math.random() * 8999 + 1000)}`,
        status: 'succeeded',
      };
    } else {
      prop.status = 'declined';
      foundCase.state = 'HUMAN_REVIEW';
      return {
        action_id: `ACT-00${Math.floor(Math.random() * 8999 + 1000)}`,
        status: 'declined',
      };
    }
  }
}

export const devMockService = new DevMockService();
