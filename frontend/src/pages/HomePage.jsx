import { useCallback, useEffect, useState } from 'react';
import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button, Koros, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import { fetchAllPages } from '../utils/fetchAllPages';
import { hasNoName } from '../utils/profile';
import LoadingSpinner from '../components/LoadingSpinner';
import FeedbackLink from '../components/FeedbackLink';
import CollectionLinkbox from '../components/CollectionLinkbox';
import InboxNotifications from '../components/InboxNotifications';
import useTheeeme from '../hooks/useTheeeme';
import AccountMenu from '../components/AccountMenu';
import { aboutPath } from '../deployment';
import { useLocalized } from '../utils/localized';
import ButtonLink from '../components/ButtonLink';
import StatusRegion from '../components/StatusRegion';
import useDocumentTitle from '../hooks/useDocumentTitle';

export default function HomePage() {
  const { t } = useTranslation();
  // Owner content (invitation headlines) may carry one text per language.
  const L = useLocalized();
  useDocumentTitle(t('titles.home'));
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
          setUser(data);
        }
      } catch (err) {
        onNetworkError(err);
      }
    };

    const fetchMyCollections = async () => {
      try {
        const { rows, complete } = await fetchAllPages(
          apiFetch,
          '/api/v1/collections/?page_size=100',
          { signal }
        );
        if (!signal?.aborted) {
          // A first page that failed leaves the list as it was (still loading),
          // exactly as before; a later page that failed keeps what came.
          if (complete || rows.length) setMyCollections(rows);
          setMyCollectionsError(!complete);
        }
      } catch (err) {
        onNetworkError(err);
      }
    };

    const fetchInvitedCollections = async () => {
      try {
        const res = await apiFetch('/api/v1/invited-collections/', { signal });
        if (res.ok) {
          const data = await res.json();
          if (!signal?.aborted) {
            // A co-curator is always on the invite list too, so the group they
            // help run came back here as well and showed twice, under "My
            // collections" and under "Shared with me". It is
            // theirs to run: it stays under "My collections" only. Filtered here,
            // not in the endpoint, because the profile's "My groups" reads the
            // same list and must keep it.
            setInvitedCollections(data.filter((c) => !c.is_curator));
            setInvitedError(false);
          }
        } else if (!signal?.aborted) {
          setInvitedError(true);
        }
      } catch (err) {
        onNetworkError(err);
      }
    };

    const fetchPendingInvitations = async () => {
      try {
        const res = await apiFetch('/api/v1/my-invitations/', { signal });
        if (res.ok) {
          const data = await res.json();
          if (!signal?.aborted) setPendingInvitations(data);
        }
      } catch (err) {
        onNetworkError(err);
      }
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

  // Derive theeeme styles from the freshly-fetched colours (fall back to
  // localStorage/DEFAULT before the fetch resolves). Called at the top level so
  // the hook order stays stable across the `!user` early return below — and
  // above the two notices that follow, whose Retry buttons wear the style.
  const { tc, btnStyle, btnSecondaryStyle } = useTheeeme();

  const offlineBanner = (
    <Notification
      type="alert"
      label={t('home.offlineLabel')}
      style={{ marginBottom: 'var(--spacing-s)' }}
    >
      {t('home.offlineBody')}
      <div style={{ marginTop: 'var(--spacing-xs)' }}>
        <Button size="small" onClick={reloadDashboard} style={btnSecondaryStyle}>
          {t('common.retry')}
        </Button>
      </div>
    </Notification>
  );

  // A section failed to load over a working connection (a non-OK HTTP response,
  // not a network error): inline error + Retry, which re-runs the whole
  // dashboard and clears the error so the section swaps back to "Loading…"
  // while the refetch is in flight. Network errors stay the offline banner's
  // job via onNetworkError.
  const sectionError = (
    <Notification
      type="error"
      label={t('home.loadErrorLabel')}
      style={{ marginBottom: 'var(--spacing-s)' }}
    >
      {t('home.loadErrorBody')}
      <div style={{ marginTop: 'var(--spacing-xs)' }}>
        <Button
          size="small"
          style={btnSecondaryStyle}
          onClick={() => {
            setMyCollectionsError(false);
            setInvitedError(false);
            reloadDashboard();
          }}
        >
          {t('common.retry')}
        </Button>
      </div>
    </Notification>
  );

  // Most accounts are members, not curators: they arrive through somebody
  // else's group and may never start one. Leading with "My collections" gave
  // them an empty state and a "Create your first collection" call before the
  // one thing they actually have — below the fold on a phone, under the hero's
  // buttons. Once we know they own nothing and belong somewhere, their groups
  // come first and the invitation to create sits under them.
  const groupsFirst = myCollections?.length === 0 && invitedCollections?.length > 0;

  // One "Create collection" button, in one place (a new account saw
  // two buttons for the same thing). With any collection of their own — active or
  // not — it is in the hero and the list below is only the list. With none at all
  // it is the invitation under "My collections" instead, and the hero has none.
  // While the read is in flight there is no button yet (one that appears and then
  // disappears is worse than none); if the read fails, the hero's is the one that
  // is there, since the page cannot say which of the two this account is.
  const myCollectionsFailed = myCollectionsError || (myCollections === null && offline);
  const heroCreateButton =
    myCollectionsFailed || (myCollections !== null && myCollections.length > 0);

  const myCollectionsSection = (
    <>
      <h2>{t('userPage.myCollections')}</h2>
      <div className="spacer-m" />
      {/* A later page that failed leaves the groups already read: they are listed
          under the notice rather than hidden behind it. */}
      {myCollectionsError && myCollections?.length > 0 && sectionError}
      {myCollectionsError && !myCollections?.length ? (
        sectionError
      ) : myCollections === null ? (
        <p className="text-muted">{t('userPage.loadingCollections')}</p>
      ) : myCollections.length > 0 &&
        myCollections.filter((c) => c.status === 'ACTIVE').length === 0 ? (
        // Collections, none of them active: the hero has the button, and the
        // inactive ones are listed below. Nothing here to invite them to create.
        <p>{t('userPage.noCollections')}</p>
      ) : myCollections.length === 0 ? (
        <div>
          <p>{t('userPage.noCollectionsYet')}</p>
          <p className="text-muted">{t('userPage.collectionExplainer')}</p>
          <div className="spacer-m" />
          <div className="button-row-wide">
            <ButtonLink to="/new" style={btnStyle}>
              {t('userPage.createFirst')}
            </ButtonLink>
            {/* Only where this deployment has a page saying what it is.
                Upstream there is none — /welcome left with the demo — and this
                sits on the first screen a brand-new account sees, so a second
                button that 404s is worse here than anywhere else in the app.
                Same rule as the footer's about link: no page, no link. */}
            {aboutPath && (
              <ButtonLink to={aboutPath} style={btnSecondaryStyle}>
                {t('userPage.learnHow')}
              </ButtonLink>
            )}
          </div>
        </div>
      ) : (
        <div className="collections-grid">
          {myCollections
            .filter((c) => c.status === 'ACTIVE')
            .map((c) => (
              <CollectionLinkbox key={c.code} collection={c} showInfo />
            ))}
        </div>
      )}

      {myCollections !== null &&
        myCollections.filter((c) => c.status === 'INACTIVE').length > 0 && (
          <>
            <div className="spacer-xl" />
            <h2>{t('userPage.inactiveCollections')}</h2>
            <div className="spacer-m" />
            <div className="collections-grid">
              {myCollections
                .filter((c) => c.status === 'INACTIVE')
                .map((c) => (
                  <CollectionLinkbox key={c.code} collection={c} showInfo />
                ))}
            </div>
          </>
        )}
    </>
  );

  const sharedSection = (
    <>
      <h2>{t('userPage.sharedWithMe')}</h2>
      <div className="spacer-m" />
      {invitedError ? (
        sectionError
      ) : invitedCollections === null ? (
        <p className="text-muted">{t('userPage.loadingCollections')}</p>
      ) : invitedCollections.length === 0 ? (
        <p>{t('userPage.noShared')}</p>
      ) : (
        <>
          <div className="collections-grid">
            {invitedCollections.map((c) => (
              <CollectionLinkbox key={c.code} collection={c} showInfo />
            ))}
          </div>
        </>
      )}
    </>
  );

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
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div
          className="form-hero-content"
          style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}
        >
          <span className="hero-corners">
            <AccountMenu />
          </span>
          {/* The address is never the greeting: someone who arrived by invitation and
              never set a name is just greeted. */}
          <h1 className="form-hero-title">
            {user.name ? t('home.greeting', { name: user.name }) : t('home.greetingNoName')}
          </h1>
          {user.headline && <p className="form-hero-text">{user.headline}</p>}
          {/* One button, the one thing only Home offers. "My profile", "My
              requests" and "Requests to me" live in the account menu above (in
              every hero since 2026-09-28): this row used to repeat all three, up
              to four full-width buttons stacked on a phone before the inbox and
              the groups — the crowding that had to go. It
              also judged "Requests to me" differently from the menu (hidden from
              whoever cannot receive requests, where the menu always shows it).
              And only once there is something to create *another* of: an account
              with no collection gets the invitation under "My collections". */}
          {heroCreateButton && (
            <div className="button-row-wide">
              <ButtonLink to="/new" style={btnStyle}>
                {t('home.createCollection')}
              </ButtonLink>
            </div>
          )}
        </div>
        <Koros
          className="form-hero-koros"
          type={user.koro || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <StatusRegion>{offline && offlineBanner}</StatusRegion>

        <InboxNotifications reloadKey={inboxReloads} onNetworkError={handleNetworkError} />

        {pendingInvitations.length > 0 && (
          <>
            {pendingInvitations.map((inv) => (
              <Notification
                key={inv.accept_code}
                // `owner_name` is the bare name — the API withholds the owner's
                // address from someone who is only invited so far — so an
                // owner who never set one arrives empty and needs a subject.
                label={t('home.invitedBy', { name: inv.owner_name || t('common.aMember') })}
                type="info"
                dismissible
                closeButtonLabelText={t('home.dismiss')}
                onClose={() => dismissInvitation(inv.accept_code)}
                style={{ marginBottom: 'var(--spacing-s)' }}
              >
                <strong>{L(inv.collection_headline)}</strong>
                {/* The answer is two buttons, as everywhere else something is decided
                    (a thing's hero, the invitation email): accepting is the primary
                    and comes first, declining the secondary. They
                    used to be two text links side by side. In a `.button-row-wide`, so on a
                    phone each is the width of the screen; the destinations are the same
                    `/verify/` links as ever. */}
                <div className="button-row-wide" style={{ marginTop: 'var(--spacing-xs)' }}>
                  <ButtonLink to={`/verify/${inv.accept_code}`} style={btnStyle}>
                    {t('home.acceptInvitation')}
                  </ButtonLink>
                  <ButtonLink to={`/verify/${inv.reject_code}`} style={btnSecondaryStyle}>
                    {t('home.declineInvitation')}
                  </ButtonLink>
                </div>
              </Notification>
            ))}
            <div className="spacer-m" />
          </>
        )}

        {/* Until the account has a name (a nickname will do), a kind nudge to give one: whoever
            runs a group sees "A member" otherwise. No close button and nothing remembered in
            the browser: it goes by itself when the name is there. No `state` on the link, so
            saving the profile comes back here, which is where the person is. */}
        {hasNoName(user) && (
          <>
            <Notification label={t('profileNudge.label')} type="info">
              {t('profileNudge.body')} <Link to="/me/edit">{t('profileNudge.link')}</Link>
            </Notification>
            <div className="spacer-m" />
          </>
        )}

        {groupsFirst ? sharedSection : myCollectionsSection}
        <div className="spacer-xl" />
        {groupsFirst ? myCollectionsSection : sharedSection}

        {/* Alone, and secondary. A loose action button goes in a
            `.button-row-wide` even when it is the only one, so on a phone it is the
            width of the screen; `.feedback-link` on the same
            element keeps the gap above it. The row is empty when the deployment
            has no feedback URL, and App.css hides an empty `.feedback-link`. */}
        <div className="button-row-wide feedback-link">
          <FeedbackLink style={btnSecondaryStyle} />
        </div>
      </div>
    </div>
  );
}
