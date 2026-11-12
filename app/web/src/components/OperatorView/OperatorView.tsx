import React, { useState, useEffect } from 'react';
import { api } from '../../api/client';
import { CourierEventRequest } from '../../types';
import { computeReliabilitySummary } from '../../utils/format';

export const OperatorView: React.FC = () => {
  // 1. Courier Event State
  const [shipmentId, setShipmentId] = useState('SHP-3110');
  const [eventType, setEventType] = useState<'NDR' | 'RETURN_RECEIVED' | 'DELAYED'>('NDR');
  const [attemptNo, setAttemptNo] = useState(1);
  const [reason, setReason] = useState('customer_not_available');
  const [courierResult, setCourierResult] = useState<string | null>(null);

  // 2. Counterfactual Tracking State
  const [orderId, setOrderId] = useState('ORD-2030');
  const [trackingStatus, setTrackingStatus] = useState('Delivered');
  const [deliveredDate, setDeliveredDate] = useState('2026-11-07');
  const [trackingResult, setTrackingResult] = useState<string | null>(null);

  // 3. Reset Demo State
  const [resetting, setResetting] = useState(false);
  const [resetMessage, setResetMessage] = useState<string | null>(null);

  // 4. Live System Provenance
  const [modelId, setModelId] = useState<string>('');
  const [reliabilitySummary, setReliabilitySummary] = useState<string>('9 of 10 scenarios pass 5/5 (k=5, ffaccd04)');

  useEffect(() => {
    let mounted = true;
    api.getAutonomyPolicy().then((policy) => {
      if (mounted) {
        if (policy.model_id) {
          setModelId(policy.model_id);
        }
        setReliabilitySummary(computeReliabilitySummary(policy));
      }
    }).catch(() => {});
    return () => {
      mounted = false;
    };
  }, []);

  const handleFireCourierEvent = async (e: React.FormEvent) => {
    e.preventDefault();
    setCourierResult(null);
    try {
      const req: CourierEventRequest = {
        shipment_id: shipmentId,
        type: eventType,
        attempt_no: attemptNo,
        reason,
      };
      const res = await api.fireCourierEvent(req);
      setCourierResult(`✓ Event fired successfully! ID: ${res.event_id || 'EVT-OK'}`);
    } catch (err: any) {
      setCourierResult(`✗ Error: ${err.message || 'Failed to fire courier event'}`);
    }
  };

  const handleUpdateTracking = async (e: React.FormEvent) => {
    e.preventDefault();
    setTrackingResult(null);
    try {
      await api.changeTracking(orderId, trackingStatus, deliveredDate);
      setTrackingResult(`✓ Tracking updated for ${orderId}: ${trackingStatus} (${deliveredDate})`);
    } catch (err: any) {
      setTrackingResult(`✗ Error: ${err.message || 'Failed to update tracking'}`);
    }
  };

  const handleResetDemo = async () => {
    if (!confirm('Are you sure you want to reset the demo database? All current cases will revert to seed fixtures.')) {
      return;
    }
    setResetting(true);
    setResetMessage(null);
    try {
      await api.resetDemo();
      setResetMessage('✓ Demo database cleanly reset to seed fixtures.');
    } catch (err: any) {
      setResetMessage(`✗ Error: ${err.message || 'Reset failed'}`);
    } finally {
      setResetting(false);
    }
  };

  return (
    <div style={{ maxWidth: '980px', margin: '0 auto', display: 'flex', flexDirection: 'column', gap: '20px' }}>
      <div>
        <h2 style={{ fontSize: '20px', fontWeight: 700, color: 'var(--pine-green)' }}>
          Operator & Judge Control Console
        </h2>
        <div style={{ fontSize: '12px', color: 'var(--text-muted)' }}>
          Simulate courier webhook events, inject counterfactual tracking updates, and reset demo data.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Card 1: Courier Webhook Event Simulation */}
        <div className="seller-col">
          <div className="col-header">
            <h3>Fire a courier event</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>Dispatch delivery and NDR webhooks</span>
          </div>

          <form onSubmit={handleFireCourierEvent} className="form-stack">
            <div className="field">
              <label className="field-label">Shipment or order ID</label>
              <input
                type="text"
                className="select-field"
                value={shipmentId}
                onChange={(e) => setShipmentId(e.target.value)}
                required
              />
            </div>

            <div className="form-row-2">
              <div className="field">
              <label className="field-label">Event type</label>
                <select
                  className="select-field"
                  value={eventType}
                  onChange={(e) => setEventType(e.target.value as any)}
                >
                  <option value="NDR">NDR (Delivery Failed)</option>
                  <option value="RETURN_RECEIVED">RETURN_RECEIVED</option>
                  <option value="DELAYED">DELAYED</option>
                </select>
              </div>

              <div className="field">
              <label className="field-label">Attempt</label>
                <select
                  className="select-field"
                  value={attemptNo}
                  onChange={(e) => setAttemptNo(parseInt(e.target.value, 10))}
                >
                  <option value={1}>1 of 3</option>
                  <option value={2}>2 of 3</option>
                  <option value={3}>3 of 3</option>
                </select>
              </div>
            </div>

            <div className="field">
              <label className="field-label">Reason code</label>
              <select
                className="select-field"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              >
                <option value="customer_not_available">customer_not_available</option>
                <option value="door_locked">door_locked</option>
                <option value="address_incomplete">address_incomplete</option>
                <option value="warehouse_inward_scan">warehouse_inward_scan (Return received)</option>
              </select>
            </div>

            <button type="submit" className="btn-primary" style={{ marginTop: '4px' }}>
              Dispatch Courier Webhook
            </button>

            {courierResult && (
              <div className={`form-result ${courierResult.startsWith('✓') ? 'ok' : 'err'}`}>
                {courierResult.replace(/^[✓✗] /, '')}
              </div>
            )}
          </form>
        </div>

        {/* Card 2: Counterfactual Tracking Injection */}
        <div className="seller-col">
          <div className="col-header">
            <h3>Change tracking facts</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>Update shipment status and delivery dates live</span>
          </div>

          <form onSubmit={handleUpdateTracking} className="form-stack">
            <div className="field">
              <label className="field-label">Order</label>
              <select
                className="select-field"
                value={orderId}
                onChange={(e) => setOrderId(e.target.value)}
              >
                <option value="ORD-2030">ORD-2030 (WISMO / Dhun Buds)</option>
                <option value="ORD-1042">ORD-1042 (Case A / Dhun Lite)</option>
                <option value="ORD-7729">ORD-7729 (Case B / Dhun Wave)</option>
                <option value="ORD-5150">ORD-5150 (Case C / Dhun Wave)</option>
              </select>
            </div>

            <div className="field">
              <label className="field-label">New shipment status</label>
              <select
                className="select-field"
                value={trackingStatus}
                onChange={(e) => setTrackingStatus(e.target.value)}
              >
                <option value="Delivered">Delivered</option>
                <option value="In transit">In transit</option>
                <option value="Out for delivery">Out for delivery</option>
                <option value="NDR attempt 1">NDR attempt 1</option>
              </select>
            </div>

            <div className="field">
              <label className="field-label">Delivered date (YYYY-MM-DD)</label>
              <input
                type="text"
                className="select-field"
                value={deliveredDate}
                onChange={(e) => setDeliveredDate(e.target.value)}
                placeholder="e.g. 2026-10-25 for >7 days late"
              />
              <span className="field-hint">Use 2026-10-25 to test an expired return window.</span>
            </div>

            <button type="submit" className="btn-primary" style={{ marginTop: '4px' }}>
              Inject Fact Update
            </button>

            {trackingResult && (
              <div className={`form-result ${trackingResult.startsWith('✓') ? 'ok' : 'err'}`}>
                {trackingResult.replace(/^[✓✗] /, '')}
              </div>
            )}
          </form>
        </div>
      </div>

      {/* Row 2: Reset Demo & System Metadata */}
      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Card 3: Reset Demo */}
        <div className="seller-col">
          <div className="col-header">
            <h3>Reset demo</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>Restore seed state</span>
          </div>

          <p style={{ fontSize: '13px', color: 'var(--text-muted)', lineHeight: 1.5 }}>
            Resets the domain database, clears created jobs and uploaded evidence, and restores the pristine cold-open demo seed.
          </p>

          <button
            type="button"
            onClick={handleResetDemo}
            className="btn-danger"
            disabled={resetting}
            style={{ alignSelf: 'flex-start', marginTop: '10px' }}
          >
            {resetting ? 'Resetting…' : 'Reset Database Now'}
          </button>

          {resetMessage && (
            <div className={`form-result ${resetMessage.startsWith('✓') ? 'ok' : 'err'}`}>
                {resetMessage.replace(/^[✓✗] /, '')}
            </div>
          )}
        </div>

        {/* Card 4: System Provenance & Configuration */}
        <div className="seller-col">
          <div className="col-header">
            <h3>System provenance</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>Deterministic state</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
            <div className="fact-row">
              <span className="fact-label">Agent engine</span>
              <span className="fact-value">ReturnLens Core v1.0</span>
            </div>
            <div className="fact-row">
              <span className="fact-label">Demo clock</span>
              <span className="fact-value">2026-11-11 (Asia/Kolkata)</span>
            </div>
            <div className="fact-row">
              <span className="fact-label">Vision model</span>
              <span className="fact-value">{modelId || 'gemini-3.5-flash-lite'}</span>
            </div>
            <div className="fact-row">
              <span className="fact-label">Voice transcription</span>
              <span className="fact-value">Hindi / Hinglish / English</span>
            </div>
            <div className="fact-row">
              <span className="fact-label">Reliability</span>
              <span className="fact-value" style={{ color: 'var(--pine-green)', fontWeight: 600 }}>
                {reliabilitySummary}
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
