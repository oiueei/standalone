import { useState } from 'react';
import { FileInput, Button } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../services/api';
import useTheeeme from '../hooks/useTheeeme';

const MAX_SIZE = 1024 * 1024; // 1 MB
const MAX_FILES = 5;
const ACCEPT = '.pdf,.doc,.docx,.xls,.xlsx,.md';

// HDS only supports fi, sv, en — everything else falls back to en
function hdsLang(lang) {
  if (lang === 'fi' || lang === 'sv') return lang;
  return 'en';
}

/**
 * Multi-document upload component backed by Cloudinary raw upload.
 * Max 5 documents, max 1MB each.
 *
 * Props:
 *   documents   – current array of {public_id, filename, content_type}
 *   onChange     – called with updated array on upload/remove
 */
export default function DocumentUpload({ documents = [], onChange }) {
  const { t, i18n } = useTranslation();
  const { tc } = useTheeeme();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  const handleRemove = (index) => {
    onChange(documents.filter((_, i) => i !== index));
  };

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return;
    const file = files[0];

    setFileInputKey((k) => k + 1);

    if (file.size > MAX_SIZE) {
      setError(t('documents.fileTooLarge'));
      return;
    }

    if (documents.length >= MAX_FILES) {
      setError(t('documents.maxFiles'));
      return;
    }

    setUploading(true);
    setError(null);

    try {
      const sigRes = await apiFetch('/api/v1/upload/signature/', {
        method: 'POST',
        body: JSON.stringify({ folder: 'oiueei/documents', resource_type: 'raw' }),
      });
      if (!sigRes.ok) throw new Error('signature_failed');
      const { signature, timestamp, api_key, cloud_name, folder, public_id, allowed_formats, resource_type, type } =
        await sigRes.json();

      // Send back exactly the server-signed parameters — changing any of them
      // (public_id, allowed_formats, type) would break the signature.
      const formData = new FormData();
      formData.append('file', file);
      formData.append('api_key', api_key);
      formData.append('timestamp', String(timestamp));
      formData.append('signature', signature);
      formData.append('folder', folder);
      formData.append('public_id', public_id);
      formData.append('allowed_formats', allowed_formats);
      if (type) formData.append('type', type);

      const uploadRes = await fetch(
        `https://api.cloudinary.com/v1_1/${cloud_name}/${resource_type}/upload`,
        { method: 'POST', body: formData }
      );
      if (!uploadRes.ok) throw new Error('upload_failed');
      const data = await uploadRes.json();

      onChange([
        ...documents,
        {
          public_id: data.public_id,
          filename: file.name,
          content_type: file.type || 'application/octet-stream',
        },
      ]);
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
      {documents.length > 0 && (
        <ul className="document-list">
          {documents.map((doc, i) => (
            <li key={doc.public_id || i} className="document-list-item">
              <span>{doc.filename}</span>
              <Button
                variant="supplementary"
                iconLeft={<span>✕</span>}
                size="small"
                onClick={() => handleRemove(i)}
              >
                {t('documents.remove')}
              </Button>
            </li>
          ))}
        </ul>
      )}
      <FileInput
        key={fileInputKey}
        id="document-upload"
        label={t('documents.uploadLabel')}
        accept={ACCEPT}
        multiple={false}
        onChange={handleFiles}
        disabled={uploading || documents.length >= MAX_FILES}
        language={hdsLang(i18n.language)}
        buttonLabel={t('upload.addFile')}
        helperText={
          uploading
            ? t('upload.uploading')
            : documents.length >= MAX_FILES
              ? t('documents.maxFiles')
              : t('documents.uploadHelper')
        }
        errorText={error || undefined}
        invalid={!!error}
      />
    </div>
  );
}
