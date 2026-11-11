import React, { useState, useEffect, useRef, useCallback } from 'react';
import { SellerCaseSummary, CaseDetail, AuditEvent } from '../../types';
import { api } from '../../api/client';
import { InboxList } from './InboxList';
import { CaseChatMedia } from './CaseChatMedia';
import { TriadFactsPanel } from './TriadFactsPanel';
import { PolicyChecks } from './PolicyChecks';
import { PlanCard } from './PlanCard';
import { ProposalsPanel } from './ProposalsPanel';
import { TimelineDrawer } from './TimelineDrawer';

export const SellerView: React.FC = () => {
  const [inboxCases, setInboxCases] = useState<SellerCaseSummary[]>([]);
  const [inboxFilter, setInboxFilter] = useState('ALL');
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(null);
  const [activeCase, setActiveCase] = useState<CaseDetail | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [isTimelineOpen, setIsTimelineOpen] = useState(false);

  const [activeSeekSeconds, setActiveSeekSeconds] = useState<number | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const pollingTimerRef = useRef<number | null>(null);

  // 1. Fetch Inbox list
  const refreshInbox = useCallback(async () => {
    try {
      const list = await api.getSellerCases();
      setInboxCases(list);
      // Auto-select first case if none selected
      if (!selectedCaseId && list.length > 0) {
        setSelectedCaseId(list[0].case_id);
      }
    } catch (err) {
      console.error('Failed to load seller inbox:', err);
    }
  }, [selectedCaseId]);

  useEffect(() => {
    refreshInbox();
  }, [refreshInbox]);

  // 2. Fetch Active Case detail & events
  const refreshActiveCase = useCallback(async (caseId: string) => {
    try {
      const [detail, evts] = await Promise.all([
        api.getCase(caseId),
        api.getEvents(caseId),
      ]);
      setActiveCase(detail);
      setEvents(evts);
    } catch (err) {
      console.error(`Failed to load case ${caseId}:`, err);
    }
  }, []);

  useEffect(() => {
    if (selectedCaseId) {
      refreshActiveCase(selectedCaseId);
    }
  }, [selectedCaseId, refreshActiveCase]);

  // 3. Polling per Card 4 & 17 §8:
  // 1s while processing, 5s while waiting. No optimistic success.
  useEffect(() => {
    if (!selectedCaseId || !activeCase) return;

    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }

    const isProcessing =
      activeCase.state === 'PROCESSING' ||
      activeCase.state === 'NEW' ||
      activeCase.state === 'ACTION_PENDING';

    const intervalMs = isProcessing ? 1000 : 5000;

    pollingTimerRef.current = window.setInterval(() => {
      refreshActiveCase(selectedCaseId);
      refreshInbox();
    }, intervalMs);

    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [selectedCaseId, activeCase?.state, refreshActiveCase, refreshInbox]);

  // 4. Video Seek Handler
  const handleSeekToTimestamp = (seconds: number) => {
    setActiveSeekSeconds(seconds);
    if (videoRef.current) {
      videoRef.current.currentTime = seconds;
      videoRef.current.play().catch(() => {
        // Autoplay policy or video not ready
      });
    }
  };

  // 5. Decision Handler for Proposals
  const handleDecideProposal = async (
    proposalId: string,
    decision: 'approve' | 'decline' | 'manual_review',
    payloadHash: string,
    idempotencyKey: string
  ) => {
    const res = await api.decideProposal(proposalId, decision, payloadHash, idempotencyKey);
    // Refresh both case and inbox to reflect committed state (No optimistic UI!)
    if (selectedCaseId) {
      await refreshActiveCase(selectedCaseId);
    }
    await refreshInbox();
    return res;
  };

  return (
    <div>
      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--pine-green)' }}>
            Seller Review Console
          </h2>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
            Review unboxing evidence, ground-truth observations, and authorize dispute resolutions.
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsTimelineOpen(!isTimelineOpen)}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <span>📜</span>
          <span>{isTimelineOpen ? 'Close Timeline' : 'Open Timeline Drawer'}</span>
          {events.length > 0 && (
            <span style={{ background: 'var(--pine-green)', color: '#ffffff', borderRadius: '10px', padding: '1px 6px', fontSize: '10px' }}>
              {events.length}
            </span>
          )}
        </button>
      </div>

      <div className="seller-layout">
        {/* Column 1: Inbox & Media/Chat */}
        <div className="seller-col">
          <InboxList
            cases={inboxCases}
            selectedCaseId={selectedCaseId}
            onSelectCase={(id) => setSelectedCaseId(id)}
            filter={inboxFilter}
            onFilterChange={(f) => setInboxFilter(f)}
          />

          {activeCase && (
            <CaseChatMedia
              messages={activeCase.messages}
              evidenceList={activeCase.evidence}
              videoRef={videoRef}
              activeSeekSeconds={activeSeekSeconds}
            />
          )}
        </div>

        {/* Column 2: Triad Facts & Policy Checks */}
        <div className="seller-col">
          <div className="col-header">
            <h3>Dispute Ground Truth</h3>
            {activeCase && (
              <span
                className={`badge ${
                  activeCase.state === 'RESOLVED'
                    ? 'badge-pass'
                    : activeCase.state === 'WAITING_SELLER'
                    ? 'badge-waiting'
                    : 'badge-unknown'
                }`}
              >
                {activeCase.state}
              </span>
            )}
          </div>

          {activeCase ? (
            <>
              <TriadFactsPanel
                caseDetail={activeCase}
                onSeekToTimestamp={handleSeekToTimestamp}
              />
              <PolicyChecks checks={activeCase.policy_checks} />
            </>
          ) : (
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-light)' }}>
              Select a case from the inbox to inspect facts and evidence.
            </div>
          )}
        </div>

        {/* Column 3: Plan Cards & Proposals Panel */}
        <div className="seller-col">
          <div className="col-header">
            <h3>Decisions & Plan</h3>
          </div>

          {activeCase ? (
            <>
              <PlanCard plan={activeCase.plan} />
              <ProposalsPanel
                proposals={activeCase.proposals}
                onDecide={handleDecideProposal}
              />
            </>
          ) : (
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-light)' }}>
              No case selected.
            </div>
          )}
        </div>
      </div>

      {activeCase && (
        <TimelineDrawer
          isOpen={isTimelineOpen}
          onClose={() => setIsTimelineOpen(false)}
          events={events}
          caseId={activeCase.case_id}
        />
      )}
    </div>
  );
};
