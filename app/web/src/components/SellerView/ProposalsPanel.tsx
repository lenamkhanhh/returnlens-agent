import React, { useState } from 'react';
import { Proposal } from '../../types';
import { formatPaise } from '../../utils/format';
import { ApprovalModal } from './ApprovalModal';

interface ProposalsPanelProps {
  proposals: Proposal[];
  onDecide: (proposalId: string, decision: 'approve' | 'decline' | 'manual_review', payloadHash: string, idempotencyKey: string) => Promise<any>;
}

export const ProposalsPanel: React.FC<ProposalsPanelProps> = ({
  proposals,
  onDecide,
}) => {
  const [selectedProposal, setSelectedProposal] = useState<Proposal | null>(null);
  const [staleError, setStaleError] = useState<string | null>(null);
  const [blockedError, setBlockedError] = useState<{ code: string; message: string } | null>(null);
  const [successMsg, setSuccessMsg] = useState<string | null>(null);

  const handleConfirmDecision = async (
    decision: 'approve' | 'decline' | 'manual_review',
    payloadHash: string,
    idempotencyKey: string
  ) => {
    if (!selectedProposal) return;
    setStaleError(null);
    setBlockedError(null);
    setSuccessMsg(null);

    try {
      const res = await onDecide(selectedProposal.proposal_id, decision, payloadHash, idempotencyKey);
      setSuccessMsg(`Action executed successfully! (ID: ${res.action_id || 'ACT-OK'}, status: ${res.status || 'succeeded'})`);
    } catch (err: any) {
      if (err.status === 409 || err.code === 'stale_proposal') {
        setStaleError(err.userMessage || '409 Conflict: Proposal is stale. The underlying order, evidence, or store policy basis has changed.');
      } else if (err.status === 422 || err.code?.startsWith('P_')) {
        setBlockedError({
          code: err.code || '422_BLOCKED',
          message: err.userMessage || '422 Unprocessable Entity: Action blocked by domain guardrails (e.g. balance or cap exceeded).',
        });
      } else {
        alert(err.userMessage || err.message || 'Operation failed');
      }
      throw err;
    }
  };

  return (
    <div>
      <div className="col-header" style={{ marginBottom: '10px' }}>
        <h3>Action Proposals ({proposals.length})</h3>
        <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>
          Immutable Action Drafts
        </span>
      </div>

      {/* 409 Stale Alert */}
      {staleError && (
        <div className="alert-box alert-409">
          <strong>⚠️ 409 Conflict — Stale Proposal</strong>
          <div>{staleError}</div>
          <button
            type="button"
            onClick={() => setStaleError(null)}
            style={{ alignSelf: 'flex-start', marginTop: '4px', fontSize: '11px', padding: '2px 8px' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* 422 Blocked Alert */}
      {blockedError && (
        <div className="alert-box alert-422">
          <strong>🚫 422 Blocked — Policy Gate {blockedError.code}</strong>
          <div>{blockedError.message}</div>
          <div style={{ fontSize: '11px', color: 'var(--terracotta)', marginTop: '2px' }}>
            Domain guardrails prevent this mutation from executing on the ledger.
          </div>
          <button
            type="button"
            onClick={() => setBlockedError(null)}
            style={{ alignSelf: 'flex-start', marginTop: '4px', fontSize: '11px', padding: '2px 8px' }}
          >
            Dismiss
          </button>
        </div>
      )}

      {/* Success Notification */}
      {successMsg && (
        <div style={{ background: 'var(--pine-green-light)', border: '1px solid #b7dcce', color: 'var(--pine-green)', padding: '8px 12px', borderRadius: '4px', fontSize: '12.5px', marginBottom: '10px' }}>
          ✓ {successMsg}
        </div>
      )}

      {proposals.length === 0 ? (
        <div style={{ padding: '16px', textAlign: 'center', color: 'var(--text-light)', fontSize: '12px', background: '#fbfbfa', borderRadius: '4px', border: 'var(--border-thin)' }}>
          No pending proposals. Agent has not formulated an authorized next step yet.
        </div>
      ) : (
        proposals.map((prop) => {
          const isPending = prop.status === 'pending';

          return (
            <div key={prop.proposal_id} className="proposal-box">
              <div className="proposal-action">
                <span>{prop.action_type}</span>
                {prop.amount_minor !== undefined && (
                  <span style={{ color: 'var(--terracotta)', fontWeight: 700 }}>
                    {formatPaise(prop.amount_minor)}
                  </span>
                )}
              </div>

              {prop.item_id && (
                <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginBottom: '4px' }}>
                  Target: <strong>{prop.item_id}</strong>
                </div>
              )}

              <div className="proposal-preview">
                "{prop.reply_preview}"
              </div>

              <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                <span
                  className={`badge ${
                    prop.status === 'approved'
                      ? 'badge-pass'
                      : prop.status === 'declined'
                      ? 'badge-fail'
                      : 'badge-waiting'
                  }`}
                >
                  {prop.status}
                </span>

                {isPending && (
                  <div style={{ display: 'flex', gap: '6px' }}>
                    <button
                      type="button"
                      className="btn-primary"
                      onClick={() => setSelectedProposal(prop)}
                      style={{ padding: '4px 10px', fontSize: '12px' }}
                    >
                      Review & Approve
                    </button>
                  </div>
                )}
              </div>
            </div>
          );
        })
      )}

      {/* Test Error Triggers for Demo Verification */}
      <div style={{ marginTop: '14px', paddingTop: '10px', borderTop: '1px dashed #e2e0db' }}>
        <div style={{ fontSize: '11px', color: 'var(--text-light)', marginBottom: '6px', textTransform: 'uppercase' }}>
          Verify Response Handlers
        </div>
        <div style={{ display: 'flex', gap: '8px' }}>
          <button
            type="button"
            onClick={() => {
              if (proposals[0]) {
                handleConfirmDecision('approve', 'stale', 'test-stale-key');
              } else {
                setStaleError('409 Conflict: Proposal is stale. Order basis has changed since creation.');
              }
            }}
            style={{ fontSize: '11px', padding: '3px 8px' }}
            title="Simulate 409 Conflict response"
          >
            Simulate 409 Stale
          </button>
          <button
            type="button"
            onClick={() => {
              setBlockedError({
                code: 'P_BALANCE',
                message: 'Refund ₹1,800 exceeds remaining refundable balance ₹1,499.',
              });
            }}
            style={{ fontSize: '11px', padding: '3px 8px' }}
            title="Simulate 422 Blocked response"
          >
            Simulate 422 Blocked
          </button>
        </div>
      </div>

      {selectedProposal && (
        <ApprovalModal
          proposal={selectedProposal}
          onClose={() => setSelectedProposal(null)}
          onConfirm={handleConfirmDecision}
        />
      )}
    </div>
  );
};
