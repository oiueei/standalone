import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { useParams, Link } from 'react-router-dom';
import { TextInput, Button, Notification, Koros } from 'hds-react';
import { getCsrfToken } from '../services/api';

export default function SharePage() {
  const { t } = useTranslation();
  const { token } = useParams();
  useEffect(() => { document.title = t('titles.share'); }, [t]);

  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null); // 'success' | 'error'
  const [message, setMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus(null);
    setLoading(true);
    try {
      const res = await fetch('/api/v1/auth/pop-in/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ email, share_token: token }),
      });
      if (res.ok) {
        localStorage.removeItem('seenWelcome');
        setStatus('success');
        setMessage(t('share.magicLinkSent'));
      } else {
        setStatus('error');
        setMessage(t('share.errorSendingLink'));
      }
    } catch {
      setStatus('error');
      setMessage(t('common.connectionError'));
    } finally {
      setLoading(false);
    }
  };

  const DEFAULT_COLORS = { color_01: 'bus', color_02: 'suomenlinna-light', color_03: 'copper', color_04: 'black', color_05: 'white', color_06: 'white' };
  const tc = (() => {
    try { return JSON.parse(localStorage.getItem('theeemeColors')) || DEFAULT_COLORS; } catch { return DEFAULT_COLORS; }
  })();
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
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
          <h1 className="form-hero-title">{t('share.pageTitle')}</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <p className="section-mt" style={{ maxWidth: '400px' }}>{t('share.pageDescription')}</p>
        {status ? (
          <Notification
            label={status === 'success' ? t('common.sent') : t('common.error')}
            type={status}
            style={{ marginTop: 'var(--spacing-m)' }}
          >
            {message}
          </Notification>
        ) : (
          <form onSubmit={handleSubmit} style={{ maxWidth: '400px' }}>
            <TextInput
              id="share-email"
              label={t('share.emailLabel')}
              type="email"
              placeholder={t('share.emailPlaceholder')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="section-mt"
            />
            <div>
              <Button type="submit" fullWidth disabled={loading} style={btnStyle}>
                {loading ? t('share.joining') : t('share.join')}
              </Button>
            </div>
          </form>
        )}
        <p style={{ marginTop: 'var(--spacing-m)', maxWidth: '400px' }}>
          <Link to="/login">{t('share.alreadyHaveAccount')}</Link>
        </p>
      </div>
    </div>
  );
}
