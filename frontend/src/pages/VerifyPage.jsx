import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { Button, Notification, Koros } from 'hds-react';

const DEFAULT_COLORS = { color_01: 'bus', color_02: 'suomenlinna-light', color_03: 'copper', color_04: 'black', color_05: 'white' };

export default function VerifyPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  useEffect(() => { document.title = 'Verifying — OIUEEI'; }, []);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [title, setTitle] = useState('');
  const isLoggedIn = !!localStorage.getItem('userCode');

  const tc = (() => {
    try { return JSON.parse(localStorage.getItem('theeemeColors')) || DEFAULT_COLORS; } catch { return DEFAULT_COLORS; }
  })();
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;

  useEffect(() => {
    const verify = async () => {
      try {
        const res = await fetch(`/api/v1/auth/verify/${code}/`);
        const data = await res.json();
        if (res.ok && data.action === 'COLLECTION_REJECT') {
          setTitle('Declined');
          setSuccess('Invitation declined. The collection owner has been notified.');
        } else if (res.ok && data.action === 'BOOKING_ACCEPT') {
          setTitle('Confirmed!');
          setSuccess('The hold has been confirmed!');
        } else if (res.ok && data.action === 'BOOKING_REJECT') {
          setTitle('Rejected');
          setSuccess('The hold has been rejected.');
        } else if (res.ok && data.user) {
          if (data.user?.code) localStorage.setItem('userCode', data.user.code);
          if (data.invited_collection) {
            navigate(`/collections/${data.invited_collection}`, { state: { fromInvite: true } });
          } else {
            navigate('/');
          }
        } else {
          setError(data.error || 'Invalid or expired link.');
        }
      } catch {
        setError('Connection error.');
      }
    };
    verify();
  }, [code, navigate]);

  if (success) {
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
            <h1 className="form-hero-title">{title}</h1>
            <div className="section-mt">
              <Link to={isLoggedIn ? '/' : '/login'}>
                <Button style={btnStyle}>{isLoggedIn ? 'Go to homepage' : 'Go to login'}</Button>
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
          <Notification label="Done" type="success">
            {success}
          </Notification>
        </div>
      </div>
    );
  }

  if (error) {
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
            <h1 className="form-hero-title">Oops</h1>
            <div className="section-mt">
              <Link to={isLoggedIn ? '/' : '/login'}>
                <Button style={btnStyle}>{isLoggedIn ? 'Go to homepage' : 'Go to login'}</Button>
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
          <Notification label="Error" type="error">
            {error}
          </Notification>
          <p className="section-mt">
            If your link has expired, ask the person who invited you to send a new one, or request a new magic link.
          </p>
        </div>
      </div>
    );
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
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_04})` } : undefined}>
          <h1 className="form-hero-title">Verifying…</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container" />
    </div>
  );
}
