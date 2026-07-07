import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Notification, Koros } from 'hds-react';
import { DEFAULT_COLORS } from '../hooks/useTheeeme';

export default function VerifyPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  useEffect(() => { document.title = t('titles.verify'); }, [t]);
  const [error, setError] = useState('');
  const [success, setSuccess] = useState('');
  const [title, setTitle] = useState('');
  // Guards the auto-commit POST so React 19 StrictMode's double-invoked effect
  // (dev only) can't fire the irreversible booking decision twice.
  const committedRef = useRef(false);
  const isLoggedIn = !!localStorage.getItem('userCode');

  const tc = (() => {
    try { return JSON.parse(localStorage.getItem('theeemeColors')) || DEFAULT_COLORS; } catch { return DEFAULT_COLORS; }
  })();
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;

  useEffect(() => {
    let settled = false;
    // Don't let a stalled network leave the user stuck on "Verifying…" forever:
    // after 15s with no response, fall through to the existing error screen.
    const timer = setTimeout(() => {
      if (!settled) setError(t('common.connectionError'));
    }, 15000);
    const verify = async () => {
      try {
        const res = await fetch(`/api/v1/auth/verify/${code}/`);
        const data = await res.json();
        if (res.ok && data.requires_confirmation) {
          // Booking accept/reject is irreversible, so the API only *previews* on a
          // bare GET — an email link-scanner must never decide a hold. The human's
          // single click was opening this link, so commit it now with a POST fired
          // from real JS: a scanner runs no JS and still can't auto-decide, while
          // the person needs no second click. The ref guards StrictMode's dev-only
          // double-invoke from firing the decision twice.
          if (!committedRef.current) {
            committedRef.current = true;
            const commit = await fetch(`/api/v1/auth/verify/${code}/`, {
              method: 'POST',
              credentials: 'include',
            });
            const done = await commit.json();
            if (commit.ok && done.action === 'BOOKING_ACCEPT') {
              setTitle(t('verify.confirmed'));
              setSuccess(t('verify.holdConfirmed'));
            } else if (commit.ok && done.action === 'BOOKING_REJECT') {
              setTitle(t('verify.rejected'));
              setSuccess(t('verify.holdRejected'));
            } else {
              setError(t('verify.invalidOrExpired'));
            }
          }
        } else if (res.ok && data.action === 'COLLECTION_REJECT') {
          setTitle(t('verify.declined'));
          setSuccess(t('verify.invitationDeclined'));
        } else if (res.ok && data.user) {
          const prevUserCode = localStorage.getItem('userCode');
          if (data.user?.code) localStorage.setItem('userCode', data.user.code);
          if (data.user?.theeeme_colors) localStorage.setItem('theeemeColors', JSON.stringify(data.user.theeeme_colors));
          if (data.user?.koro) localStorage.setItem('koro', data.user.koro);
          if (data.user?.code && data.user.code !== prevUserCode) {
            localStorage.removeItem('seenWelcome');
          }
          if (data.invited_collection) {
            navigate(`/collections/${data.invited_collection}`, { state: { fromInvite: true } });
          } else if (!localStorage.getItem('seenWelcome')) {
            navigate('/welcome');
          } else {
            navigate('/');
          }
        } else {
          setError(t('verify.invalidOrExpired'));
        }
      } catch {
        setError(t('common.connectionError'));
      } finally {
        settled = true;
        clearTimeout(timer);
      }
    };
    verify();
    return () => clearTimeout(timer);
  }, [code, navigate, t]);

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
          <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
            <h1 className="form-hero-title">{title}</h1>
            <div>
              <Link to={isLoggedIn ? '/' : '/login'}>
                <Button style={btnStyle}>{isLoggedIn ? t('verify.goToHomepage') : t('verify.goToLogin')}</Button>
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
          <Notification label={t('common.done')} type="success">
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
          <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
            <h1 className="form-hero-title">{t('verify.oops')}</h1>
            <div>
              <Link to={isLoggedIn ? '/' : '/login'}>
                <Button style={btnStyle}>{isLoggedIn ? t('verify.goToHomepage') : t('verify.goToLogin')}</Button>
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
          <Notification label={t('common.error')} type="error">
            {error}
          </Notification>
          <p className="section-mt">
            {t('verify.expiredHelp')}
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
        <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <h1 className="form-hero-title">{t('verify.verifying')}</h1>
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
