import { describe, it, expect } from 'vitest';
import { devMockService } from '../devmock';

describe('Autonomy Bar & 7-Step "Why?" Checklist (17 §6 & 23 W4)', () => {
  it('retrieves default autonomy policy', async () => {
    const policy = await devMockService.getAutonomyPolicy();
    expect(policy.store_id).toBe('store_dhun');
    expect(policy.levels.WISMO).toBe('L1');
    expect(policy.levels.DAMAGE).toBe('L0');
    expect(policy.per_order_cap_minor).toBe(150000); // ₹1,500
    expect(policy.per_customer_daily_cap_minor).toBe(200000); // ₹2,000
    expect(policy.kill_switch).toBe(false);
  });

  it('allows updating policy levels for eligible case types', async () => {
    const updated = await devMockService.updateAutonomyPolicy({
      levels: {
        WISMO: 'L1',
        DAMAGE: 'L2',
        MISMATCH: 'L2',
        UNCLEAR: 'L0',
        LATE: 'L0',
        NDR: 'L1',
      },
    });
    expect(updated.levels.DAMAGE).toBe('L2');
  });

  it('rejects promoting UNCLEAR to L2 due to reliability gate lock (17 §2)', async () => {
    await expect(
      devMockService.updateAutonomyPolicy({
        levels: {
          WISMO: 'L1',
          DAMAGE: 'L0',
          MISMATCH: 'L0',
          UNCLEAR: 'L2',
          LATE: 'L0',
          NDR: 'L1',
        },
      })
    ).rejects.toMatchObject({
      status: 422,
      code: 'reliability_locked',
    });
  });

  it('activates kill switch setting all levels to L0', async () => {
    await devMockService.killAutonomy('Seller panic button');
    const policy = await devMockService.getAutonomyPolicy();
    expect(policy.kill_switch).toBe(true);
    expect(policy.levels.WISMO).toBe('L0');
    expect(policy.levels.DAMAGE).toBe('L0');
    expect(policy.levels.MISMATCH).toBe('L0');
  });

  it('evaluates 7-step checklist for "Why?" explanation matching 17 §3', async () => {
    devMockService.resetDemo();
    const explanation = await devMockService.getAutonomyExplanation('CASE-0012');
    expect(explanation.checks.length).toBe(7);
    expect(explanation.checks[0].step).toBe(1);
    expect(explanation.checks[0].title).toBe('Kill Switch Check');
    expect(explanation.checks[1].step).toBe(2);
    expect(explanation.checks[1].title).toBe('Prohibited Actions Check');
    expect(explanation.checks[3].step).toBe(4);
    expect(explanation.checks[3].title).toBe('Reliability Gate');
    expect(explanation.checks[5].step).toBe(6);
    expect(explanation.checks[5].title).toBe('Ledger & Cumulative Cap Check');
    expect(explanation.checks[6].step).toBe(7);
    expect(explanation.checks[6].title).toBe('Final Autonomy Verdict');
  });
});
