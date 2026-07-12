import { useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { TextInput, Button, Notification } from 'hds-react';
import { getCsrfToken } from '../services/api';
import useTheeeme from '../hooks/useTheeeme';

/**
 * "Log in to act" body rendered by JoinPage for an anonymous visitor on a PUBLIC
 * collection or thing. Captures an email and POSTs it to `/auth/pop-in/` along
 * with the collection code: the backend adds the visitor to that public
 * collection's invitees and emails a magic link, so once they follow it they're
 * a member and can reserve, ask and contribute. No account or prior invitation
 * is needed — and the code only ever joins a PUBLIC collection (the backend
 * silently ignores it otherwise).
 */
export default function JoinToAct({ collectionCode, collectionHeadline }) {
  const { t, i18n } = useTranslation();
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
        // `language` is stored on a brand-new user, so their very first magic link
        // already speaks the language they're reading this page in.
        body: JSON.stringify({
          email,
          collection_code: collectionCode,
          language: i18n.resolvedLanguage || i18n.language,
        }),
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
      <>
        <Notification label={t('joinToAct.sent')} type="success">
          {message}
        </Notification>
        <p className="section-mt">{t('popin.closeThisTab')}</p>
      </>
    );
  }

  const body = (
    <>
      <p style={{ marginTop: 0 }}>
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
          aria-describedby={status === 'error' ? 'join-to-act-error' : undefined}
        />
        {status === 'error' && (
          <p id="join-to-act-error" role="alert" style={{ color: 'var(--color-error)', marginBottom: 0 }}>
            {message}
          </p>
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

  // JoinPage is the only caller: render the body unboxed — the page hero supplies
  // the heading and container.
  return <div style={{ maxWidth: '480px' }}>{body}</div>;
}
