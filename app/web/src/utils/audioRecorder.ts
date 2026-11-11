/**
 * Audio recorder utility based on MediaRecorder.
 * Mime type is chosen by isTypeSupported per 17 §6:
 * audio/webm;codecs=opus -> audio/mp4 (Safari)
 */

export interface RecordedAudio {
  blob: Blob;
  mimeType: string;
  durationSeconds: number;
  url: string;
}

export function getSupportedAudioMimeType(): string {
  if (typeof window === 'undefined' || !window.MediaRecorder) {
    return 'audio/webm';
  }

  const recorder = typeof window !== 'undefined' ? window.MediaRecorder : (typeof MediaRecorder !== 'undefined' ? MediaRecorder : null);
  if (!recorder || !recorder.isTypeSupported) {
    return 'audio/webm';
  }

  const preferredTypes = [
    'audio/webm;codecs=opus',
    'audio/webm',
    'audio/mp4',
    'audio/ogg;codecs=opus',
    'audio/aac',
  ];

  for (const mime of preferredTypes) {
    if (recorder.isTypeSupported(mime)) {
      return mime;
    }
  }

  return ''; // Browser default
}

export class AudioRecordingSession {
  private mediaRecorder: MediaRecorder | null = null;
  private stream: MediaStream | null = null;
  private chunks: Blob[] = [];
  private startTime: number = 0;
  private timerInterval: number | null = null;
  private selectedMime: string = '';

  onTick?: (seconds: number) => void;
  onMaxReached?: () => void;

  async start(): Promise<void> {
    if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
      throw new Error('Microphone access is not supported in this browser or insecure context');
    }

    this.stream = await navigator.mediaDevices.getUserMedia({ audio: true });
    this.selectedMime = getSupportedAudioMimeType();

    const options: MediaRecorderOptions = {};
    if (this.selectedMime) {
      options.mimeType = this.selectedMime;
    }

    this.mediaRecorder = new MediaRecorder(this.stream, options);
    this.chunks = [];
    this.startTime = Date.now();

    this.mediaRecorder.ondataavailable = (e: BlobEvent) => {
      if (e.data && e.data.size > 0) {
        this.chunks.push(e.data);
      }
    };

    this.mediaRecorder.start(250); // Slice every 250ms

    // Max 120s per 17 §8
    this.timerInterval = window.setInterval(() => {
      const elapsed = (Date.now() - this.startTime) / 1000;
      if (this.onTick) {
        this.onTick(Math.floor(elapsed));
      }
      if (elapsed >= 120) {
        this.stop();
        if (this.onMaxReached) {
          this.onMaxReached();
        }
      }
    }, 500);
  }

  stop(): Promise<RecordedAudio> {
    return new Promise((resolve, reject) => {
      if (!this.mediaRecorder) {
        return reject(new Error('Recorder not initialized'));
      }

      if (this.timerInterval) {
        clearInterval(this.timerInterval);
        this.timerInterval = null;
      }

      this.mediaRecorder.onstop = () => {
        const finalDuration = Math.max(1, Math.round((Date.now() - this.startTime) / 1000));
        const mimeType = this.selectedMime || this.mediaRecorder?.mimeType || 'audio/webm';
        const blob = new Blob(this.chunks, { type: mimeType });
        const url = URL.createObjectURL(blob);

        // Stop all audio tracks
        if (this.stream) {
          this.stream.getTracks().forEach((track) => track.stop());
          this.stream = null;
        }

        resolve({
          blob,
          mimeType,
          durationSeconds: finalDuration,
          url,
        });
      };

      if (this.mediaRecorder.state !== 'inactive') {
        this.mediaRecorder.stop();
      }
    });
  }

  cancel(): void {
    if (this.timerInterval) {
      clearInterval(this.timerInterval);
      this.timerInterval = null;
    }
    if (this.mediaRecorder && this.mediaRecorder.state !== 'inactive') {
      try {
        this.mediaRecorder.stop();
      } catch {
        // Ignore
      }
    }
    if (this.stream) {
      this.stream.getTracks().forEach((track) => track.stop());
      this.stream = null;
    }
    this.chunks = [];
  }
}
