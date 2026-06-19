import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros, Linkbox, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

export default function HomePage() {
  const navigate = useNavigate();
  const { t } = useTranslation();
  useEffect(() => { document.title = t('titles.home'); }, [t]);
  const [user, setUser] = useState(null);
  const [myCollections, setMyCollections] = useState(null);
  const [invitedCollections, setInvitedCollections] = useState(null);
  const [pendingInvitations, setPendingInvitations] = useState([]);
  const [inboxNotifications, setInboxNotifications] = useState([]);
  const [error, setError] = useState('');

  useEffect(() => {
    const fetchMe = async () => {
      try {
        const res = await apiFetch('/api/v1/auth/me/');
        if (res.ok) {
          const data = await res.json();
          if (data.code) localStorage.setItem('userCode', data.code);
          if (data.theeeme_colors) localStorage.setItem('theeemeColors', JSON.stringify(data.theeeme_colors));
          if (data.koro) localStorage.setItem('koro', data.koro);
          localStorage.setItem('seenWelcome', 'true');
          setUser(data);
        }
      } catch {
        setError(t('common.connectionError'));
      }
    };

    const fetchMyCollections = async () => {
      try {
        const res = await apiFetch('/api/v1/collections/');
        if (res.ok) {
          const data = await res.json();
          setMyCollections(data.results);
        }
      } catch { /* silently fail */ }
    };

    const fetchInvitedCollections = async () => {
      try {
        const res = await apiFetch('/api/v1/invited-collections/');
        if (res.ok) {
          const data = await res.json();
          setInvitedCollections(data);
        }
      } catch { /* silently fail */ }
    };

    const fetchPendingInvitations = async () => {
      try {
        const res = await apiFetch('/api/v1/my-invitations/');
        if (res.ok) {
          const data = await res.json();
          setPendingInvitations(data);
        }
      } catch { /* silently fail */ }
    };

    const fetchInbox = async () => {
      try {
        const res = await apiFetch('/api/v1/inbox/');
        if (res.ok) {
          const data = await res.json();
          setInboxNotifications(data);
        }
      } catch { /* silently fail */ }
    };

    fetchMe();
    fetchMyCollections();
    fetchInvitedCollections();
    fetchPendingInvitations();
    fetchInbox();
  }, [navigate, t]);

  const dismissInvitation = (acceptCode) => {
    setPendingInvitations((prev) => prev.filter((inv) => inv.accept_code !== acceptCode));
  };

  const dismissInboxNotification = async (code) => {
    setInboxNotifications((prev) => prev.filter((n) => n.code !== code));
    try { await apiFetch(`/api/v1/inbox/${code}/`, { method: 'DELETE' }); } catch { /* silently fail */ }
  };

  const ALERT_TYPES = new Set([
    'COLLECTION_DELETED', 'COLLECTION_REVOKED', 'BOOKING_REJECTED', 'FAQ_HIDDEN', 'INVITE_REJECTED',
  ]);
  const SUCCESS_TYPES = new Set(['BOOKING_ACCEPTED']);

  const inboxNotificationType = (type) => {
    if (ALERT_TYPES.has(type)) return 'alert';
    if (SUCCESS_TYPES.has(type)) return 'success';
    return 'info';
  };

  const inboxNotificationLabel = (n, tFn) => {
    const p = n.payload;
    switch (n.type) {
      case 'COLLECTION_DELETED': return tFn('home.collectionDeletedLabel');
      case 'COLLECTION_REVOKED': return tFn('home.collectionRevokedLabel');
      case 'BOOKING_ACCEPTED': return tFn('home.bookingAcceptedLabel');
      case 'BOOKING_REJECTED': return tFn('home.bookingRejectedLabel');
      case 'BOOKING_REQUESTED': return tFn('home.bookingRequestedLabel');
      case 'BOOKING_UNAVAILABLE': return tFn('home.bookingUnavailableLabel');
      case 'SWAP_REQUESTED': return tFn('home.swapRequestedLabel');
      case 'FAQ_QUESTION': return tFn('home.faqQuestionLabel');
      case 'FAQ_ANSWERED': return tFn('home.faqAnsweredLabel');
      case 'FAQ_HIDDEN': return tFn('home.faqHiddenLabel');
      case 'INVITE_REJECTED': return tFn('home.inviteRejectedLabel');
      case 'WISH_POSTED': return tFn('home.wishPostedLabel');
      case 'WISH_RESPONSE': return tFn('home.wishResponseLabel');
      case 'WISH_ACCEPTED': return tFn('home.wishAcceptedLabel');
      default: return tFn('home.broadcastLabel', { owner_name: p.owner_name, collection_headline: p.collection_headline });
    }
  };

  const inboxNotificationBody = (n, tFn) => {
    const p = n.payload;
    switch (n.type) {
      case 'COLLECTION_DELETED': return tFn('home.collectionDeletedBody', { collection_headline: p.collection_headline, owner_name: p.owner_name });
      case 'COLLECTION_REVOKED': return tFn('home.collectionRevokedBody', { collection_headline: p.collection_headline, owner_name: p.owner_name });
      case 'BOOKING_ACCEPTED': return tFn('home.bookingAcceptedBody', { thing_headline: p.thing_headline, owner_name: p.owner_name });
      case 'BOOKING_REJECTED': return tFn('home.bookingRejectedBody', { thing_headline: p.thing_headline, owner_name: p.owner_name });
      case 'BOOKING_REQUESTED': return tFn('home.bookingRequestedBody', { thing_headline: p.thing_headline, requester_name: p.requester_name });
      case 'BOOKING_UNAVAILABLE': return tFn('home.bookingUnavailableBody', { thing_headline: p.thing_headline });
      case 'SWAP_REQUESTED': return tFn('home.swapRequestedBody', { thing_headline: p.thing_headline, requester_name: p.requester_name });
      case 'FAQ_QUESTION': return tFn('home.faqQuestionBody', { thing_headline: p.thing_headline, questioner_name: p.questioner_name });
      case 'FAQ_ANSWERED': return tFn('home.faqAnsweredBody', { thing_headline: p.thing_headline, owner_name: p.owner_name });
      case 'FAQ_HIDDEN': return tFn('home.faqHiddenBody', { thing_headline: p.thing_headline, owner_name: p.owner_name });
      case 'INVITE_REJECTED': return tFn('home.inviteRejectedBody', { collection_headline: p.collection_headline, invitee_name: p.invitee_name });
      case 'WISH_POSTED': return tFn('home.wishPostedBody', { creator_name: p.creator_name, wish_headline: p.wish_headline });
      case 'WISH_RESPONSE': return tFn('home.wishResponseBody', { responder_name: p.responder_name, wish_headline: p.wish_headline });
      case 'WISH_ACCEPTED': return tFn('home.wishAcceptedBody', { owner_name: p.owner_name, wish_headline: p.wish_headline });
      default: return tFn('home.broadcastBody', { message: p.message });
    }
  };

  // Deep link to the object that originated a notification: the wish page for
  // wish notifications, the collection for a broadcast. Returns {to, label} or null.
  const inboxNotificationLink = (n) => {
    const p = n.payload || {};
    if (p.wish_code) {
      const to = p.collection_code
        ? `/collections/${p.collection_code}/things/${p.wish_code}`
        : `/things/${p.wish_code}`;
      return { to, label: t('home.viewWish') };
    }
    if (n.type === 'BROADCAST' && p.collection_code) {
      return { to: `/collections/${p.collection_code}`, label: t('home.viewCollection') };
    }
    return null;
  };

  if (error) {
    return (
      <div className="page-container">
        <Notification label={t('common.error')} type="error">{error}</Notification>
      </div>
    );
  }

  if (!user) {
    return <LoadingSpinner />;
  }

  const tc = user.theeeme_colors || {};
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--background-color': 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_04})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
  } : undefined;

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
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

        {inboxNotifications.length > 0 && (
          <>
            {inboxNotifications.map((n) => {
              const link = inboxNotificationLink(n);
              return (
                <Notification
                  key={n.code}
                  type={inboxNotificationType(n.type)}
                  label={inboxNotificationLabel(n, t)}
                  dismissible
                  closeButtonLabelText={t('home.dismiss')}
                  onClose={() => dismissInboxNotification(n.code)}
                  style={{ marginBottom: 'var(--spacing-s)' }}
                >
                  {inboxNotificationBody(n, t)}
                  {link && (
                    <>
                      {' '}
                      <Link to={link.to}>{link.label}</Link>
                    </>
                  )}
                </Notification>
              );
            })}
            <div className="spacer-m" />
          </>
        )}

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
                <strong>{inv.collection_headline}</strong>
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
        {myCollections === null ? (
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
              <Linkbox
                key={c.code}
                href={`/collections/${c.code}`}
                onClick={(e) => { e.preventDefault(); navigate(`/collections/${c.code}`); }}
                heading={c.headline}
                text={t('userPage.collectionInfo', { things: c.things.length, guests: c.invites.length })}
                linkAriaLabel={t('userPage.viewCollection', { headline: c.headline })}
                linkboxAriaLabel={c.headline}
                imgProps={c.thumbnail_url ? { src: c.thumbnail_url, alt: c.headline } : undefined}
                border
                size="small"
              />
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
                <Linkbox
                  key={c.code}
                  href={`/collections/${c.code}`}
                  onClick={(e) => { e.preventDefault(); navigate(`/collections/${c.code}`); }}
                  heading={c.headline}
                  text={t('userPage.collectionInfo', { things: c.things.length, guests: c.invites.length })}
                  linkAriaLabel={t('userPage.viewCollection', { headline: c.headline })}
                  linkboxAriaLabel={c.headline}
                  imgProps={c.thumbnail_url ? { src: c.thumbnail_url, alt: c.headline } : undefined}
                  border
                  size="small"
                />
              ))}
            </div>
          </>
        )}

        <div className="spacer-xl" />
        <h2>{t('userPage.sharedWithMe')}</h2>
        <div className="spacer-m" />
        {invitedCollections === null ? (
          <p className="text-muted">{t('userPage.loadingCollections')}</p>
        ) : invitedCollections.length === 0 ? (
          <p>{t('userPage.noShared')}</p>
        ) : (
          <div className="collections-grid">
            {invitedCollections.map((c) => (
              <Linkbox
                key={c.code}
                href={`/collections/${c.code}`}
                onClick={(e) => { e.preventDefault(); navigate(`/collections/${c.code}`); }}
                heading={c.headline}
                text={t('userPage.collectionInfo', { things: c.things.length, guests: c.invites.length })}
                linkAriaLabel={t('userPage.viewCollection', { headline: c.headline })}
                linkboxAriaLabel={c.headline}
                imgProps={c.thumbnail_url ? { src: c.thumbnail_url, alt: c.headline } : undefined}
                border
                size="small"
              />
            ))}
          </div>
        )}

      </div>
    </div>
  );
}
