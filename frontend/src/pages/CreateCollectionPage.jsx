import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Select, Button, Checkbox, Koros } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

export default function CreateCollectionPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  useEffect(() => { document.title = t('titles.newCollection'); }, [t]);
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.home');
  const userCode = localStorage.getItem('userCode');
  const theeemeColors = JSON.parse(localStorage.getItem('theeemeColors') || '{}');

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
    }
  }, [userCode, navigate]);

  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [mode, setMode] = useState('PROPRIETARY');
  const [isSwap, setIsSwap] = useState(false);
  const [isShare, setIsShare] = useState(false);
  const [errors, setErrors] = useState({});

  const MODE_OPTIONS = [
    { label: t('createCollection.modeProprietary'), value: 'PROPRIETARY' },
    { label: t('createCollection.modeCommunity'), value: 'COMMUNITY' },
  ];
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('createCollection.titleRequired');
    if (headline.length > 64) newErrors.headline = t('createCollection.maxHeadline');
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = {
      headline: headline.trim(),
      mode,
      is_swap: isSwap && mode === 'COMMUNITY',
      is_share: isShare && mode === 'COMMUNITY',
    };
    if (description.trim()) body.description = description.trim();
    try {
      const res = await apiFetch('/api/v1/collections/', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        navigate(`/collections/${data.code}`);
      } else {
        setToast({ type: 'error', message: t('createCollection.errorCreating') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

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
        <h1 className="page-title-xl">{t('createCollection.pageTitle')}</h1>
        <div className="form-grid">
          <TextInput
            id="create-collection-headline"
            label={t('createCollection.titleLabel')}
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            required
            invalid={!!errors.headline}
            errorText={errors.headline}
            helperText={`${headline.length}/64`}
          />
          <TextArea
            id="create-collection-description"
            label={t('createCollection.descriptionLabel')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            helperText={`${description.length}/256`}
          />
          <Select
            id="create-collection-mode"
            texts={{ label: t('createCollection.modeLabel') }}
            helper={t('createCollection.modeHelper')}
            options={MODE_OPTIONS}
            value={mode}
            onChange={(selectedOptions) => {
              if (selectedOptions.length > 0) {
                const newMode = selectedOptions[0].value;
                setMode(newMode);
                if (newMode !== 'COMMUNITY') { setIsSwap(false); setIsShare(false); }
              }
            }}
          />
          {mode === 'COMMUNITY' && (
            <Checkbox
              id="create-collection-swap"
              label={t('swap.enableSwap')}
              checked={isSwap}
              onChange={(e) => { setIsSwap(e.target.checked); if (e.target.checked) setIsShare(false); }}
            />
          )}
          {mode === 'COMMUNITY' && (
            <Checkbox
              id="create-collection-share"
              label={t('share.enableShare')}
              checked={isShare}
              onChange={(e) => { setIsShare(e.target.checked); if (e.target.checked) setIsSwap(false); }}
            />
          )}
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
            {submitting ? t('common.creating') : t('common.create')}
          </Button>
        </div>
        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
