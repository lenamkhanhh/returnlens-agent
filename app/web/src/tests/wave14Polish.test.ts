import { describe, it, expect } from 'vitest';
import { sanitizeVisibleText, getStatusBadge } from '../utils/format';

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
});
