import { useId, useRef, useState } from 'react';
import { FileInput, Button, Notification, IconInfoCircleFill } from 'hds-react';
import { useTranslation } from 'react-i18next';
import Papa from 'papaparse';
import { apiFetch } from '../services/api';
import { stripSepLine, CSV_DELIMITERS } from '../utils/csv';
import useTheeeme from '../hooks/useTheeeme';
import hdsLang from '../utils/hdsLang';

const MAX_ROWS = 100;
// An "email" column (required) and an optional "name" column.
const COLUMNS = ['email', 'name'];

// Shown in the format hint popover. Language-agnostic, so it lives here rather
// than in the i18n bundles.
const EXAMPLE_CSV = `email,name
lala@mail.com,
lele@mail.com,LeLe
lili@mail.com,Super LiLi
lolo@mail.com,
lulu@mail.com,`;

const REASON_KEY = {
  invalid: 'bulkInvite.reasonInvalid',
  duplicate: 'bulkInvite.reasonDuplicate',
  already_member: 'bulkInvite.reasonAlreadyMember',
  already_invited: 'bulkInvite.reasonAlreadyInvited',
};

/**
 * Bulk-invite collection guests from a CSV. Parses the file client-side with
 * PapaParse, previews the addresses, then posts them to the best-effort batch
 * endpoint (`POST /collections/{code}/invite/bulk/`). Valid, new addresses are
 * invited and emailed; the rest come back as skipped with a reason, which we
 * surface in the summary.
 *
 * Props:
 *   collectionCode – target collection
 *   onInvited() – called after a successful send (e.g. to refresh the list)
 */
export default function BulkInviteCsv({ collectionCode, onInvited }) {
  const { t, i18n } = useTranslation();
  const { btnStyle } = useTheeeme();
  const [rows, setRows] = useState([]);
  const [error, setError] = useState(null);
  const [sending, setSending] = useState(false);
  const [result, setResult] = useState(null);
  const [fileInputKey, setFileInputKey] = useState(0);
  const [showFormat, setShowFormat] = useState(false);
  const formatPanelId = useId();
  const sendLockRef = useRef(false);

  const handleFiles = (files) => {
    setError(null);
    setRows([]);
    setResult(null);
    setFileInputKey((k) => k + 1);
    const file = files && files[0];
    if (!file) return;

    Papa.parse(file, {
      header: true,
      skipEmptyLines: true,
      delimitersToGuess: CSV_DELIMITERS,
      beforeFirstChunk: stripSepLine,
      transformHeader: (h) => h.trim().toLowerCase(),
      complete: (parseResult) => {
        const parsed = (parseResult.data || [])
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
          setError(t('bulkInvite.empty'));
        } else if (parsed.length > MAX_ROWS) {
          setError(t('bulkInvite.tooMany', { max: MAX_ROWS }));
        } else if (parsed.some((row) => !row.email)) {
          setError(t('bulkInvite.emailRequired'));
        } else {
          setRows(parsed);
        }
      },
      error: () => setError(t('bulkInvite.parseError')),
    });
  };

  const handleSend = async () => {
    if (sendLockRef.current) return;
    sendLockRef.current = true;
    setSending(true);
    setError(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${collectionCode}/invite/bulk/`, {
        method: 'POST',
        body: JSON.stringify({ invites: rows }),
      });
      if (res.ok) {
        const data = await res.json();
        setResult(data);
        setRows([]);
        if (onInvited) onInvited();
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
      setError(data.error || t('bulkInvite.error'));
    } catch {
      setError(t('common.connectionError'));
    } finally {
      setSending(false);
      sendLockRef.current = false;
    }
  };

  return (
    <div className="bulk-add">
      <div className="bulk-add-help-row">
        <p className="bulk-add-help">{t('bulkInvite.help')}</p>
        <span
          className="bulk-add-info"
          onMouseEnter={() => setShowFormat(true)}
          onMouseLeave={() => setShowFormat(false)}
          onFocus={() => setShowFormat(true)}
          onBlur={() => setShowFormat(false)}
        >
          <button
            type="button"
            className="bulk-add-info-button"
            aria-label={t('bulkInvite.formatTitle')}
            aria-expanded={showFormat}
            aria-controls={showFormat ? formatPanelId : undefined}
            onClick={() => setShowFormat((v) => !v)}
          >
            <IconInfoCircleFill aria-hidden="true" />
          </button>
          {showFormat && (
            <div id={formatPanelId}>
              <Notification
                type="info"
                size="small"
                label={t('bulkInvite.formatTitle')}
                className="bulk-add-format-popover"
              >
                <p className="bulk-add-format-body">{t('bulkInvite.formatBody')}</p>
                <pre className="bulk-add-example">{EXAMPLE_CSV}</pre>
              </Notification>
            </div>
          )}
        </span>
      </div>
      <FileInput
        key={fileInputKey}
        id="bulk-invite-csv"
        label={t('bulkInvite.fileLabel')}
        accept=".csv,text/csv"
        multiple={false}
        onChange={handleFiles}
        language={hdsLang(i18n.language)}
        buttonLabel={t('upload.addFileGeneric')}
        disabled={sending}
      />
      {error && (
        <Notification type="error" size="small" style={{ marginTop: 'var(--spacing-s)' }}>
          {error}
        </Notification>
      )}
      {result && (
        <Notification
          type={result.invited > 0 ? 'success' : 'info'}
          size="small"
          style={{ marginTop: 'var(--spacing-s)' }}
        >
          {t('bulkInvite.resultInvited', { count: result.invited })}
          {result.skipped && result.skipped.length > 0 && (
            <>
              <div style={{ marginTop: 'var(--spacing-2-xs)' }}>
                {t('bulkInvite.resultSkipped', { count: result.skipped.length })}
              </div>
              <ul style={{ margin: 'var(--spacing-2-xs) 0 0', paddingLeft: 'var(--spacing-m)' }}>
                {result.skipped.map((s, i) => (
                  <li key={i}>
                    {s.email} — {t(REASON_KEY[s.reason] || 'bulkInvite.reasonInvalid')}
                  </li>
                ))}
              </ul>
            </>
          )}
        </Notification>
      )}
      {rows.length > 0 && (
        <>
          <h3 className="bulk-add-preview-title">
            {t('bulkInvite.preview', { count: rows.length })}
          </h3>
          <ol className="bulk-add-preview">
            {rows.map((row, i) => (
              <li key={i}>
                {row.email}
                {row.name ? ` — ${row.name}` : ''}
              </li>
            ))}
          </ol>
          <Button
            style={{ ...btnStyle, marginTop: 'var(--spacing-s)' }}
            disabled={sending}
            onClick={handleSend}
          >
            {sending ? t('common.sending') : t('bulkInvite.send', { count: rows.length })}
          </Button>
        </>
      )}
    </div>
  );
}
