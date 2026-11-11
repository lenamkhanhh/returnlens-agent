import React, { useState } from 'react';
import { Proposal } from '../../types';
import { formatPaise } from '../../utils/format';

interface ApprovalModalProps {
  proposal: Proposal;
  onClose: () => void;
  onConfirm: (decision: 'approve' | 'decline' | 'manual_review', payloadHash: string, idempotencyKey: string) => Promise<void>;
}

export const ApprovalModal: React.FC<ApprovalModalProps> = ({
  proposal,
  onClose,
  onConfirm,
}) => {
  const [submitting, setSubmitting] = useState(false);
  const [idempotencyKey] = useState(`d-${Math.random().toString(16).slice(2, 10)}`);

  const handleAction = async (decision: 'approve' | 'decline' | 'manual_review') => {
    setSubmitting(true);
    try {
      await onConfirm(decision, proposal.payload_hash, idempotencyKey);
      onClose();
    } catch {
      setSubmitting(false);
    }
  };

  return (
    <div className="modal-overlay" onClick={onClose}>
      <div className="modal-card" onClick={(e) => e.stopPropagation()}>
        <div className="modal-header">
          <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--pine-green)' }}>
            Seller Authorization Required
          </h3>
          <button type="button" onClick={onClose} style={{ border: 'none', background: 'none', fontSize: '16px' }}>
            ✕
          </button>
        </div>

        <div className="modal-body">
          <div style={{ background: '#f8f7f4', padding: '10px 14px', borderRadius: '4px', border: 'var(--border-thin)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
              <span style={{ color: 'var(--text-muted)' }}>Action:</span>
              <strong style={{ color: 'var(--pine-green)', textTransform: 'uppercase' }}>
                {proposal.action_type}
              </strong>
            </div>

            {proposal.item_id && (
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Target SKU:</span>
                <strong>{proposal.item_id}</strong>
              </div>
            )}

            {proposal.amount_minor !== undefined && (
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '4px' }}>
                <span style={{ color: 'var(--text-muted)' }}>Monetary Impact:</span>
                <strong style={{ color: 'var(--terracotta)', fontSize: '14px' }}>
                  {formatPaise(proposal.amount_minor)}
                </strong>
              </div>
            )}

            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginTop: '6px', borderTop: '1px dashed #e2e0db', paddingTop: '6px' }}>
              <span style={{ color: 'var(--text-light)' }}>Payload Hash:</span>
              <code style={{ color: 'var(--text-muted)' }}>{proposal.payload_hash}</code>
            </div>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '11px', marginTop: '2px' }}>
              <span style={{ color: 'var(--text-light)' }}>Idempotency Key:</span>
              <code style={{ color: 'var(--text-muted)' }}>{idempotencyKey}</code>
            </div>
          </div>

          <div>
            <div style={{ fontSize: '12px', fontWeight: 600, color: 'var(--text-muted)', marginBottom: '4px' }}>
              Reply Preview to Customer:
            </div>
            <div style={{ padding: '8px 12px', background: '#fbfbfa', borderRadius: '4px', borderLeft: '3px solid var(--pine-green)', fontStyle: 'italic', fontSize: '12.5px' }}>
              "{proposal.reply_preview}"
            </div>
          </div>
        </div>

        <div className="modal-footer">
          <button
            type="button"
            onClick={() => handleAction('decline')}
            className="btn-danger"
            disabled={submitting}
          >
            Decline Proposal
          </button>
          <button
            type="button"
            onClick={() => handleAction('approve')}
            className="btn-primary"
            disabled={submitting}
          >
            {submitting ? 'Executing Mutation…' : 'Approve Action'}
          </button>
        </div>
      </div>
    </div>
  );
};
