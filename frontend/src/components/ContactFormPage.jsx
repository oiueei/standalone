import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Notification, TextInput, TextArea } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from './PageLayout';
import useTheeeme from '../hooks/useTheeeme';

/**
 * The shared operator-message form, rendered by `ContactPage` (support,
 * `kind="support"`) and `CollaboratePage` (`kind="collab"`) with their own
 * copy — the same pattern as `MagicLinkJoinPage` for popin/share. Public on
 * purpose: the person who most needs the support form is the one who can't
 * sign in. Name (optional), a reply address and the message; the backend
 * forwards it to the operator with Reply-To set and a per-kind subject.
 *
 * Props: `docTitleKey` / `titleKey` / `introKey` (full i18n keys — the copy
 * differs per page), `kind` (`support` | `collab`), `idPrefix` (input ids),
 * `children` (optional extra content under the form, e.g. ContactPage's link
 * to the collaborate page).
 */
export default function ContactFormPage({ docTitleKey, titleKey, introKey, kind, idPrefix, children }) {
  const { t } = useTranslation();
  useEffect(() => { document.title = t(docTitleKey); }, [t, docTitleKey]);
  const { btnStyle } = useTheeeme();
  const [name, setName] = useState('');
  const [email, setEmail] = useState('');
  const [message, setMessage] = useState('');
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');
  const isLoggedIn = !!localStorage.getItem('userCode');

  const handleSubmit = async (e) => {
    e.preventDefault();
    setSending(true);
    setError('');
    try {
      const res = await apiFetch('/api/v1/contact/', {
        method: 'POST',
        body: JSON.stringify({ name, email, message, kind }),
      });
      if (res.ok) {
        setSent(true);
      } else if (res.status === 429) {
        setError(t('common.tooManyAttempts'));
      } else {
        setError(t('contact.error'));
      }
    } catch {
      setError(t('common.connectionError'));
    } finally {
      setSending(false);
    }
  };

  return (
    <PageLayout
      title={t(titleKey)}
      backTo={isLoggedIn ? '/' : '/login'}
      backLabel={isLoggedIn ? t('common.home') : t('verify.goToLogin')}
      description={t(introKey)}
    >
      <div style={{ maxWidth: '600px' }}>
        {sent ? (
          <Notification label={t('contact.sentLabel')} type="success">
            {t('contact.sentBody')}
          </Notification>
        ) : (
          <form onSubmit={handleSubmit} className="form-grid">
            <TextInput
              id={`${idPrefix}-name`}
              label={t('contact.nameLabel')}
              value={name}
              maxLength={32}
              onChange={(e) => setName(e.target.value)}
            />
            <TextInput
              id={`${idPrefix}-email`}
              label={t('contact.emailLabel')}
              type="email"
              required
              value={email}
              onChange={(e) => setEmail(e.target.value)}
            />
            <TextArea
              id={`${idPrefix}-message`}
              label={t('contact.messageLabel')}
              required
              value={message}
              maxLength={2000}
              onChange={(e) => setMessage(e.target.value)}
            />
            {error && (
              <Notification label={t('common.error')} type="error">
                {error}
              </Notification>
            )}
            <div>
              <Button type="submit" disabled={sending || !message.trim()} style={btnStyle}>
                {sending ? t('common.sending') : t('common.send')}
              </Button>
            </div>
          </form>
        )}
        {children}
      </div>
    </PageLayout>
  );
}
