import React from 'react';
import { PlanRecord } from '../../types';

interface PlanCardProps {
  plan: PlanRecord | null;
}

export const PlanCard: React.FC<PlanCardProps> = ({ plan }) => {
  if (!plan) {
    return (
      <div className="plan-card">
        <div className="plan-card-title">Agent Plan</div>
        <div style={{ fontSize: '12px', color: 'var(--text-light)', fontStyle: 'italic' }}>
          No execution plan generated for this turn yet.
        </div>
      </div>
    );
  }

  return (
    <div className="plan-card">
      <div className="plan-card-title">Agent Turn Plan (3 Fields)</div>

      <div className="plan-field">
        <div className="plan-field-label">Goal</div>
        <div style={{ fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>
          {plan.goal}
        </div>
      </div>

      <div className="plan-field">
        <div className="plan-field-label">Tools Called</div>
        <div style={{ marginTop: '2px' }}>
          {plan.tools.map((t) => (
            <span key={t} className="tool-chip">
              {t}()
            </span>
          ))}
        </div>
      </div>

      <div className="plan-field">
        <div className="plan-field-label">Outcome</div>
        <div style={{ color: 'var(--text-main)', marginTop: '2px' }}>
          {plan.outcome}
        </div>
      </div>

      {plan.memory_used && plan.memory_used.length > 0 && (
        <div className="plan-field" style={{ marginTop: '8px', borderTop: '1px dashed #e2e0db', paddingTop: '6px' }}>
          <div className="plan-field-label">Customer Memory Used</div>
          <div style={{ marginTop: '2px' }}>
            {plan.memory_used.map((m) => (
              <span key={m} className="memory-chip">
                🏷️ {m}
              </span>
            ))}
          </div>
        </div>
      )}
    </div>
  );
};
