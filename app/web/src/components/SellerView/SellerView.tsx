import React, { useState, useEffect, useRef, useCallback } from 'react';
import { SellerCaseSummary, CaseDetail, AuditEvent, AutonomyPolicy, AutonomyExplanation } from '../../types';
import { api } from '../../api/client';
import { getStatusBadge } from '../../utils/format';
import { AutonomyBar } from './AutonomyBar';
import { WhyExplanationModal } from './WhyExplanationModal';
import { InboxList } from './InboxList';
import { CaseChatMedia } from './CaseChatMedia';
import { TriadFactsPanel } from './TriadFactsPanel';
import { PolicyChecks } from './PolicyChecks';
import { PlanCard } from './PlanCard';
import { ProposalsPanel } from './ProposalsPanel';
import { TimelineDrawer } from './TimelineDrawer';

export const SellerView: React.FC = () => {
  const urlParams = typeof window !== 'undefined' ? new URLSearchParams(window.location.search) : null;
  const paramCaseId = urlParams?.get('case_id') || null;
  const paramModal = urlParams?.get('modal');

  const [inboxCases, setInboxCases] = useState<SellerCaseSummary[]>([]);
  const [inboxFilter, setInboxFilter] = useState('ALL');
  const [selectedCaseId, setSelectedCaseId] = useState<string | null>(paramCaseId);
  const [activeCase, setActiveCase] = useState<CaseDetail | null>(null);
  const [events, setEvents] = useState<AuditEvent[]>([]);
  const [isTimelineOpen, setIsTimelineOpen] = useState(false);
  const [caseError, setCaseError] = useState<string | null>(null);
  const [inboxError, setInboxError] = useState<string | null>(null);

  // Autonomy state
  const [autonomyPolicy, setAutonomyPolicy] = useState<AutonomyPolicy | null>(null);
  const [whyExplanation, setWhyExplanation] = useState<AutonomyExplanation | null>(null);
  const [isWhyOpen, setIsWhyOpen] = useState(false);

  const [activeSeekSeconds, setActiveSeekSeconds] = useState<number | null>(null);
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const pollingTimerRef = useRef<number | null>(null);

  // 1. Fetch Autonomy Policy & Inbox list
  const refreshInbox = useCallback(async () => {
    try {
      setInboxError(null);
      const [list, policy] = await Promise.all([
        api.getSellerCases(),
        api.getAutonomyPolicy(),
      ]);
      setInboxCases(list);
      setAutonomyPolicy(policy);
      if (!selectedCaseId && list.length > 0) {
        const found = paramCaseId ? list.find(c => c.case_id === paramCaseId) : null;
        setSelectedCaseId(found ? found.case_id : list[0].case_id);
      }
    } catch (err: any) {
      console.error('Failed to load seller inbox:', err);
      setInboxError(err?.userMessage || err?.message || 'Failed to load seller inbox');
    }
  }, [selectedCaseId, paramCaseId]);

  useEffect(() => {
    refreshInbox();
  }, [refreshInbox]);

  // Open Why modal if requested in URL
  useEffect(() => {
    if (paramModal === 'why' && selectedCaseId) {
      api.getAutonomyExplanation(selectedCaseId).then((expl) => {
        setWhyExplanation(expl);
        setIsWhyOpen(true);
      });
    }
  }, [paramModal, selectedCaseId]);

  // 2. Fetch Active Case detail & events
  const refreshActiveCase = useCallback(async (caseId: string) => {
    try {
      setCaseError(null);
      const [detail, evts] = await Promise.all([
        api.getCase(caseId),
        api.getEvents(caseId),
      ]);
      setActiveCase(detail);
      setEvents(evts);
    } catch (err: any) {
      console.error(`Failed to load case ${caseId}:`, err);
      setActiveCase(null);
      setCaseError(err?.userMessage || err?.message || `Failed to load case ${caseId}`);
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
      videoRef.current.play().catch(() => {});
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
    if (selectedCaseId) {
      await refreshActiveCase(selectedCaseId);
    }
    await refreshInbox();
    return res;
  };

  // 6. Autonomy Handlers
  const handleUpdateAutonomy = async (policyUpdate: Partial<AutonomyPolicy>) => {
    const fullPayload = {
      levels: policyUpdate.levels || autonomyPolicy?.levels || {},
      per_order_cap_minor: policyUpdate.per_order_cap_minor ?? autonomyPolicy?.per_order_cap_minor ?? 150000,
      per_customer_daily_cap_minor: policyUpdate.per_customer_daily_cap_minor ?? autonomyPolicy?.per_customer_daily_cap_minor ?? 200000,
    };
    const updated = await api.updateAutonomyPolicy(fullPayload as any);
    setAutonomyPolicy(updated);
  };

  const handleKillSwitch = async () => {
    await api.killAutonomy('Seller manual kill switch');
    const updated = await api.getAutonomyPolicy();
    setAutonomyPolicy(updated);
    if (selectedCaseId) {
      await refreshActiveCase(selectedCaseId);
    }
  };

  const handleOpenWhy = async () => {
    if (!selectedCaseId) return;
    try {
      const expl = await api.getAutonomyExplanation(selectedCaseId);
      setWhyExplanation(expl);
      setIsWhyOpen(true);
    } catch (err) {
      console.error('Failed to get autonomy explanation:', err);
    }
  };

  return (
    <div>
      {/* Autonomy Bar per 17 §6 (trên cùng seller) */}
      <AutonomyBar
        policy={autonomyPolicy}
        onUpdatePolicy={handleUpdateAutonomy}
        onKillSwitch={handleKillSwitch}
        onOpenWhy={handleOpenWhy}
        activeCaseId={selectedCaseId || undefined}
      />

      <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '16px' }}>
        <div>
          <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--pine-green)' }}>
            Seller Review Console
          </h2>
          <div style={{ fontSize: '13px', color: 'var(--text-muted)' }}>
            Review unboxing evidence, verified facts, and authorize dispute resolutions.
          </div>
        </div>

        <button
          type="button"
          onClick={() => setIsTimelineOpen(!isTimelineOpen)}
          style={{ display: 'flex', alignItems: 'center', gap: '6px' }}
        >
          <span>📜</span>
          <span>{isTimelineOpen ? 'Close timeline' : 'Case audit timeline'}</span>
          {events.length > 0 && (
            <span style={{ background: 'var(--pine-green)', color: '#ffffff', borderRadius: '10px', padding: '1px 6px', fontSize: '11px' }}>
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

          {inboxError && (
            <div
              className="error-banner"
              data-testid="inbox-error-state"
              role="alert"
              style={{
                padding: '10px',
                background: '#fef2f2',
                border: '1px solid #f87171',
                borderRadius: '4px',
                color: '#b91c1c',
                fontSize: '12px',
                marginTop: '8px',
              }}
            >
              {inboxError}
            </div>
          )}

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
            <h3>Case facts & evidence</h3>
            {activeCase && (() => {
              const b = getStatusBadge(activeCase.state);
              return (
                <span className={`badge ${b.className}`}>
                  {b.label}
                </span>
              );
            })()}
          </div>

          {caseError && (
            <div
              className="error-banner"
              data-testid="case-error-state"
              role="alert"
              style={{
                padding: '14px',
                background: '#fef2f2',
                border: '1px solid #f87171',
                borderRadius: '6px',
                color: '#b91c1c',
                fontSize: '13px',
                marginBottom: '12px',
              }}
            >
              <strong>Error Loading Case:</strong> {caseError}
            </div>
          )}

          {activeCase ? (
            <>
              <TriadFactsPanel
                caseDetail={activeCase}
                onSeekToTimestamp={handleSeekToTimestamp}
              />
              <PolicyChecks checks={activeCase.policy_checks} />
            </>
          ) : (
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-light)', fontSize: '13px' }}>
              Select a case from the inbox to inspect facts and evidence.
            </div>
          )}
        </div>

        {/* Column 3: Plan Cards & Proposals Panel */}
        <div className="seller-col">
          <div className="col-header">
            <h3>Plan & proposals</h3>
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
            <div style={{ padding: '32px', textAlign: 'center', color: 'var(--text-light)', fontSize: '13px' }}>
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

      {isWhyOpen && (
        <WhyExplanationModal
          explanation={whyExplanation}
          onClose={() => setIsWhyOpen(false)}
        />
      )}
    </div>
  );
};
