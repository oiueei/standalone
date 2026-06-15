import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

export default function DeleteCollectionPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const userCode = localStorage.getItem('userCode');
  const { tc, koro, btnStyle, btnSecondaryStyle } = useTheeeme();
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
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <BackLink to={backPath} label={backLabel} />
          <h1 className="form-hero-title">{t('deleteCollection.pageTitle', { headline: collection.headline })}</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={koro}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
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
      </div>
    </div>
  );
}
