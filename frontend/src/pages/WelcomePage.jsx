import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros } from 'hds-react';
import BackLink from '../components/BackLink';
import { apiFetch } from '../services/api';

const PERSONA_LINKS = {
  Lala: [{ code: 'La1aC1', key: 'personaLalaLink2' }],
  Lele: [{ code: 'L3L3C1', key: 'personaLeleLink1' }],
  Lili: [{ code: 'l1l1C1', key: 'personaLiliLink1' }, { code: 'l1l1C2', key: 'personaLiliLink2' }],
  Lolo: [{ code: 'l0l0C1', key: 'personaLoloLink1' }],
  Lulu: [{ code: '1u1uC1', key: 'personaLuluLink1' }],
};

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
          <BackLink to="/" label={t('common.home')} />
          <div className="spacer-m" />
          {userName && <p style={{ fontSize: 'var(--fontsize-heading-m)', fontWeight: 500, lineHeight: 'var(--lineheight-s)', color: 'var(--hero-text-color, var(--color-black-90))' }}>{t('welcome.greeting', { name: userName })}</p>}
          <h1 className="form-hero-title">{t('welcome.pageTitle')}</h1>
          <div className="button-row-wide" style={{ paddingBottom: 'var(--spacing-s)' }}>
            <Link to="/collections/new" state={{ backPath: '/welcome', backLabel: t('welcome.pageTitle') }}>
              <Button style={btnStyle}>{t('welcome.createCollection')}</Button>
            </Link>
            <Link to="/me/edit" state={{ backPath: '/welcome', backLabel: t('welcome.pageTitle') }}>
              <Button variant="secondary" style={btnSecondaryStyle}>{t('welcome.editProfile')}</Button>
            </Link>
          </div>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container welcome-content">
        <p>
          {t('welcome.description')}
        </p>
        <div className="spacer-xl" />
        <h2>{t('welcome.whoUsesTitle')}</h2>
        <div className="spacer-s" />
        {['Lala', 'Lele', 'Lili', 'Lolo', 'Lulu'].map((name, i) => (
          <div key={name}>
            {i > 0 && <div className="spacer-s" />}
            <p>
              <b>{t(`welcome.persona${name}Title`)}</b>{' '}
              {t(`welcome.persona${name}Body`)}
            </p>
            <div style={{ display: 'flex', flexWrap: 'wrap', gap: 'var(--spacing-xs)', marginTop: 'var(--spacing-xs)' }}>
              {PERSONA_LINKS[name].map(({ code, key }) => (
                <Link
                  key={code}
                  to={`/collections/${code}`}
                  style={{ color: tc.color_01 ? `var(--color-${tc.color_01})` : 'var(--color-bus)', textDecoration: 'underline', fontSize: 'var(--fontsize-body-m)', fontWeight: 700 }}
                >
                  {t(`welcome.${key}`)} →
                </Link>
              ))}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}
