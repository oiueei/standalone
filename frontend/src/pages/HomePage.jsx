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
    const userCode = localStorage.getItem('userCode');
    if (!userCode) {
      navigate('/login');
      return;
    }

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
    '--background-color': tc.color_02 ? `var(--color-${tc.color_02})` : undefined,
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
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <h1 className="form-hero-title" style={{ paddingTop: 'var(--spacing-xl)' }}>{t('home.greeting', { name: user.name || user.email })}</h1>
          {user.headline && <p className="form-hero-text">{user.headline}</p>}
          <div className="button-row-wide">
            <Link to="/collections/new">
              <Button style={btnStyle}>{t('home.createCollection')}</Button>
            </Link>
            <Link to="/me/edit">
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
            {inboxNotifications.map((n) => (
              <Notification
                key={n.code}
                type={n.type === 'COLLECTION_DELETED' ? 'alert' : 'info'}
                label={n.type === 'COLLECTION_DELETED'
                  ? t('home.collectionDeletedLabel')
                  : t('home.broadcastLabel', { owner_name: n.payload.owner_name, collection_headline: n.payload.collection_headline })}
                dismissible
                closeButtonLabelText={t('home.dismiss')}
                onClose={() => dismissInboxNotification(n.code)}
                style={{ marginBottom: 'var(--spacing-s)' }}
              >
                {n.type === 'COLLECTION_DELETED'
                  ? t('home.collectionDeletedBody', { collection_headline: n.payload.collection_headline, owner_name: n.payload.owner_name })
                  : t('home.broadcastBody', { subject: n.payload.subject, message: n.payload.message })}
              </Notification>
            ))}
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
          <p>{t('userPage.noCollections')} <Link to="/collections/new">{t('userPage.createFirst')}</Link> {t('userPage.toGetStarted')}</p>
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
