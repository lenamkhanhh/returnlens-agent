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

/**
 * Formats transcriber detected language into human-friendly label.
 * Defaults to 'English' for stock English voice notes if unspecified or 'en'.
 */
export function formatDetectedLanguage(lang?: string | null): string {
  if (!lang) return 'English';
  const clean = lang.trim().toLowerCase();
  if (clean === 'en' || clean === 'english') return 'English';
  if (clean === 'hi' || clean === 'hindi') return 'Hindi';
  if (clean === 'hinglish') return 'Hinglish';
  if (clean === 'other') return 'Other';
  return lang.charAt(0).toUpperCase() + lang.slice(1);
}

/**
 * Returns consistent status chip presentation per Wave 14 D §3:
 * - waiting = amber (.badge-waiting)
 * - needs you = blue (.badge-needs-you)
 * - resolved = green (.badge-resolved)
 * - blocked = red (.badge-blocked)
 */
export function getStatusBadge(raw?: string | null): { label: string; className: string } {
  if (!raw) return { label: 'Unknown', className: 'badge-unknown' };
  const s = raw.trim().toUpperCase();

  switch (s) {
    case 'RESOLVED':
    case 'APPROVED':
    case 'PASS':
    case 'SUCCEEDED':
    case 'DONE':
    case 'VISIBLE':
      return { label: 'Resolved', className: 'badge-resolved' };

    case 'WAITING_SELLER':
    case 'HUMAN_REVIEW':
    case 'NEEDS_REVIEW':
    case 'PENDING':
      return { label: 'Needs review', className: 'badge-needs-you' };

    case 'WAITING_CUSTOMER':
    case 'PROCESSING':
    case 'ACTION_PENDING':
    case 'RECONCILIATION':
    case 'NEW':
    case 'WAITING':
    case 'WAITING_RETURN':
    case 'SENDING':
      return { label: s === 'PROCESSING' ? 'Processing' : s === 'WAITING_CUSTOMER' ? 'Waiting customer' : 'Waiting', className: 'badge-waiting' };

    case 'BLOCKED':
    case 'DECLINED':
    case 'FAIL':
    case 'FAILED':
    case 'ERROR':
    case 'UNCLEAR':
      return { label: s === 'BLOCKED' ? 'Blocked' : s === 'DECLINED' ? 'Declined' : s === 'UNCLEAR' ? 'Unclear' : 'Failed', className: 'badge-blocked' };

    default:
      return { label: raw, className: 'badge-unknown' };
  }
}

/**
 * Removes internal citations (e.g. 17 §3, 23 W1, Card B15, Test 14) from strings for visible display.
 */
export function sanitizeVisibleText(text?: string | null): string {
  if (!text) return '';
  return text
    .replace(/\s*\(\d+\s*§\d+\)/g, '')
    .replace(/\s*\(\d+\s*W\d+[^)]*\)/g, '')
    .replace(/\s*\(Card\s*[A-Z0-9]+[^)]*\)/gi, '')
    .replace(/\s*\(Test\s*\d+[^)]*\)/gi, '')
    .trim();
}

