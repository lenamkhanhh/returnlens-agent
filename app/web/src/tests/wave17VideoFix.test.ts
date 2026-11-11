import { describe, it, expect } from 'vitest';
import {
  formatAutonomyLockError,
  getCaseTypePassDisplay,
  isCourierOrSystemMessage,
  formatCourierOrSystemMessage,
  computeReliabilitySummary,
} from '../utils/format';

describe('Wave 17 UI Fixes: Autonomy bar reasons, dict parsing, courier notes, provenance', () => {
  describe('1. Autonomy bar lock error banner parsing (no raw python dict)', () => {
    it('parses raw Python dict with single quotes for DAMAGE synthetic S10', () => {
      const rawPythonDict =
        "{'code': 'reliability_locked', 'case_type': 'DAMAGE', 'pass_pow_k': 1.0, 'k': 5, 'user_message': 'Cannot unlock L3 for DAMAGE: reliability requirement not met. Reliability locked for DAMAGE: Missing run for scenario S10'}";
      const result = formatAutonomyLockError(rawPythonDict);
      expect(result).toBe(
        "DAMAGE can't go above L1 yet: the cumulative-limit test (S10) is synthetic, and synthetic tests don't count on the live site."
      );
      expect(result).not.toContain("{'code'");
      expect(result).not.toContain('reliability_locked');
    });

    it('parses raw Python dict for MISMATCH S04 4/5 failure', () => {
      const rawPythonDict =
        "{'code': 'reliability_locked', 'case_type': 'MISMATCH', 'pass_pow_k': 0.0, 'k': 5, 'user_message': \"Cannot unlock L2 for MISMATCH: reliability requirement not met. Reliability locked for MISMATCH: S04 is failed (DB: Case state WAITING_CUSTOMER not in expected ['WAITING_SELLER', 'HUMAN_REVIEW', 'PROCESSING'])\"}";
      const result = formatAutonomyLockError(rawPythonDict);
      expect(result).toBe(
        "MISMATCH can't go above L1 yet: scenario S04 is 4/5 (needs 5/5 to unlock)."
      );
      expect(result).not.toContain("{'code'");
    });

    it('parses object error shapes from ApiError', () => {
      const errObj = {
        code: 'reliability_locked',
        case_type: 'DAMAGE',
        user_message: 'Cannot unlock L3 for DAMAGE: Missing run for scenario S10',
      };
      const result = formatAutonomyLockError(errObj);
      expect(result).toBe(
        "DAMAGE can't go above L1 yet: the cumulative-limit test (S10) is synthetic, and synthetic tests don't count on the live site."
      );
    });

    it('falls back gracefully on unknown errors while keeping plain words', () => {
      const err = { userMessage: 'Unexpected server response' };
      expect(formatAutonomyLockError(err, 'LATE')).toBe('Unexpected server response');
    });
  });

  describe('2. Case type lock reason labels (real API numbers, no hardcoding)', () => {
    it('shows real reason for DAMAGE: S03 5/5, S10 synthetic (not counted)', () => {
      const lock = {
        eligible_for_l2_l3: false,
        status_message: 'Reliability locked for DAMAGE: Missing run for scenario S10',
        metrics: {
          S03: { k: 5, passes: 5, pass_pow_k: 1.0, status: 'passed' },
          S10: { status: 'MISSING' },
        },
      };
      const result = getCaseTypePassDisplay(lock);
      expect(result).toEqual({
        text: 'Locked · S03 5/5, S10 synthetic (not counted)',
        isLocked: true,
        passCount: '5/5',
      });
    });

    it('shows real reason for MISMATCH: S04 4/5', () => {
      const lock = {
        eligible_for_l2_l3: false,
        status_message:
          "Reliability locked for MISMATCH: S04 is failed (DB: Case state WAITING_CUSTOMER not in expected ['WAITING_SELLER', 'HUMAN_REVIEW', 'PROCESSING'])",
        metrics: {
          S04: { k: 5, passes: 4, pass_pow_k: 0.0, status: 'failed' },
          S08: { k: 5, passes: 5, pass_pow_k: 1.0, status: 'passed' },
        },
      };
      const result = getCaseTypePassDisplay(lock);
      expect(result).toEqual({
        text: 'Locked · S04 4/5',
        isLocked: true,
        passCount: '4/5',
      });
    });

    it('shows simple 5/5 when unlocked (e.g. WISMO)', () => {
      const lock = {
        eligible_for_l2_l3: true,
        status_message: 'WISMO passed reliability gate (all scenarios pass^5 = 1.0)',
        metrics: {
          S01: { k: 5, passes: 5, pass_pow_k: 1.0, status: 'passed' },
          S02: { k: 5, passes: 5, pass_pow_k: 1.0, status: 'passed' },
        },
      };
      const result = getCaseTypePassDisplay(lock);
      expect(result).toEqual({
        text: '5/5',
        isLocked: false,
        passCount: '5/5',
      });
    });
  });

  describe('3. Customer chat: Courier event detection and clean centered note text', () => {
    it('identifies courier events even when sent with customer role', () => {
      expect(isCourierOrSystemMessage({ role: 'customer', text: 'Courier NDR: customer_not_available' })).toBe(true);
      expect(isCourierOrSystemMessage({ role: 'system', text: 'Courier: delivery failed' })).toBe(true);
      expect(isCourierOrSystemMessage({ role: 'courier', text: 'Out for delivery' })).toBe(true);
      expect(isCourierOrSystemMessage({ role: 'customer', text: 'Where is my order?' })).toBe(false);
      expect(isCourierOrSystemMessage({ role: 'agent', text: 'Your order is on the way.' })).toBe(false);
    });

    it('formats Courier NDR customer_not_available to Courier update: delivery attempt failed', () => {
      expect(formatCourierOrSystemMessage('Courier NDR: customer_not_available')).toBe(
        'Courier update: delivery attempt failed'
      );
    });

    it('formats other courier reasons nicely', () => {
      expect(formatCourierOrSystemMessage('Courier NDR: door_locked')).toBe(
        'Courier update: delivery attempt failed (door locked)'
      );
      expect(formatCourierOrSystemMessage('Courier NDR: address_incomplete')).toBe(
        'Courier update: delivery attempt failed (address incomplete)'
      );
    });
  });

  describe('4. Operator System Provenance reliability computation', () => {
    it('computes 9 of 10 scenarios pass 5/5 from the API policy data', () => {
      const mockPolicy = {
        agent_version: 'ffaccd04c091ced6c3ccf577cd44519ff4789db09e8a07be7231f9078463f30a',
        lock_status: {
          WISMO: {
            metrics: {
              S01: { k: 5, passes: 5, status: 'passed' },
              S02: { k: 5, passes: 5, status: 'passed' },
            },
          },
          DAMAGE: {
            metrics: {
              S03: { k: 5, passes: 5, status: 'passed' },
              S10: { status: 'MISSING' },
            },
          },
          MISMATCH: {
            metrics: {
              S04: { k: 5, passes: 4, status: 'failed' },
              S08: { k: 5, passes: 5, status: 'passed' },
            },
          },
          UNCLEAR: {
            metrics: {
              S05: { k: 5, passes: 5, status: 'passed' },
              S09: { k: 5, passes: 5, status: 'passed' },
            },
          },
          LATE: {
            metrics: {
              S06: { k: 5, passes: 5, status: 'passed' },
            },
          },
          NDR: {
            metrics: {
              S07: { k: 5, passes: 5, status: 'passed' },
            },
          },
        },
      };

      const result = computeReliabilitySummary(mockPolicy);
      expect(result).toBe('9 of 10 scenarios pass 5/5 (k=5, ffaccd04)');
    });
  });
});
