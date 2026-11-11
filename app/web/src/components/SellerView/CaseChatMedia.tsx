import React from 'react';
import { Message, Evidence } from '../../types';
import { formatDate } from '../../utils/format';

interface CaseChatMediaProps {
  messages: Message[];
  evidenceList: Evidence[];
  videoRef: React.RefObject<HTMLVideoElement>;
  activeSeekSeconds: number | null;
}

export const CaseChatMedia: React.FC<CaseChatMediaProps> = ({
  messages,
  evidenceList,
  videoRef,
}) => {
  const videoEvidence = evidenceList.find((e) => e.media_type === 'video');
  const audioEvidenceList = evidenceList.filter((e) => e.media_type === 'audio');

  const videoUrl = videoEvidence
    ? (videoEvidence.evidence_id ? `/api/media/${videoEvidence.evidence_id}` : videoEvidence.url)
    : '';

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '14px' }}>
      {/* 1. Evidence Video Player */}
      {videoEvidence && (
        <div>
          <div className="col-header" style={{ marginBottom: '8px' }}>
            <h3>Customer Unboxing Video</h3>
            <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>
              {videoEvidence.filename}
            </span>
          </div>

          <div className="media-container">
            <video
              ref={videoRef}
              controls
              playsInline
              src={videoUrl}
              className="video-player"
            />
          </div>
          <div style={{ fontSize: '11px', color: 'var(--text-muted)', marginTop: '4px' }}>
            💡 Click any observation timestamp in the center panel to seek video.
          </div>
        </div>
      )}

      {/* 2. Audio Voice Notes */}
      {audioEvidenceList.map((audio) => {
        const audioUrl = audio.evidence_id ? `/api/media/${audio.evidence_id}` : audio.url;
        return (
          <div key={audio.evidence_id} style={{ background: '#fbfbfa', padding: '10px', borderRadius: '4px', border: 'var(--border-thin)' }}>
            <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '6px' }}>
              <span style={{ fontSize: '12px', fontWeight: 600 }}>
                🎙️ Voice Note ({audio.language_detected || 'Hindi'})
              </span>
              <span style={{ fontSize: '11px', color: 'var(--text-light)' }}>{audio.filename}</span>
            </div>
            <audio controls src={audioUrl} style={{ width: '100%', height: '32px' }} />
            {audio.transcript && (
              <div style={{ fontSize: '12px', fontStyle: 'italic', marginTop: '6px', color: 'var(--text-main)', background: '#ffffff', padding: '6px', borderRadius: '3px', border: '1px solid #eeede8' }}>
                "{audio.transcript}"
              </div>
            )}
          </div>
        );
      })}

      {/* 3. Case Chat History */}
      <div>
        <div className="col-header" style={{ marginBottom: '8px' }}>
          <h3>Conversation History</h3>
        </div>

        <div style={{ display: 'flex', flexDirection: 'column', gap: '8px', maxHeight: '240px', overflowY: 'auto' }}>
          {messages.map((m) => (
            <div
              key={m.message_id}
              style={{
                padding: '8px 10px',
                borderRadius: '4px',
                background: m.role === 'customer' ? 'var(--pine-green-light)' : '#f3f2ee',
                border: '1px solid #e5e3de',
                fontSize: '12.5px',
              }}
            >
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '2px', fontSize: '11px' }}>
                <strong style={{ color: m.role === 'customer' ? 'var(--pine-green)' : 'var(--text-main)' }}>
                  {m.role === 'customer' ? 'Customer' : 'Agent Assistant'}
                </strong>
                <span style={{ color: 'var(--text-light)' }}>{formatDate(m.created_at)}</span>
              </div>
              <div>{m.text}</div>
            </div>
          ))}
        </div>
      </div>
    </div>
  );
};
