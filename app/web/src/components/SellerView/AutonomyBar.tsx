import React, { useState } from 'react';
import { AutonomyPolicy, CaseType, AutonomyLevel } from '../../types';
import { formatPaise } from '../../utils/format';

interface AutonomyBarProps {
  policy: AutonomyPolicy | null;
  onUpdatePolicy: (policy: Partial<AutonomyPolicy>) => Promise<void>;
  onKillSwitch: () => Promise<void>;
  onOpenWhy: () => void;
  activeCaseId?: string;
}

const CASE_TYPES: CaseType[] = ['WISMO', 'DAMAGE', 'MISMATCH', 'UNCLEAR', 'LATE', 'NDR'];

export const AutonomyBar: React.FC<AutonomyBarProps> = ({
  policy,
  onUpdatePolicy,
  onKillSwitch,
  onOpenWhy,
  activeCaseId,
}) => {
  const [updating, setUpdating] = useState(false);
  const [lockError, setLockError] = useState<string | null>(null);

  if (!policy) return null;

  const isKilled = policy.kill_switch;

  const handleLevelChange = async (caseType: CaseType, newLevel: AutonomyLevel) => {
    setLockError(null);
    setUpdating(true);
    try {
      await onUpdatePolicy({
        levels: {
          ...policy.levels,
          [caseType]: newLevel,
        },
      });
    } catch (err: any) {
      if (err.code === 'reliability_locked' || err.status === 422) {
        setLockError(err.userMessage || `${caseType} is locked: Reliability benchmark < 5/5`);
      } else {
        alert(err.userMessage || err.message || 'Failed to update policy');
      }
    } finally {
      setUpdating(false);
    }
  };

  return (
    <div
      id="autonomy-bar"
      className="autonomy-bar-container"
      style={{
        background: isKilled ? '#fee2e2' : '#ffffff',
        border: `1px solid ${isKilled ? '#ef4444' : '#e2e0db'}`,
        borderRadius: '6px',
        padding: '12px 18px',
        marginBottom: '16px',
        display: 'flex',
        flexDirection: 'column',
        gap: '10px',
      }}
    >
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <strong style={{ fontSize: '13px', textTransform: 'uppercase', letterSpacing: '0.5px', color: isKilled ? '#b91c1c' : 'var(--pine-green)' }}>
            🛡️ Autonomy Bar
          </strong>

          <span
            className={`badge ${isKilled ? 'badge-fail' : 'badge-pass'}`}
            style={{ fontSize: '11px' }}
          >
            {isKilled ? 'KILL SWITCH ENGAGED (ALL L0)' : 'AUTONOMY ACTIVE'}
          </span>

          <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Caps: <strong>{formatPaise(policy.per_order_cap_minor)}</strong> / order ·{' '}
            <strong>{formatPaise(policy.per_customer_daily_cap_minor)}</strong> / customer / day
          </span>
        </div>

        <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
          {activeCaseId && (
            <button
              type="button"
              onClick={onOpenWhy}
              style={{
                background: 'var(--pine-green-light)',
                color: 'var(--pine-green)',
                borderColor: '#b7dcce',
                fontWeight: 700,
                fontSize: '12px',
                padding: '4px 10px',
              }}
              title="Inspect 7-Step Autonomy Evaluation Checklist (23 W4)"
            >
              ❓ "Why?" Checklist
            </button>
          )}

          <button
            type="button"
            onClick={onKillSwitch}
            className={isKilled ? '' : 'btn-danger'}
            style={{
              padding: '4px 12px',
              fontSize: '12px',
              fontWeight: 700,
            }}
          >
            {isKilled ? '⚠️ Autonomy Killed' : '⚡ Kill Switch'}
          </button>
        </div>
      </div>

      {/* Case Types Ladder */}
      <div
        style={{
          display: 'grid',
          gridTemplateColumns: 'repeat(6, 1fr)',
          gap: '8px',
          alignItems: 'center',
        }}
      >
        {CASE_TYPES.map((ct) => {
          const currentLevel = policy.levels[ct] || 'L0';
          // Reliability gate from the backend (reliability.json + agent_version); L2/L3 need 5/5.
          const lock = policy.lock_status?.[ct];
          const isLocked = lock ? !lock.eligible_for_l2_l3 : false;

          return (
            <div
              key={ct}
              style={{
                background: isKilled ? '#ffffff' : '#fbfbfa',
                border: 'var(--border-thin)',
                borderRadius: '4px',
                padding: '6px 8px',
                fontSize: '11.5px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <strong style={{ color: 'var(--text-main)' }}>{ct}</strong>
                <span
                  style={{
                    fontWeight: 700,
                    color: currentLevel === 'L0' ? 'var(--text-muted)' : 'var(--pine-green)',
                  }}
                >
                  {currentLevel}
                </span>
              </div>

              {isLocked && (
                <div
                  title={lock?.status_message}
                  style={{ color: 'var(--terracotta)', fontSize: '10px', fontWeight: 600, marginBottom: '2px' }}
                >
                  🔒 L2/L3 locked (below 5/5)
                </div>
              )}
              {(
                <select
                  value={currentLevel}
                  onChange={(e) => handleLevelChange(ct, e.target.value as AutonomyLevel)}
                  disabled={updating || isKilled}
                  style={{
                    width: '100%',
                    padding: '2px 4px',
                    fontSize: '11px',
                    border: 'var(--border-thin)',
                    borderRadius: '2px',
                  }}
                >
                  <option value="L0">L0 (Draft)</option>
                  <option value="L1">L1 (Inform)</option>
                  <option value="L2" disabled={isLocked}>L2 (Act)</option>
                  <option value="L3" disabled={isLocked}>L3 (Refund)</option>
                </select>
              )}
            </div>
          );
        })}
      </div>

      {lockError && (
        <div style={{ fontSize: '11.5px', color: 'var(--terracotta)', fontWeight: 600 }}>
          ⚠️ {lockError}
        </div>
      )}
    </div>
  );
};
