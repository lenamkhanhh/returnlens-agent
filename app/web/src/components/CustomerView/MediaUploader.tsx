import React, { useRef, useState } from 'react';

interface MediaUploaderProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
  showAttachedLabel?: boolean;
}

export const MediaUploader: React.FC<MediaUploaderProps> = ({
  onFileSelected,
  disabled,
  showAttachedLabel = false,
}) => {
  const fileInputRef = useRef<HTMLInputElement | null>(null);
  const [selectedFileName, setSelectedFileName] = useState<string | null>(null);
  const [errorMsg, setErrorMsg] = useState<string | null>(null);

  const handleFileChange = (e: React.ChangeEvent<HTMLInputElement>) => {
    setErrorMsg(null);
    const file = e.target.files?.[0];
    if (!file) return;

    // Check size limit (≤20 MB per 17 §8)
    const maxBytes = 20 * 1024 * 1024;
    if (file.size > maxBytes) {
      setErrorMsg(`File size ${(file.size / (1024 * 1024)).toFixed(1)} MB exceeds the 20 MB limit.`);
      return;
    }

    setSelectedFileName(file.name);
    onFileSelected(file);
    // Reset input value so same file can be re-selected if removed
    if (fileInputRef.current) {
      fileInputRef.current.value = '';
    }
  };

  const handleTrigger = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '4px' }}>
      <input
        type="file"
        ref={fileInputRef}
        onChange={handleFileChange}
        accept="video/mp4,video/webm,video/quicktime,image/jpeg,image/png,image/webp"
        style={{ display: 'none' }}
      />
      <button
        type="button"
        onClick={handleTrigger}
        disabled={disabled}
        className="icon-action-btn"
        title="Upload video or photo"
        style={{
          background: 'none',
          border: 'none',
          cursor: 'pointer',
          padding: '6px 6px',
          fontSize: '18px',
          display: 'flex',
          alignItems: 'center',
          justifyContent: 'center',
          color: 'var(--text-muted)',
          flexShrink: 0,
        }}
      >
        <span>📎</span>
      </button>

      {showAttachedLabel && selectedFileName && (
        <span style={{ fontSize: '11px', color: 'var(--pine-green)', fontWeight: 600 }}>
          Attached: {selectedFileName}
        </span>
      )}

      {errorMsg && (
        <span style={{ fontSize: '11px', color: 'var(--terracotta)' }}>{errorMsg}</span>
      )}
    </div>
  );
};
