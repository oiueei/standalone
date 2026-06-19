import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Button, ToggleButton, Select } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import TheeemeSelector from '../components/TheeemeSelector';
import KoroSelector from '../components/KoroSelector';
import ImageUpload from '../components/ImageUpload';
import useTheeeme from '../hooks/useTheeeme';
import { SUPPORTED_LANGUAGES } from '../i18n';

export default function EditProfilePage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  useEffect(() => { document.title = t('titles.editProfile'); }, [t]);
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.home');
  const userCode = localStorage.getItem('userCode');
  const { tc: theeemeColors } = useTheeeme();

  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [headline, setHeadline] = useState('');
  const [about, setAbout] = useState('');
  const [photo, setPhoto] = useState('');
  const [photoUrl, setPhotoUrl] = useState('');
  const [koro, setKoro] = useState('basic');
  const [theeeme, setTheeeme] = useState('');
  const [theeemes, setTheeemes] = useState([]);
  const [notifyActivity, setNotifyActivity] = useState(true);
  const [notifyNews, setNotifyNews] = useState(true);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
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
          setAbout(data.about || '');
          setPhoto(data.photo || '');
          setPhotoUrl(data.photo_url || '');
          setKoro(data.koro || 'basic');
          setTheeeme(data.theeeme || '');
          setNotifyActivity(data.notify_activity ?? true);
          setNotifyNews(data.notify_news ?? true);
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
    if (about.length > 2000) newErrors.about = t('editProfile.maxAbout');
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
      about: about.trim(),
      photo,
      koro,
      notify_activity: notifyActivity,
      notify_news: notifyNews,
    };
    if (theeeme) body.theeeme = theeeme;

    try {
      const res = await apiFetch(`/api/v1/users/${userCode}/`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate('/');
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('editProfile.errorSaving') });
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
    <PageLayout backTo={backPath} backLabel={backLabel}>
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
          <TextInput
            id="edit-profile-headline"
            label={t('editProfile.bioLabel')}
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            invalid={!!errors.headline}
            errorText={errors.headline}
            helperText={`${headline.length}/64`}
          />
          <TextArea
            id="edit-profile-about"
            label={t('editProfile.aboutLabel')}
            value={about}
            onChange={(e) => setAbout(e.target.value)}
            invalid={!!errors.about}
            errorText={errors.about}
            helperText={`${t('editProfile.aboutHelper')} · ${about.length}/2000`}
            style={{ minHeight: '8rem' }}
          />
          <ImageUpload
            id="edit-profile-photo"
            label={t('editProfile.photoLabel')}
            folder="oiueei/users"
            currentUrl={photoUrl}
            onChange={setPhoto}
            helperText={t('editProfile.photoHelper')}
          />
          <TheeemeSelector
            theeemes={theeemes}
            value={theeeme}
            onChange={setTheeeme}
          />
          <KoroSelector value={koro} onChange={setKoro} />
          <Select
            language="en"
            id="edit-profile-language"
            texts={{ label: t('editProfile.languageLabel') }}
            options={SUPPORTED_LANGUAGES.map((l) => ({ label: l.name, value: l.code }))}
            value={i18n.resolvedLanguage || i18n.language}
            onChange={(selectedOptions) => {
              if (selectedOptions.length > 0) {
                i18n.changeLanguage(selectedOptions[0].value);
              }
            }}
          />
        </div>
        <h2 style={{ marginTop: 'var(--spacing-xl)' }}>{t('notifications.pageTitle')}</h2>
        <p style={{ marginBottom: 'var(--spacing-m)' }}>{t('notifications.intro')}</p>
        <div className="form-grid">
          <div className="toggle-left">
            <ToggleButton
              id="notify-magic"
              label={<>{t('notifications.magicLabel')}<br/><span style={{ fontSize: 'var(--fontsize-body-s)', fontWeight: 400, color: 'var(--color-black-70)' }}>{t('notifications.magicHelper')}</span></>}
              checked
              disabled
              onChange={() => {}}
              variant="inline"
              theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
            />
          </div>
          <div className="toggle-left">
            <ToggleButton
              id="notify-activity"
              label={<>{t('notifications.activityLabel')}<br/><span style={{ fontSize: 'var(--fontsize-body-s)', fontWeight: 400, color: 'var(--color-black-70)' }}>{t('notifications.activityHelper')}</span></>}
              checked={notifyActivity}
              onChange={(val) => setNotifyActivity(!val)}
              variant="inline"
              theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
            />
          </div>
          <div className="toggle-left">
            <ToggleButton
              id="notify-news"
              label={<>{t('notifications.newsLabel')}<br/><span style={{ fontSize: 'var(--fontsize-body-s)', fontWeight: 400, color: 'var(--color-black-70)' }}>{t('notifications.newsHelper')}</span></>}
              checked={notifyNews}
              onChange={(val) => setNotifyNews(!val)}
              variant="inline"
              theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
            />
          </div>
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
    </PageLayout>
  );
}
