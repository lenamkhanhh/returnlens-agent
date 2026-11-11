import React, { useState } from 'react';
import { api } from '../../api/client';
import { CourierEventRequest } from '../../types';

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
          Simulate courier webhook events, inject counterfactual tracking facts (S02), and reset demo data.
        </div>
      </div>

      <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '20px' }}>
        {/* Card 1: Courier Webhook Event Simulation */}
        <div className="seller-col">
          <div className="col-header">
            <h3>🚚 Fire courier event</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>POST /api/operator/courier-events</span>
          </div>

          <form onSubmit={handleFireCourierEvent} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                Shipment / Order ID:
              </label>
              <input
                type="text"
                className="select-field"
                value={shipmentId}
                onChange={(e) => setShipmentId(e.target.value)}
                required
              />
            </div>

            <div style={{ display: 'grid', gridTemplateColumns: '1fr 1fr', gap: '10px' }}>
              <div>
                <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                  Event Type:
                </label>
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

              <div>
                <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                  Attempt No:
                </label>
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

            <div>
              <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                Reason Code:
              </label>
              <select
                className="select-field"
                value={reason}
                onChange={(e) => setReason(e.target.value)}
              >
                <option value="customer_not_available">customer_not_available</option>
                <option value="door_locked">door_locked</option>
                <option value="address_incomplete">address_incomplete</option>
                <option value="warehouse_inward_scan">warehouse_inward_scan (RETURN_RECEIVED)</option>
              </select>
            </div>

            <button type="submit" className="btn-primary" style={{ marginTop: '4px' }}>
              Dispatch Courier Webhook
            </button>

            {courierResult && (
              <div style={{ fontSize: '12px', fontWeight: 600, color: courierResult.startsWith('✓') ? 'var(--pine-green)' : 'var(--terracotta)' }}>
                {courierResult}
              </div>
            )}
          </form>
        </div>

        {/* Card 2: Counterfactual Tracking Injection */}
        <div className="seller-col">
          <div className="col-header">
            <h3>🔄 Counterfactual tracking</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>Change order facts live</span>
          </div>

          <form onSubmit={handleUpdateTracking} style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
            <div>
              <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                Target Order:
              </label>
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

            <div>
              <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                New Shipment Status:
              </label>
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

            <div>
              <label style={{ fontSize: '11px', fontWeight: 700, color: 'var(--text-muted)' }}>
                Delivered Date (YYYY-MM-DD):
              </label>
              <input
                type="text"
                className="select-field"
                value={deliveredDate}
                onChange={(e) => setDeliveredDate(e.target.value)}
                placeholder="e.g. 2026-10-25 for >7 days late"
              />
              <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
                Set to 2026-10-25 to test return window violation (P_WINDOW FAIL).
              </span>
            </div>

            <button type="submit" className="btn-primary" style={{ marginTop: '4px' }}>
              Inject Fact Update
            </button>

            {trackingResult && (
              <div style={{ fontSize: '12px', fontWeight: 600, color: trackingResult.startsWith('✓') ? 'var(--pine-green)' : 'var(--terracotta)' }}>
                {trackingResult}
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
            <h3>🧹 Reset Demo Database</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>POST /api/operator/reset</span>
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
            <div style={{ fontSize: '12px', fontWeight: 600, color: resetMessage.startsWith('✓') ? 'var(--pine-green)' : 'var(--terracotta)' }}>
              {resetMessage}
            </div>
          )}
        </div>

        {/* Card 4: System Provenance & Configuration */}
        <div className="seller-col">
          <div className="col-header">
            <h3>⚙️ System Provenance</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>Deterministic State</span>
          </div>

          <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', fontSize: '12px' }}>
            <div className="fact-row">
              <span className="fact-label">Agent Engine:</span>
              <span className="fact-value">ReturnLens Core v1.0</span>
            </div>
            <div className="fact-row">
              <span className="fact-label">Clock (DEMO_TODAY):</span>
              <span className="fact-value">2026-11-11 (Asia/Kolkata)</span>
            </div>
            <div className="fact-row">
              <span className="fact-label">Primary Vision Model:</span>
              <span className="fact-value">gemini-2.5-flash</span>
            </div>
            <div className="fact-row">
              <span className="fact-label">Audio Transcriber:</span>
              <span className="fact-value">Hindi / Hinglish / English</span>
            </div>
            <div className="fact-row">
              <span className="fact-label">Reliability Benchmark:</span>
              <span className="fact-value" style={{ color: 'var(--pine-green)' }}>
                10 Scenarios (k=5)
              </span>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};
