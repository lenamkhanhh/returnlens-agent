import React, { useEffect, useRef } from 'react';
import { Message, Evidence } from '../../types';
import { formatDate } from '../../utils/format';

interface ChatThreadProps {
  messages: Message[];
  evidenceList: Evidence[];
}

export const ChatThread: React.FC<ChatThreadProps> = ({ messages, evidenceList }) => {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages]);

  return (
    <div className="chat-thread">
      {messages.length === 0 ? (
        <div style={{ textAlign: 'center', color: 'var(--text-light)', marginTop: '40px', fontSize: '13px' }}>
          No messages yet. Send a message or record a voice note below to start the support request.
        </div>
      ) : (
        messages.map((m) => {
          const isCustomer = m.role === 'customer';
          // Find attached evidence if any
          const attached = (m.attachment_ids || [])
            .map((id) => evidenceList.find((e) => e.evidence_id === id))
            .filter(Boolean) as Evidence[];

          return (
            <div
              key={m.message_id}
              className={`chat-bubble ${isCustomer ? 'customer' : 'agent'}`}
            >
              <div>{m.text}</div>

              {attached.map((evi) => (
                <div key={evi.evidence_id} className="chat-attachment">
                  {evi.media_type === 'audio' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontSize: '11px', opacity: 0.9 }}>
                        🎙️ Voice Note {evi.language_detected ? `(${evi.language_detected})` : ''}
                      </span>
                      <audio controls src={evi.url} style={{ width: '100%', height: '30px' }} />
                      {evi.transcript && (
                        <div style={{ fontSize: '11px', fontStyle: 'italic', marginTop: '2px' }}>
                          "{evi.transcript}"
                        </div>
                      )}
                    </div>
                  )}

                  {evi.media_type === 'video' && (
                    <div style={{ display: 'flex', flexDirection: 'column', gap: '4px' }}>
                      <span style={{ fontSize: '11px', opacity: 0.9 }}>🎥 Attached Clip: {evi.filename}</span>
                      <video
                        controls
                        src={evi.url}
                        style={{ maxWidth: '100%', maxHeight: '180px', borderRadius: '4px' }}
                      />
                    </div>
                  )}

                  {evi.media_type === 'image' && (
                    <div>
                      <span style={{ fontSize: '11px', opacity: 0.9 }}>🖼️ Image: {evi.filename}</span>
                      <img
                        src={evi.url}
                        alt="Evidence"
                        style={{ maxWidth: '100%', maxHeight: '180px', borderRadius: '4px', display: 'block', marginTop: '4px' }}
                      />
                    </div>
                  )}
                </div>
              ))}

              <div className="msg-time">{formatDate(m.created_at)}</div>
            </div>
          );
        })
      )}
      <div ref={bottomRef} />
    </div>
  );
};
