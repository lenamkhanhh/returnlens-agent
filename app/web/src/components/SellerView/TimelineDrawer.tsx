import React, { useState } from 'react';
import { AuditEvent } from '../../types';
import { getHumanEventLabel } from '../../utils/timelineLabels';
import { formatDate } from '../../utils/format';

interface TimelineDrawerProps {
  isOpen: boolean;
  onClose: () => void;
  events: AuditEvent[];
  caseId: string;
}

export const TimelineDrawer: React.FC<TimelineDrawerProps> = ({
  isOpen,
  onClose,
  events,
  caseId,
}) => {
  const [expandedSeqMap, setExpandedSeqMap] = useState<Record<number, boolean>>({});

  if (!isOpen) return null;

  const toggleExpand = (seq: number) => {
    setExpandedSeqMap((prev) => ({
      ...prev,
      [seq]: !prev[seq],
    }));
  };

  const sortedEvents = [...events].sort((a, b) => a.seq - b.seq);

  return (
    <div className="timeline-drawer">
      <div className="drawer-header">
        <div>
          <h3 style={{ fontSize: '15px', fontWeight: 700, color: 'var(--pine-green)' }}>
            Case Audit Timeline
          </h3>
          <span style={{ fontSize: '11px', color: 'var(--text-light)', fontFamily: 'monospace' }}>
            {caseId} · Sequential Event Ledger
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

      <div className="drawer-body">
        {sortedEvents.length === 0 ? (
          <div style={{ textAlign: 'center', color: 'var(--text-light)', fontSize: '13px', marginTop: '40px' }}>
            No audit events recorded for this case yet.
          </div>
        ) : (
          sortedEvents.map((evt) => {
            const label = getHumanEventLabel(evt);
            const isExpanded = !!expandedSeqMap[evt.seq];

            return (
              <div key={evt.event_id || evt.seq} className="timeline-event-item">
                <div className="timeline-event-label">{label}</div>

                <div className="timeline-event-meta">
                  <span>Seq #{evt.seq}</span> · <span>Actor: {evt.actor}</span> · <span>{formatDate(evt.recorded_at)}</span>
                </div>

                <button
                  type="button"
                  className="timeline-details-toggle"
                  onClick={() => toggleExpand(evt.seq)}
                >
                  {isExpanded ? 'Hide Raw Details ▲' : 'Inspect Safe Args ▼'}
                </button>

                {isExpanded && (
                  <div className="timeline-redacted-args">
                    <div style={{ fontWeight: 600, color: 'var(--pine-green)', marginBottom: '2px' }}>
                      Event: {evt.event_type} (Outcome: {evt.outcome})
                    </div>
                    {JSON.stringify(evt.safe_payload, null, 2)}
                  </div>
                )}
              </div>
            );
          })
        )}
      </div>
    </div>
  );
};
