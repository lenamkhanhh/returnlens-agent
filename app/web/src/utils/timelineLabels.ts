import { AuditEvent } from '../types';
import { formatPaise } from './format';

/**
 * Returns human-readable label according to 17 §7:
 * | event_type | Nhãn hiển thị |
 * | tool_call_succeeded | "Checked order ORD-7729" / "Checked tracking" |
 * | tool_call_blocked | "Blocked: refund exceeds remaining ₹1,499" |
 * | observation_validated | "Saw black item at 00:07" |
 * | voice_note_transcribed | "Voice note transcribed (Hindi)" |
 * | clarification_sent | "Asked for a close-up photo (1 of 1)" |
 * | proposal_created | "Suggested: request box label" |
 * | approval_recorded | "Seller approved" / "Auto-approved by autonomy policy L3" |
 * | autonomy_deferred_to_seller | "Sent to seller: cumulative limit ₹2,000/day" |
 * | kill_switch_engaged | "Autonomy turned off by seller" |
 * | courier_event_received | "Courier: delivery failed (attempt 1)" |
 * | ndr_action_taken | "Re-delivery requested with updated address" |
 * | refund_posted | "Refund ₹1,299 processed" |
 * | handoff_created | "Handed to seller with summary" |
 */
export function getHumanEventLabel(event: AuditEvent): string {
  const p = event.safe_payload || {};

  switch (event.event_type) {
    case 'tool_call_succeeded':
      if (p.tool === 'get_order') {
        return `Checked order ${p.order_id || ''}`.trim();
      }
      if (p.tool === 'get_tracking') {
        return `Checked tracking ${p.tracking_number ? `(${p.tracking_number})` : ''}`.trim();
      }
      return `Checked ${p.tool || 'system tool'}`;

    case 'tool_call_blocked':
      if (p.amount_minor !== undefined) {
        return `Blocked: refund exceeds remaining ${formatPaise(p.amount_minor)}`;
      }
      return `Blocked: ${p.reason || 'policy limit exceeded'}`;

    case 'observation_validated':
      if (p.t) {
        const itemDesc = p.color_class ? `${p.color_class} item` : (p.value || p.attribute || 'item');
        return `Saw ${itemDesc} at ${p.t}`;
      }
      return `Observed ${p.attribute || 'attribute'}: ${p.value || 'identified'}`;

    case 'voice_note_transcribed':
      return `Voice note transcribed (${p.language || 'Hindi'})`;

    case 'clarification_sent':
      return `Asked for a close-up photo (${p.count || 1} of 1)`;

    case 'proposal_created':
      if (p.action_type === 'PROPOSE_RETURN') return 'Suggested: approve return for exchange';
      if (p.action_type === 'PROPOSE_REFUND') {
        const amt = p.amount_minor ? ` (${formatPaise(p.amount_minor)})` : '';
        return `Suggested: issue refund${amt}`;
      }
      if (p.action_type === 'REQUEST_EVIDENCE') return 'Suggested: request box label';
      return `Suggested: ${p.action_type || 'next action'}`;

    case 'approval_recorded':
      if (event.actor?.startsWith('policy:autonomy')) {
        return `Auto-approved by autonomy policy ${p.level || 'L3'}`;
      }
      return 'Seller approved';

    case 'autonomy_deferred_to_seller':
      if (p.reason === 'cumulative_limit') {
        return `Sent to seller: cumulative limit ${p.limit_minor ? formatPaise(p.limit_minor) : '₹2,000'}/day`;
      }
      return `Sent to seller: ${p.reason || 'requires seller authorization'}`;

    case 'kill_switch_engaged':
      return 'Autonomy turned off by seller';

    case 'courier_event_received':
      return `Courier: delivery failed (attempt ${p.attempt_no || 1})`;

    case 'ndr_action_taken':
      return 'Re-delivery requested with updated address';

    case 'refund_posted':
      if (p.amount_minor !== undefined) {
        return `Refund ${formatPaise(p.amount_minor)} processed`;
      }
      return 'Refund processed';

    case 'handoff_created':
      return 'Handed to seller with summary';

    default:
      return `${event.event_type.replace(/_/g, ' ')}`;
  }
}
