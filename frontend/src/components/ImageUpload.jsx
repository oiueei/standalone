import { useState, useEffect } from 'react';
import { FileInput, Button } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../services/api';
import { resizeImage } from '../utils/resizeImage';
import useTheeeme from '../hooks/useTheeeme';

// HDS only supports fi, sv, en — everything else falls back to en
function hdsLang(lang) {
  if (lang === 'fi' || lang === 'sv') return lang;
  return 'en';
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
 *   onChange    – called with the new public_id (or '') on upload / remove
 *   currentUrl  – full URL of the current saved image (for the initial preview)
 *   folder      – Cloudinary upload folder (default 'oiueei/users')
 *   helperText  – optional helper text shown below the input
 */
export default function ImageUpload({ id, label, onChange, currentUrl, folder = 'oiueei/users', helperText }) {
  const { t, i18n } = useTranslation();
  const { tc } = useTheeeme();
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
    const file = await resizeImage(files[0]);

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

  const wrapperStyle = tc.color_01 ? {
    '--upload-border': `var(--color-${tc.color_01})`,
    '--upload-color': tc.color_04 ? `var(--color-${tc.color_04})` : `var(--color-${tc.color_01})`,
    '--upload-bg-hover': `var(--color-${tc.color_01})`,
    '--upload-color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
  } : {};

  return (
    <div className="image-upload" style={wrapperStyle}>
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
          buttonLabel={t('upload.addFile')}
          helperText={uploading ? t('upload.uploading') : (helperText || t('upload.acceptHint'))}
          errorText={error || undefined}
          invalid={!!error}
        />
      )}
    </div>
  );
}
