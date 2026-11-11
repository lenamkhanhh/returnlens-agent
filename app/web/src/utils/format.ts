import { CaseState, CustomerFacingStatus } from '../types';

/**
 * Formats integer paise into INR string.
 * Example: 149900 -> "₹1,499"
 * Never uses float arithmetic.
 */
export function formatPaise(minor: number, currency = 'INR'): string {
  if (isNaN(minor)) return `${currency} 0`;
  const major = Math.floor(minor / 100);
  const remainingPaise = minor % 100;
  const formatted = major.toLocaleString('en-IN');
  if (remainingPaise > 0) {
    const paiseStr = remainingPaise.toString().padStart(2, '0');
    return `₹${formatted}.${paiseStr}`;
  }
  return `₹${formatted}`;
}

/**
 * Parses timestamp string "MM:SS" into seconds.
 * Example: "00:07" -> 7
 */
export function parseTimestampToSeconds(t: string | null): number {
  if (!t) return 0;
  const parts = t.split(':');
  if (parts.length === 2) {
    const mins = parseInt(parts[0], 10) || 0;
    const secs = parseFloat(parts[1]) || 0;
    return mins * 60 + secs;
  }
  const parsed = parseFloat(t);
  return isNaN(parsed) ? 0 : parsed;
}

/**
 * Formats seconds into "MM:SS".
 */
export function formatSecondsToTimestamp(totalSeconds: number): string {
  const rounded = Math.floor(Math.max(0, totalSeconds));
  const mins = Math.floor(rounded / 60);
  const secs = rounded % 60;
  return `${mins.toString().padStart(2, '0')}:${secs.toString().padStart(2, '0')}`;
}

/**
 * Maps domain CaseState to CustomerFacingStatus per BRIEF_D_WEB.md:
 * states: sending, processing, waiting for you, done, error
 */
export function mapCaseStateToCustomerStatus(state?: CaseState | null): CustomerFacingStatus {
  if (!state) return 'new conversation';
  switch (state) {
    case 'NEW':
    case 'PROCESSING':
    case 'ACTION_PENDING':
    case 'RECONCILIATION':
      return 'processing';
    case 'WAITING_CUSTOMER':
    case 'HUMAN_REVIEW':
      return 'waiting for you';
    case 'WAITING_SELLER':
    case 'WAITING_RETURN':
      return 'waiting for seller';
    case 'RESOLVED':
      return 'done';
    default:
      return 'processing';
  }
}

export function formatDate(isoString?: string): string {
  if (!isoString) return '—';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return isoString;
    return d.toLocaleString('en-IN', {
      month: 'short',
      day: 'numeric',
      hour: '2-digit',
      minute: '2-digit',
    });
  } catch {
    return isoString;
  }
}
