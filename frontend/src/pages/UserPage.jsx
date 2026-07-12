import { useEffect, useState } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros, Notification } from 'hds-react';
import BackLink from '../components/BackLink';
import PageLayout from '../components/PageLayout';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import MarkdownText from '../components/MarkdownText';
import CollectionLinkbox from '../components/CollectionLinkbox';
import HeroPhoto from '../components/HeroPhoto';

export default function UserPage() {
  const { userCode: paramCode } = useParams();
  const { t, i18n } = useTranslation();
  const [user, setUser] = useState(null);
  const [error, setError] = useState('');

  const userCode = paramCode || localStorage.getItem('userCode');
  const isOwnProfile = !paramCode || paramCode === localStorage.getItem('userCode');
  useEffect(() => { document.title = user ? t('titles.user', { name: user.name || 'Profile' }) : t('titles.user', { name: 'Profile' }); }, [user, t]);

  useEffect(() => {
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

  }, [userCode, isOwnProfile, t]);

  if (error) {
    return (
      <PageLayout title={t('common.error')} backTo="/" backLabel={t('common.home')}>
        <Notification label={t('common.error')} type="error">{error}</Notification>
      </PageLayout>
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
    '--background-color': 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': tc.color_04 ? `var(--color-${tc.color_04})` : undefined,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
  } : undefined;

  const koroType = localStorage.getItem('koro') || 'basic';

  const heroContent = (
    <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
      <BackLink to="/" label={t('common.home')} />
      <div className="spacer-m" />
      {user.headline && <p style={{ fontSize: 'var(--fontsize-heading-m)', fontWeight: 700, lineHeight: 'var(--lineheight-m)', letterSpacing: '-0.2px', color: 'var(--hero-text-color, var(--color-black-90))' }}>{user.headline}</p>}
      <h1 className="form-hero-title">{user.name || user.email}</h1>
      {user.created && (
        <p className="form-hero-text" style={{ fontSize: 'var(--fontsize-body-m)' }}>
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
  );

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className={`form-hero${user.photo_url ? ' form-hero--photo' : ''}`}
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})`, '--hero-logo-color': `var(--color-${tc.color_02})` } : undefined}
      >
        <div className="form-hero-split">
          {heroContent}
        </div>
        {user.photo_url && (
          <HeroPhoto
            photoUrl={user.photo_url}
            alt={t('userPage.photoAlt', { name: user.name || user.email })}
            koroType={koroType}
            color03={tc.color_03}
          />
        )}
        <Koros
          className="form-hero-koros"
          type={koroType}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        {user.about && (
          <>
            <h2>{t('userPage.aboutHeading')}</h2>
            <div className="spacer-s" />
            <MarkdownText text={user.about} className="about-markdown" />
            <div className="spacer-l" />
          </>
        )}
        {!isOwnProfile && user.shared_collections && user.shared_collections.length > 0 && (
          <>
            <h2>{t('userPage.collectionsInCommon')}</h2>
            <div className="spacer-m" />
            <div className="collections-grid">
              {user.shared_collections.map((c) => (
                <CollectionLinkbox key={c.code} collection={c} />
              ))}
            </div>
          </>
        )}
        {!isOwnProfile &&
          !user.about &&
          (!user.shared_collections || user.shared_collections.length === 0) && (
            <p>{t('userPage.noSharedCollections', { name: user.name || user.email })}</p>
          )}
      </div>
    </div>
  );
}
