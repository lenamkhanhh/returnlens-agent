import React from 'react';
import { PolicyCheck } from '../../types';

interface PolicyChecksProps {
  checks: PolicyCheck[];
}

export const PolicyChecks: React.FC<PolicyChecksProps> = ({ checks }) => {
  const safeChecks = checks || [];
  return (
    <div style={{ marginTop: '12px' }}>
      <div className="col-header" style={{ marginBottom: '8px' }}>
        <h3>Domain Policy Guardrails</h3>
        <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>
          Strict Code-Enforced Checks
        </span>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
        {safeChecks.length === 0 ? (
          <div style={{ fontSize: '12px', color: 'var(--text-light)', fontStyle: 'italic' }}>
            No policy checks evaluated yet.
          </div>
        ) : (
          safeChecks.map((pc) => {
            const badgeClass =
              pc.result === 'PASS'
                ? 'badge-pass'
                : pc.result === 'FAIL'
                ? 'badge-fail'
                : 'badge-unknown';

            return (
              <div
                key={pc.rule_id}
                style={{
                  display: 'flex',
                  justifyContent: 'space-between',
                  alignItems: 'center',
                  padding: '6px 10px',
                  borderRadius: '4px',
                  background: '#fbfbfa',
                  border: 'var(--border-thin)',
                  fontSize: '12px',
                }}
              >
                <div>
                  <strong style={{ fontFamily: 'monospace', fontSize: '12.5px' }}>
                    {pc.rule_id}
                  </strong>
                  <span style={{ color: 'var(--text-muted)', marginLeft: '8px' }}>
                    ({pc.reason_code.replace(/_/g, ' ')})
                  </span>
                </div>
                <span className={`badge ${badgeClass}`}>{pc.result}</span>
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
