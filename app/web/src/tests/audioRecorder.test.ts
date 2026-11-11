import { describe, it, expect, vi, beforeEach } from 'vitest';
import { getSupportedAudioMimeType } from '../utils/audioRecorder';

describe('Voice note recorder MIME type selection', () => {
  beforeEach(() => {
    vi.restoreAllMocks();
  });

  it('selects audio/webm;codecs=opus if supported (Chrome/Firefox standard)', () => {
    (globalThis as any).window = {
      MediaRecorder: {
        isTypeSupported: (mime: string) => mime === 'audio/webm;codecs=opus',
      },
    };
    expect(getSupportedAudioMimeType()).toBe('audio/webm;codecs=opus');
  });

  it('falls back to audio/mp4 if opus is not supported (Safari on iOS/macOS)', () => {
    (globalThis as any).window = {
      MediaRecorder: {
        isTypeSupported: (mime: string) => mime === 'audio/mp4',
      },
    };
    expect(getSupportedAudioMimeType()).toBe('audio/mp4');
  });

  it('returns empty string fallback if none in list are supported', () => {
    (globalThis as any).window = {
      MediaRecorder: {
        isTypeSupported: () => false,
      },
    };
    expect(getSupportedAudioMimeType()).toBe('');
  });
});
