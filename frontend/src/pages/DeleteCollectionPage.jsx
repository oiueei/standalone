import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

export default function DeleteCollectionPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const userCode = localStorage.getItem('userCode');
  const { btnStyle, btnSecondaryStyle } = useTheeeme();
  const backPath = location.state?.backPath || `/collections/${code}/edit`;
  const backLabel = location.state?.backLabel || t('common.back');

  const [collection, setCollection] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    document.title = collection
      ? t('titles.deleteCollection', { headline: collection.headline })
      : t('titles.deleteCollectionDefault');
  }, [collection, t]);

  useEffect(() => {
    if (!userCode) return;
    apiFetch(`/api/v1/collections/${code}/`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => { if (data) setCollection(data); })
      .catch(() => {});
  }, [userCode, code]);

  const handleDelete = async () => {
    setDeleting(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, { method: 'DELETE' });
      if (res.ok || res.status === 204) {
        navigate('/');
      } else {
        setToast({ type: 'error', message: t('deleteCollection.errorDeleting') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setDeleting(false);
    }
  };

  if (!collection) return null;

  return (
    <PageLayout
      title={t('deleteCollection.pageTitle', { headline: collection.headline })}
      backTo={backPath}
      backLabel={backLabel}
    >
      <p>{t('deleteCollection.warning')}</p>
      <div className="spacer-xs" />
      <div className="form-grid">
        <Button fullWidth disabled={deleting} onClick={handleDelete} style={btnStyle}>
          {deleting ? t('common.deleting') : t('common.delete')}
        </Button>
        <Button variant="secondary" fullWidth onClick={() => navigate(backPath)} style={btnSecondaryStyle}>
          {t('common.cancel')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
