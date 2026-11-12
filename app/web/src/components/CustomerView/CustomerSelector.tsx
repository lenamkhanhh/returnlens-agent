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
    <div className="demo-order-strip">
      <div className="demo-strip-label">
        <span className="demo-tag">DEMO</span>
        <span>Choose a customer and order</span>
      </div>

      <div className="demo-strip-controls">
        <div className="demo-control-group">
          <label>Customer</label>
          <select
            className="select-field demo-select"
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
        </div>

        <div className="demo-control-group">
          <label>Order</label>
          <select
            className="select-field demo-select"
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
        </div>

        {selectedOrder && (
          <div className="demo-order-info">
            <span className="info-badge">
              <strong>{selectedOrder.item_name}</strong> ({selectedOrder.catalog_color})
            </span>
            <span className="info-badge">
              <strong>{selectedOrder.shipping_status}</strong>
            </span>
            <span className="info-badge scenario-badge">
              {selectedOrder.scenario_tag}
            </span>
          </div>
        )}
      </div>
    </div>
  );
};
