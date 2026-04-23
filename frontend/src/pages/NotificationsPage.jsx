import { useEffect, useState } from 'react';
import { useNavigate, useLocation, useSearchParams } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Checkbox, Button, Koros, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';

export default function NotificationsPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  const token = searchParams.get('t');

  useEffect(() => { document.title = t('titles.notifications'); }, [t]);

  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.home');
  const userCode = localStorage.getItem('userCode');
  const theeemeColors = JSON.parse(localStorage.getItem('theeemeColors') || '{}');

  const [loading, setLoading] = useState(true);
  const [notifyActivity, setNotifyActivity] = useState(true);
  const [notifyNews, setNotifyNews] = useState(true);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const [saved, setSaved] = useState(false);
  const [invalidToken, setInvalidToken] = useState(false);

  useEffect(() => {
    const load = async () => {
      try {
        if (token) {
          const res = await apiFetch(`/api/v1/notifications/token/${token}/`);
          if (res.ok) {
            const data = await res.json();
            setNotifyActivity(data.notify_activity);
            setNotifyNews(data.notify_news);
          } else {
            setInvalidToken(true);
          }
          setLoading(false);
          return;
        }

        if (!userCode) {
          navigate('/login');
          return;
        }

        const res = await apiFetch('/api/v1/auth/me/');
        if (res.ok) {
          const data = await res.json();
          setNotifyActivity(data.notify_activity);
          setNotifyNews(data.notify_news);
        } else {
          setToast({ type: 'error', message: t('notifications.errorLoading') });
        }
      } catch {
        setToast({ type: 'error', message: t('common.connectionError') });
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [token, userCode, navigate, t]);

  const handleSave = async () => {
    setSubmitting(true);
    setSaved(false);
    setToast(null);
    const body = { notify_activity: notifyActivity, notify_news: notifyNews };
    try {
      const url = token
        ? `/api/v1/notifications/token/${token}/`
        : `/api/v1/users/${userCode}/`;
      const method = token ? 'PATCH' : 'PUT';
      const res = await apiFetch(url, { method, body: JSON.stringify(body) });
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

  const btnStyle = theeemeColors.color_01 ? {
    '--background-color': `var(--color-${theeemeColors.color_01})`,
    '--background-color-hover': `var(--color-${theeemeColors.color_01}-dark)`,
    '--color': theeemeColors.color_06 ? `var(--color-${theeemeColors.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${theeemeColors.color_01})`,
  } : undefined;

  return (
    <div
      className="form-page"
      style={theeemeColors.color_02 ? { backgroundColor: `var(--color-${theeemeColors.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={theeemeColors.color_03 ? { backgroundColor: `var(--color-${theeemeColors.color_03})` } : undefined}
      >
        <div
          className="form-hero-content"
          style={theeemeColors.color_05 ? { '--hero-text-color': `var(--color-${theeemeColors.color_05})` } : undefined}
        >
          {!token && <BackLink to={backPath} label={backLabel} />}
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={theeemeColors.color_02 ? { fill: `var(--color-${theeemeColors.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <h1 className="page-title-xl">{t('notifications.pageTitle')}</h1>

        {invalidToken ? (
          <Notification type="error" label={t('common.error')}>
            {t('notifications.invalidLink')}
          </Notification>
        ) : (
          <>
            <p>{t('notifications.intro')}</p>
            <div className="form-grid">
              <Checkbox
                id="notify-magic"
                label={t('notifications.magicLabel')}
                helperText={t('notifications.magicHelper')}
                checked
                disabled
              />
              <Checkbox
                id="notify-activity"
                label={t('notifications.activityLabel')}
                helperText={t('notifications.activityHelper')}
                checked={notifyActivity}
                onChange={(e) => { setNotifyActivity(e.target.checked); setSaved(false); }}
              />
              <Checkbox
                id="notify-news"
                label={t('notifications.newsLabel')}
                helperText={t('notifications.newsHelper')}
                checked={notifyNews}
                onChange={(e) => { setNotifyNews(e.target.checked); setSaved(false); }}
              />
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
      </div>
    </div>
  );
}
