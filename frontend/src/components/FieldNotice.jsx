import { useState } from 'react';
import { Notification } from 'hds-react';
import { useTranslation } from 'react-i18next';

/**
 * A small inline help notice that sits open above the field it explains, instead
 * of behind an (i) button. Closing it hides it for as long as the component stays
 * mounted and nothing more: no storage and no server, so it comes back on reload
 * or when the page is opened again.
 *
 * Props: `id`, `label` (the notice's accessible name), `children` (first
 * paragraph), `example` (optional code sample the owner copies) and `after`
 * (optional second paragraph).
 */
export default function FieldNotice({ id, label, children, example, after }) {
  const { t } = useTranslation();
  const [closed, setClosed] = useState(false);

  if (closed) return null;

  return (
    <Notification
      id={id}
      type="info"
      size="small"
      label={label}
      // HDS names its landmark "Notification" by default; two notices on one page would
      // be two landmarks with the same name (axe: landmark-unique). The field's own name
      // follows "Notice:", so the landmark never answers to the label of its field.
      notificationAriaLabel={`${t('common.notice')}: ${label}`}
      dismissible
      closeButtonLabelText={t('common.close')}
      onClose={() => setClosed(true)}
      style={{ marginBottom: 'var(--spacing-xs)' }}
    >
      <p>{children}</p>
      {example && <code className="localized-example">{example}</code>}
      {after && <p>{after}</p>}
    </Notification>
  );
}
