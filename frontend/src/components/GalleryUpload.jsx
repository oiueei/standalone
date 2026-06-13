import { useState } from 'react';
import { FileInput, Button } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../services/api';
import { resizeImage } from '../utils/resizeImage';

const MAX_IMAGES = 8;

// HDS only supports fi, sv, en — everything else falls back to en
function hdsLang(lang) {
  if (lang === 'fi' || lang === 'sv') return lang;
  return 'en';
}

/**
 * Multi-image gallery upload (additional photos beyond the cover thumbnail).
 * Backed by Cloudinary direct upload (folder oiueei/things), client-resized to
 * 1216px like ImageUpload. Max 8 images. Things only.
 *
 * Items are {publicId, url} pairs so the parent can both preview each photo and
 * submit the ordered list of public_ids (`items.map(i => i.publicId)`).
 *
 * Props:
 *   items     – current array of {publicId, url}
 *   onChange  – called with the updated array on add / remove
 */
export default function GalleryUpload({ items = [], onChange }) {
  const { t, i18n } = useTranslation();
  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  const handleRemove = (index) => {
    onChange(items.filter((_, i) => i !== index));
  };

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return;
    setFileInputKey((k) => k + 1); // reset so HDS file list never shows

    if (items.length >= MAX_IMAGES) {
      setError(t('gallery.maxImages', { max: MAX_IMAGES }));
      return;
    }

    const file = await resizeImage(files[0]);
    setUploading(true);
    setError(null);

    try {
      const sigRes = await apiFetch('/api/v1/upload/signature/', {
        method: 'POST',
        body: JSON.stringify({ folder: 'oiueei/things' }),
      });
      if (!sigRes.ok) throw new Error('signature_failed');
      const { signature, timestamp, api_key, cloud_name } = await sigRes.json();

      const formData = new FormData();
      formData.append('file', file);
      formData.append('api_key', api_key);
      formData.append('timestamp', String(timestamp));
      formData.append('signature', signature);
      formData.append('folder', 'oiueei/things');

      const uploadRes = await fetch(
        `https://api.cloudinary.com/v1_1/${cloud_name}/image/upload`,
        { method: 'POST', body: formData }
      );
      if (!uploadRes.ok) throw new Error('upload_failed');
      const data = await uploadRes.json();

      onChange([...items, { publicId: data.public_id, url: data.secure_url }]);
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
      {items.length > 0 && (
        <ul className="gallery-thumbs">
          {items.map((item, i) => (
            <li key={item.publicId || i} className="gallery-thumb">
              <img src={item.url} alt={t('gallery.thumbAlt', { index: i + 1 })} />
              <Button
                variant="supplementary"
                iconLeft={<span aria-hidden="true">✕</span>}
                size="small"
                onClick={() => handleRemove(i)}
              >
                {t('upload.remove')}
              </Button>
            </li>
          ))}
        </ul>
      )}
      {items.length < MAX_IMAGES && (
        <FileInput
          key={fileInputKey}
          id="gallery-upload"
          label={t('gallery.uploadLabel')}
          accept="image/*"
          multiple={false}
          onChange={handleFiles}
          disabled={uploading}
          language={hdsLang(i18n.language)}
          buttonLabel={t('upload.addFile')}
          helperText={uploading ? t('upload.uploading') : t('gallery.uploadHelper', { max: MAX_IMAGES })}
          errorText={error || undefined}
          invalid={!!error}
        />
      )}
    </div>
  );
}
