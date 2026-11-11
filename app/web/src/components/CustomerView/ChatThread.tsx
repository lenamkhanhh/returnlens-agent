import React, { useEffect, useRef, useState } from 'react';
import { Message, Evidence } from '../../types';
import {
  formatDetectedLanguage,
  formatMessageTime,
  formatSecondsToTimestamp,
  isCourierOrSystemMessage,
  formatCourierOrSystemMessage,
} from '../../utils/format';

interface ChatThreadProps {
  messages: Message[];
  evidenceList: Evidence[];
  isProcessing?: boolean;
}

const WaveformVoicePlayer: React.FC<{
  src: string;
  language?: string | null;
  transcript?: string | null;
}> = ({ src, language, transcript }) => {
  const audioRef = useRef<HTMLAudioElement | null>(null);
  const [isPlaying, setIsPlaying] = useState(false);
  const [currentTime, setCurrentTime] = useState(0);
  const [duration, setDuration] = useState(0);

  const togglePlay = () => {
    if (!audioRef.current) return;
    if (isPlaying) {
      audioRef.current.pause();
      setIsPlaying(false);
    } else {
      audioRef.current.play().then(() => setIsPlaying(true)).catch(() => {});
    }
  };

  const handleTimeUpdate = () => {
    if (audioRef.current) {
      setCurrentTime(audioRef.current.currentTime);
    }
  };

  const handleLoadedMetadata = () => {
    if (audioRef.current) {
      setDuration(audioRef.current.duration || 0);
    }
  };

  const handleEnded = () => {
    setIsPlaying(false);
    setCurrentTime(0);
  };

  // 24 simulated waveform bars
  const bars = [8, 14, 22, 12, 18, 24, 16, 26, 20, 14, 22, 18, 28, 16, 10, 18, 24, 14, 20, 12, 16, 10, 14, 8];
  const progress = duration > 0 ? currentTime / duration : 0;
  const activeBarIndex = Math.floor(progress * bars.length);

  return (
    <div className="waveform-player-box">
      <audio
        ref={audioRef}
        src={src}
        onTimeUpdate={handleTimeUpdate}
        onLoadedMetadata={handleLoadedMetadata}
        onEnded={handleEnded}
        style={{ display: 'none' }}
      />
      <div className="waveform-controls">
        <button
          type="button"
          className="waveform-play-btn"
          onClick={togglePlay}
          title={isPlaying ? 'Pause' : 'Play voice note'}
        >
          {isPlaying ? '❚❚' : '▶'}
        </button>

        <div className="waveform-bars">
          {bars.map((h, i) => (
            <span
              key={i}
              className={`waveform-bar ${i <= activeBarIndex ? 'played' : ''}`}
              style={{ height: `${h}px` }}
            />
          ))}
        </div>

        <span className="waveform-time">
          {formatSecondsToTimestamp(isPlaying ? currentTime : (duration || 11))}
        </span>

        <span className="waveform-lang-chip">
          🎙️ {formatDetectedLanguage(language)}
        </span>
      </div>

      {transcript && (
        <div className="waveform-transcript">
          "{transcript}"
        </div>
      )}
    </div>
  );
};

export const ChatThread: React.FC<ChatThreadProps> = ({ messages, evidenceList, isProcessing }) => {
  const bottomRef = useRef<HTMLDivElement | null>(null);

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' });
  }, [messages, isProcessing]);

  return (
    <div className="chat-thread messaging-thread">
      {/* Date badge */}
      <div className="chat-date-divider">
        <span>Today</span>
      </div>

      {messages.length === 0 ? (
        <div className="chat-empty-hint">
          <div style={{ fontSize: '24px', marginBottom: '6px' }}>💬</div>
          <strong style={{ color: 'var(--text-main)', fontSize: '13px' }}>Start a conversation with Dhun Audio</strong>
          <div style={{ fontSize: '12px', color: 'var(--text-muted)', marginTop: '4px' }}>
            Ask where your order is, report damage, or request a return with video/photos.
          </div>
        </div>
      ) : (
        messages.map((m) => {
          if (isCourierOrSystemMessage(m)) {
            return (
              <div key={m.message_id} className="chat-system-event-note">
                <span>{formatCourierOrSystemMessage(m.text || '')}</span>
              </div>
            );
          }

          const isCustomer = m.role === 'customer';
          const attached = (m.attachment_ids || [])
            .map((id) => evidenceList.find((e) => e.evidence_id === id))
            .filter(Boolean) as Evidence[];

          return (
            <div
              key={m.message_id}
              className={`chat-bubble ${isCustomer ? 'customer' : 'agent'}`}
            >
              {m.text && <div className="chat-bubble-text">{m.text}</div>}

              {attached.map((evi) => {
                const mediaUrl = evi.evidence_id ? `/api/media/${evi.evidence_id}` : evi.url;
                return (
                  <div key={evi.evidence_id} className="chat-attachment-container">
                    {evi.media_type === 'audio' && (
                      <WaveformVoicePlayer
                        src={mediaUrl}
                        language={evi.language_detected}
                        transcript={evi.transcript}
                      />
                    )}

                    {evi.media_type === 'video' && (
                      <div className="chat-media-thumb video-thumb">
                        <video
                          controls
                          src={mediaUrl}
                          className="chat-video-player"
                        />
                        <div className="chat-thumb-label">🎥 {evi.filename}</div>
                      </div>
                    )}

                    {evi.media_type === 'image' && (
                      <div className="chat-media-thumb image-thumb">
                        <img
                          src={mediaUrl}
                          alt="Customer upload"
                          className="chat-image-preview"
                        />
                        <div className="chat-thumb-label">🖼️ {evi.filename}</div>
                      </div>
                    )}
                  </div>
                );
              })}

              <div className="msg-meta">
                <span className="msg-time">{formatMessageTime(m.created_at)}</span>
                {isCustomer && (
                  <span className="delivered-ticks" title="Delivered">
                    ✓✓
                  </span>
                )}
              </div>
            </div>
          );
        })
      )}

      {/* Typing indicator while processing */}
      {isProcessing && (
        <div className="chat-bubble agent typing-indicator-bubble">
          <div className="typing-dots">
            <span className="typing-dot" />
            <span className="typing-dot" />
            <span className="typing-dot" />
          </div>
          <span className="typing-text">Dhun Audio is replying…</span>
        </div>
      )}

      <div ref={bottomRef} />
    </div>
  );
};
