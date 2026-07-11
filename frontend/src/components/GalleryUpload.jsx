import { useState } from 'react';
import { FileInput, Button } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { uploadImageToCloudinary } from '../utils/uploadImage';
import useTheeeme from '../hooks/useTheeeme';
import hdsLang from '../utils/hdsLang';

const MAX_IMAGES = 8;

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
  const { uploadStyle } = useTheeeme();
  const [uploading, setUploading] = useState(false);
  const [error, setError] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  const handleRemove = (index) => {
    onChange(items.filter((_, i) => i !== index));
  };

  const handleFiles = async (files) => {
    if (!files || files.length === 0) return;
    setFileInputKey((k) => k + 1); // reset so HDS file list never shows

    const remaining = MAX_IMAGES - items.length;
    if (remaining <= 0) {
      setError(t('gallery.maxImages', { max: MAX_IMAGES }));
      return;
    }

    // Allow selecting several photos at once; only take what fits under the cap.
    const selected = Array.from(files).slice(0, remaining);
    const truncated = files.length > remaining;
    setUploading(true);
    setError(null);

    const uploaded = [];
    try {
      for (const original of selected) {
        uploaded.push(await uploadImageToCloudinary(original, 'oiueei/things'));
      }
      // Selected more than the remaining slots — keep what fit, flag the cap.
      if (truncated) setError(t('gallery.maxImages', { max: MAX_IMAGES }));
    } catch {
      setError(t('upload.uploadError'));
    } finally {
      if (uploaded.length) onChange([...items, ...uploaded]);
      setUploading(false);
    }
  };

  return (
    <div className="image-upload" style={uploadStyle}>
      {items.length > 0 && (
        <ul className="gallery-thumbs">
          {items.map((item, i) => (
            <li key={item.publicId || i} className="gallery-thumb">
              <img src={item.url} alt={t('gallery.thumbAlt', { index: i + 1 })} />
              <Button
                variant="supplementary"
                iconStart={<span aria-hidden="true">✕</span>}
                size="small"
                onClick={() => handleRemove(i)}
              >
                {t('upload.remove')}
              </Button>
            </li>
          ))}
        </ul>
      )}
      <FileInput
        key={fileInputKey}
        id="gallery-upload"
        label={t('gallery.uploadLabel')}
        accept="image/*"
        multiple
        onChange={handleFiles}
        disabled={uploading || items.length >= MAX_IMAGES}
        language={hdsLang(i18n.language)}
        buttonLabel={t('upload.addFile')}
        helperText={
          uploading
            ? t('upload.uploading')
            : items.length >= MAX_IMAGES
              ? t('gallery.maxImages', { max: MAX_IMAGES })
              : t('gallery.uploadHelper', { max: MAX_IMAGES })
        }
        errorText={error || undefined}
        invalid={!!error}
      />
    </div>
  );
}
