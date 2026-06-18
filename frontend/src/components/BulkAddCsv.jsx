import { useState } from 'react';
import { FileInput, Button, Notification } from 'hds-react';
import { useTranslation } from 'react-i18next';
import Papa from 'papaparse';
import { apiFetch } from '../services/api';
import useTheeeme from '../hooks/useTheeeme';

const MAX_ROWS = 100;
// The plain text/scalar columns a CSV can carry. Photos, gallery, documents and
// tags are not part of a bulk upload (they need uploads / collection vocabulary).
const COLUMNS = ['type', 'headline', 'description', 'fee', 'availability', 'location', 'condition'];

// HDS FileInput only supports fi, sv, en — everything else falls back to en.
function hdsLang(lang) {
  if (lang === 'fi' || lang === 'sv') return lang;
  return 'en';
}

/**
 * Bulk-add things from a CSV (F-9). Parses the file client-side with PapaParse,
 * shows a preview, then posts the rows to the atomic batch endpoint
 * (`POST /collections/{code}/things/bulk/`) — all rows are created or none.
 * Server-side validators reject HTML, line breaks and spreadsheet-formula
 * (CSV) injection per field.
 *
 * Props:
 *   collectionCode – target collection
 *   onImported(count) – called after a successful import
 */
export default function BulkAddCsv({ collectionCode, onImported }) {
  const { t, i18n } = useTranslation();
  const { btnStyle } = useTheeeme();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [importing, setImporting] = useState(false);
  const [fileInputKey, setFileInputKey] = useState(0);

  const handleFiles = (files) => {
    setError(null);
    setRows([]);
    setFileInputKey((k) => k + 1);
    const file = files && files[0];
    if (!file) return;

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      transformHeader: (h) => h.trim().toLowerCase(),
      complete: (result) => {
        const parsed = (result.data || [])
          .map((raw) => {
            const row = {};
            for (const col of COLUMNS) {
              const value = raw[col];
              if (value !== undefined && String(value).trim() !== '') {
                row[col] = String(value).trim();
              }
            }
            return row;
          })
          .filter((row) => Object.keys(row).length > 0);

        if (parsed.length === 0) {
          setError(t('bulkAdd.empty'));
        } else if (parsed.length > MAX_ROWS) {
          setError(t('bulkAdd.tooMany', { max: MAX_ROWS }));
        } else if (parsed.some((row) => !row.headline)) {
          setError(t('bulkAdd.headlineRequired'));
        } else {
          setRows(parsed);
        }
      },
      error: () => setError(t('bulkAdd.parseError')),
    });
  };

  const handleImport = async () => {
    setImporting(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${collectionCode}/things/bulk/`, {
        method: 'POST',
        body: JSON.stringify({ rows }),
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
    }
  };

  return (
    <div className="bulk-add">
      <p className="bulk-add-help">{t('bulkAdd.help')}</p>
      <FileInput
        key={fileInputKey}
        id="bulk-add-csv"
        label={t('bulkAdd.fileLabel')}
        accept=".csv,text/csv"
        multiple={false}
        onChange={handleFiles}
        language={hdsLang(i18n.language)}
        buttonLabel={t('upload.addFile')}
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
              </li>
            ))}
          </ol>
          <Button
            style={{ ...btnStyle, marginTop: 'var(--spacing-s)' }}
            disabled={importing}
            onClick={handleImport}
          >
            {importing ? t('bulkAdd.importing') : t('bulkAdd.import', { count: rows.length })}
          </Button>
        </>
      )}
    </div>
  );
}
