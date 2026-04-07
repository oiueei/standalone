import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros, Linkbox, Notification } from 'hds-react';
import BackLink from '../components/BackLink';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';

export default function UserPage() {
  const { userCode: paramCode } = useParams();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [user, setUser] = useState(null);
  const [myCollections, setMyCollections] = useState(null);
  const [invitedCollections, setInvitedCollections] = useState(null);
  const [error, setError] = useState('');

  const userCode = paramCode || localStorage.getItem('userCode');
  const isOwnProfile = !paramCode || paramCode === localStorage.getItem('userCode');
  useEffect(() => { document.title = user ? t('titles.user', { name: user.name || 'Profile' }) : t('titles.user', { name: 'Profile' }); }, [user, t]);

  useEffect(() => {
    if (!localStorage.getItem('userCode')) {
      navigate('/login');
      return;
    }

    if (!userCode) {
      // If no userCode yet, fetch /me to get it
      apiFetch('/api/v1/auth/me/')
        .then((res) => res.ok ? res.json() : Promise.reject())
        .then((data) => {
          if (data.code) localStorage.setItem('userCode', data.code);
          setUser(data);
        })
        .catch(() => setError(t('userPage.errorLoading')));
      return;
    }

    const fetchUser = async () => {
      try {
        const res = await apiFetch(`/api/v1/users/${userCode}/`);
        if (res.ok) {
          const data = await res.json();
          setUser(data);
        } else if (res.status === 403) {
          setError(t('userPage.noPermission'));
        } else if (res.status === 404) {
          setError(t('userPage.notFound'));
        } else {
          setError(t('userPage.errorLoading'));
        }
      } catch {
        setError(t('common.connectionError'));
      }
    };
    fetchUser();

    if (isOwnProfile) {
      apiFetch('/api/v1/collections/')
        .then((res) => res.ok ? res.json() : Promise.reject())
        .then((data) => setMyCollections(data.results))
        .catch(() => {});
      apiFetch('/api/v1/invited-collections/')
        .then((res) => res.ok ? res.json() : Promise.reject())
        .then((data) => setInvitedCollections(data))
        .catch(() => {});
    }
  }, [userCode, isOwnProfile, navigate, t]);

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

  // Use theeeme colors from user data (own profile) or localStorage (other profiles)
  const tc = user.theeeme_colors || (() => {
    try { return JSON.parse(localStorage.getItem('theeemeColors')) || {}; } catch { return {}; }
  })();
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
          <BackLink to="/" label={t('common.home')} />
          <div className="spacer-m" />
          {user.headline && <p style={{ fontSize: 'var(--fontsize-heading-m)', fontWeight: 500, lineHeight: 'var(--lineheight-s)', color: 'var(--hero-text-color, var(--color-black-90))' }}>{user.headline}</p>}
          <h1 className="form-hero-title">{user.name || user.email}</h1>
          {user.created && (
            <p className="form-hero-text" style={{ fontSize: 'var(--fontsize-body-m)', opacity: 0.7 }}>
              {t('userPage.memberSince', { date: new Date(user.created).toLocaleDateString(i18n.language, { month: 'long', year: 'numeric' }) })}
            </p>
          )}
          {isOwnProfile && (
            <div className="button-row-wide" style={{ paddingBottom: 'var(--spacing-s)' }}>
              <Link to="/me/edit">
                <Button style={btnStyle}>{t('userPage.editProfile')}</Button>
              </Link>
              <Link to="/logout">
                <Button variant="secondary" style={btnSecondaryStyle}>{t('userPage.logout')}</Button>
              </Link>
            </div>
          )}
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        {!isOwnProfile && user.shared_collections && user.shared_collections.length > 0 && (
          <>
            <h2>{t('userPage.collectionsInCommon')}</h2>
            <div className="spacer-m" />
            <div className="collections-grid">
              {user.shared_collections.map((c) => (
                <Linkbox
                  key={c.code}
                  href={`/collections/${c.code}`}
                  onClick={(e) => { e.preventDefault(); navigate(`/collections/${c.code}`); }}
                  heading={c.headline}
                  linkAriaLabel={t('userPage.viewCollection', { headline: c.headline })}
                  linkboxAriaLabel={c.headline}
                  border
                  size="small"
                />
              ))}
            </div>
          </>
        )}

        {isOwnProfile && (
          <>
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
                    border
                    size="small"
                  />
                ))}
              </div>
            )}
          </>
        )}
      </div>
    </div>
  );
}
