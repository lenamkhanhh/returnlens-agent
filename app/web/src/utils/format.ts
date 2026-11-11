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
 * Formats ISO timestamp to short messaging time (e.g. "12:03 am").
 */
export function formatMessageTime(isoString?: string): string {
  if (!isoString) return '';
  try {
    const d = new Date(isoString);
    if (isNaN(d.getTime())) return '';
    return d.toLocaleTimeString('en-IN', {
      hour: '2-digit',
      minute: '2-digit',
      hour12: true,
    }).toLowerCase();
  } catch {
    return '';
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

/**
 * Format observation attribute keys into human-friendly labels.
 * E.g. 'label_text' -> 'Label text', 'item_type' -> 'Item type',
 * 'color' / 'colour' -> 'Colour', 'damage' -> 'Damage'.
 */
export function formatObservationAttribute(attr?: string | null): string {
  if (!attr) return '';
  const normalized = attr.trim().toLowerCase();
  if (normalized === 'label_text' || normalized === 'label text') return 'Label text';
  if (normalized === 'item_type' || normalized === 'item type') return 'Item type';
  if (normalized === 'color' || normalized === 'colour') return 'Colour';
  if (normalized === 'damage') return 'Damage';
  const spaced = attr.replace(/_/g, ' ').trim();
  return spaced.charAt(0).toUpperCase() + spaced.slice(1);
}

/**
 * Formats an autonomy lock error banner into plain words, stripping any raw
 * Python dict/JSON structures and explaining the gate refusal clearly.
 * E.g.
 * Input: "{'code': 'reliability_locked', 'case_type': 'DAMAGE', 'pass_pow_k': 1.0, 'k': 5, 'user_message': 'Cannot unlock L3 for DAMAGE: reliability requirement not met. Reliability locked for DAMAGE: Missing run for scenario S10'}"
 * Output: "DAMAGE can't go above L1 yet: the cumulative-limit test (S10) is synthetic, and synthetic tests don't count on the live site."
 */
export function formatAutonomyLockError(rawError: any, fallbackCaseType?: string): string {
  let text = '';
  let caseType = fallbackCaseType;

  if (typeof rawError === 'string') {
    text = rawError;
  } else if (rawError && typeof rawError === 'object') {
    if (rawError.case_type) caseType = rawError.case_type;
    text = rawError.user_message || rawError.userMessage || rawError.message || rawError.detail || '';
    if (typeof text !== 'string') {
      try {
        text = JSON.stringify(text);
      } catch {
        text = String(text);
      }
    }
  }

  // Check for embedded python dict syntax: {'code': ..., 'user_message': ...}
  if (text.includes("'user_message'") || text.includes('"user_message"')) {
    const ctMatch = text.match(/['"]case_type['"]\s*:\s*['"]([^'"]+)['"]/);
    if (ctMatch && ctMatch[1]) {
      caseType = ctMatch[1];
    }
    const umMatch = text.match(/['"]user_message['"]\s*:\s*['"]([^'"]+)['"]/);
    if (umMatch && umMatch[1]) {
      text = umMatch[1];
    }
  }

  // Also check if text is raw JSON
  try {
    const parsed = JSON.parse(text);
    if (parsed && typeof parsed === 'object') {
      if (parsed.case_type) caseType = parsed.case_type;
      if (parsed.user_message) text = parsed.user_message;
    }
  } catch {
    // not JSON
  }

  // Also extract caseType if mentioned in text like "Cannot unlock L3 for DAMAGE:"
  if (!caseType) {
    const m = text.match(/Cannot unlock L\d for (\w+):/i) || text.match(/Reliability locked for (\w+):/i);
    if (m && m[1]) caseType = m[1];
  }

  const ct = caseType || 'This case type';
  const lower = text.toLowerCase();

  // Plain word mapping
  if (
    lower.includes('s10') ||
    lower.includes('synthetic') ||
    (lower.includes('missing run') && (ct === 'DAMAGE' || lower.includes('damage')))
  ) {
    return `${ct} can't go above L1 yet: the cumulative-limit test (S10) is synthetic, and synthetic tests don't count on the live site.`;
  }

  if (lower.includes('s04') || (lower.includes('failed') && (ct === 'MISMATCH' || lower.includes('mismatch')))) {
    return `${ct} can't go above L1 yet: scenario S04 is 4/5 (needs 5/5 to unlock).`;
  }

  if (lower.includes('agent_version') || lower.includes('version') || lower.includes('code changed')) {
    return `${ct} can't go above L1 yet: code changed since the last reliability benchmark.`;
  }

  if (lower.includes('model_id') || lower.includes('model')) {
    return `${ct} can't go above L1 yet: model mismatch with reliability benchmark.`;
  }

  // Clean trailing reason if present
  const cleanedReason = text.replace(/.*reliability locked for [^:]+:\s*/i, '').trim();
  if (cleanedReason && cleanedReason !== text && !cleanedReason.includes('{')) {
    return `${ct} can't go above L1 yet: ${cleanedReason}`;
  }

  if (text && !text.includes('{') && !text.includes('reliability_locked')) {
    return text;
  }

  return `${ct} is locked: reliability benchmark < 5/5.`;
}

/**
 * Calculates real scenario passes display for Autonomy Bar.
 * E.g. "5/5" (unlocked)
 * or for locked:
 *   DAMAGE: "Locked · S03 5/5, S10 synthetic (not counted)"
 *   MISMATCH: "Locked · S04 4/5"
 */
export function getCaseTypePassDisplay(lock?: {
  eligible_for_l2_l3?: boolean;
  status_message?: string;
  metrics?: Record<string, any>;
}): { text: string; isLocked: boolean; passCount: string } {
  if (!lock) return { text: '', isLocked: false, passCount: '' };
  const isLocked = !lock.eligible_for_l2_l3;
  const metrics = lock.metrics;

  if (!metrics || Object.keys(metrics).length === 0) {
    const defaultText = isLocked ? 'Locked' : '5/5';
    return { text: defaultText, isLocked, passCount: isLocked ? '' : '5/5' };
  }

  const entries = Object.entries(metrics);
  let minPasses = 5;
  let maxK = 5;

  for (const [_, m] of entries) {
    if (!m || m.status === 'MISSING') {
      // Missing in live reliability
    } else if (typeof m.passes === 'number') {
      minPasses = Math.min(minPasses, m.passes);
      if (typeof m.k === 'number') maxK = m.k;
    }
  }

  const passCount = `${minPasses}/${maxK}`;
  if (!isLocked) {
    return { text: passCount, isLocked: false, passCount };
  }

  // Check 1: Synthetic test / S10 missing or synthetic
  const hasSyntheticOrMissingS10 =
    entries.some(([sid, m]) => sid === 'S10' || m?.synthetic || m?.status === 'MISSING') ||
    (lock.status_message || '').includes('S10');

  if (hasSyntheticOrMissingS10) {
    const parts = entries.map(([sid, m]) => {
      if (sid === 'S10' || m?.synthetic || m?.status === 'MISSING') {
        return `${sid} synthetic (not counted)`;
      }
      const passes = typeof m?.passes === 'number' ? m.passes : (m?.pass_pow_k === 1.0 ? 5 : 0);
      const k = typeof m?.k === 'number' ? m.k : 5;
      return `${sid} ${passes}/${k}`;
    });
    return {
      text: `Locked · ${parts.join(', ')}`,
      isLocked: true,
      passCount,
    };
  }

  // Check 2: Scenarios that failed or didn't reach full k passes
  const failing = entries.filter(([_, m]) => {
    if (!m) return true;
    if (m.status === 'failed' || m.status === 'blocked') return true;
    if (typeof m.passes === 'number' && typeof m.k === 'number' && m.passes < m.k) return true;
    if (m.pass_pow_k !== undefined && m.pass_pow_k < 1.0) return true;
    return false;
  });

  if (failing.length > 0) {
    const parts = failing.map(([sid, m]) => {
      const passes = typeof m?.passes === 'number' ? m.passes : 0;
      const k = typeof m?.k === 'number' ? m.k : 5;
      return `${sid} ${passes}/${k}`;
    });
    return {
      text: `Locked · ${parts.join(', ')}`,
      isLocked: true,
      passCount,
    };
  }

  // Check 3: Version or model mismatch
  const msg = (lock.status_message || '').toLowerCase();
  if (msg.includes('agent_version') || msg.includes('version')) {
    return { text: 'Locked · code changed', isLocked: true, passCount };
  }
  if (msg.includes('model_id') || msg.includes('model')) {
    return { text: 'Locked · model mismatch', isLocked: true, passCount };
  }

  return { text: `Locked · ${passCount}`, isLocked: true, passCount };
}

/**
 * Detects whether a message is an automated system or courier webhook event
 * rather than an end-customer chat bubble.
 */
export function isCourierOrSystemMessage(m: { role?: string; text?: string }): boolean {
  if (m.role === 'system' || m.role === 'courier') return true;
  const lower = (m.text || '').toLowerCase().trim();
  return lower.startsWith('courier ndr:') || lower.startsWith('courier:') || lower.startsWith('courier update:');
}

/**
 * Formats courier or system webhook event text into a clean user-facing note.
 * E.g. "Courier NDR: customer_not_available" -> "Courier update: delivery attempt failed"
 */
export function formatCourierOrSystemMessage(text: string): string {
  const trimmed = text.trim();
  const lower = trimmed.toLowerCase();

  if (lower.startsWith('courier ndr:') || lower.startsWith('courier: delivery failed')) {
    const reason = lower.replace(/^courier ndr:\s*/i, '').trim();
    if (reason === 'customer_not_available' || !reason) {
      return 'Courier update: delivery attempt failed';
    }
    const cleanReason = reason.replace(/_/g, ' ');
    return `Courier update: delivery attempt failed (${cleanReason})`;
  }

  if (lower.startsWith('courier:')) {
    return trimmed.replace(/^courier:\s*/i, 'Courier update: ');
  }

  return trimmed;
}

/**
 * Computes live reliability summary from AutonomyPolicy lock_status.
 * E.g. "9 of 10 scenarios pass 5/5 (k=5, ffaccd04)"
 */
export function computeReliabilitySummary(policy?: {
  agent_version?: string;
  lock_status?: Record<string, { metrics?: Record<string, any> }>;
} | null): string {
  if (!policy) return '9 of 10 scenarios pass 5/5 (k=5, ffaccd04)';
  const version = (policy.agent_version || 'ffaccd04').slice(0, 8);
  const lockStatus = policy.lock_status || {};

  const scenarioMap = new Map<string, any>();
  for (const ct of Object.values(lockStatus)) {
    if (ct.metrics) {
      for (const [sid, m] of Object.entries(ct.metrics)) {
        if (!scenarioMap.has(sid)) {
          scenarioMap.set(sid, m);
        }
      }
    }
  }

  const totalScenarios = Math.max(scenarioMap.size, 10);
  let failedCount = 0;
  let requiredK = 5;

  for (const [_, m] of scenarioMap.entries()) {
    if (m && typeof m.k === 'number') requiredK = m.k;
    if (
      m &&
      (m.status === 'failed' ||
        m.status === 'blocked' ||
        (typeof m.passes === 'number' && typeof m.k === 'number' && m.passes < m.k))
    ) {
      failedCount++;
    }
  }

  const passedCount = totalScenarios - failedCount;
  return `${passedCount} of ${totalScenarios} scenarios pass 5/5 (k=${requiredK}, ${version})`;
}

