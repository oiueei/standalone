import { useState } from 'react';
import { FileInput } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../services/api';

/**
 * Multi-image upload component backed by Cloudinary direct upload.
 * Uploads all selected files in parallel and replaces the current array.
 *
 * Props:
 *   id          – HTML id for the FileInput
 *   label       – visible label text
 *   value       – current array of Cloudinary public_ids
 *   onChange    – called with the new public_id array after successful uploads
 *   currentUrls – array of full URLs for the current images (for previews)
 *   folder      – Cloudinary upload folder (default 'oiueei/things')
 */
export default function MultiImageUpload({ id, label, value = [], onChange, currentUrls = [], folder = 'oiueei/things' }) {
  const { t } = useTranslation();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  const uploadOne = async (file, signature, timestamp, api_key, cloud_name) => {
    const formData = new FormData();
    formData.append('file', file);
    formData.append('api_key', api_key);
    formData.append('timestamp', String(timestamp));
    formData.append('signature', signature);
    formData.append('folder', folder);

    const res = await fetch(
      `https://api.cloudinary.com/v1_1/${cloud_name}/image/upload`,
      { method: 'POST', body: formData }
    );
    if (!res.ok) throw new Error('upload_failed');
    const data = await res.json();
    return data.public_id;
  };

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return;

    setUploading(true);
    setError(null);

    try {
      const sigRes = await apiFetch('/api/v1/upload/signature/', {
        method: 'POST',
        body: JSON.stringify({ folder }),
      });
      if (!sigRes.ok) throw new Error('signature_failed');
      const { signature, timestamp, api_key, cloud_name } = await sigRes.json();

      const publicIds = await Promise.all(
        Array.from(files).map((file) => uploadOne(file, signature, timestamp, api_key, cloud_name))
      );

      onChange(publicIds);
      setFileInputKey((k) => k + 1);
    } catch {
      setError(t('upload.uploadError'));
    } finally {
      setUploading(false);
    }
  };

  return (
    <div className="image-upload">
      {currentUrls.length > 0 && (
        <div className="image-upload-gallery">
          {currentUrls.map((url, i) => (
            <img key={i} src={url} alt="" className="image-upload-gallery-item" />
          ))}
        </div>
      )}
      <FileInput
        key={fileInputKey}
        id={id}
        label={label}
        accept="image/*"
        multiple
        onChange={handleFiles}
        disabled={uploading}
        helperText={uploading ? t('upload.uploading') : undefined}
        errorText={error || undefined}
        invalid={!!error}
      />
    </div>
  );
}
