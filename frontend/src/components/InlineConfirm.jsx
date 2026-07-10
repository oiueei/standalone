import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button } from 'hds-react';

/**
 * Inline consequence-confirm (DESIGN §3): a trigger Button whose `aria-expanded`
 * toggles a confirm box directly beneath it — no modal. The canonical pattern for
 * irreversible or "touches another person" actions (report a listing, resolve /
 * accept a wish, accept an ownership-transferring hold).
 *
 * Two modes:
 *  - Controlled (pass `open`): the parent owns the open state, so a list of rows
 *    can key it per-item and keep at most one open at a time. `onTriggerClick`
 *    toggles; `onClose` always closes (Cancel).
 *  - Uncontrolled (omit `open`): the component manages its own open state. Use for
 *    a single confirm whose trigger unmounts once the action resolves (e.g. the
 *    owner hold-confirm), so no stale open state can linger.
 *
 * The trigger and confirm Buttons are styled via `triggerProps` / `confirmProps`
 * (variant / size / style / iconStart / loadingText), mirroring the
 * `.thing-report-confirm` markup this replaces.
 *
 * Required: triggerLabel, title, body, confirmLabel, onConfirm. Controlled also
 * needs: open, onTriggerClick, onClose. Optional: triggerProps, confirming,
 * confirmProps.
 */
export default function InlineConfirm({
  open: openProp,
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
  const controlled = openProp !== undefined;
  const [internalOpen, setInternalOpen] = useState(false);
  const open = controlled ? openProp : internalOpen;
  const handleTrigger = controlled ? onTriggerClick : () => setInternalOpen((o) => !o);
  const handleClose = controlled ? onClose : () => setInternalOpen(false);
  // In uncontrolled mode, close the panel once the action settles (success or
  // error) so a re-rendered trigger — e.g. the next pending hold — starts fresh,
  // with no stale open state. Controlled mode leaves closing to the parent.
  const handleConfirmClick = controlled
    ? onConfirm
    : async () => {
        try {
          await onConfirm?.();
        } finally {
          setInternalOpen(false);
        }
      };

  return (
    <>
      <Button aria-expanded={open} onClick={handleTrigger} {...triggerProps}>
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
              onClick={handleConfirmClick}
            >
              {confirmLabel}
            </Button>
            <Button variant="supplementary" size="small" onClick={handleClose}>
              {t('common.cancel')}
            </Button>
          </div>
        </div>
      )}
    </>
  );
}
