import { Navigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Notification } from 'hds-react';
import PageLayout from './PageLayout';
import NotFoundPage from '../pages/NotFoundPage';

/**
 * What a collection form shows instead of a form when `useCollectionForm` has no
 * form to offer: the collection page for whoever cannot edit it (no message, and
 * `replace`, so "back" does not return to the setting), the not-found page, or the
 * failure said in words.
 */
export default function CollectionFormRefusal({ refusal, base }) {
  const { t } = useTranslation();
  if (refusal.type === 'redirect') return <Navigate to={base} replace />;
  if (refusal.type === 'notFound') return <NotFoundPage />;
  return (
    <PageLayout title={t('common.error')} backTo={base} backLabel={t('common.collection')}>
      <Notification label={t('common.error')} type="error">
        {t(refusal.key)}
      </Notification>
    </PageLayout>
  );
}
