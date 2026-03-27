import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { Button, Koros } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

export default function RemoveGuestPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const userCode = localStorage.getItem('userCode');
  const backPath = `/collections/${code}/invites`;
  const backLabel = location.state?.backLabel || 'Guests';
  const guestCode = location.state?.guestCode;
  const guestName = location.state?.guestName || 'this guest';

  useEffect(() => {
    if (!userCode) navigate('/login');
    if (!guestCode) navigate(backPath);
  }, [userCode, guestCode, navigate, backPath]);

  useEffect(() => {
    document.title = 'Remove guest — OIUEEI';
  }, []);

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
        setToast({ type: 'error', message: 'Error removing guest.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setRemoving(false);
    }
  };

  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
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
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_04})` } : undefined}>
          <BackLink to={backPath} label={backLabel} />
          <h1 className="form-hero-title">Remove: {guestName}</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <p>This will remove <strong>{guestName}</strong> from the collection. They will lose access immediately.</p>
        <div className="spacer-xs" />
        <div className="form-grid">
          <Button fullWidth disabled={removing} onClick={handleRemove} style={btnStyle}>
            {removing ? 'Removing...' : 'Remove'}
          </Button>
          <Button variant="secondary" fullWidth onClick={() => navigate(backPath)} style={btnSecondaryStyle}>
            Cancel
          </Button>
        </div>
        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
