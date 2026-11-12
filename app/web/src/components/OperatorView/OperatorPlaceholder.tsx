import React from 'react';

export const OperatorPlaceholder: React.FC = () => {
  return (
    <div className="operator-placeholder-card">
      
      <h2 style={{ fontSize: '18px', fontWeight: 700, color: 'var(--pine-green)', marginBottom: '8px' }}>
        Operator Console & Autonomy Bar
      </h2>
      <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.6, maxWidth: '440px', margin: '0 auto' }}>
        Per Wave 1 scope, the Operator controls and Autonomy bar will be built in Wave 2 (after H6).
        This will include courier event simulation (NDR, RETURN_RECEIVED), counterfactual tracking toggles,
        and autonomy level thresholds (L0–L3) backed by <code>reliability.json</code>.
      </p>
      <div style={{ marginTop: '20px' }}>
        <span className="badge badge-unknown" style={{ fontSize: '12px', padding: '4px 10px' }}>
          Wave 2 Scheduled
        </span>
      </div>
    </div>
  );
};
