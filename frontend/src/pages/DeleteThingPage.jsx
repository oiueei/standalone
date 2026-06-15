import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Koros } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

export default function DeleteThingPage() {
  const { t } = useTranslation();
  const { thingCode } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const userCode = localStorage.getItem('userCode');
  const { tc, koro, btnStyle, btnSecondaryStyle } = useTheeeme();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.back');

  const [thing, setThing] = useState(null);
  const [deleting, setDeleting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    document.title = thing ? t('titles.deleteThing', { headline: thing.headline }) : t('titles.deleteThingDefault');
  }, [thing, t]);

  useEffect(() => {
    if (!userCode) return;
    apiFetch(`/api/v1/things/${thingCode}/`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => { if (data) setThing(data); })
      .catch(() => {});
  }, [userCode, thingCode]);

  const handleDelete = async () => {
    setDeleting(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/`, { method: 'DELETE' });
      if (res.ok || res.status === 204) {
        navigate(backPath);
      } else {
        setToast({ type: 'error', message: t('deleteThing.errorDeleting') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setDeleting(false);
    }
  };

  if (!thing) return null;

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
          <h1 className="form-hero-title">{t('deleteThing.pageTitle', { headline: thing.headline })}</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={koro}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <p>{t('deleteThing.warning')}</p>
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
