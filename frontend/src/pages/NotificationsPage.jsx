import { useEffect, useState } from 'react';
import { useNavigate, useParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Notification, ToggleButton } from 'hds-react';
import { apiFetch } from '../services/api';
import LoadingSpinner from '../components/LoadingSpinner';
import PageLayout from '../components/PageLayout';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

export default function NotificationsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const { token } = useParams();

  useEffect(() => { document.title = t('titles.notifications'); }, [t]);

  const { tc: theeemeColors, btnStyle } = useTheeeme();

  const [loading, setLoading] = useState(true);
  const [notifyActivity, setNotifyActivity] = useState(true);
  const [notifyNews, setNotifyNews] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const [saved, setSaved] = useState(false);
  const [invalidToken, setInvalidToken] = useState(false);

  useEffect(() => {
    if (!token) {
      navigate('/me/edit', { replace: true });
      return;
    }

    const load = async () => {
      try {
        const res = await apiFetch(`/api/v1/notifications/token/${token}/`);
        if (res.ok) {
          const data = await res.json();
          setNotifyActivity(data.notify_activity);
          setNotifyNews(data.notify_news);
        } else {
          setInvalidToken(true);
        }
      } catch {
        setToast({ type: 'error', message: t('common.connectionError') });
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [token, navigate, t]);

  const handleSave = async () => {
    setSubmitting(true);
    setSaved(false);
    setToast(null);
    const body = { notify_activity: notifyActivity, notify_news: notifyNews };
    try {
      const res = await apiFetch(`/api/v1/notifications/token/${token}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setSaved(true);
      } else {
        setToast({ type: 'error', message: t('notifications.errorSaving') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingSpinner />;

  return (
    <PageLayout>
        <h1 className="page-title-xl">{t('notifications.pageTitle')}</h1>

        {invalidToken ? (
          <Notification type="error" label={t('common.error')}>
            {t('notifications.invalidLink')}
          </Notification>
        ) : (
          <>
            <p>{t('notifications.intro')}</p>
            <div className="form-grid">
              <div className="toggle-left">
                <ToggleButton
                  id="notify-magic"
                  label={<>{t('notifications.magicLabel')}<br/><span style={{ fontSize: 'var(--fontsize-body-s)', fontWeight: 400, color: 'var(--color-black-70)' }}>{t('notifications.magicHelper')}</span></>}
                  checked
                  disabled
                  onChange={() => {}}
                  variant="inline"
                  theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
                />
              </div>
              <div className="toggle-left">
                <ToggleButton
                  id="notify-activity"
                  label={<>{t('notifications.activityLabel')}<br/><span style={{ fontSize: 'var(--fontsize-body-s)', fontWeight: 400, color: 'var(--color-black-70)' }}>{t('notifications.activityHelper')}</span></>}
                  checked={notifyActivity}
                  onChange={(val) => { setNotifyActivity(!val); setSaved(false); }}
                  variant="inline"
                  theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
                />
              </div>
              <div className="toggle-left">
                <ToggleButton
                  id="notify-news"
                  label={<>{t('notifications.newsLabel')}<br/><span style={{ fontSize: 'var(--fontsize-body-s)', fontWeight: 400, color: 'var(--color-black-70)' }}>{t('notifications.newsHelper')}</span></>}
                  checked={notifyNews}
                  onChange={(val) => { setNotifyNews(!val); setSaved(false); }}
                  variant="inline"
                  theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
                />
              </div>
            </div>
            {saved && (
              <Notification type="success" label={t('common.done')}>
                {t('notifications.saved')}
              </Notification>
            )}
            <div className="form-actions">
              <Button fullWidth disabled={submitting} onClick={handleSave} style={btnStyle}>
                {submitting ? t('common.saving') : t('common.save')}
              </Button>
            </div>
          </>
        )}
        <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
