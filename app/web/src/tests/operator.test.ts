import { describe, it, expect } from 'vitest';
import { devMockService } from '../devmock';

describe('Operator Controls (17 §6 & 23 W3)', () => {
  it('fires NDR courier event updating order status', async () => {
    devMockService.resetDemo();
    const res = await devMockService.fireCourierEvent({
      shipment_id: 'SHP-3110',
      type: 'NDR',
      attempt_no: 2,
      reason: 'customer_not_available',
    });
    expect(res.status).toBe('event_processed');
    expect(res.event_id).toMatch(/^EVT-COURIER-/);

    const orders = await devMockService.getOrders();
    const ndrOrder = orders.find((o) => o.order_id === 'ORD-3110');
    expect(ndrOrder?.shipping_status).toBe('NDR attempt 2');
  });

  it('injects counterfactual tracking changes (23 W3)', async () => {
    await devMockService.changeTracking('ORD-2030', 'Delivered', '2026-10-20');
    const orders = await devMockService.getOrders();
    const changed = orders.find((o) => o.order_id === 'ORD-2030');
    expect(changed?.shipping_status).toBe('Delivered');
    expect(changed?.delivered_date).toBe('2026-10-20');
  });

  it('cleanly resets demo database to pristine seed', async () => {
    devMockService.resetDemo();
    const orders = await devMockService.getOrders();
    const original = orders.find((o) => o.order_id === 'ORD-2030');
    expect(original?.shipping_status).toBe('In transit');
  });
});
