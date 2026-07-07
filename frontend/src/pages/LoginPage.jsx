import { useEffect, useState } from 'react';
import { useTranslation, Trans } from 'react-i18next';
import { Link } from 'react-router-dom';
import { TextInput, Button, Notification, Koros } from 'hds-react';
import { getCsrfToken } from '../services/api';
import { DEFAULT_COLORS } from '../hooks/useTheeeme';

export default function LoginPage() {
  const { t } = useTranslation();
  useEffect(() => { document.title = t('titles.login'); }, [t]);
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null); // 'success' | 'alert' | 'error'
  const [message, setMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setStatus(null);
    setLoading(true);
    try {
      const res = await fetch('/api/v1/auth/request-link/', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRFToken': getCsrfToken(),
        },
        body: JSON.stringify({ email }),
      });
      if (res.ok) {
        setStatus('success');
        setMessage(t('login.magicLinkSent'));
      } else if (res.status === 429) {
        setStatus('error');
        setMessage(t('common.tooManyAttempts'));
      } else {
        setStatus('error');
        setMessage(t('login.errorSendingLink'));
      }
    } catch {
      setStatus('error');
      setMessage(t('common.connectionError'));
    } finally {
      setLoading(false);
    }
  };

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
          <h1 className="form-hero-title">{t('login.title')}</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <p className="section-mt" style={{ maxWidth: '400px', fontWeight: 700 }}>{t('login.description')}</p>
        <p style={{ maxWidth: '400px', marginTop: 'var(--spacing-s)' }}>
          <Trans
            i18nKey="login.openSource"
            components={[
              <span key="0" />,
              // eslint-disable-next-line jsx-a11y/anchor-has-content -- the link text is injected by <Trans> from the i18n string at runtime
              <a key="1" href="https://github.com/oiueei/standalone" target="_blank" rel="noopener noreferrer" />,
            ]}
          />
        </p>
        <p style={{ maxWidth: '400px', marginTop: 'var(--spacing-s)' }}>{t('login.manifesto')}</p>
        <p style={{ maxWidth: '400px', marginTop: 'var(--spacing-s)' }}>
          <Link to="/popin">{t('login.popIn')}</Link>
        </p>
        {status ? (
          <>
            <Notification label={status === 'success' ? t('common.sent') : status === 'alert' ? t('common.warning') : t('common.error')} type={status}>
              {message}
            </Notification>
            <div style={{ marginTop: 'var(--spacing-s)' }}>
              <Button variant="secondary" onClick={() => { setStatus(null); setMessage(''); }}>
                {t('login.tryAnotherEmail')}
              </Button>
            </div>
          </>
        ) : (
          <form onSubmit={handleSubmit} style={{ maxWidth: '400px', marginTop: 'var(--spacing-s)' }}>
            <TextInput
              id="login-email"
              label={t('login.emailLabel')}
              type="email"
              placeholder={t('login.emailPlaceholder')}
              value={email}
              onChange={(e) => setEmail(e.target.value)}
              required
              className="section-mt"
            />
            <div>
              <Button type="submit" fullWidth disabled={loading} style={btnStyle}>
                {loading ? t('common.sending') : t('login.signIn')}
              </Button>
            </div>
          </form>
        )}
      </div>
    </div>
  );
}
