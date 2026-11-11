import { describe, it, expect } from 'vitest';
import { getHumanEventLabel } from '../utils/timelineLabels';
import { AuditEvent } from '../types';

describe('17 §7 Timeline Human Labels', () => {
  it('maps tool_call_succeeded for order and tracking', () => {
    const e1: AuditEvent = {
      event_id: '1',
      seq: 1,
      event_type: 'tool_call_succeeded',
      actor: 'system',
      outcome: 'success',
      safe_payload: { tool: 'get_order', order_id: 'ORD-7729' },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e1)).toBe('Checked order ORD-7729');

    const e2: AuditEvent = {
      event_id: '2',
      seq: 2,
      event_type: 'tool_call_succeeded',
      actor: 'system',
      outcome: 'success',
      safe_payload: { tool: 'get_tracking', tracking_number: 'BLU-8829' },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e2)).toBe('Checked tracking (BLU-8829)');
  });

  it('maps tool_call_blocked with remaining balance', () => {
    const e: AuditEvent = {
      event_id: '3',
      seq: 3,
      event_type: 'tool_call_blocked',
      actor: 'policy',
      outcome: 'blocked',
      safe_payload: { amount_minor: 149900 },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Blocked: refund exceeds remaining ₹1,499');
  });

  it('maps observation_validated with timestamp', () => {
    const e: AuditEvent = {
      event_id: '4',
      seq: 4,
      event_type: 'observation_validated',
      actor: 'observer',
      outcome: 'success',
      safe_payload: { color_class: 'black', t: '00:07' },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Saw black item at 00:07');
  });

  it('maps voice_note_transcribed with language', () => {
    const e: AuditEvent = {
      event_id: '5',
      seq: 5,
      event_type: 'voice_note_transcribed',
      actor: 'transcriber',
      outcome: 'success',
      safe_payload: { language: 'Hindi' },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Voice note transcribed (Hindi)');

    const eEn: AuditEvent = {
      event_id: '5b',
      seq: 5,
      event_type: 'voice_note_transcribed',
      actor: 'transcriber',
      outcome: 'success',
      safe_payload: { language: 'en' },
      recorded_at: '',
    };
    expect(getHumanEventLabel(eEn)).toBe('Voice note transcribed (English)');

    const eObs: AuditEvent = {
      event_id: '5c',
      seq: 5,
      event_type: 'observation_validated',
      actor: 'model:transcriber',
      outcome: 'Transcribed voice note: intent=RETURN',
      safe_payload: { language: 'en', intent: 'RETURN' },
      recorded_at: '',
    };
    expect(getHumanEventLabel(eObs)).toBe('Voice note transcribed (English)');
  });

  it('maps clarification_sent', () => {
    const e: AuditEvent = {
      event_id: '6',
      seq: 6,
      event_type: 'clarification_sent',
      actor: 'agent',
      outcome: 'sent',
      safe_payload: { count: 1 },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Asked for a close-up photo (1 of 1)');
  });

  it('maps proposal_created', () => {
    const e: AuditEvent = {
      event_id: '7',
      seq: 7,
      event_type: 'proposal_created',
      actor: 'planner',
      outcome: 'created',
      safe_payload: { action_type: 'REQUEST_EVIDENCE' },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Suggested: request box label');
  });

  it('maps approval_recorded for seller and autonomy policy', () => {
    const e1: AuditEvent = {
      event_id: '8',
      seq: 8,
      event_type: 'approval_recorded',
      actor: 'seller',
      outcome: 'approved',
      safe_payload: {},
      recorded_at: '',
    };
    expect(getHumanEventLabel(e1)).toBe('Seller approved');

    const e2: AuditEvent = {
      event_id: '9',
      seq: 9,
      event_type: 'approval_recorded',
      actor: 'policy:autonomy@1.0',
      outcome: 'approved',
      safe_payload: { level: 'L3' },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e2)).toBe('Auto-approved by autonomy policy L3');
  });

  it('maps autonomy_deferred_to_seller with cumulative limit', () => {
    const e: AuditEvent = {
      event_id: '10',
      seq: 10,
      event_type: 'autonomy_deferred_to_seller',
      actor: 'policy',
      outcome: 'deferred',
      safe_payload: { reason: 'cumulative_limit', limit_minor: 200000 },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Sent to seller: cumulative limit ₹2,000/day');
  });

  it('maps kill_switch_engaged', () => {
    const e: AuditEvent = {
      event_id: '11',
      seq: 11,
      event_type: 'kill_switch_engaged',
      actor: 'seller',
      outcome: 'disabled',
      safe_payload: {},
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Autonomy turned off by seller');
  });

  it('maps courier_event_received', () => {
    const e: AuditEvent = {
      event_id: '12',
      seq: 12,
      event_type: 'courier_event_received',
      actor: 'courier',
      outcome: 'ndr',
      safe_payload: { attempt_no: 1 },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Courier: delivery failed (attempt 1)');
  });

  it('maps ndr_action_taken', () => {
    const e: AuditEvent = {
      event_id: '13',
      seq: 13,
      event_type: 'ndr_action_taken',
      actor: 'system',
      outcome: 'updated',
      safe_payload: {},
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Re-delivery requested with updated address');
  });

  it('maps refund_posted', () => {
    const e: AuditEvent = {
      event_id: '14',
      seq: 14,
      event_type: 'refund_posted',
      actor: 'ledger',
      outcome: 'success',
      safe_payload: { amount_minor: 129900 },
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Refund ₹1,299 processed');
  });

  it('maps handoff_created', () => {
    const e: AuditEvent = {
      event_id: '15',
      seq: 15,
      event_type: 'handoff_created',
      actor: 'agent',
      outcome: 'handoff',
      safe_payload: {},
      recorded_at: '',
    };
    expect(getHumanEventLabel(e)).toBe('Handed to seller with summary');
  });
});
