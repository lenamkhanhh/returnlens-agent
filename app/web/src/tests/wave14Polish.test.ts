import { describe, it, expect } from 'vitest';
import {
  sanitizeVisibleText,
  getStatusBadge,
  formatObservationAttribute,
  getCaseTypePassDisplay,
  formatMessageTime,
} from '../utils/format';

describe('Wave 14 D: UI/UX design polish and plain presentation', () => {
  describe('1. Removal of internal references from visible text', () => {
    it('strips section numbers such as (17 §3), (17 §6), (14 §5)', () => {
      expect(sanitizeVisibleText('"Why?" — 7-Step Autonomy Gate Evaluation (17 §3)')).toBe(
        '"Why?" — 7-Step Autonomy Gate Evaluation'
      );
      expect(sanitizeVisibleText('Reliability Gate (17 §3)')).toBe('Reliability Gate');
      expect(sanitizeVisibleText('pristine cold-open demo seed (14 §5)')).toBe(
        'pristine cold-open demo seed'
      );
    });

    it('strips wave citations such as (23 W1), (23 W3), (23 W4)', () => {
      expect(sanitizeVisibleText('⚡ Try to Break It (23 W1 — Judge Sandbox)')).toBe(
        '⚡ Try to Break It'
      );
      expect(sanitizeVisibleText('Counterfactual Tracking (23 W3)')).toBe(
        'Counterfactual Tracking'
      );
    });

    it('strips card and test references such as (Card B15) and (Test 14)', () => {
      expect(sanitizeVisibleText('Polling per Card 4 (Card B15)')).toBe('Polling per Card 4');
      expect(sanitizeVisibleText('Verification Step (Test 14)')).toBe('Verification Step');
    });

    it('preserves clean strings untouched', () => {
      expect(sanitizeVisibleText('What the agent saw')).toBe('What the agent saw');
      expect(sanitizeVisibleText('Still unverified')).toBe('Still unverified');
      expect(sanitizeVisibleText('Proposals awaiting you')).toBe('Proposals awaiting you');
      expect(sanitizeVisibleText('Why did it stop?')).toBe('Why did it stop?');
    });
  });

  describe('2. Status chips consistent colours (waiting = amber, needs you = blue, resolved = green, blocked = red)', () => {
    it('maps resolved states to green badge-resolved', () => {
      expect(getStatusBadge('RESOLVED')).toEqual({ label: 'Resolved', className: 'badge-resolved' });
      expect(getStatusBadge('APPROVED')).toEqual({ label: 'Resolved', className: 'badge-resolved' });
      expect(getStatusBadge('PASS')).toEqual({ label: 'Resolved', className: 'badge-resolved' });
    });

    it('maps needs you / seller action states to blue badge-needs-you', () => {
      expect(getStatusBadge('WAITING_SELLER')).toEqual({ label: 'Needs review', className: 'badge-needs-you' });
      expect(getStatusBadge('HUMAN_REVIEW')).toEqual({ label: 'Needs review', className: 'badge-needs-you' });
      expect(getStatusBadge('PENDING')).toEqual({ label: 'Needs review', className: 'badge-needs-you' });
    });

    it('maps waiting / in-progress states to amber badge-waiting', () => {
      expect(getStatusBadge('WAITING_CUSTOMER')).toEqual({ label: 'Waiting customer', className: 'badge-waiting' });
      expect(getStatusBadge('PROCESSING')).toEqual({ label: 'Processing', className: 'badge-waiting' });
      expect(getStatusBadge('WAITING')).toEqual({ label: 'Waiting', className: 'badge-waiting' });
    });

    it('maps blocked / declined / failed states to red badge-blocked', () => {
      expect(getStatusBadge('BLOCKED')).toEqual({ label: 'Blocked', className: 'badge-blocked' });
      expect(getStatusBadge('DECLINED')).toEqual({ label: 'Declined', className: 'badge-blocked' });
      expect(getStatusBadge('FAIL')).toEqual({ label: 'Failed', className: 'badge-blocked' });
      expect(getStatusBadge('UNCLEAR')).toEqual({ label: 'Unclear', className: 'badge-blocked' });
    });
  });

  describe('3. Observation attribute formatting (plain natural labels, no code identifiers)', () => {
    it('formats label_text to Label text', () => {
      expect(formatObservationAttribute('label_text')).toBe('Label text');
    });

    it('formats item_type to Item type', () => {
      expect(formatObservationAttribute('item_type')).toBe('Item type');
    });

    it('formats color and colour to Colour', () => {
      expect(formatObservationAttribute('color')).toBe('Colour');
      expect(formatObservationAttribute('colour')).toBe('Colour');
    });

    it('formats damage to Damage', () => {
      expect(formatObservationAttribute('damage')).toBe('Damage');
    });

    it('formats generic snake_case identifiers into sentence case', () => {
      expect(formatObservationAttribute('outer_box_seal')).toBe('Outer box seal');
    });
  });

  describe('4. Proposal return card amount and empty preview handling', () => {
    it('determines whether to show monetary impact for return vs refund', () => {
      const isReturn = (action: string) => action.toUpperCase().includes('RETURN');
      const shouldShowAmount = (action: string, amount?: number | null) =>
        amount !== undefined && amount !== null && (!isReturn(action) || amount > 0);

      expect(shouldShowAmount('PROPOSE_RETURN', 0)).toBe(false);
      expect(shouldShowAmount('PROPOSE_RETURN', null)).toBe(false);
      expect(shouldShowAmount('PROPOSE_RETURN', 50000)).toBe(true);
      expect(shouldShowAmount('PROPOSE_REFUND', 149900)).toBe(true);
    });

    it('hides empty or whitespace-only reply previews', () => {
      const hasPreview = (preview?: string | null) => Boolean(preview && preview.trim().length > 0);

      expect(hasPreview('')).toBe(false);
      expect(hasPreview('   ')).toBe(false);
      expect(hasPreview(null)).toBe(false);
      expect(hasPreview('We have initiated your return label.')).toBe(true);
    });
  });

  describe('5. Wave 15 Track W: Real pass display and messaging helpers', () => {
    it('computes 5/5 for unlocked case type where all scenarios pass', () => {
      const lock = {
        eligible_for_l2_l3: true,
        metrics: {
          S01: { k: 5, passes: 5 },
          S02: { k: 5, passes: 5 },
        },
      };
      expect(getCaseTypePassDisplay(lock)).toEqual({
        text: '5/5',
        isLocked: false,
        passCount: '5/5',
      });
    });

    it('computes locked scenario when bottleneck scenario is 4/5', () => {
      const lock = {
        eligible_for_l2_l3: false,
        metrics: {
          S04: { k: 5, passes: 5 },
          S08: { k: 5, passes: 4 },
        },
      };
      expect(getCaseTypePassDisplay(lock)).toEqual({
        text: 'Locked · S08 4/5',
        isLocked: true,
        passCount: '4/5',
      });
    });

    it('computes locked reason with synthetic notice when S10 is missing or synthetic', () => {
      const lock = {
        eligible_for_l2_l3: false,
        metrics: {
          S03: { k: 5, passes: 5 },
          S10: { status: 'MISSING' },
        },
      };
      expect(getCaseTypePassDisplay(lock)).toEqual({
        text: 'Locked · S03 5/5, S10 synthetic (not counted)',
        isLocked: true,
        passCount: '5/5',
      });
    });

    it('explains locked when all scenarios 5/5 but locked due to synthetic test or reason', () => {
      const lock = {
        eligible_for_l2_l3: false,
        status_message: 'Reliability locked for DAMAGE: S10 is synthetic',
        metrics: {
          S03: { k: 5, passes: 5 },
          S10: { k: 5, passes: 5, synthetic: true },
        },
      };
      expect(getCaseTypePassDisplay(lock)).toEqual({
        text: 'Locked · S03 5/5, S10 synthetic (not counted)',
        isLocked: true,
        passCount: '5/5',
      });
    });

    it('formats ISO timestamps to short messaging time string', () => {
      const timeStr = formatMessageTime('2026-11-12T00:03:00Z');
      expect(timeStr.length).toBeGreaterThan(0);
      expect(timeStr).toMatch(/\d{1,2}:\d{2}\s*(am|pm)/i);
    });
  });
});
