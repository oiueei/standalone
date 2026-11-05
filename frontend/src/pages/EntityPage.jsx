import { useEffect, useState } from 'react';
import { useParams } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Koros, Notification, IconGlobe, IconLocation, IconClock, IconCalendar } from 'hds-react';
import { apiFetch } from '../services/api';
import AccountMenu from '../components/AccountMenu';
import BackLink from '../components/BackLink';
import ButtonLink from '../components/ButtonLink';
import LoadingSpinner from '../components/LoadingSpinner';
import MarkdownText from '../components/MarkdownText';
import PageLayout from '../components/PageLayout';
import RefusalWayOut from '../components/RefusalWayOut';
import NotFoundPage from './NotFoundPage';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { useCanonicalCollectionPath } from '../hooks/useCollectionBase';
import { collectionPath } from '../utils/collectionPath';
import { useLocalized } from '../utils/localized';
import { weekdayLabel } from '../utils/rental';
import { formatList } from '../utils/team';

/**
 * The page a curator has in a group, as everyone who can read the group sees it
 * (`/{kind}/{code}/organisation/{userCode}`, public like the collection itself): the
 * entity's logo and name in the collection's own hero, then its contact and, **in a
 * network**, where and when to collect and return, its About and a way to what it lends.
 * Outside a network the place belongs to the group, so only the contact and the About.
 *
 * It reads the collection (`GET /collections/{code}/`, whose `points` carry every
 * curator's page) and finds the person's in it: there is no endpoint of its own. Someone
 * who is not the founder or a co-curator has no page here; a curator who never set one
 * is shown by their account name, with no logo and no About.
 */
export default function EntityPage() {
  const { t, i18n } = useTranslation();
  const L = useLocalized();
  const { code, userCode } = useParams();
  const { btnStyle, tc, koro } = useTheeeme();
  const [collection, setCollection] = useState(null);
  const [error, setError] = useState('');

  useCollectionTheeeme(collection?.theeeme_colors, collection?.koro);
  useCollectionLanguage(collection?.language || '', [collection?.headline]);
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

  const isOwner = collection?.owner === userCode;
  const coOwner = (collection?.co_owners || []).find((member) => member.code === userCode);
  const isTeam = !!collection && (isOwner || !!coOwner);
  const card = isTeam ? (collection.points || []).find((point) => point.user === userCode) : null;
  const name =
    card?.display_name || (isOwner ? collection?.owner_name : coOwner?.name) || t('common.aMember');
  useDocumentTitle(isTeam ? t('titles.user', { name }) : t('titles.notFound'));

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
  if (!isTeam) return <NotFoundPage />;

  const isNetwork = collection.mode === 'NETWORK';
  const base = collectionPath(code, collection.kind);
  const groupName = L(collection.headline);
  const language = i18n.resolvedLanguage || i18n.language;
  const days = isNetwork && card?.weekdays?.length ? card.weekdays : [];
  const about = card?.about ? L(card.about) : '';
  // The place is a network's: outside one the address, hours and days are never shown,
  // whatever the answer holds.
  const rows = [
    { key: 'contact', icon: IconGlobe, value: card?.contact, label: 'organisation.contact' },
    ...(isNetwork
      ? [
          {
            key: 'address',
            icon: IconLocation,
            value: card?.address,
            label: 'organisation.address',
          },
          { key: 'hours', icon: IconClock, value: card?.hours_note, label: 'organisation.hours' },
          {
            key: 'days',
            icon: IconCalendar,
            value: days.length
              ? formatList(
                  days.map((day) => weekdayLabel(day, language)),
                  language
                )
              : '',
            label: 'organisation.days',
          },
        ]
      : []),
  ].filter((row) => row.value);

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero form-hero--collection"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-split">
          <div
            className="form-hero-content"
            style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}
          >
            <span className="hero-corners">
              <AccountMenu />
            </span>
            <BackLink to={base} label={groupName || t('common.collection')} />
            {card?.logo_url && <img className="hero-logo" src={card.logo_url} alt="" />}
            <h1 className="form-hero-title">{name}</h1>
            <p className="form-hero-text">
              {t(isNetwork ? 'organisation.pickupOf' : 'organisation.runs', {
                collection: groupName,
              })}
            </p>
          </div>
        </div>
        <Koros
          className="form-hero-koros"
          type={koro}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        {rows.length > 0 && (
          <div className="thing-card-info">
            {rows.map((row) => {
              const RowIcon = row.icon;
              return (
                <div className="thing-card-info-row" key={row.key}>
                  <RowIcon size="m" aria-hidden="true" />
                  <span>{t(row.label, { value: row.value })}</span>
                </div>
              );
            })}
          </div>
        )}
        {about && (
          <>
            <h2>{t('organisation.aboutLabel')}</h2>
            <MarkdownText text={about} />
          </>
        )}
        {isNetwork && (
          <div className="button-row-wide">
            <ButtonLink to={`${base}/${userCode}`} style={btnStyle}>
              {t('organisation.seeWhatTheyLend')}
            </ButtonLink>
          </div>
        )}
      </div>
    </div>
  );
}
