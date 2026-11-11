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

  const goalText = plan.goal || (plan as any).summary || (plan as any).action_type || 'Customer Inquiry Resolution';
  const tools = plan.tools || [];
  const outcomeText = plan.outcome || (plan as any).summary || 'Awaiting customer response';
  const memoryUsed = plan.memory_used || [];

  return (
    <div className="plan-card">
      <div className="plan-card-title">Agent Turn Plan (3 Fields)</div>

      <div className="plan-field">
        <div className="plan-field-label">Goal</div>
        <div style={{ fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>
          {goalText}
        </div>
      </div>

      <div className="plan-field">
        <div className="plan-field-label">Tools Called</div>
        <div style={{ marginTop: '2px' }}>
          {tools.length > 0 ? (
            tools.map((t) => (
              <span key={t} className="tool-chip">
                {t}()
              </span>
            ))
          ) : (
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>None (fast-path rule gate)</span>
          )}
        </div>
      </div>

      <div className="plan-field">
        <div className="plan-field-label">Outcome</div>
        <div style={{ color: 'var(--text-main)', marginTop: '2px' }}>
          {outcomeText}
        </div>
      </div>

      {memoryUsed.length > 0 && (
        <div className="plan-field" style={{ marginTop: '8px', borderTop: '1px dashed #e2e0db', paddingTop: '6px' }}>
          <div className="plan-field-label">Customer Memory Used</div>
          <div style={{ marginTop: '2px' }}>
            {memoryUsed.map((m) => (
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
