import { useEffect, useState } from 'react';
import { Link, useNavigate, useLocation } from 'react-router';
import { useTranslation, Trans } from 'react-i18next';
import { TextInput, TextArea, Button, Select, ToggleButton } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import ImageUpload from '../components/ImageUpload';
import useTheeeme from '../hooks/useTheeeme';
import { invalidateMe } from '../hooks/useCapabilities';
import { SUPPORTED_LANGUAGES } from '../i18n';
import hdsLang from '../utils/hdsLang';
import useDocumentTitle from '../hooks/useDocumentTitle';

const AGE_RANGES = ['PRE_1946', 'BOOMER', 'GEN_X', 'GEN_Y', 'GEN_Z', 'GEN_A', 'GEN_B'];

export default function EditProfilePage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  useDocumentTitle(t('titles.editProfile'));
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.home');
  const userCode = localStorage.getItem('userCode');
  const { tc: theeemeColors, btnStyle } = useTheeeme();

  const [loading, setLoading] = useState(true);
  const [name, setName] = useState('');
  const [headline, setHeadline] = useState('');
  const [about, setAbout] = useState('');
  const [photo, setPhoto] = useState('');
  const [photoUrl, setPhotoUrl] = useState('');
  const [notifyActivity, setNotifyActivity] = useState(true);
  const [notifyNews, setNotifyNews] = useState(false);
  const [language, setLanguage] = useState('');
  const [ageRange, setAgeRange] = useState('');
  const [postalCode, setPostalCode] = useState('');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    const fetchData = async () => {
      try {
        const profileRes = await apiFetch('/api/v1/auth/me/');

        if (profileRes.ok) {
          const data = await profileRes.json();
          setName(data.name || '');
          setHeadline(data.headline || '');
          setAbout(data.about || '');
          setPhoto(data.photo || '');
          setPhotoUrl(data.photo_url || '');
          setNotifyActivity(data.notify_activity ?? true);
          setNotifyNews(data.notify_news ?? false);
          // The SAVED preference, blank included — never the language the
          // browser happens to be showing. Pre-filling with the effective one
          // stamped it on save for anyone who merely edited their name: a
          // blank preference (the Automatic option) is what lets each
          // group's own language reach this member, and it has to survive
          // an unrelated profile edit.
          setLanguage(data.language || '');
          setAgeRange(data.age_range || '');
          setPostalCode(data.postal_code || '');
        } else {
          setToast({ type: 'error', message: t('editProfile.errorLoading') });
        }
      } catch {
        setToast({ type: 'error', message: t('common.connectionError') });
      } finally {
        setLoading(false);
      }
    };
    fetchData();
    // t/i18n must stay out of this array: i18n.changeLanguage() (the language
    // Select below) gives them a new identity on every change, which re-ran
    // this effect, re-fetched /auth/me/, and clobbered every unsaved field
    // (including the language pick itself) with the server's stale copy.
    // This load is meant to run once per mount.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [userCode, navigate]);

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
      notify_activity: notifyActivity,
      notify_news: notifyNews,
      // Also the language OIUEEI writes to this user in (email included).
      language,
      age_range: ageRange,
      postal_code: postalCode,
    };

    try {
      const res = await apiFetch(`/api/v1/users/${userCode}/`, {
        method: 'PUT',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        // The shared /auth/me/ cache (useCapabilities.loadUserLanguage) would
        // otherwise keep answering with the pre-edit language for the rest of
        // this session — it caches per account, not per save.
        invalidateMe();
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
          helperText={`${t('editProfile.nameHelper')} ${name.length}/32`}
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
        {/* Group the textarea and its Markdown hint in one grid cell so the hint
              hugs the textarea, and the grid gap separates it from the photo field. */}
        <div>
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
          <p
            style={{
              fontSize: 'var(--fontsize-body-s)',
              color: 'var(--color-black-60)',
              marginTop: 'var(--spacing-2-xs)',
            }}
          >
            <Trans
              i18nKey="editProfile.aboutMarkdownHint"
              components={[
                // eslint-disable-next-line jsx-a11y/anchor-has-content -- the link text is injected by <Trans> from the i18n string at runtime
                <a key="0" href="https://dillinger.io" target="_blank" rel="noopener noreferrer" />,
              ]}
            />
          </p>
        </div>
        <ImageUpload
          id="edit-profile-photo"
          label={t('editProfile.photoLabel')}
          folder="oiueei/users"
          currentUrl={photoUrl}
          onChange={setPhoto}
          helperText={t('editProfile.photoHelper')}
        />
        <Select
          id="edit-profile-language"
          texts={{
            label: t('editProfile.languageLabel'),
            assistive: t('editProfile.languageHelper'),
            language: hdsLang(i18n.language),
          }}
          options={[
            { label: t('editProfile.languageAutomatic'), value: '' },
            ...SUPPORTED_LANGUAGES.map((l) => ({ label: l.name, value: l.code })),
          ]}
          value={language}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setLanguage(selectedOptions[0].value);
              // A concrete pick switches the interface at once (as it always
              // did); Save then persists it, so the emails follow the
              // interface. Automatic saves a blank preference — the
              // hierarchy (each group's own language, else the browser's)
              // takes over again from the next visit, so there is nothing
              // to switch to here mid-session.
              if (selectedOptions[0].value) i18n.changeLanguage(selectedOptions[0].value);
            }
          }}
        />
      </div>
      <h2 style={{ marginTop: 'var(--spacing-xl)' }}>{t('communityProfile.heading')}</h2>
      <p style={{ marginBottom: 'var(--spacing-m)' }}>{t('communityProfile.helper')}</p>
      <div className="form-grid">
        <Select
          id="edit-profile-age"
          texts={{ label: t('communityProfile.ageLabel'), language: hdsLang(i18n.language) }}
          options={[
            { label: t('communityProfile.ageUnset'), value: '' },
            ...AGE_RANGES.map((c) => ({ label: t(`ageRange.${c}`), value: c })),
          ]}
          value={ageRange}
          onChange={(selectedOptions) => {
            setAgeRange(selectedOptions.length > 0 ? selectedOptions[0].value : '');
          }}
        />
        <TextInput
          id="edit-profile-postal"
          label={t('communityProfile.postalLabel')}
          value={postalCode}
          onChange={(e) => setPostalCode(e.target.value)}
          maxLength={10}
        />
      </div>
      <h2 style={{ marginTop: 'var(--spacing-xl)' }}>{t('notifications.pageTitle')}</h2>
      <p style={{ marginBottom: 'var(--spacing-m)' }}>{t('notifications.intro')}</p>
      <div className="form-grid">
        <ToggleButton
          id="notify-magic"
          variant="inline"
          label={t('notifications.magicFull')}
          checked
          disabled
          onChange={() => {}}
          theme={
            theeemeColors.color_01
              ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` }
              : undefined
          }
        />
        <ToggleButton
          id="notify-activity"
          variant="inline"
          label={t('notifications.activityFull')}
          checked={notifyActivity}
          onChange={(val) => setNotifyActivity(!val)}
          theme={
            theeemeColors.color_01
              ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` }
              : undefined
          }
        />
        <ToggleButton
          id="notify-news"
          variant="inline"
          label={t('notifications.newsFull')}
          checked={notifyNews}
          onChange={(val) => setNotifyNews(!val)}
          theme={
            theeemeColors.color_01
              ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` }
              : undefined
          }
        />
      </div>
      <div className="form-actions">
        <Button fullWidth disabled={submitting} onClick={handleSubmit} style={btnStyle}>
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
      </div>
      {/* Portability before erasure, in that order: reading your own copy
            first is the sane sequence and the legally solid one, and it's why
            this link sits above deleteAccount's rather than below it. */}
      <div
        style={{
          marginTop: 'var(--spacing-xl)',
          borderTop: '1px solid var(--color-black-20)',
          paddingTop: 'var(--spacing-m)',
        }}
      >
        <Link to="/me/data" style={{ color: 'var(--color-black-60)', textDecoration: 'underline' }}>
          {t('editProfile.downloadData')}
        </Link>
      </div>
      {/* Right to erasure — a quiet link, not a red button: deletion has its
            own page that explains everything and still requires an email
            confirmation, so this is an entrance, not the trigger. */}
      <div style={{ marginTop: 'var(--spacing-xs)' }}>
        <Link
          to="/me/delete"
          style={{ color: 'var(--color-black-60)', textDecoration: 'underline' }}
        >
          {t('editProfile.deleteAccount')}
        </Link>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
