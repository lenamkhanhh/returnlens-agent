import React, { useRef, useState } from 'react';

interface MediaUploaderProps {
  onFileSelected: (file: File) => void;
  disabled?: boolean;
}

export const MediaUploader: React.FC<MediaUploaderProps> = ({ onFileSelected, disabled }) => {
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
  };

  const handleTrigger = () => {
    if (fileInputRef.current) {
      fileInputRef.current.click();
    }
  };

  return (
    <div style={{ display: 'inline-flex', alignItems: 'center', gap: '8px' }}>
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
        style={{ display: 'flex', alignItems: 'center', gap: '5px' }}
      >
        <span>📎</span>
        <span>Upload Video / Photo</span>
      </button>

      {selectedFileName && (
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
