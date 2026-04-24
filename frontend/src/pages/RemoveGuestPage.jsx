import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import { Button, Koros } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

export default function RemoveGuestPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const userCode = localStorage.getItem('userCode');
  const backPath = `/collections/${code}/invites`;
  const backLabel = location.state?.backLabel || t('removeGuest.guests');
  const guestCode = location.state?.guestCode;
  const guestName = location.state?.guestName || 'this guest';

  useEffect(() => {
    if (!userCode) navigate('/login');
    if (!guestCode) navigate(backPath);
  }, [userCode, guestCode, navigate, backPath]);

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

  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--background-color': 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_04})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
  } : undefined;

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <BackLink to={backPath} label={backLabel} />
          <h1 className="form-hero-title">{t('removeGuest.pageTitle', { name: guestName })}</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
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
      </div>
    </div>
  );
}
