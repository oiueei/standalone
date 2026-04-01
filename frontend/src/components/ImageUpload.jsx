import { useState } from 'react';
import { FileInput } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../services/api';

/**
 * Single-image upload component backed by Cloudinary direct upload.
 *
 * Props:
 *   id          – HTML id for the FileInput
 *   label       – visible label text
 *   value       – current Cloudinary public_id (string)
 *   onChange    – called with the new public_id after a successful upload
 *   currentUrl  – full URL of the current image (for the preview)
 *   folder      – Cloudinary upload folder (default 'oiueei/users')
 *   helperText  – optional helper text shown below the input
 */
export default function ImageUpload({ id, label, value, onChange, currentUrl, folder = 'oiueei/users', helperText }) {
  const { t } = useTranslation();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return;
    const file = files[0];

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

      onChange(data.public_id);
      setFileInputKey((k) => k + 1);
    } catch {
      setError(t('upload.uploadError'));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="image-upload">
      {currentUrl && (
        <div className="image-upload-preview">
          <img src={currentUrl} alt="" />
        </div>
      )}
      <FileInput
        key={fileInputKey}
        id={id}
        label={label}
        accept="image/*"
        multiple={false}
        onChange={handleFiles}
        disabled={uploading}
        helperText={uploading ? t('upload.uploading') : (helperText || undefined)}
        errorText={error || undefined}
        invalid={!!error}
      />
    </div>
  );
}
