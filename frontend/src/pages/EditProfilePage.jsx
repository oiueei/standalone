import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Button, Koros } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import TheeemeSelector from '../components/TheeemeSelector';
import KoroSelector from '../components/KoroSelector';

export default function EditProfilePage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  useEffect(() => { document.title = t('titles.editProfile'); }, [t]);
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.home');
  const userCode = localStorage.getItem('userCode');
  const theeemeColors = JSON.parse(localStorage.getItem('theeemeColors') || '{}');

  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [headline, setHeadline] = useState('');
  const [koro, setKoro] = useState('basic');
  const [theeeme, setTheeeme] = useState('');
  const [theeemes, setTheeemes] = useState([]);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
      return;
    }

    const fetchData = async () => {
      try {
        const [profileRes, theemesRes] = await Promise.all([
          apiFetch('/api/v1/auth/me/'),
          apiFetch('/api/v1/theeemes/'),
        ]);

        if (profileRes.ok) {
          const data = await profileRes.json();
          setName(data.name || '');
          setHeadline(data.headline || '');
          setKoro(data.koro || 'basic');
          setTheeeme(data.theeeme || '');
        } else {
          setToast({ type: 'error', message: t('editProfile.errorLoading') });
        }

        if (theemesRes.ok) {
          const data = await theemesRes.json();
          setTheeemes(Array.isArray(data) ? data : data.results || []);
        }
      } catch {
        setToast({ type: 'error', message: t('common.connectionError') });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [userCode, navigate, t]);

  const validate = () => {
    const newErrors = {};
    if (name.length > 32) newErrors.name = t('editProfile.maxName');
    if (headline.length > 64) newErrors.headline = t('editProfile.maxBio');
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = {
      name: name.trim(),
      headline: headline.trim(),
      koro,
    };
    if (theeeme) body.theeeme = theeeme;

    try {
      const res = await apiFetch(`/api/v1/users/${userCode}/`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate('/');
      } else {
        setToast({ type: 'error', message: t('editProfile.errorSaving') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) {
    return <LoadingSpinner />;
  }

  return (
    <div
      className="form-page"
      style={theeemeColors.color_02 ? { backgroundColor: `var(--color-${theeemeColors.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={theeemeColors.color_03 ? { backgroundColor: `var(--color-${theeemeColors.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={theeemeColors.color_05 ? { '--hero-text-color': `var(--color-${theeemeColors.color_05})` } : undefined}>
          <BackLink to={backPath} label={backLabel} />
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={theeemeColors.color_02 ? { fill: `var(--color-${theeemeColors.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <h1 className="page-title-xl">{t('editProfile.pageTitle')}</h1>
        <div className="form-grid">
          <TextInput
            id="edit-profile-name"
            label={t('editProfile.nameLabel')}
            value={name}
            onChange={(e) => setName(e.target.value)}
            invalid={!!errors.name}
            errorText={errors.name}
            helperText={`${name.length}/32`}
          />
          <TextArea
            id="edit-profile-headline"
            label={t('editProfile.bioLabel')}
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            invalid={!!errors.headline}
            errorText={errors.headline}
            helperText={`${headline.length}/64`}
          />
          <TheeemeSelector
            theeemes={theeemes}
            value={theeeme}
            onChange={setTheeeme}
          />
          <KoroSelector value={koro} onChange={setKoro} />
        </div>
        <div className="form-actions">
          <Button
            fullWidth
            disabled={submitting}
            onClick={handleSubmit}
            style={theeemeColors.color_01 ? {
              '--background-color': `var(--color-${theeemeColors.color_01})`,
              '--background-color-hover': `var(--color-${theeemeColors.color_01}-dark)`,
              '--color': theeemeColors.color_06 ? `var(--color-${theeemeColors.color_06})` : 'var(--color-white)',
              '--border-color': `var(--color-${theeemeColors.color_01})`,
            } : undefined}
          >
            {submitting ? t('common.saving') : t('common.save')}
          </Button>
        </div>
        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
