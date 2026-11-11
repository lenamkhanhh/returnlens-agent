import React from 'react';
import { AutonomyExplanation } from '../../types';

interface WhyExplanationModalProps {
  explanation: AutonomyExplanation | null;
  onClose: () => void;
}

export const WhyExplanationModal: React.FC<WhyExplanationModalProps> = ({
  explanation,
  onClose,
}) => {
  if (!explanation) return null;

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" style={{ width: '560px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--pine-green)' }}>
              "Why?" — 7-Step Autonomy Gate Evaluation (17 §3)
            </h3>
            <span style={{ fontSize: '11px', color: 'var(--text-light)', fontFamily: 'monospace' }}>
              Case {explanation.case_id} · Type: {explanation.case_type} · Action: {explanation.action_type}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: 'none', background: 'none', fontSize: '16px', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        <div className="modal-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <div
            style={{
              padding: '10px 14px',
              borderRadius: '4px',
              background:
                explanation.decision === 'AUTO'
                  ? 'var(--pine-green-light)'
                  : explanation.decision === 'BLOCK'
                  ? 'var(--terracotta-light)'
                  : 'var(--status-pending-bg)',
              border: `1px solid ${
                explanation.decision === 'AUTO'
                  ? '#b7dcce'
                  : explanation.decision === 'BLOCK'
                  ? 'var(--terracotta)'
                  : '#fae6a6'
              }`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, color: 'var(--text-muted)' }}>
                Resulting Verdict
              </div>
              <strong style={{ fontSize: '14px', color: 'var(--text-main)' }}>
                {explanation.decision} ({explanation.reason_code})
              </strong>
            </div>
            <span
              className={`badge ${
                explanation.decision === 'AUTO'
                  ? 'badge-pass'
                  : explanation.decision === 'BLOCK'
                  ? 'badge-fail'
                  : 'badge-waiting'
              }`}
              style={{ fontSize: '12px', padding: '4px 10px' }}
            >
              {explanation.decision}
            </span>
          </div>

          <div style={{ marginTop: '10px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {(explanation.checks || []).map((chk) => (
              <div
                key={chk.step}
                style={{
                  display: 'flex',
                  gap: '12px',
                  alignItems: 'flex-start',
                  padding: '8px 12px',
                  borderRadius: '4px',
                  background: chk.passed ? '#fcfdfc' : 'var(--terracotta-light)',
                  border: `1px solid ${chk.passed ? '#e2e0db' : '#f8d7cc'}`,
                }}
              >
                <span
                  style={{
                    display: 'inline-flex',
                    alignItems: 'center',
                    justifyContent: 'center',
                    width: '22px',
                    height: '22px',
                    borderRadius: '50%',
                    background: chk.passed ? 'var(--pine-green)' : 'var(--terracotta)',
                    color: '#ffffff',
                    fontSize: '12px',
                    fontWeight: 700,
                    flexShrink: 0,
                    marginTop: '2px',
                  }}
                >
                  {chk.passed ? '✓' : '✗'}
                </span>

                <div style={{ flex: 1 }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    <strong style={{ fontSize: '12.5px', color: 'var(--text-main)' }}>
                      Step {chk.step}: {chk.title}
                    </strong>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 600,
                        color: chk.passed ? 'var(--pine-green)' : 'var(--terracotta)',
                      }}
                    >
                      {chk.passed ? 'PASS' : 'STOP'}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {chk.detail}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" onClick={onClose} className="btn-primary">
            Close Explanation
          </button>
        </div>
      </div>
    </div>
  );
};
