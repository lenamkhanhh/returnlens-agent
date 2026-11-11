import React from 'react';
import { CaseDetail, Observation } from '../../types';
import { formatPaise, parseTimestampToSeconds } from '../../utils/format';

interface TriadFactsPanelProps {
  caseDetail: CaseDetail;
  onSeekToTimestamp: (seconds: number) => void;
}

export const TriadFactsPanel: React.FC<TriadFactsPanelProps> = ({
  caseDetail,
  onSeekToTimestamp,
}) => {
  const { facts, observations, unknowns } = caseDetail;

  return (
    <div>
      {/* 1. Verified Order Facts */}
      <div className="triad-group">
        <div className="triad-header verified">
          <span>✓ Verified Order Facts</span>
          <span style={{ fontSize: '11px', textTransform: 'none', fontWeight: 500 }}>
            Source: Store DB & Carrier API
          </span>
        </div>
        <div className="triad-content">
          <div className="fact-row">
            <span className="fact-label">Order ID:</span>
            <span className="fact-value">{facts.order.order_id}</span>
          </div>
          <div className="fact-row">
            <span className="fact-label">Item / SKU:</span>
            <span className="fact-value">{facts.order.item_name || facts.order.sku}</span>
          </div>
          <div className="fact-row">
            <span className="fact-label">Catalog Color:</span>
            <span className="fact-value" style={{ textTransform: 'capitalize' }}>
              {facts.order.catalog_color}
            </span>
          </div>
          <div className="fact-row">
            <span className="fact-label">Paid Amount:</span>
            <span className="fact-value" style={{ color: 'var(--pine-green)' }}>
              {formatPaise(facts.order.paid_minor, facts.order.currency)}
            </span>
          </div>
          <div className="fact-row">
            <span className="fact-label">Shipment Status:</span>
            <span className="fact-value">{facts.shipment.status}</span>
          </div>
          {facts.shipment.delivered_date && (
            <div className="fact-row">
              <span className="fact-label">Delivered Date:</span>
              <span className="fact-value">{facts.shipment.delivered_date}</span>
            </div>
          )}
          {facts.shipment.carrier_label && (
            <div className="fact-row">
              <span className="fact-label">Carrier & Tracking:</span>
              <span className="fact-value">
                {facts.shipment.carrier_label} ({facts.shipment.tracking_number || 'N/A'})
              </span>
            </div>
          )}
        </div>
      </div>

      {/* 2. Observed in Evidence */}
      <div className="triad-group">
        <div className="triad-header observed">
          <span>👁️ Observed in Evidence</span>
          <span style={{ fontSize: '11px', textTransform: 'none', fontWeight: 500 }}>
            Ground Truth from Model Observer
          </span>
        </div>
        <div className="triad-content">
          {observations.length === 0 ? (
            <div style={{ color: 'var(--text-light)', fontStyle: 'italic', padding: '4px 0' }}>
              No visual observations recorded yet.
            </div>
          ) : (
            observations.map((obs: Observation) => {
              const seconds = obs.t ? parseTimestampToSeconds(obs.t) : null;
              const isMismatch =
                obs.color_class &&
                facts.order.catalog_color &&
                obs.color_class !== facts.order.catalog_color &&
                obs.color_class !== 'unknown';

              return (
                <div
                  key={obs.id}
                  style={{
                    padding: '8px',
                    borderRadius: '4px',
                    background: isMismatch ? 'var(--terracotta-light)' : '#f8f9fa',
                    border: isMismatch ? '1px solid var(--terracotta)' : '1px solid #e9ecef',
                  }}
                >
                  <div style={{ display: 'flex', alignItems: 'center', justifyContent: 'space-between', marginBottom: '4px' }}>
                    <div style={{ display: 'flex', alignItems: 'center' }}>
                      {obs.t && seconds !== null ? (
                        <button
                          type="button"
                          className="timestamp-pill"
                          onClick={() => onSeekToTimestamp(seconds)}
                          title={`Click to seek video to ${obs.t}`}
                        >
                          ▶ {obs.t}
                        </button>
                      ) : (
                        <span style={{ fontSize: '11px', color: 'var(--text-light)', marginRight: '6px' }}>[Photo]</span>
                      )}
                      <strong style={{ fontSize: '12px', textTransform: 'capitalize' }}>
                        {obs.attribute}:
                      </strong>
                    </div>

                    <span
                      className={`badge ${
                        obs.visibility === 'visible'
                          ? 'badge-pass'
                          : obs.visibility === 'unclear'
                          ? 'badge-fail'
                          : 'badge-unknown'
                      }`}
                    >
                      {obs.visibility}
                    </span>
                  </div>

                  <div style={{ fontSize: '12.5px', marginTop: '2px' }}>
                    {obs.value}
                    {obs.color_class && (
                      <span style={{ marginLeft: '6px', fontWeight: 600, color: isMismatch ? 'var(--terracotta)' : 'inherit' }}>
                        (Detected: {obs.color_class})
                      </span>
                    )}
                  </div>

                  {isMismatch && (
                    <div style={{ fontSize: '11px', color: 'var(--terracotta)', fontWeight: 600, marginTop: '4px' }}>
                      ⚠️ Discrepancy: Ordered "{facts.order.catalog_color}", but evidence shows "{obs.color_class}".
                    </div>
                  )}

                  {obs.limitation && (
                    <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '2px' }}>
                      Note: {obs.limitation}
                    </div>
                  )}
                </div>
              );
            })
          )}
        </div>
      </div>

      {/* 3. Still Unverified */}
      <div className="triad-group">
        <div className="triad-header unverified">
          <span>❓ Still Unverified / Unknowns</span>
          <span style={{ fontSize: '11px', textTransform: 'none', fontWeight: 500 }}>
            Requires Evidence or Review
          </span>
        </div>
        <div className="triad-content">
          {unknowns.length === 0 ? (
            <div style={{ color: 'var(--pine-green)', fontWeight: 500, padding: '4px 0' }}>
              ✓ All required policy fields verified.
            </div>
          ) : (
            <ul style={{ paddingLeft: '18px', display: 'flex', flexDirection: 'column', gap: '4px' }}>
              {unknowns.map((u, i) => (
                <li key={i} style={{ color: 'var(--terracotta)', fontWeight: 600 }}>
                  {u.replace(/_/g, ' ')}
                  <span style={{ fontWeight: 400, color: 'var(--text-muted)', marginLeft: '6px', fontSize: '11.5px' }}>
                    (not conclusively visible in submitted media)
                  </span>
                </li>
              ))}
            </ul>
          )}
        </div>
      </div>
    </div>
  );
};
