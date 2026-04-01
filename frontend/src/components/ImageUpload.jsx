import { useState, useEffect } from 'react';
import { FileInput, Button } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../services/api';

// HDS only supports fi, sv, en — everything else falls back to en
function hdsLang(lang) {
  if (lang === 'fi' || lang === 'sv') return lang;
  return 'en';
}

const MAX_PX = 1216;

function resizeIfNeeded(file) {
  return new Promise((resolve) => {
    const img = new Image();
    const url = URL.createObjectURL(file);
    img.onload = () => {
      URL.revokeObjectURL(url);
      if (img.width <= MAX_PX && img.height <= MAX_PX) {
        resolve(file);
        return;
      }
      const scale = MAX_PX / Math.max(img.width, img.height);
      const canvas = document.createElement('canvas');
      canvas.width = Math.round(img.width * scale);
      canvas.height = Math.round(img.height * scale);
      canvas.getContext('2d').drawImage(img, 0, 0, canvas.width, canvas.height);
      canvas.toBlob((blob) => resolve(new File([blob], file.name, { type: file.type })), file.type);
    };
    img.src = url;
  });
}

/**
 * Single-image upload component backed by Cloudinary direct upload.
 * Images wider or taller than 1216 px are resized on the client before upload.
 * Shows a preview with a Remove button after upload or when an existing image
 * is present. Removing clears the field without deleting from Cloudinary.
 *
 * Props:
 *   id          – HTML id for the FileInput
 *   label       – visible label text
 *   value       – current Cloudinary public_id (string)
 *   onChange    – called with the new public_id (or '') on upload / remove
 *   currentUrl  – full URL of the current saved image (for the initial preview)
 *   folder      – Cloudinary upload folder (default 'oiueei/users')
 *   helperText  – optional helper text shown below the input
 */
export default function ImageUpload({ id, label, value, onChange, currentUrl, folder = 'oiueei/users', helperText }) {
  const { t, i18n } = useTranslation();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [previewUrl, setPreviewUrl] = useState(currentUrl || null);

  // Sync preview when the parent reloads with a new currentUrl
  useEffect(() => {
    setPreviewUrl(currentUrl || null);
  }, [currentUrl]);

  const handleRemove = () => {
    setPreviewUrl(null);
    onChange('');
  };

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return;
    const file = await resizeIfNeeded(files[0]);

    setFileInputKey((k) => k + 1); // reset immediately so HDS file list never shows
    setUploading(true);
    setError(null);

    try {
      const sigRes = await apiFetch('/api/v1/upload/signature/', {
        method: 'POST',
        body: JSON.stringify({ folder }),
      });
      if (!sigRes.ok) throw new Error('signature_failed');
      const { signature, timestamp, api_key, cloud_name } = await sigRes.json();

      const formData = new FormData();
      formData.append('file', file);
      formData.append('api_key', api_key);
      formData.append('timestamp', String(timestamp));
      formData.append('signature', signature);
      formData.append('folder', folder);

      const uploadRes = await fetch(
        `https://api.cloudinary.com/v1_1/${cloud_name}/image/upload`,
        { method: 'POST', body: formData }
      );
      if (!uploadRes.ok) throw new Error('upload_failed');
      const data = await uploadRes.json();

      setPreviewUrl(data.secure_url);
      onChange(data.public_id);
    } catch {
      setError(t('upload.uploadError'));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="image-upload">
      {previewUrl && (
        <div className="image-upload-preview">
          <img src={previewUrl} alt="" />
          <Button
            variant="supplementary"
            iconLeft={<span>✕</span>}
            size="small"
            onClick={handleRemove}
            style={{ marginTop: 'var(--spacing-xs)' }}
          >
            {t('upload.remove')}
          </Button>
        </div>
      )}
      {!previewUrl && (
        <FileInput
          key={fileInputKey}
          id={id}
          label={label}
          accept="image/*"
          multiple={false}
          onChange={handleFiles}
          disabled={uploading}
          language={hdsLang(i18n.language)}
          helperText={uploading ? t('upload.uploading') : (helperText || undefined)}
          errorText={error || undefined}
          invalid={!!error}
        />
      )}
      {previewUrl && (
        <FileInput
          key={`${fileInputKey}-replace`}
          id={`${id}-replace`}
          label={t('upload.replaceLabel')}
          accept="image/*"
          multiple={false}
          onChange={handleFiles}
          disabled={uploading}
          language={hdsLang(i18n.language)}
          helperText={uploading ? t('upload.uploading') : undefined}
          errorText={error || undefined}
          invalid={!!error}
        />
      )}
    </div>
  );
}
