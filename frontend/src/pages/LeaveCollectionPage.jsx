import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import { Button } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

export default function LeaveCollectionPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const backPath = `/collections/${code}`;
  const headline = location.state?.headline || t('leaveCollection.thisCollection');

  useEffect(() => {
    document.title = t('titles.leaveCollection');
  }, [t]);

  const [leaving, setLeaving] = useState(false);
  const [toast, setToast] = useState(null);

  const handleLeave = async () => {
    setLeaving(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/leave/`, { method: 'POST' });
      if (res.ok) {
        navigate('/');
      } else {
        setToast({ type: 'error', message: t('leaveCollection.errorLeaving') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setLeaving(false);
    }
  };

  const { btnStyle, btnSecondaryStyle } = useTheeeme();

  return (
    <PageLayout title={t('leaveCollection.pageTitle', { headline })} backTo={backPath} backLabel={headline}>
      <p><Trans i18nKey="leaveCollection.warning" values={{ headline }} components={[<strong key="0" />]} /></p>
      <div className="spacer-xs" />
      <div className="form-grid">
        <Button fullWidth disabled={leaving} onClick={handleLeave} style={btnStyle}>
          {leaving ? t('leaveCollection.leaving') : t('leaveCollection.leave')}
        </Button>
        <Button variant="secondary" fullWidth onClick={() => navigate(backPath)} style={btnSecondaryStyle}>
          {t('common.cancel')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
