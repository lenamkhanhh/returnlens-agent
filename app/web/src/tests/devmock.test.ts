import { describe, it, expect } from 'vitest';
import { devMockService } from '../devmock';

describe('Dev Mock Service & 17 §5 API Contracts', () => {
  it('returns fake customers CUS-01 through CUS-05', async () => {
    const customers = await devMockService.getCustomers();
    expect(customers.length).toBe(5);
    expect(customers.map((c) => c.customer_id)).toEqual([
      'CUS-01',
      'CUS-02',
      'CUS-03',
      'CUS-04',
      'CUS-05',
    ]);
  });

  it('filters fake orders by customer', async () => {
    const cus2Orders = await devMockService.getOrders('CUS-02');
    expect(cus2Orders.length).toBe(1);
    expect(cus2Orders[0].order_id).toBe('ORD-7729');
    expect(cus2Orders[0].sku).toBe('HEAD-WHT-02');
    expect(cus2Orders[0].paid_minor).toBe(149900);
  });

  it('loads pre-seeded case CASE-0012 with Triad facts, observations, and proposals', async () => {
    const c = await devMockService.getCase('CASE-0012');
    expect(c.case_id).toBe('CASE-0012');
    expect(c.case_type).toBe('MISMATCH');
    expect(c.facts.order.sku).toBe('HEAD-WHT-02');
    expect(c.facts.order.catalog_color).toBe('white');
    expect(c.observations.length).toBeGreaterThan(0);
    expect(c.observations[0].color_class).toBe('black');
    expect(c.unknowns).toContain('barcode');
    expect(c.proposals.length).toBe(1);
    expect(c.proposals[0].proposal_id).toBe('PRP-0007');
  });

  it('creates new case starting in PROCESSING state', async () => {
    const res = await devMockService.createCase('ORD-2030', 'Where is my order?');
    expect(res.case_id).toMatch(/^CASE-/);
    expect(res.job_id).toMatch(/^JOB-/);

    const created = await devMockService.getCase(res.case_id);
    expect(created.state).toBe('PROCESSING');
  });

  it('returns HTTP 422 Blocked when proposal amount exceeds paid balance', async () => {
    // CASE-0014 has PRP-0009 requesting ₹1,800 on a ₹1,499 order
    await expect(
      devMockService.decideProposal('PRP-0009', 'approve', '772bba0011', 'd-idemp-1')
    ).rejects.toMatchObject({
      status: 422,
      code: 'P_BALANCE',
    });
  });

  it('returns HTTP 409 Conflict when proposal is stale', async () => {
    await expect(
      devMockService.decideProposal('PRP-0007', 'approve', 'stale', 'd-idemp-2')
    ).rejects.toMatchObject({
      status: 409,
      code: 'stale_proposal',
    });
  });

  it('successfully approves a valid proposal with action ID and status succeeded', async () => {
    const res = await devMockService.decideProposal(
      'PRP-0007',
      'approve',
      '9f83a21bc90d',
      'd-idemp-3'
    );
    expect(res.status).toBe('succeeded');
    expect(res.action_id).toMatch(/^ACT-/);

    const updated = await devMockService.getCase('CASE-0012');
    expect(updated.proposals[0].status).toBe('approved');
  });
});
