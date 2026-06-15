import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import { Button } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

export default function RemoveGuestPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const backPath = `/collections/${code}/invites`;
  const backLabel = location.state?.backLabel || t('removeGuest.guests');
  const guestCode = location.state?.guestCode;
  const guestName = location.state?.guestName || 'this guest';

  useEffect(() => {
    if (!guestCode) navigate(backPath);
  }, [guestCode, navigate, backPath]);

  useEffect(() => {
    document.title = t('titles.removeGuest');
  }, [t]);

  const [removing, setRemoving] = useState(false);
  const [toast, setToast] = useState(null);

  const handleRemove = async () => {
    setRemoving(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/invite/`, {
        method: 'DELETE',
        body: JSON.stringify({ user_code: guestCode }),
      });
      if (res.ok) {
        navigate(backPath);
      } else {
        setToast({ type: 'error', message: t('removeGuest.errorRemoving') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setRemoving(false);
    }
  };

  const { btnStyle, btnSecondaryStyle } = useTheeeme();

  return (
    <PageLayout
      title={t('removeGuest.pageTitle', { name: guestName })}
      backTo={backPath}
      backLabel={backLabel}
    >
      <p><Trans i18nKey="removeGuest.warning" values={{ name: guestName }} components={[<strong key="0" />]} /></p>
      <div className="spacer-xs" />
      <div className="form-grid">
        <Button fullWidth disabled={removing} onClick={handleRemove} style={btnStyle}>
          {removing ? t('common.removing') : t('common.remove')}
        </Button>
        <Button variant="secondary" fullWidth onClick={() => navigate(backPath)} style={btnSecondaryStyle}>
          {t('common.cancel')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
