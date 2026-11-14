import { useEffect, useState } from 'react';
import { useParams } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import MarkdownText from '../components/MarkdownText';
import PageLayout from '../components/PageLayout';
import RefusalWayOut from '../components/RefusalWayOut';
import NotFoundPage from './NotFoundPage';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { useCanonicalCollectionPath } from '../hooks/useCollectionBase';
import { collectionPath } from '../utils/collectionPath';
import { useLocalized } from '../utils/localized';

/**
 * "Donate things" (`/{kind}/{code}/donate`): the instructions a library's team wrote for
 * whoever wants to give it things, in the collection's own hero. **Public, like the
 * collection**: whoever can read the group reads it. Nothing is sent or saved here; it is
 * a page of words.
 *
 * It reads the collection (`GET /collections/{code}/`) and shows `donations_info`. A
 * collection that is not a library, or does not accept donations, has no such page: the
 * usual not-found, even if it still holds a text from before it was turned off.
 */
export default function DonatePage() {
  const { t } = useTranslation();
  const L = useLocalized();
  const { code } = useParams();
  const [collection, setCollection] = useState(null);
  const [error, setError] = useState('');

  useCollectionTheeeme(collection?.theeeme_colors, collection?.koro);
  useCollectionLanguage(collection?.language || '', [
    collection?.headline,
    collection?.donations_info,
  ]);
  useCanonicalCollectionPath(collection?.kind);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`, { signal });
        if (signal.aborted) return;
        if (res.ok) {
          const data = await res.json();
          if (!signal.aborted) setCollection(data);
        } else if (res.status === 403) {
          setError('collectionPage.noPermission');
        } else if (res.status === 404) {
          setError('notFound');
        } else {
          setError('collectionPage.errorLoading');
        }
      } catch (err) {
        if (!signal.aborted && err?.name !== 'AbortError') setError('common.connectionError');
      }
    })();
    return () => controller.abort();
  }, [code]);

  const available = !!collection && collection.kind === 'LIBRARY' && !!collection.accepts_donations;
  useDocumentTitle(
    available ? t('titles.donate', { collection: L(collection.headline) }) : t('titles.notFound')
  );

  if (error === 'notFound') return <NotFoundPage />;
  if (error) {
    const noAccess = error === 'collectionPage.noPermission';
    return (
      <PageLayout
        title={noAccess ? t('collectionPage.noAccessTitle') : t('common.error')}
        backTo="/"
        backLabel={t('common.home')}
      >
        <Notification
          label={noAccess ? t('common.notice') : t('common.error')}
          type={noAccess ? 'info' : 'error'}
        >
          {t(error)}
        </Notification>
        {noAccess && <RefusalWayOut />}
      </PageLayout>
    );
  }
  if (!collection) return <LoadingSpinner />;
  if (!available) return <NotFoundPage />;

  return (
    <PageLayout
      title={t('donations.pageTitle')}
      backTo={collectionPath(code, collection.kind)}
      backLabel={L(collection.headline) || t('common.collection')}
      logoUrl={collection.thumbnail_url}
      heroClassName="form-hero--collection"
    >
      {/* The text IS the page's content, as the legal text is: its `#` is an h2, so the outline
          goes h1 → h2 with no level skipped. */}
      <MarkdownText text={L(collection.donations_info)} headingBase={2} />
    </PageLayout>
  );
}
