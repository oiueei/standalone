import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Select, Button, Koros } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import ImageUpload from '../components/ImageUpload';

export default function EditCollectionPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');
  const [loading, setLoading] = useState(true);
  const [headline, setHeadline] = useState('');
  useEffect(() => { document.title = headline ? t('titles.editCollection', { headline }) : t('titles.editCollectionDefault'); }, [headline, t]);
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [thumbnailUrl, setThumbnailUrl] = useState('');
  const [hero, setHero] = useState('');
  const [heroUrl, setHeroUrl] = useState('');
  const [status, setStatus] = useState('ACTIVE');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const STATUS_OPTIONS = [
    { label: t('editCollection.statusActive'), value: 'ACTIVE' },
    { label: t('editCollection.statusInactive'), value: 'INACTIVE' },
  ];

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
      return;
    }

    const fetchData = async () => {
      try {
        const collectionRes = await apiFetch(`/api/v1/collections/${code}/`);

        if (collectionRes.ok) {
          const data = await collectionRes.json();
          setHeadline(data.headline || '');
          setDescription(data.description || '');
          setThumbnail(data.thumbnail || '');
          setThumbnailUrl(data.thumbnail_url || '');
          setHero(data.hero || '');
          setHeroUrl(data.hero_url || '');
          setStatus(data.status || 'ACTIVE');
        } else {
          setToast({ type: 'error', message: t('editCollection.errorLoading') });
        }
      } catch {
        setToast({ type: 'error', message: t('common.connectionError') });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
  }, [userCode, code, navigate, t]);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('editCollection.titleRequired');
    if (headline.length > 64) newErrors.headline = t('editCollection.maxHeadline');
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = {
      headline: headline.trim(),
      description: description.trim(),
      thumbnail: thumbnail || '',
      hero: hero || '',
      status,
    };

    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(`/collections/${code}`);
      } else {
        setToast({ type: 'error', message: t('editCollection.errorSaving') });
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

  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
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
          <BackLink to={`/collections/${code}`} label={headline || t('common.collection')} />
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <h1 className="page-title-xl">{t('editCollection.pageTitle')}</h1>
      <div className="form-grid">
        <TextInput
          id="edit-collection-headline"
          label={t('editCollection.titleLabel')}
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          required
          invalid={!!errors.headline}
          errorText={errors.headline}
          helperText={`${headline.length}/64`}
        />
        <TextArea
          id="edit-collection-description"
          label={t('editCollection.descriptionLabel')}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          helperText={`${description.length}/256`}
        />
        <ImageUpload
          id="edit-collection-thumbnail"
          label={t('upload.thumbnailLabel')}
          value={thumbnail}
          onChange={setThumbnail}
          currentUrl={thumbnailUrl}
          folder="oiueei/collections"
        />
        <ImageUpload
          id="edit-collection-hero"
          label={t('upload.heroLabel')}
          value={hero}
          onChange={setHero}
          currentUrl={heroUrl}
          folder="oiueei/collections"
        />
        <Select
          id="edit-collection-status"
          texts={{ label: t('editCollection.statusLabel') }}
          helper={t('editCollection.statusHelper')}
          options={STATUS_OPTIONS}
          value={status}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setStatus(selectedOptions[0].value);
            }
          }}
        />
      </div>
      <div className="form-actions">
        <Button disabled={submitting} onClick={handleSubmit} style={{ ...btnStyle, width: '100%' }}>
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
