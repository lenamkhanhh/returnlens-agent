import React, { useState, useEffect, useRef, useCallback } from 'react';
import { Customer, Order, CaseDetail, CustomerFacingStatus } from '../../types';
import { api } from '../../api/client';
import { mapCaseStateToCustomerStatus } from '../../utils/format';
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
    <div className="customer-layout">
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

      <div className="customer-main">
        <CaseStatusBar
          status={status}
          caseId={activeCase?.case_id}
          errorMessage={errorMessage}
        />

        <ChatThread
          messages={activeCase?.messages || []}
          evidenceList={activeCase?.evidence || []}
        />

        <div className="customer-input-area">
          <div className="input-row">
            <input
              type="text"
              className="text-input"
              placeholder={
                activeCase
                  ? 'Type your reply or question…'
                  : 'Describe your issue (e.g. "Where is my order?")…'
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
              className="btn-primary"
              onClick={handleSend}
              disabled={status === 'sending' || (!inputText.trim() && !pendingFile && !pendingAudio)}
            >
              Send
            </button>
          </div>

          <div className="input-actions-bar">
            <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
              <VoiceRecorder
                onAudioReady={(audio) => setPendingAudio(audio)}
                disabled={status === 'sending'}
              />
              <MediaUploader
                onFileSelected={(file) => setPendingFile(file)}
                disabled={status === 'sending'}
              />
            </div>
            {pendingAudio && (
              <span style={{ fontSize: '11px', color: 'var(--pine-green)', fontWeight: 600 }}>
                🎙️ Voice note ready
              </span>
            )}
          </div>
        </div>
      </div>
    </div>
  );
};
