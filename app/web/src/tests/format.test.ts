import { describe, it, expect } from 'vitest';
import {
  formatPaise,
  parseTimestampToSeconds,
  formatSecondsToTimestamp,
  mapCaseStateToCustomerStatus,
} from '../utils/format';

describe('format utilities', () => {
  it('formats integer paise into INR currency representation', () => {
    expect(formatPaise(149900)).toBe('₹1,499');
    expect(formatPaise(129900)).toBe('₹1,299');
    expect(formatPaise(99900)).toBe('₹999');
    expect(formatPaise(300000)).toBe('₹3,000');
    expect(formatPaise(0)).toBe('₹0');
    expect(formatPaise(150050)).toBe('₹1,500.50');
  });

  it('parses "MM:SS" timestamps into integer seconds', () => {
    expect(parseTimestampToSeconds('00:07')).toBe(7);
    expect(parseTimestampToSeconds('01:30')).toBe(90);
    expect(parseTimestampToSeconds('00:00')).toBe(0);
    expect(parseTimestampToSeconds(null)).toBe(0);
  });

  it('formats seconds into "MM:SS"', () => {
    expect(formatSecondsToTimestamp(7)).toBe('00:07');
    expect(formatSecondsToTimestamp(90)).toBe('01:30');
    expect(formatSecondsToTimestamp(0)).toBe('00:00');
  });

  it('maps domain CaseState to customer-facing status states', () => {
    expect(mapCaseStateToCustomerStatus('NEW')).toBe('processing');
    expect(mapCaseStateToCustomerStatus('PROCESSING')).toBe('processing');
    expect(mapCaseStateToCustomerStatus('WAITING_CUSTOMER')).toBe('waiting for you');
    expect(mapCaseStateToCustomerStatus('WAITING_SELLER')).toBe('processing');
    expect(mapCaseStateToCustomerStatus('HUMAN_REVIEW')).toBe('waiting for you');
    expect(mapCaseStateToCustomerStatus('RESOLVED')).toBe('done');
  });
});
