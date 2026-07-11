import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { TextInput, Button, Notification } from 'hds-react';
import { getCsrfToken } from '../services/api';
import useTheeeme from '../hooks/useTheeeme';
import PageLayout from './PageLayout';

/**
 * Shared pop-in landing page: an email form that POSTs to `/auth/pop-in/` and
 * swaps into a sent/error Notification. `PopInPage` and `SharePage` are this
 * page with different copy and payload (`extraBody` carries SharePage's
 * `share_token`). JoinPage's variant (`JoinToAct`) stays separate on purpose —
 * it renders unboxed inside another page's hero and reports errors inline.
 *
 * Props:
 * - `ns`: i18n namespace ('popin' | 'share') for the form strings
 *   (emailLabel/emailPlaceholder/magicLinkSent/errorSendingLink/joining/join/
 *   alreadyHaveAccount) and the email input id (`{ns}-email`).
 * - `docTitleKey` / `titleKey` / `descriptionKey`: full i18n keys for the
 *   document title, hero title and intro paragraph (their names differ per page).
 * - `extraBody`: extra fields merged into the POST body.
 */
export default function MagicLinkJoinPage({ ns, docTitleKey, titleKey, descriptionKey, extraBody }) {
  const { t } = useTranslation();
  useEffect(() => { document.title = t(docTitleKey); }, [t, docTitleKey]);
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
        body: JSON.stringify({ email, ...extraBody }),
      });
      if (res.ok) {
        localStorage.removeItem('seenWelcome');
        setStatus('success');
        setMessage(t(`${ns}.magicLinkSent`));
      } else if (res.status === 429) {
        setStatus('error');
        setMessage(t('common.tooManyAttempts'));
      } else {
        setStatus('error');
        setMessage(t(`${ns}.errorSendingLink`));
      }
    } catch {
      setStatus('error');
      setMessage(t('common.connectionError'));
    } finally {
      setLoading(false);
    }
  };

  const { btnStyle } = useTheeeme();

  return (
    <PageLayout title={t(titleKey)}>
      <p className="section-mt" style={{ maxWidth: '400px' }}>{t(descriptionKey)}</p>
      {status ? (
        <>
          <Notification
            label={status === 'success' ? t('common.sent') : t('common.error')}
            type={status}
            style={{ marginTop: 'var(--spacing-m)' }}
          >
            {message}
          </Notification>
          {status === 'success' && (
            <p className="section-mt">{t('popin.closeThisTab')}</p>
          )}
        </>
      ) : (
        <form onSubmit={handleSubmit} style={{ maxWidth: '400px' }}>
          <TextInput
            id={`${ns}-email`}
            label={t(`${ns}.emailLabel`)}
            type="email"
            placeholder={t(`${ns}.emailPlaceholder`)}
            value={email}
            onChange={(e) => setEmail(e.target.value)}
            required
            className="section-mt"
          />
          <div>
            <Button type="submit" fullWidth disabled={loading} style={btnStyle}>
              {loading ? t(`${ns}.joining`) : t(`${ns}.join`)}
            </Button>
          </div>
        </form>
      )}
      <p style={{ marginTop: 'var(--spacing-m)', maxWidth: '400px' }}>
        <Link to="/login">{t(`${ns}.alreadyHaveAccount`)}</Link>
      </p>
    </PageLayout>
  );
}
