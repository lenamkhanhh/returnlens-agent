import React from 'react';
import { SellerCaseSummary } from '../../types';
import { formatPaise, getStatusBadge } from '../../utils/format';

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

  const filterLabels: Record<string, string> = {
    ALL: 'All',
    WAITING_SELLER: 'Needs review',
    PROCESSING: 'Processing',
  };

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
                padding: '3px 8px',
                fontSize: '11px',
                borderRadius: '4px',
                fontWeight: 600,
                background: filter === f ? 'var(--pine-green)' : '#ffffff',
                color: filter === f ? '#ffffff' : 'var(--text-muted)',
                borderColor: filter === f ? 'var(--pine-green)' : '#e2e0db',
              }}
            >
              {filterLabels[f] || f}
            </button>
          ))}
        </div>
      </div>

      <div className="inbox-list" style={{ marginTop: '10px' }}>
        {filtered.length === 0 ? (
          <div style={{ padding: '20px', textAlign: 'center', color: 'var(--text-light)', fontSize: '13px' }}>
            No cases found in this view.
          </div>
        ) : (
          filtered.map((c) => {
            const isSelected = c.case_id === selectedCaseId;
            const isPendingMoney = c.state === 'WAITING_SELLER' && c.pending_amount_minor > 0;
            const badgeInfo = getStatusBadge(c.state);

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
                    <span className={`badge ${badgeInfo.className}`}>
                      {badgeInfo.label}
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
