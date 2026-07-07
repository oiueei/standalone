import { useTranslation } from 'react-i18next';
import { LoadingSpinner as HdsSpinner } from 'hds-react';

export default function LoadingSpinner() {
  const { t } = useTranslation();
  return (
    <div className="page-container">
      <div className="spinner-container" role="status" aria-live="polite">
        <HdsSpinner loadingText={t('common.loading')} />
      </div>
    </div>
  );
}
