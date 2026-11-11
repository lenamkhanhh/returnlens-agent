import React from 'react';
import { Customer, Order } from '../../types';
import { formatPaise } from '../../utils/format';

interface CustomerSelectorProps {
  customers: Customer[];
  selectedCustomer: Customer | null;
  onSelectCustomer: (c: Customer) => void;
  orders: Order[];
  selectedOrder: Order | null;
  onSelectOrder: (o: Order) => void;
}

export const CustomerSelector: React.FC<CustomerSelectorProps> = ({
  customers,
  selectedCustomer,
  onSelectCustomer,
  orders,
  selectedOrder,
  onSelectOrder,
}) => {
  return (
    <div className="customer-sidebar">
      <div className="sidebar-title">Select Customer Profile</div>
      <select
        className="select-field"
        value={selectedCustomer?.customer_id || ''}
        onChange={(e) => {
          const found = customers.find((c) => c.customer_id === e.target.value);
          if (found) onSelectCustomer(found);
        }}
      >
        {customers.map((c) => (
          <option key={c.customer_id} value={c.customer_id}>
            {c.customer_id}: {c.name} ({c.language})
          </option>
        ))}
      </select>

      {selectedCustomer && (
        <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '14px' }}>
          <div>📍 {selectedCustomer.city_pin}</div>
          <div>📞 {selectedCustomer.phone}</div>
        </div>
      )}

      <div className="sidebar-title" style={{ marginTop: '10px' }}>
        Select Order
      </div>
      <select
        className="select-field"
        value={selectedOrder?.order_id || ''}
        onChange={(e) => {
          const found = orders.find((o) => o.order_id === e.target.value);
          if (found) onSelectOrder(found);
        }}
      >
        {orders.map((o) => (
          <option key={o.order_id} value={o.order_id}>
            {o.order_id} — {o.item_name} ({formatPaise(o.paid_minor)})
          </option>
        ))}
      </select>

      {selectedOrder && (
        <div className="order-card-preview">
          <div className="order-id">
            <span>{selectedOrder.order_id}</span>
            <span>{formatPaise(selectedOrder.paid_minor)}</span>
          </div>
          <div className="order-details">
            <div><strong>Product:</strong> {selectedOrder.item_name}</div>
            <div><strong>Color:</strong> {selectedOrder.catalog_color}</div>
            <div><strong>SKU:</strong> {selectedOrder.sku}</div>
            <div><strong>Status:</strong> {selectedOrder.shipping_status}</div>
            {selectedOrder.delivered_date && (
              <div><strong>Delivered:</strong> {selectedOrder.delivered_date}</div>
            )}
            {selectedOrder.eta_days_relative !== undefined && (
              <div><strong>ETA:</strong> in {selectedOrder.eta_days_relative} days</div>
            )}
            <div style={{ marginTop: '6px', color: 'var(--pine-green)', fontWeight: 600 }}>
              Tag: {selectedOrder.scenario_tag}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
