import React from 'react';
import { CustomerFacingStatus } from '../../types';

interface CaseStatusBarProps {
  status: CustomerFacingStatus;
  caseId?: string;
  errorMessage?: string;
}

export const CaseStatusBar: React.FC<CaseStatusBarProps> = ({ status, caseId, errorMessage }) => {
  const getLabelAndDesc = () => {
    switch (status) {
      case 'sending':
        return { label: 'Sending message…', desc: 'Delivering your update to store support' };
      case 'processing':
        return { label: 'Agent is processing', desc: 'Analyzing order tracking, unboxing media, and store policy' };
      case 'waiting for you':
        return { label: 'Waiting for you', desc: 'Please review agent instructions or provide requested evidence' };
      case 'done':
        return { label: 'Case resolved', desc: 'Your request has been processed and concluded' };
      case 'error':
        return { label: 'Error encountered', desc: errorMessage || 'An unexpected issue occurred' };
      default:
        return { label: 'Ready', desc: 'Start a conversation regarding your order' };
    }
  };

  const { label, desc } = getLabelAndDesc();
  const pillClass = status.replace(/\s+/g, '-');

  return (
    <div className="case-status-bar">
      <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
        <div className={`status-pill ${pillClass}`}>
          {(status === 'processing' || status === 'sending') && <span className="status-pulse" />}
          {label}
        </div>
        <span style={{ fontSize: '12px', color: 'var(--text-muted)' }}>{desc}</span>
      </div>
      {caseId && (
        <span style={{ fontSize: '11px', fontFamily: 'monospace', color: 'var(--text-light)' }}>
          Case: {caseId}
        </span>
      )}
    </div>
  );
};
