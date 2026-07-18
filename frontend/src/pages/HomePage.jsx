import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import FeedbackLink from '../components/FeedbackLink';
import CollectionLinkbox from '../components/CollectionLinkbox';
import InboxNotifications from '../components/InboxNotifications';
import useTheeeme from '../hooks/useTheeeme';
import ContactCorner from '../components/ContactCorner';
import { useLocalized } from '../utils/localized';

export default function HomePage() {
  const { t } = useTranslation();
  // Owner content (invitation headlines) may carry one text per language.
  const L = useLocalized();
  useEffect(() => { document.title = t('titles.home'); }, [t]);
  const [user, setUser] = useState(null);
  const [myCollections, setMyCollections] = useState(null);
  const [invitedCollections, setInvitedCollections] = useState(null);
  const [pendingInvitations, setPendingInvitations] = useState([]);
  const [offline, setOffline] = useState(false);
  const [myCollectionsError, setMyCollectionsError] = useState(false);
  const [invitedError, setInvitedError] = useState(false);
  // The inbox fetches itself; bumping this makes it re-fetch alongside a dashboard
  // retry (a returning connection, the Retry buttons).
  const [inboxReloads, setInboxReloads] = useState(0);

  const loadDashboard = useCallback((signal) => {
    // A failed fetch rejects with a TypeError ("Failed to fetch") only on a real
    // network/connection error; an HTTP error status resolves normally. Surface
    // a degraded banner + retry on that (or an explicit offline) instead of a
    // silent gap or an endless "Loading collections..." spinner. An aborted
    // request (unmount) is neither an error nor an offline signal — ignore it.
    const onNetworkError = (err) => {
      if (signal?.aborted) return;
      if (err?.name === 'TypeError' || !navigator.onLine) setOffline(true);
    };

    const fetchMe = async () => {
      try {
        const res = await apiFetch('/api/v1/auth/me/', { signal });
        if (res.ok) {
          const data = await res.json();
          if (signal?.aborted) return;
          if (data.code) localStorage.setItem('userCode', data.code);
          if (data.theeeme_colors) localStorage.setItem('theeemeColors', JSON.stringify(data.theeeme_colors));
          if (data.koro) localStorage.setItem('koro', data.koro);
          localStorage.setItem('seenWelcome', 'true');
          setUser(data);
        }
      } catch (err) {
        onNetworkError(err);
      }
    };

    const fetchMyCollections = async () => {
      try {
        const res = await apiFetch('/api/v1/collections/', { signal });
        if (res.ok) {
          const data = await res.json();
          if (!signal?.aborted) { setMyCollections(data.results); setMyCollectionsError(false); }
        } else if (!signal?.aborted) {
          setMyCollectionsError(true);
        }
      } catch (err) { onNetworkError(err); }
    };

    const fetchInvitedCollections = async () => {
      try {
        const res = await apiFetch('/api/v1/invited-collections/', { signal });
        if (res.ok) {
          const data = await res.json();
          if (!signal?.aborted) { setInvitedCollections(data); setInvitedError(false); }
        } else if (!signal?.aborted) {
          setInvitedError(true);
        }
      } catch (err) { onNetworkError(err); }
    };

    const fetchPendingInvitations = async () => {
      try {
        const res = await apiFetch('/api/v1/my-invitations/', { signal });
        if (res.ok) {
          const data = await res.json();
          if (!signal?.aborted) setPendingInvitations(data);
        }
      } catch (err) { onNetworkError(err); }
    };

    fetchMe();
    fetchMyCollections();
    fetchInvitedCollections();
    fetchPendingInvitations();
  }, []);

  // Stable across renders so the inbox's fetch effect doesn't re-run on every one.
  const handleNetworkError = useCallback((err) => {
    if (err?.name === 'TypeError' || !navigator.onLine) setOffline(true);
  }, []);

  const reloadDashboard = useCallback(() => {
    setOffline(false);
    setInboxReloads((n) => n + 1);
    loadDashboard();
  }, [loadDashboard]);

  useEffect(() => {
    const controller = new AbortController();
    loadDashboard(controller.signal);
    return () => controller.abort();
  }, [loadDashboard]);

  useEffect(() => {
    // Re-fetch automatically when the browser regains connectivity.
    window.addEventListener('online', reloadDashboard);
    return () => window.removeEventListener('online', reloadDashboard);
  }, [reloadDashboard]);

  const dismissInvitation = (acceptCode) => {
    setPendingInvitations((prev) => prev.filter((inv) => inv.accept_code !== acceptCode));
  };

  const offlineBanner = (
    <Notification type="alert" label={t('home.offlineLabel')} style={{ marginBottom: 'var(--spacing-s)' }}>
      {t('home.offlineBody')}
      <div style={{ marginTop: 'var(--spacing-xs)' }}>
        <Button size="small" onClick={reloadDashboard}>{t('common.retry')}</Button>
      </div>
    </Notification>
  );

  // A section failed to load over a working connection (a non-OK HTTP response,
  // not a network error): inline error + Retry, which re-runs the whole
  // dashboard and clears the error so the section swaps back to "Loading…"
  // while the refetch is in flight. Network errors stay the offline banner's
  // job via onNetworkError.
  const sectionError = (
    <Notification type="error" label={t('home.loadErrorLabel')} style={{ marginBottom: 'var(--spacing-s)' }}>
      {t('home.loadErrorBody')}
      <div style={{ marginTop: 'var(--spacing-xs)' }}>
        <Button
          size="small"
          onClick={() => { setMyCollectionsError(false); setInvitedError(false); reloadDashboard(); }}
        >
          {t('common.retry')}
        </Button>
      </div>
    </Notification>
  );

  // Derive theeeme styles from the freshly-fetched colours (fall back to
  // localStorage/DEFAULT before the fetch resolves). Called at the top level so
  // the hook order stays stable across the `!user` early return below.
  const { tc, btnStyle, btnSecondaryStyle } = useTheeeme(user?.theeeme_colors);

  if (!user) {
    return offline ? <div className="page-container">{offlineBanner}</div> : <LoadingSpinner />;
  }

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})`, '--hero-logo-color': `var(--color-${tc.color_02})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <ContactCorner />
          <h1 className="form-hero-title" style={{ paddingTop: 'var(--spacing-xl)' }}>{t('home.greeting', { name: user.name || user.email })}</h1>
          {user.headline && <p className="form-hero-text">{user.headline}</p>}
          <div className="button-row-wide">
            <Link to="/collections/new">
              <Button style={btnStyle}>{t('home.createCollection')}</Button>
            </Link>
            <Link to="/me">
              <Button variant="secondary" style={btnSecondaryStyle}>{t('home.myProfile')}</Button>
            </Link>
            <Link to="/my-bookings">
              <Button variant="secondary" style={btnSecondaryStyle}>{t('home.myRequests')}</Button>
            </Link>
          </div>
        </div>
        <Koros
          className="form-hero-koros"
          type={user.koro || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">

        {offline && offlineBanner}

        <InboxNotifications reloadKey={inboxReloads} onNetworkError={handleNetworkError} />

        {pendingInvitations.length > 0 && (
          <>
            {pendingInvitations.map((inv) => (
              <Notification
                key={inv.accept_code}
                label={t('home.invitedBy', { name: inv.owner_name })}
                type="info"
                dismissible
                closeButtonLabelText={t('home.dismiss')}
                onClose={() => dismissInvitation(inv.accept_code)}
                style={{ marginBottom: 'var(--spacing-s)' }}
              >
                <strong>{L(inv.collection_headline)}</strong>
                <div style={{ marginTop: 'var(--spacing-xs)', display: 'flex', gap: 'var(--spacing-s)', flexWrap: 'wrap' }}>
                  <Link to={`/verify/${inv.accept_code}`}>{t('home.acceptInvitation')}</Link>
                  <Link to={`/verify/${inv.reject_code}`}>{t('home.declineInvitation')}</Link>
                </div>
              </Notification>
            ))}
            <div className="spacer-m" />
          </>
        )}

        <h2>{t('userPage.myCollections')}</h2>
        <div className="spacer-m" />
        {myCollectionsError ? (
          sectionError
        ) : myCollections === null ? (
          <p className="text-muted">{t('userPage.loadingCollections')}</p>
        ) : myCollections.filter((c) => c.status === 'ACTIVE').length === 0 ? (
          <div>
            <p>{t('userPage.noCollections')}</p>
            <p className="text-muted">{t('userPage.collectionExplainer')}</p>
            <div className="spacer-m" />
            <div className="button-row-wide">
              <Link to="/collections/new">
                <Button style={btnStyle}>{t('userPage.createFirst')}</Button>
              </Link>
              <Link to="/welcome">
                <Button variant="secondary" style={btnSecondaryStyle}>{t('userPage.learnHow')}</Button>
              </Link>
            </div>
          </div>
        ) : (
          <div className="collections-grid">
            {myCollections.filter((c) => c.status === 'ACTIVE').map((c) => (
              <CollectionLinkbox key={c.code} collection={c} showInfo />
            ))}
          </div>
        )}

        {myCollections !== null && myCollections.filter((c) => c.status === 'INACTIVE').length > 0 && (
          <>
            <div className="spacer-xl" />
            <h2>{t('userPage.inactiveCollections')}</h2>
            <div className="spacer-m" />
            <div className="collections-grid">
              {myCollections.filter((c) => c.status === 'INACTIVE').map((c) => (
                <CollectionLinkbox key={c.code} collection={c} showInfo />
              ))}
            </div>
          </>
        )}

        <div className="spacer-xl" />
        <h2>{t('userPage.sharedWithMe')}</h2>
        <div className="spacer-m" />
        {invitedError ? (
          sectionError
        ) : invitedCollections === null ? (
          <p className="text-muted">{t('userPage.loadingCollections')}</p>
        ) : invitedCollections.length === 0 ? (
          <p>{t('userPage.noShared')}</p>
        ) : (
          <div className="collections-grid">
            {invitedCollections.map((c) => (
              <CollectionLinkbox key={c.code} collection={c} showInfo />
            ))}
          </div>
        )}

        <FeedbackLink />
      </div>
    </div>
  );
}
