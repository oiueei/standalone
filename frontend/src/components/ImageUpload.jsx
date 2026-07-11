import { useState, useEffect } from 'react';
import { FileInput, Button } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { uploadImageToCloudinary } from '../utils/uploadImage';
import useTheeeme from '../hooks/useTheeeme';
import hdsLang from '../utils/hdsLang';

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
  const { uploadStyle } = useTheeeme();
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

    setFileInputKey((k) => k + 1); // reset immediately so HDS file list never shows
    setUploading(true);
    setError(null);

    try {
      const { publicId, url } = await uploadImageToCloudinary(files[0], folder);
      setPreviewUrl(url);
      onChange(publicId);
    } catch {
      setError(t('upload.uploadError'));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="image-upload" style={uploadStyle}>
      {previewUrl && (
        <div className="image-upload-preview">
          <img src={previewUrl} alt={t('upload.previewAlt')} />
          <Button
            variant="supplementary"
            iconStart={<span aria-hidden="true">✕</span>}
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
