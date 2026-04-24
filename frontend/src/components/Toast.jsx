import { Notification } from 'hds-react';
import { useTranslation } from 'react-i18next';

export default function Toast({ toast, onClose }) {
  const { t } = useTranslation();

  if (!toast) return null;

  return (
    <Notification
      aria-live="polite"
      label={toast.type === 'success' ? t('common.done') : t('common.error')}
      type={toast.type}
      dismissible
      closeButtonLabelText={t('common.close')}
      onClose={onClose}
      style={{ marginTop: 'var(--spacing-m)' }}
    >
      {toast.message}
    </Notification>
  );
}
