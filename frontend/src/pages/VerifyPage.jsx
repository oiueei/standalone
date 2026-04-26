import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Notification, Koros } from 'hds-react';
import { identifyUser, track } from '../services/analytics';

const DEFAULT_COLORS = { color_01: 'bus', color_02: 'suomenlinna-light', color_03: 'copper', color_04: 'black', color_05: 'white', color_06: 'white' };

export default function VerifyPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  useEffect(() => { document.title = t('titles.verify'); }, [t]);
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
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;

  useEffect(() => {
    const verify = async () => {
      try {
        const res = await fetch(`/api/v1/auth/verify/${code}/`);
        const data = await res.json();
        if (res.ok && data.action === 'COLLECTION_REJECT') {
          track('invite_declined');
          setTitle(t('verify.declined'));
          setSuccess(t('verify.invitationDeclined'));
        } else if (res.ok && data.action === 'BOOKING_ACCEPT') {
          setTitle(t('verify.confirmed'));
          setSuccess(t('verify.holdConfirmed'));
        } else if (res.ok && data.action === 'BOOKING_REJECT') {
          setTitle(t('verify.rejected'));
          setSuccess(t('verify.holdRejected'));
        } else if (res.ok && data.user) {
          const prevUserCode = localStorage.getItem('userCode');
          if (data.user?.code) localStorage.setItem('userCode', data.user.code);
          if (data.user?.theeeme_colors) localStorage.setItem('theeemeColors', JSON.stringify(data.user.theeeme_colors));
          if (data.user?.koro) localStorage.setItem('koro', data.user.koro);
          if (data.user?.code && data.user.code !== prevUserCode) {
            localStorage.removeItem('seenWelcome');
          }
          if (data.user?.code) identifyUser(data.user.code);
          track('magic_link_verified', { action: data.action });
          if (data.is_first_login) track('signup');
          if (data.action === 'COLLECTION_INVITE' && data.invited_collection) {
            track('invite_accepted', { collection_code: data.invited_collection });
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
      }
    };
    verify();
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
          <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
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
          <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
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
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
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
