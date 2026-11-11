import React, { useState } from 'react';
import { AutonomyPolicy, CaseType, AutonomyLevel } from '../../types';
import { formatPaise, getCaseTypePassDisplay } from '../../utils/format';

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
  const agentVersionShort = (policy.agent_version || '071a86f2').slice(0, 8);
  const modelId = policy.model_id || 'gemini-3.5-flash-lite';

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
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start' }}>
        <div>
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <strong style={{ fontSize: '14px', letterSpacing: '-0.2px', color: isKilled ? '#b91c1c' : 'var(--pine-green)' }}>
              🛡️ Autonomy bar
            </strong>

            <span
              className={`badge ${isKilled ? 'badge-blocked' : 'badge-resolved'}`}
              style={{ fontSize: '12px' }}
            >
              {isKilled ? 'Kill switch active (all L0)' : 'Autonomy active'}
            </span>

            <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
              Caps: <strong>{formatPaise(policy.per_order_cap_minor)}</strong> / order ·{' '}
              <strong>{formatPaise(policy.per_customer_daily_cap_minor)}</strong> / customer / day
            </span>
          </div>

          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '3px' }}>
            Measured on this exact code · <code style={{ fontWeight: 600 }}>{agentVersionShort}</code> · <code style={{ fontWeight: 600 }}>{modelId}</code> · k=5
          </div>
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
                fontWeight: 600,
                fontSize: '12px',
                padding: '4px 10px',
              }}
              title="Inspect 7-step autonomy evaluation checklist"
            >
              ❓ Why did it stop?
            </button>
          )}

          <button
            type="button"
            onClick={onKillSwitch}
            className={isKilled ? '' : 'btn-danger'}
            style={{
              padding: '4px 12px',
              fontSize: '12px',
              fontWeight: 600,
            }}
          >
            {isKilled ? '⚠️ Autonomy killed' : '⚡ Kill switch'}
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
          const passInfo = getCaseTypePassDisplay(lock);

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

              <div
                title={lock?.status_message || (isLocked ? 'Locked' : 'All scenarios passed')}
                style={{
                  color: isLocked ? 'var(--terracotta)' : 'var(--pine-green)',
                  fontSize: '10px',
                  fontWeight: 600,
                  marginBottom: '2px',
                  whiteSpace: 'nowrap',
                  overflow: 'hidden',
                  textOverflow: 'ellipsis',
                }}
              >
                {isLocked ? `🔒 ${passInfo.text}` : `✓ ${passInfo.text}`}
              </div>

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
