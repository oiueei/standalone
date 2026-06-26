import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { TextInput, Button, Notification } from 'hds-react';
import { getCsrfToken } from '../services/api';
import useTheeeme from '../hooks/useTheeeme';

/**
 * Inline "log in to act" prompt shown to an anonymous visitor on a PUBLIC
 * collection or thing. Captures an email and POSTs it to `/auth/pop-in/` along
 * with the collection code: the backend adds the visitor to that public
 * collection's invitees and emails a magic link, so once they follow it they're
 * a member and can reserve, ask and contribute. No account or prior invitation
 * is needed — and the code only ever joins a PUBLIC collection (the backend
 * silently ignores it otherwise).
 */
export default function JoinToAct({ collectionCode, collectionHeadline, asPage = false }) {
  const { t } = useTranslation();
  const { btnStyle } = useTheeeme();
  const [email, setEmail] = useState('');
  const [loading, setLoading] = useState(false);
  const [status, setStatus] = useState(null); // 'success' | 'error'
  const [message, setMessage] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (loading) return;
    setStatus(null);
    setLoading(true);
    try {
      const res = await fetch('/api/v1/auth/pop-in/', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRFToken': getCsrfToken() },
        body: JSON.stringify({ email, collection_code: collectionCode }),
      });
      if (res.ok) {
        localStorage.removeItem('seenWelcome');
        setStatus('success');
        setMessage(t('joinToAct.sentBody'));
      } else if (res.status === 429) {
        setStatus('error');
        setMessage(t('common.tooManyAttempts'));
      } else {
        setStatus('error');
        setMessage(t('joinToAct.error'));
      }
    } catch {
      setStatus('error');
      setMessage(t('common.connectionError'));
    } finally {
      setLoading(false);
    }
  };

  if (status === 'success') {
    return (
      <Notification label={t('joinToAct.sent')} type="success" className={asPage ? undefined : 'join-to-act'}>
        {message}
      </Notification>
    );
  }

  const body = (
    <>
      <p style={asPage ? { marginTop: 0 } : undefined}>
        {collectionHeadline
          ? t('joinToAct.bodyNamed', { collection: collectionHeadline })
          : t('joinToAct.body')}
      </p>
      <form onSubmit={handleSubmit}>
        <TextInput
          id="join-to-act-email"
          label={t('joinToAct.emailLabel')}
          type="email"
          placeholder={t('joinToAct.emailPlaceholder')}
          value={email}
          onChange={(e) => setEmail(e.target.value)}
          required
        />
        {status === 'error' && (
          <p style={{ color: 'var(--color-error)', marginBottom: 0 }}>{message}</p>
        )}
        <div style={{ marginTop: 'var(--spacing-s)' }}>
          <Button type="submit" disabled={loading} style={btnStyle}>
            {loading ? t('joinToAct.joining') : t('joinToAct.join')}
          </Button>
        </div>
      </form>
      <p style={{ marginBottom: 0 }}>
        <Link to="/login">{t('joinToAct.alreadyHaveAccount')}</Link>
      </p>
    </>
  );

  // Page mode (JoinPage): no bordered box or heading — the page hero supplies them.
  if (asPage) {
    return <div style={{ maxWidth: '480px' }}>{body}</div>;
  }

  return (
    <section
      className="join-to-act"
      style={{
        border: '1px solid var(--color-black-20)',
        borderRadius: '4px',
        padding: 'var(--spacing-m)',
        maxWidth: '480px',
      }}
    >
      <h2 style={{ marginTop: 0 }}>{t('joinToAct.heading')}</h2>
      {body}
    </section>
  );
}
