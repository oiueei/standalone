import { useState } from 'react';
import { FileInput, Button, Notification } from 'hds-react';
import { useTranslation } from 'react-i18next';
import Papa from 'papaparse';
import { apiFetch } from '../services/api';
import { uploadImageToCloudinary } from '../utils/uploadImage';
import useTheeeme from '../hooks/useTheeeme';

const MAX_ROWS = 100;
// The plain text/scalar columns a CSV can carry. `tags` is a single `|`-separated
// cell and `photo` is a filename — both handled separately below.
const COLUMNS = ['type', 'headline', 'description', 'fee', 'availability', 'location', 'condition'];
// Image extensions recognised inside a ZIP — kept in sync with the backend's
// Cloudinary `IMAGE_FORMATS` allow-list (core/views/upload.py).
const IMAGE_RE = /\.(jpe?g|png|webp|gif|bmp|tiff?|avif|heic|heif)$/i;
const MIME_BY_EXT = {
  jpg: 'image/jpeg', jpeg: 'image/jpeg', png: 'image/png', webp: 'image/webp',
  gif: 'image/gif', bmp: 'image/bmp', tif: 'image/tiff', tiff: 'image/tiff',
  avif: 'image/avif', heic: 'image/heic', heif: 'image/heif',
};
// Shown in the bottom format hint. Language-agnostic, so it lives here rather
// than in the i18n bundles (matches BulkInviteCsv's EXAMPLE_CSV).
const EXAMPLE_CSV = `headline,type,fee,location,condition,tags,photo
Cazo de acero,RENT_THING,1,LC (08038),GOOD,Cocina,cazo.jpg`;

function basename(path) {
  return path.split('/').pop();
}
function mimeFromName(name) {
  return MIME_BY_EXT[name.split('.').pop().toLowerCase()] || 'image/jpeg';
}

// HDS FileInput only supports fi, sv, en — everything else falls back to en.
function hdsLang(lang) {
  if (lang === 'fi' || lang === 'sv') return lang;
  return 'en';
}

/**
 * Bulk-add things from a CSV or a ZIP (F-9). Parses the file client-side with
 * PapaParse, shows a preview, then posts the rows to the atomic batch endpoint
 * (`POST /collections/{code}/things/bulk/`) — all rows are created or none.
 *
 * Plain `.csv`: text-only rows. `.zip` (CSV + image files): each row may name its
 * cover photo by filename in a `photo` column; on import the referenced images are
 * uploaded to Cloudinary (reusing the secure signed-upload path) and their
 * public_ids are sent as `thumbnail`. Server-side validators reject HTML, line
 * breaks and spreadsheet-formula (CSV) injection per field.
 *
 * Props:
 *   collectionCode – target collection
 *   onImported(count) – called after a successful import
 */
export default function BulkAddCsv({ collectionCode, onImported }) {
  const { t, i18n } = useTranslation();
  const { btnStyle } = useTheeeme();
  const [rows, setRows] = useState([]);
  // basename(lowercased) → JSZip entry, for the rows' `photo` references (ZIP only).
  const [zipImages, setZipImages] = useState(null);
  const [error, setError] = useState(null);
  const [importing, setImporting] = useState(false);
  const [uploadProgress, setUploadProgress] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);

  // Map one parsed CSV record to a row payload. `withPhoto` keeps the `photo`
  // filename for later Cloudinary resolution (ZIP path only).
  const mapRow = (raw, withPhoto) => {
    const row = {};
    for (const col of COLUMNS) {
      const value = raw[col];
      if (value !== undefined && String(value).trim() !== '') {
        row[col] = String(value).trim();
      }
    }
    // Tags are a single cell holding a `|`-separated list (pipe avoids clashing
    // with the CSV field delimiter, which is `;` in some locales).
    if (raw.tags !== undefined && String(raw.tags).trim() !== '') {
      const tags = String(raw.tags).split('|').map((tag) => tag.trim()).filter(Boolean);
      if (tags.length > 0) row.tags = tags;
    }
    if (withPhoto && raw.photo !== undefined && String(raw.photo).trim() !== '') {
      row.photo = String(raw.photo).trim();
    }
    return row;
  };

  // Shared bounds/required checks. Returns an error string or null.
  const validate = (parsed) => {
    if (parsed.length === 0) return t('bulkAdd.empty');
    if (parsed.length > MAX_ROWS) return t('bulkAdd.tooMany', { max: MAX_ROWS });
    if (parsed.some((row) => !row.headline)) return t('bulkAdd.headlineRequired');
    return null;
  };

  const handleFiles = (files) => {
    setError(null);
    setRows([]);
    setZipImages(null);
    setFileInputKey((k) => k + 1);
    const file = files && files[0];
    if (!file) return;
    const isZip = /\.zip$/i.test(file.name) || /zip/i.test(file.type || '');
    if (isZip) parseZip(file);
    else parseCsv(file);
  };

  const parseCsv = (file) => {
    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      transformHeader: (h) => h.trim().toLowerCase(),
      complete: (result) => {
        const parsed = (result.data || []).map((raw) => mapRow(raw, false))
          .filter((row) => Object.keys(row).length > 0);
        const err = validate(parsed);
        if (err) setError(err);
        else setRows(parsed);
      },
      error: () => setError(t('bulkAdd.parseError')),
    });
  };

  const parseZip = async (file) => {
    try {
      const { default: JSZip } = await import('jszip');
      const zip = await JSZip.loadAsync(file);
      let csvEntry = null;
      const images = new Map();
      zip.forEach((path, entry) => {
        if (entry.dir) return;
        const name = basename(path);
        if (name.startsWith('.')) return; // skip __MACOSX / dotfiles
        if (/\.csv$/i.test(name) && !csvEntry) csvEntry = entry;
        else if (IMAGE_RE.test(name)) images.set(name.toLowerCase(), entry);
      });
      if (!csvEntry) {
        setError(t('bulkAdd.zipNoCsv'));
        return;
      }
      const text = await csvEntry.async('string');
      Papa.parse(text, {
        header: true,
        skipEmptyLines: true,
        transformHeader: (h) => h.trim().toLowerCase(),
        complete: (result) => {
          const parsed = (result.data || []).map((raw) => mapRow(raw, true))
            .filter((row) => Object.keys(row).length > 0);
          const err = validate(parsed);
          if (err) {
            setError(err);
            return;
          }
          // Every referenced photo must actually be in the ZIP.
          const missing = [...new Set(parsed.filter((r) => r.photo).map((r) => r.photo))]
            .filter((name) => !images.has(name.toLowerCase()));
          if (missing.length > 0) {
            setError(t('bulkAdd.zipMissingImages', { files: missing.join(', ') }));
            return;
          }
          setZipImages(images);
          setRows(parsed);
        },
        error: () => setError(t('bulkAdd.parseError')),
      });
    } catch {
      setError(t('bulkAdd.zipError'));
    }
  };

  // Upload every photo referenced by the rows once, returning filename → public_id.
  const uploadZipImages = async () => {
    const names = [...new Set(rows.filter((r) => r.photo).map((r) => r.photo))];
    const idByName = new Map();
    setUploadProgress({ done: 0, total: names.length });
    for (const name of names) {
      const entry = zipImages.get(name.toLowerCase());
      const blob = await entry.async('blob');
      const imgFile = new File([blob], name, { type: blob.type || mimeFromName(name) });
      const { publicId } = await uploadImageToCloudinary(imgFile, 'oiueei/things');
      idByName.set(name, publicId);
      setUploadProgress((p) => ({ done: p.done + 1, total: p.total }));
    }
    return idByName;
  };

  const handleImport = async () => {
    setImporting(true);
    setError(null);
    try {
      let payloadRows;
      if (zipImages) {
        let idByName;
        try {
          idByName = await uploadZipImages();
        } catch {
          setError(t('bulkAdd.imageUploadError'));
          return;
        }
        // Swap the `photo` filename for the uploaded `thumbnail` public_id.
        payloadRows = rows.map(({ photo, ...rest }) =>
          photo ? { ...rest, thumbnail: idByName.get(photo) } : rest);
      } else {
        payloadRows = rows;
      }

      const res = await apiFetch(`/api/v1/collections/${collectionCode}/things/bulk/`, {
        method: 'POST',
        body: JSON.stringify({ rows: payloadRows }),
      });
      if (res.ok) {
        const data = await res.json();
        onImported(data.created);
        return;
      }
      if (res.status === 429) {
        setError(t('common.tooManyAttempts'));
        return;
      }
      let data = {};
      try {
        data = await res.json();
      } catch {
        data = {};
      }
      if (Array.isArray(data.errors) && data.errors.length > 0) {
        const badRows = data.errors.map((e) => e.row + 1).join(', ');
        setError(t('bulkAdd.rowErrors', { rows: badRows }));
      } else {
        setError(data.error || t('bulkAdd.error'));
      }
    } catch {
      setError(t('common.connectionError'));
    } finally {
      setImporting(false);
      setUploadProgress(null);
    }
  };

  const importLabel = importing
    ? (uploadProgress ? t('bulkAdd.uploadingImages', uploadProgress) : t('bulkAdd.importing'))
    : t('bulkAdd.import', { count: rows.length });

  return (
    <div className="bulk-add">
      <p className="bulk-add-help">{t('bulkAdd.help')}</p>
      <FileInput
        key={fileInputKey}
        id="bulk-add-csv"
        label={t('bulkAdd.fileLabel')}
        accept=".csv,text/csv,.zip,application/zip,application/x-zip-compressed"
        multiple={false}
        onChange={handleFiles}
        language={hdsLang(i18n.language)}
        buttonLabel={t('upload.addFileGeneric')}
        disabled={importing}
      />
      {error && (
        <Notification type="error" size="small" style={{ marginTop: 'var(--spacing-s)' }}>
          {error}
        </Notification>
      )}
      {rows.length > 0 && (
        <>
          <h3 className="bulk-add-preview-title">{t('bulkAdd.preview', { count: rows.length })}</h3>
          {/* Numbered so the row numbers in an import error map to what's shown. */}
          <ol className="bulk-add-preview">
            {rows.map((row, i) => (
              <li key={i}>
                {row.headline}
                {row.type ? ` — ${t(`types.${row.type}`, row.type)}` : ''}
                {row.fee ? ` · ${row.fee}` : ''}
                {row.tags ? ` · ${row.tags.join(', ')}` : ''}
                {row.photo ? ` · 📷 ${row.photo}` : ''}
              </li>
            ))}
          </ol>
          <Button
            style={{ ...btnStyle, marginTop: 'var(--spacing-s)' }}
            disabled={importing}
            onClick={handleImport}
          >
            {importLabel}
          </Button>
        </>
      )}
      <div className="bulk-add-format">
        <p className="bulk-add-help">{t('bulkAdd.formatBody')}</p>
        <pre className="bulk-add-example">{EXAMPLE_CSV}</pre>
        <p className="bulk-add-help">
          <a href="/cocina-ejemplo.zip" download>{t('bulkAdd.downloadExample')}</a>
        </p>
      </div>
    </div>
  );
}
