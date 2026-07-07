import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, IconAlertCircleFill } from 'hds-react';
import { apiFetch } from '../services/api';

/**
 * The quiet "report this listing" footer on ThingPage, shown to logged-in
 * non-owners. Clicking expands an inline confirm right below the button (no
 * modal, `aria-expanded`); confirming POSTs the report. The owner is told
 * *someone* reported it, never who — the reporter stays server-side. Owns its
 * own open/submitting state and reports feedback via `onToast`.
 *
 * Props: `thingCode`, `onToast({type, message})`.
 */
export default function ThingReportFooter({ thingCode, onToast }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const [reporting, setReporting] = useState(false);

  const handleReport = async () => {
    setReporting(true);
    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/report/`, { method: 'POST' });
      setOpen(false);
      if (res.ok) {
        onToast({ type: 'success', message: t('thingPage.reportThanks') });
      } else if (res.status === 429) {
        onToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        onToast({ type: 'error', message: t('thingPage.reportError') });
      }
    } catch {
      setOpen(false);
      onToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setReporting(false);
    }
  };

  return (
    <div className="thing-report-footer">
      <Button
        variant="supplementary"
        size="small"
        iconStart={<IconAlertCircleFill aria-hidden="true" />}
        onClick={() => setOpen((o) => !o)}
        aria-expanded={open}
      >
        {t('thingPage.report')}
      </Button>
      {open && (
        <div className="thing-report-confirm">
          <p><strong>{t('thingPage.reportConfirmTitle')}</strong></p>
          <p>{t('thingPage.reportConfirmBody')}</p>
          <div className="button-row">
            <Button
              variant="danger"
              size="small"
              onClick={handleReport}
              disabled={reporting}
              isLoading={reporting}
              loadingText={t('thingPage.reporting')}
            >
              {t('thingPage.reportConfirm')}
            </Button>
            <Button variant="supplementary" size="small" onClick={() => setOpen(false)}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      )}
    </div>
  );
}
