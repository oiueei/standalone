import { Notification } from 'hds-react';
import { useTranslation } from 'react-i18next';

export default function Toast({ toast, onClose }) {
  const { t } = useTranslation();

  if (!toast) return null;

  return (
    <Notification
      position="top-right"
      autoClose
      autoCloseDuration={6000}
      aria-live="polite"
      label={toast.type === 'success' ? t('common.done') : t('common.error')}
      type={toast.type}
      dismissible
      closeButtonLabelText={t('common.close')}
      onClose={onClose}
    >
      {toast.message}
    </Notification>
  );
}
