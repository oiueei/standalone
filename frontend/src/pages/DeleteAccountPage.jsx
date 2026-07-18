import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';

/**
 * Step one of the right-to-erasure flow (`/me/delete`): states exactly what is
 * deleted and what stays (anonymised), then emails the confirmation link.
 * Nothing is deleted here — the commit happens on the page that link lands on
 * (VerifyPage), behind one more explicit button, so a stolen browser session
 * alone can never erase an account.
 */
export default function DeleteAccountPage() {
  const { t } = useTranslation();
  useEffect(() => { document.title = t('titles.deleteAccount'); }, [t]);
  const [sending, setSending] = useState(false);
  const [sent, setSent] = useState(false);
  const [error, setError] = useState('');

  const handleSend = async () => {
    setSending(true);
    setError('');
    try {
      const res = await apiFetch('/api/v1/auth/delete-account/', { method: 'POST' });
      if (res.ok) {
        setSent(true);
      } else if (res.status === 429) {
        setError(t('common.tooManyAttempts'));
      } else {
        setError(t('deleteAccount.error'));
      }
    } catch {
      setError(t('common.connectionError'));
    } finally {
      setSending(false);
    }
  };

  return (
    <PageLayout
      title={t('deleteAccount.pageTitle')}
      backTo="/me/edit"
      backLabel={t('editProfile.pageTitle')}
      description={t('deleteAccount.intro')}
    >
      <div style={{ maxWidth: '600px' }}>
        <h2>{t('deleteAccount.whatGoesTitle')}</h2>
        <p>{t('deleteAccount.whatGoes')}</p>
        <div className="spacer-m" />
        <h2>{t('deleteAccount.whatStaysTitle')}</h2>
        <p>{t('deleteAccount.whatStays')}</p>
        <div className="spacer-m" />
        <p>{t('deleteAccount.emailStep')}</p>
        <div className="spacer-m" />
        {sent ? (
          <Notification label={t('deleteAccount.sentLabel')} type="success">
            {t('deleteAccount.sentBody')}
          </Notification>
        ) : (
          <>
            {error && (
              <Notification
                label={t('common.error')}
                type="error"
                style={{ marginBottom: 'var(--spacing-s)' }}
              >
                {error}
              </Notification>
            )}
            <Button variant="danger" disabled={sending} onClick={handleSend}>
              {sending ? t('deleteAccount.sending') : t('deleteAccount.sendButton')}
            </Button>
          </>
        )}
      </div>
    </PageLayout>
  );
}
