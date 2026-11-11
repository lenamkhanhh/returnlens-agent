import React, { useState, useRef } from 'react';
import { AudioRecordingSession, RecordedAudio } from '../../utils/audioRecorder';
import { formatSecondsToTimestamp } from '../../utils/format';

interface VoiceRecorderProps {
  onAudioReady: (audio: RecordedAudio) => void;
  disabled?: boolean;
}

export const VoiceRecorder: React.FC<VoiceRecorderProps> = ({ onAudioReady, disabled }) => {
  const [isRecording, setIsRecording] = useState(false);
  const [elapsedSeconds, setElapsedSeconds] = useState(0);
  const [recordedAudio, setRecordedAudio] = useState<RecordedAudio | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const sessionRef = useRef<AudioRecordingSession | null>(null);

  const handleStart = async () => {
    setErrorMsg(null);
    try {
      const session = new AudioRecordingSession();
      session.onTick = (sec) => setElapsedSeconds(sec);
      session.onMaxReached = async () => {
        const audio = await session.stop();
        setIsRecording(false);
        setRecordedAudio(audio);
      };
      await session.start();
      sessionRef.current = session;
      setIsRecording(true);
      setElapsedSeconds(0);
      setRecordedAudio(null);
    } catch (err: any) {
      setErrorMsg(err.message || 'Microphone access denied or not supported');
    }
  };

  const handleStop = async () => {
    if (!sessionRef.current) return;
    try {
      const audio = await sessionRef.current.stop();
      setIsRecording(false);
      setRecordedAudio(audio);
      onAudioReady(audio);
    } catch (err: any) {
      setErrorMsg(err.message || 'Failed to finish recording');
      setIsRecording(false);
    }
  };

  const handleSend = () => {
    if (recordedAudio) {
      onAudioReady(recordedAudio);
      setRecordedAudio(null);
      setElapsedSeconds(0);
    }
  };

  const handleDiscard = () => {
    if (recordedAudio) {
      URL.revokeObjectURL(recordedAudio.url);
      setRecordedAudio(null);
      setElapsedSeconds(0);
    }
  };

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '6px' }}>
      <div className={`voice-recorder-box ${isRecording ? 'voice-recording-active' : ''}`}>
        {!isRecording && !recordedAudio && (
          <button
            type="button"
            onClick={handleStart}
            disabled={disabled}
            className="icon-action-btn"
            title="Record voice note"
            style={{
              background: 'none',
              border: 'none',
              cursor: 'pointer',
              padding: '6px 8px',
              fontSize: '18px',
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              color: 'var(--text-muted)',
            }}
          >
            <span>🎙️</span>
          </button>
        )}

        {isRecording && (
          <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
            <span className="record-indicator" />
            <span style={{ fontWeight: 600, color: 'var(--terracotta)', fontSize: '13px' }}>
              Recording ({formatSecondsToTimestamp(elapsedSeconds)} / 02:00)
            </span>
            <button type="button" onClick={handleStop} className="btn-danger" style={{ padding: '3px 10px' }}>
              ⏹ Stop
            </button>
          </div>
        )}

        {recordedAudio && (
          <div className="audio-preview-box">
            <audio controls src={recordedAudio.url} style={{ height: '32px' }} />
            <span style={{ fontSize: '11px', color: 'var(--text-muted)' }}>
              ({formatSecondsToTimestamp(recordedAudio.durationSeconds)})
            </span>
            <button
              type="button"
              onClick={handleSend}
              className="btn-primary"
              style={{ padding: '3px 10px', fontSize: '12px' }}
            >
              Attach Audio
            </button>
            <button
              type="button"
              onClick={handleDiscard}
              style={{ padding: '3px 8px', fontSize: '12px' }}
            >
              Discard
            </button>
          </div>
        )}
      </div>

      {errorMsg && (
        <span style={{ fontSize: '11px', color: 'var(--terracotta)' }}>{errorMsg}</span>
      )}
    </div>
  );
};
