import { useTranslation } from 'react-i18next';
import { Button } from 'hds-react';

/**
 * Inline consequence-confirm (DESIGN §3): a trigger Button whose `aria-expanded`
 * toggles a confirm box directly beneath it — no modal. The canonical pattern for
 * irreversible or "touches another person" actions (report a listing, resolve /
 * accept a wish, accept an ownership-transferring hold).
 *
 * The PARENT owns the `open` state, so a list of rows can key it per-item and keep
 * at most one open at a time. `onTriggerClick` toggles; `onClose` always closes
 * (Cancel). The trigger and confirm Buttons are styled via `triggerProps` /
 * `confirmProps` (variant / size / style / iconStart / loadingText), mirroring the
 * `.thing-report-confirm` markup this replaces.
 *
 * Required: open, onTriggerClick, onClose, triggerLabel, title, body, confirmLabel,
 * onConfirm. Optional: triggerProps, confirming, confirmProps.
 */
export default function InlineConfirm({
  open,
  onTriggerClick,
  onClose,
  triggerLabel,
  triggerProps,
  title,
  body,
  confirmLabel,
  onConfirm,
  confirming = false,
  confirmProps,
}) {
  const { t } = useTranslation();
  return (
    <>
      <Button aria-expanded={open} onClick={onTriggerClick} {...triggerProps}>
        {triggerLabel}
      </Button>
      {open && (
        <div className="thing-report-confirm">
          <p><strong>{title}</strong></p>
          <p>{body}</p>
          <div className="button-row">
            <Button
              {...confirmProps}
              disabled={confirming}
              isLoading={confirming}
              onClick={onConfirm}
            >
              {confirmLabel}
            </Button>
            <Button variant="supplementary" size="small" onClick={onClose}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
