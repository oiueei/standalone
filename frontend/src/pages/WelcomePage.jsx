import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros } from 'hds-react';
import BackLink from '../components/BackLink';
import { apiFetch } from '../services/api';

export default function WelcomePage() {
  const { t } = useTranslation();
  useEffect(() => {
    document.title = t('titles.welcome');
    localStorage.setItem('seenWelcome', 'true');
  }, [t]);
  const [userName, setUserName] = useState('');

  useEffect(() => {
    apiFetch('/api/v1/auth/me/')
      .then((res) => res.ok ? res.json() : Promise.reject())
      .then((data) => setUserName(data.name || data.email || ''))
      .catch(() => {});
  }, []);
  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
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
          {userName && <p style={{ fontSize: 'var(--fontsize-heading-m)', fontWeight: 500, lineHeight: 'var(--lineheight-s)', color: 'var(--hero-text-color, var(--color-black-90))' }}>{t('welcome.greeting', { name: userName })}</p>}
          <h1 className="form-hero-title">{t('welcome.pageTitle')}</h1>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-s)', paddingBottom: 'var(--spacing-s)' }}>
            <Link to="/collections/new" state={{ backPath: '/welcome', backLabel: t('welcome.pageTitle') }}>
              <Button style={{ ...btnStyle, width: '100%' }}>{t('welcome.createCollection')}</Button>
            </Link>
            <Link to="/me/edit" state={{ backPath: '/welcome', backLabel: t('welcome.pageTitle') }}>
              <Button variant="secondary" style={{ ...btnSecondaryStyle, width: '100%' }}>{t('welcome.editProfile')}</Button>
            </Link>
          </div>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <p>
          {t('welcome.description')}
        </p>
        <div className="spacer-xl" />
        <h2>{t('welcome.whoUsesTitle')}</h2>
        <div className="spacer-s" />
        <p>{t('welcome.personaMarc')}</p>
        <div className="spacer-s" />
        <p>{t('welcome.personaSophie')}</p>
        <div className="spacer-s" />
        <p>{t('welcome.personaTomas')}</p>
        <div className="spacer-s" />
        <p>{t('welcome.personaLeena')}</p>
        <div className="spacer-s" />
        <p>{t('welcome.personaJames')}</p>
      </div>
    </div>
  );
}
