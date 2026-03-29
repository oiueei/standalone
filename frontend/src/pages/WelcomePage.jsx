import { useEffect, useState } from 'react';
import { Link } from 'react-router-dom';
import { Button, Koros } from 'hds-react';
import BackLink from '../components/BackLink';
import { apiFetch } from '../services/api';

export default function WelcomePage() {
  useEffect(() => {
    document.title = 'Welcome — OIUEEI';
    localStorage.setItem('seenWelcome', 'true');
  }, []);
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
    '--color': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
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
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_04})` } : undefined}>
          <BackLink to="/" label="Home" />
          <div className="spacer-m" />
          {userName && <p style={{ fontSize: 'var(--fontsize-heading-m)', fontWeight: 500, lineHeight: 'var(--lineheight-s)', color: 'var(--hero-text-color, var(--color-black-90))' }}>Hello, {userName}</p>}
          <h1 className="form-hero-title">Welcome to OIUEEI!</h1>
          <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-s)', paddingBottom: 'var(--spacing-s)' }}>
            <Link to="/collections/new" state={{ backPath: '/welcome', backLabel: 'Welcome' }}>
              <Button style={{ ...btnStyle, width: '100%' }}>Create collection</Button>
            </Link>
            <Link to="/me/edit" state={{ backPath: '/welcome', backLabel: 'Welcome' }}>
              <Button variant="secondary" style={{ ...btnSecondaryStyle, width: '100%' }}>Edit profile</Button>
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
          OIUEEI is an open-source web application that lets people share their belongings with
          friends and others around. Users can create collections (wishlists, gift lists, items for
          sale) and share them with friends who can then reserve items or ask questions.
        </p>
      </div>
    </div>
  );
}
