import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Customer, Order, CaseDetail, CustomerFacingStatus } from '../../types';
import { api } from '../../api/client';
import { mapCaseStateToCustomerStatus, formatSecondsToTimestamp } from '../../utils/format';
import { CustomerSelector } from './CustomerSelector';
import { CaseStatusBar } from './CaseStatusBar';
import { ChatThread } from './ChatThread';
import { VoiceRecorder } from './VoiceRecorder';
import { MediaUploader } from './MediaUploader';
import { RecordedAudio } from '../../utils/audioRecorder';

export const CustomerView: React.FC = () => {
  const [customers, setCustomers] = useState<Customer[]>([]);
  const [selectedCustomer, setSelectedCustomer] = useState<Customer | null>(null);
  const [orders, setOrders] = useState<Order[]>([]);
  const [selectedOrder, setSelectedOrder] = useState<Order | null>(null);

  const [activeCase, setActiveCase] = useState<CaseDetail | null>(null);
  const [status, setStatus] = useState<CustomerFacingStatus>('new conversation');
  const [errorMessage, setErrorMessage] = useState<string | undefined>(undefined);

  const [inputText, setInputText] = useState('');
  const [pendingFile, setPendingFile] = useState<File | null>(null);
  const [pendingAudio, setPendingAudio] = useState<RecordedAudio | null>(null);

  const pollingTimerRef = useRef<number | null>(null);

  // 1. Load Customers on mount
  useEffect(() => {
    api.getCustomers().then((custs) => {
      setCustomers(custs);
      if (custs.length > 0) {
        setSelectedCustomer(custs[0]); // Default to Priya Sharma (CUS-01, WISMO ORD-2030)
      }
    });
  }, []);

  // 2. Load Orders when Customer changes
  useEffect(() => {
    if (!selectedCustomer) return;
    api.getOrders(selectedCustomer.customer_id).then((ordList) => {
      setOrders(ordList);
      if (ordList.length > 0) {
        setSelectedOrder(ordList[0]);
      } else {
        setSelectedOrder(null);
      }
    });
  }, [selectedCustomer]);

  // Function to refresh current case snapshot from server
  const refreshCase = useCallback(async (caseId: string) => {
    try {
      const detail = await api.getCase(caseId);
      setActiveCase(detail);
      const nextStatus = mapCaseStateToCustomerStatus(detail.state);
      setStatus(nextStatus);
      return detail;
    } catch (err: any) {
      setStatus('error');
      setErrorMessage(err.userMessage || err.message || 'Failed to fetch case update');
      return null;
    }
  }, []);

  // Polling per Card 4 & 17 §8:
  // 1s while processing, 5s while waiting. No optimistic success.
  useEffect(() => {
    if (!activeCase?.case_id) return;

    if (pollingTimerRef.current) {
      clearInterval(pollingTimerRef.current);
      pollingTimerRef.current = null;
    }

    const isProcessing = status === 'processing' || status === 'sending';
    const intervalMs = isProcessing ? 1000 : 5000;

    if (status !== 'done') {
      pollingTimerRef.current = window.setInterval(() => {
        refreshCase(activeCase.case_id);
      }, intervalMs);
    }

    return () => {
      if (pollingTimerRef.current) {
        clearInterval(pollingTimerRef.current);
        pollingTimerRef.current = null;
      }
    };
  }, [activeCase?.case_id, status, refreshCase]);

  // Load existing case if order is already linked to one
  useEffect(() => {
    if (!selectedOrder) {
      setActiveCase(null);
      setStatus('new conversation');
      return;
    }

    api.getSellerCases().then(async (cases) => {
      const match = cases.find((c) => c.order_id === selectedOrder.order_id);
      if (match) {
        await refreshCase(match.case_id);
      } else {
        setActiveCase(null);
        setStatus('new conversation');
      }
    });
  }, [selectedOrder, refreshCase]);

  // Handle Send Action
  const handleSend = async () => {
    if (!selectedOrder) return;
    if (!inputText.trim() && !pendingFile && !pendingAudio) return;

    setStatus('sending');
    setErrorMessage(undefined);

    try {
      let caseId = activeCase?.case_id;
      let textToSend = inputText.trim();
      const attachmentIds: string[] = [];

      // 1. If no case exists yet, create one
      if (!caseId) {
        const createRes = await api.createCase(
          selectedOrder.order_id,
          textToSend || 'Inquiry regarding received package',
          `c-${Date.now().toString(16)}`
        );
        caseId = createRes.case_id;
      }

      // 2. Upload pending media if any
      if (pendingFile && caseId) {
        const uploaded = await api.uploadEvidence(caseId, pendingFile);
        attachmentIds.push(uploaded.evidence_id);
      }

      if (pendingAudio && caseId) {
        const audioFile = new File(
          [pendingAudio.blob],
          `voice-note-${Date.now()}.${pendingAudio.mimeType.includes('mp4') ? 'mp4' : 'webm'}`,
          { type: pendingAudio.mimeType }
        );
        const uploaded = await api.uploadEvidence(caseId, audioFile);
        attachmentIds.push(uploaded.evidence_id);
      }

      // 3. Send message if existing case and extra text is appended
      if (activeCase && textToSend) {
        await api.sendMessage(caseId, textToSend, attachmentIds);
      }

      // Clear input buffers
      setInputText('');
      setPendingFile(null);
      setPendingAudio(null);

      // Refresh real state from server (No optimistic UI!)
      await refreshCase(caseId);
    } catch (err: any) {
      setStatus('error');
      setErrorMessage(err.userMessage || err.message || 'Failed to submit request');
    }
  };

  return (
    <div className="customer-layout messaging-portal-layout">
      {/* 1. Small "demo: choose customer/order" strip above the phone */}
      <CustomerSelector
        customers={customers}
        selectedCustomer={selectedCustomer}
        onSelectCustomer={(c) => {
          setSelectedCustomer(c);
          setActiveCase(null);
          setStatus('new conversation');
        }}
        orders={orders}
        selectedOrder={selectedOrder}
        onSelectOrder={(o) => {
          setSelectedOrder(o);
          setActiveCase(null);
          setStatus('new conversation');
        }}
      />

      {/* 2. Phone-width chat column centred on the page */}
      <div className="messaging-phone-frame">
        {/* Header with shop name "Dhun Audio" + "online" */}
        <div className="phone-header">
          <div className="phone-header-left">
            <div className="phone-avatar">
              <span className="avatar-icon">🎧</span>
              <span className="avatar-status-dot" />
            </div>
            <div className="phone-meta">
              <div className="phone-shop-name">Dhun Audio</div>
              <div className="phone-shop-status">
                <span className="online-dot" /> online
              </div>
            </div>
          </div>

          <div className="phone-header-right">
            {activeCase?.case_id ? (
              <span className="case-id-chip">
                {activeCase.case_id}
              </span>
            ) : (
              <span className="case-id-chip">Verified Shop</span>
            )}
          </div>
        </div>

        {/* Case Status Notice */}
        <CaseStatusBar
          status={status}
          caseId={activeCase?.case_id}
          errorMessage={errorMessage}
        />

        {/* Message bubbles list */}
        <ChatThread
          messages={activeCase?.messages || []}
          evidenceList={activeCase?.evidence || []}
          isProcessing={status === 'processing' || status === 'sending'}
        />

        {/* Pending media preview chips */}
        {(pendingFile || pendingAudio) && (
          <div className="staged-media-bar">
            {pendingFile && (
              <div className="staged-chip">
                <span>📎 {pendingFile.name}</span>
                <button
                  type="button"
                  onClick={() => setPendingFile(null)}
                  className="chip-remove-btn"
                  title="Remove attachment"
                >
                  ✕
                </button>
              </div>
            )}
            {pendingAudio && (
              <div className="staged-chip">
                <span>🎙️ Voice Note ({formatSecondsToTimestamp(pendingAudio.durationSeconds)})</span>
                <button
                  type="button"
                  onClick={() => setPendingAudio(null)}
                  className="chip-remove-btn"
                  title="Discard voice note"
                >
                  ✕
                </button>
              </div>
            )}
          </div>
        )}

        {/* Bottom messaging input bar */}
        <div className="customer-input-area messaging-input-area">
          <div className="messaging-input-row">
            <div className="messaging-action-buttons">
              <MediaUploader
                onFileSelected={(file) => setPendingFile(file)}
                disabled={status === 'sending'}
              />
              <VoiceRecorder
                onAudioReady={(audio) => setPendingAudio(audio)}
                disabled={status === 'sending'}
              />
            </div>

            <input
              type="text"
              className="text-input messaging-input-field"
              placeholder={
                activeCase
                  ? 'Type a message…'
                  : 'Type a message (e.g. "Where is my order?")…'
              }
              value={inputText}
              onChange={(e) => setInputText(e.target.value)}
              onKeyDown={(e) => {
                if (e.key === 'Enter' && !e.shiftKey) {
                  e.preventDefault();
                  handleSend();
                }
              }}
              disabled={status === 'sending'}
            />

            <button
              type="button"
              className="btn-primary messaging-send-btn"
              onClick={handleSend}
              disabled={status === 'sending' || (!inputText.trim() && !pendingFile && !pendingAudio)}
              title="Send message"
            >
              ➤
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};
