import React from 'react';
import { AutonomyExplanation } from '../../types';
import { sanitizeVisibleText } from '../../utils/format';

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
      <div className="modal-card" style={{ width: '580px' }} onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <div>
            <h3 style={{ fontSize: '16px', fontWeight: 700, color: 'var(--pine-green)' }}>
              "Why did it stop?" — 7-Step Autonomy Evaluation
            </h3>
            <span style={{ fontSize: '12px', color: 'var(--text-light)', fontFamily: 'monospace' }}>
              Case {explanation.case_id} · Type: {explanation.case_type} · Action: {explanation.action_type}
            </span>
          </div>
          <button
            type="button"
            onClick={onClose}
            style={{ border: 'none', background: 'none', fontSize: '18px', cursor: 'pointer' }}
          >
            ✕
          </button>
        </div>

        <div className="modal-body" style={{ maxHeight: '70vh', overflowY: 'auto' }}>
          <div
            style={{
              padding: '12px 16px',
              borderRadius: '6px',
              background:
                explanation.decision === 'AUTO'
                  ? 'var(--pine-green-light)'
                  : explanation.decision === 'BLOCK'
                  ? 'var(--terracotta-light)'
                  : 'var(--status-waiting-bg)',
              border: `1px solid ${
                explanation.decision === 'AUTO'
                  ? '#b7dcce'
                  : explanation.decision === 'BLOCK'
                  ? 'var(--terracotta)'
                  : 'var(--status-waiting-border)'
              }`,
              display: 'flex',
              justifyContent: 'space-between',
              alignItems: 'center',
            }}
          >
            <div>
              <div style={{ fontSize: '11px', textTransform: 'uppercase', fontWeight: 700, color: 'var(--text-muted)' }}>
                Resulting verdict
              </div>
              <strong style={{ fontSize: '14px', color: 'var(--text-main)' }}>
                {explanation.decision} ({explanation.reason_code})
              </strong>
            </div>
            <span
              className={`badge ${
                explanation.decision === 'AUTO'
                  ? 'badge-resolved'
                  : explanation.decision === 'BLOCK'
                  ? 'badge-blocked'
                  : 'badge-needs-you'
              }`}
              style={{ fontSize: '12px', padding: '4px 10px' }}
            >
              {explanation.decision}
            </span>
          </div>

          <div style={{ marginTop: '12px', display: 'flex', flexDirection: 'column', gap: '8px' }}>
            {(explanation.checks || []).map((chk) => (
              <div
                key={chk.step}
                style={{
                  display: 'flex',
                  gap: '12px',
                  alignItems: 'flex-start',
                  padding: '10px 14px',
                  borderRadius: '6px',
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
                    <strong style={{ fontSize: '13px', color: 'var(--text-main)' }}>
                      Step {chk.step}: {sanitizeVisibleText(chk.title)}
                    </strong>
                    <span
                      style={{
                        fontSize: '11px',
                        fontWeight: 700,
                        color: chk.passed ? 'var(--pine-green)' : 'var(--terracotta)',
                      }}
                    >
                      {chk.passed ? 'PASS' : 'STOP'}
                    </span>
                  </div>
                  <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '2px' }}>
                    {sanitizeVisibleText(chk.detail)}
                  </div>
                </div>
              </div>
            ))}
          </div>
        </div>

        <div className="modal-footer">
          <button type="button" onClick={onClose} className="btn-primary">
            Close
          </button>
        </div>
      </div>
    </div>
  );
};
