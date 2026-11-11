import React from 'react';
import { PlanRecord } from '../../types';

interface PlanCardProps {
  plan: PlanRecord | null;
}

export const PlanCard: React.FC<PlanCardProps> = ({ plan }) => {
  if (!plan) {
    return (
      <div className="plan-card">
        <div className="plan-card-title">Agent plan</div>
        <div style={{ fontSize: '13px', color: 'var(--text-light)', fontStyle: 'italic' }}>
          No active plan yet. Waiting for case activity.
        </div>
      </div>
    );
  }

  const goalText = plan.goal || (plan as any).summary || (plan as any).action_type || 'Customer inquiry resolution';
  const tools = plan.tools || [];
  const outcomeText = plan.outcome || (plan as any).summary || 'Awaiting customer response';
  const memoryUsed = plan.memory_used || [];

  return (
    <div className="plan-card">
      <div className="plan-card-title">Agent plan</div>

      <div className="plan-field">
        <div className="plan-field-label">Goal</div>
        <div style={{ fontWeight: 600, color: 'var(--text-main)', marginTop: '2px' }}>
          {goalText}
        </div>
      </div>

      <div className="plan-field">
        <div className="plan-field-label">Tools called</div>
        <div style={{ marginTop: '2px' }}>
          {tools.length > 0 ? (
            tools.map((t) => (
              <span key={t} className="tool-chip">
                {t}()
              </span>
            ))
          ) : (
            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>None (rules-based resolution)</span>
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
          <div className="plan-field-label">Customer memory used</div>
          <div style={{ marginTop: '2px' }}>
            {memoryUsed.map((m) => (
              <span key={m} className="memory-chip">
                🏷️ {m}
              </span>
            ))}
          </div>
        </div>
      )}

      {plan.model_proposed_step && (
        <div className="plan-field" style={{ marginTop: '8px', borderTop: '1px dashed #e2e0db', paddingTop: '6px' }}>
          <div className="plan-field-label">Model proposal & code gate</div>
          <div style={{ marginTop: '4px', fontSize: '12px', display: 'flex', flexDirection: 'column', gap: '3px' }}>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Model proposed: </span>
              <strong>{plan.model_proposed_step.replace(/_/g, ' ')}</strong>
              {plan.model_reason ? (
                <span style={{ color: 'var(--text-muted)', fontStyle: 'italic' }}> ({plan.model_reason})</span>
              ) : null}
            </div>
            <div>
              <span style={{ color: 'var(--text-muted)' }}>Code gate: </span>
              {plan.agreed ? (
                <span style={{ color: 'var(--pine-green)', fontWeight: 600 }}>
                  allowed{plan.gate_reason ? ` (${plan.gate_reason})` : ''}
                </span>
              ) : (
                <span style={{ color: 'var(--terracotta)', fontWeight: 600 }}>
                  overrode{plan.gate_reason ? ` (${plan.gate_reason})` : (plan.code_decision ? ` (${plan.code_decision.replace(/_/g, ' ')})` : '')}
                </span>
              )}
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
