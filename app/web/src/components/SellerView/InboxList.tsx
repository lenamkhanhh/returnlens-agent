import React from 'react';
import { SellerCaseSummary } from '../../types';
import { formatPaise } from '../../utils/format';

interface InboxListProps {
  cases: SellerCaseSummary[];
  selectedCaseId: string | null;
  onSelectCase: (caseId: string) => void;
  filter: string;
  onFilterChange: (f: string) => void;
}

export const InboxList: React.FC<InboxListProps> = ({
  cases,
  selectedCaseId,
  onSelectCase,
  filter,
  onFilterChange,
}) => {
  const filtered = cases.filter((c) => {
    if (filter === 'WAITING_SELLER') return c.state === 'WAITING_SELLER' || c.state === 'HUMAN_REVIEW';
    if (filter === 'PROCESSING') return c.state === 'PROCESSING' || c.state === 'ACTION_PENDING';
    if (filter === 'RESOLVED') return c.state === 'RESOLVED';
    return true;
  });

  return (
    <div>
      <div className="col-header">
        <h3>Inbox ({filtered.length})</h3>
        <div style={{ display: 'flex', gap: '4px' }}>
          {['ALL', 'WAITING_SELLER', 'PROCESSING'].map((f) => (
            <button
              key={f}
              type="button"
              onClick={() => onFilterChange(f)}
              style={{
                padding: '2px 6px',
                fontSize: '11px',
                background: filter === f ? 'var(--pine-green)' : '#ffffff',
                color: filter === f ? '#ffffff' : 'var(--text-muted)',
                borderColor: filter === f ? 'var(--pine-green)' : '#e2e0db',
              }}
            >
              {f === 'WAITING_SELLER' ? 'Needs Review' : f}
            </button>
          ))}
        </div>
      </div>

      <div className="inbox-list" style={{ marginTop: '10px' }}>
        {filtered.length === 0 ? (
          <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-light)', fontSize: '12px' }}>
            No cases match the selected filter.
          </div>
        ) : (
          filtered.map((c) => {
            const isSelected = c.case_id === selectedCaseId;
            const isPendingMoney = c.state === 'WAITING_SELLER' && c.pending_amount_minor > 0;

            return (
              <div
                key={c.case_id}
                className={`inbox-item ${isSelected ? 'selected' : ''}`}
                onClick={() => onSelectCase(c.case_id)}
              >
                <div className="inbox-item-top">
                  <span className="inbox-item-order">{c.order_id}</span>
                  {isPendingMoney ? (
                    <span className="inbox-money-badge">
                      {formatPaise(c.pending_amount_minor)}
                    </span>
                  ) : (
                    <span
                      className={`badge ${
                        c.state === 'RESOLVED'
                          ? 'badge-pass'
                          : c.state === 'WAITING_SELLER'
                          ? 'badge-waiting'
                          : 'badge-unknown'
                      }`}
                    >
                      {c.state}
                    </span>
                  )}
                </div>

                <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-main)', marginBottom: '2px' }}>
                  {c.customer_name} · <span style={{ color: 'var(--pine-green)' }}>{c.case_type}</span>
                </div>

                <div className="inbox-summary">{c.summary}</div>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
