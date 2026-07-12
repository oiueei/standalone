import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Select, Button, RadioButton } from 'hds-react';
import { isLockedToSingleType, reconcileAllowedTypes } from '../constants/things';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import CollectionForm from '../components/CollectionForm';
import ImageUpload from '../components/ImageUpload';
import PdfUpload from '../components/PdfUpload';
import { SUPPORTED_LANGUAGES } from '../i18n';
import TagInput from '../components/TagInput';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

export default function EditCollectionPage() {
  const { t, i18n } = useTranslation();
  const { code } = useParams();
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');
  const { tc, btnStyle, btnSecondaryStyle } = useTheeeme();
  const [loading, setLoading] = useState(true);
  const [headline, setHeadline] = useState('');
  useEffect(() => { document.title = headline ? t('titles.editCollection', { headline }) : t('titles.editCollectionDefault'); }, [headline, t]);
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState('ACTIVE');
  const [mode, setMode] = useState('PROPRIETARY');
  const [visibility, setVisibility] = useState('PRIVATE');
  const [digestFrequency, setDigestFrequency] = useState('NONE');
  const [isSwap, setIsSwap] = useState(false);
  const [isShare, setIsShare] = useState(false);
  const [newsletterEnabled, setNewsletterEnabled] = useState(false);
  const [requireMinimumSwapItems, setRequireMinimumSwapItems] = useState(false);
  const [allowedThingTypes, setAllowedThingTypes] = useState([]);
  const [rentalDurations, setRentalDurations] = useState([]);
  const [rentalWeekdays, setRentalWeekdays] = useState([]);
  const [tags, setTags] = useState([]);
  const [thumbnail, setThumbnail] = useState('');
  const [thumbnailUrl, setThumbnailUrl] = useState('');
  const [language, setLanguage] = useState('');
  const [welcomeDoc, setWelcomeDoc] = useState('');
  const [welcomeDocUrl, setWelcomeDocUrl] = useState('');
  const [pauseMessage, setPauseMessage] = useState('');
  const [isPaused, setIsPaused] = useState(false);
  const [pauseSubmitting, setPauseSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [toast, setToast] = useState(null);

  const STATUS_OPTIONS = [
    { label: t('editCollection.statusActive'), value: 'ACTIVE' },
    { label: t('editCollection.statusInactive'), value: 'INACTIVE' },
  ];

  const MODE_OPTIONS = [
    { label: t('editCollection.modeProprietary'), description: t('createCollection.modeProprietaryDesc'), value: 'PROPRIETARY' },
    { label: t('editCollection.modeCommunity'), description: t('createCollection.modeCommunityDesc'), value: 'COMMUNITY' },
  ];

  const DIGEST_OPTIONS = [
    { label: t('editCollection.digestNone'), value: 'NONE' },
    { label: t('editCollection.digestWeekly'), value: 'WEEKLY' },
    { label: t('editCollection.digestMonthly'), value: 'MONTHLY' },
  ];

  const locked = isLockedToSingleType({ isSwap, isShare });

  // Live "pick at least one" feedback once a submit has been attempted (P1-5).
  const allowedTypesError = submitAttempted && !locked && allowedThingTypes.length === 0
    ? t('createCollection.allowedTypesAtLeastOne')
    : '';

  const handleModeChange = (newMode) => {
    if (newMode === mode) return;
    const nextFlags = {
      mode: newMode,
      isSwap: newMode === 'COMMUNITY' ? isSwap : false,
      isShare: newMode === 'COMMUNITY' ? isShare : false,
    };
    setMode(newMode);
    if (newMode !== 'COMMUNITY') { setIsSwap(false); setIsShare(false); setNewsletterEnabled(false); setRequireMinimumSwapItems(false); }
    // Keep the still-valid part of the selection instead of wiping it (P1-5).
    setAllowedThingTypes((prev) => reconcileAllowedTypes(prev, nextFlags));
  };

  useEffect(() => {
    const fetchData = async () => {
      try {
        const collectionRes = await apiFetch(`/api/v1/collections/${code}/`);

        if (collectionRes.ok) {
          const data = await collectionRes.json();
          setHeadline(data.headline || '');
          setDescription(data.description || '');
          setStatus(data.status || 'ACTIVE');
          setMode(data.mode || 'PROPRIETARY');
          setVisibility(data.visibility || 'PRIVATE');
          setDigestFrequency(data.digest_frequency || 'NONE');
          setIsSwap(data.is_swap || false);
          setIsShare(data.is_share || false);
          setNewsletterEnabled(data.newsletter_enabled || false);
          setRequireMinimumSwapItems((data.swap_minimum_items || 0) > 0);
          setAllowedThingTypes(data.allowed_thing_types || []);
          setRentalDurations(data.rental_durations || []);
          setRentalWeekdays(data.rental_weekdays || []);
          setTags(data.tags || []);
          setThumbnail(data.thumbnail || '');
          setThumbnailUrl(data.thumbnail_url || '');
          // Blank = inherit the deployment default; the members' own preference
          // still wins over whatever the owner picks here.
          setLanguage(data.language || i18n.resolvedLanguage || i18n.language);
          setWelcomeDoc(data.welcome_doc || '');
          setWelcomeDocUrl(data.welcome_doc_url || '');
          setPauseMessage(data.pause_message || '');
          setIsPaused(data.is_paused || false);
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
  }, [userCode, code, navigate, t, i18n]);

  const validate = () => {
    setSubmitAttempted(true);
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('editCollection.titleRequired');
    if (headline.length > 64) newErrors.headline = t('editCollection.maxHeadline');
    setErrors(newErrors);
    const allowedTypesOk = locked || allowedThingTypes.length > 0;
    return Object.keys(newErrors).length === 0 && allowedTypesOk;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = {
      headline: headline.trim(),
      description: description.trim(),
      status,
      mode,
      visibility,
      digest_frequency: digestFrequency,
      is_swap: isSwap && mode === 'COMMUNITY',
      is_share: isShare && mode === 'COMMUNITY',
      newsletter_enabled: newsletterEnabled && isShare && mode === 'COMMUNITY',
      swap_minimum_items:
        requireMinimumSwapItems && isSwap && mode === 'COMMUNITY' ? 3 : 0,
      allowed_thing_types: allowedThingTypes,
      rental_durations: isSwap || isShare ? [] : rentalDurations,
      rental_weekdays: isSwap || isShare ? [] : rentalWeekdays,
      tags,
      thumbnail: thumbnail || '',
      language,
      welcome_doc: welcomeDoc || '',
    };

    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(`/collections/${code}`);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else if (res.status === 400) {
        // Backend rejects narrowing if it would orphan existing things — surface
        // its detail (which names the offending types) so the user can act on it.
        const detail = await res.json().catch(() => null);
        const message = (detail && (detail.non_field_errors || detail.detail))
          || t('editCollection.errorSaving');
        setToast({ type: 'error', message: Array.isArray(message) ? message[0] : message });
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

  const handlePauseToggle = async () => {
    setPauseSubmitting(true);
    setToast(null);
    const newMessage = isPaused ? '' : pauseMessage.trim();
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        body: JSON.stringify({ pause_message: newMessage }),
      });
      if (res.ok) {
        setIsPaused(!isPaused);
        if (isPaused) setPauseMessage('');
        setToast({ type: 'success', message: isPaused ? t('pause.resumed') : t('pause.paused') });
      } else {
        setToast({ type: 'error', message: t('common.error') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setPauseSubmitting(false);
    }
  };

  return (
    <PageLayout
      backTo={`/collections/${code}`}
      backLabel={headline || t('common.collection')}
    >
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
        <Select
                language="en"
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
        <fieldset style={{ border: 'none', padding: 0, margin: 0 }}>
          <legend style={{ fontWeight: 700, fontSize: 'var(--fontsize-body-m)', marginBottom: 'var(--spacing-2-xs)', padding: 0 }}>
            {t('editCollection.modeLabel')}
          </legend>
          {MODE_OPTIONS.map((opt) => (
            <div key={opt.value} style={{ marginBottom: 'var(--spacing-xs)' }}>
              <RadioButton
                id={`edit-collection-mode-${opt.value.toLowerCase()}`}
                name="edit-collection-mode"
                value={opt.value}
                label={opt.label}
                checked={mode === opt.value}
                onChange={() => handleModeChange(opt.value)}
                aria-describedby={`edit-collection-mode-${opt.value.toLowerCase()}-desc`}
              />
              <p id={`edit-collection-mode-${opt.value.toLowerCase()}-desc`} style={{ margin: '0 0 0 var(--spacing-l)', fontSize: 'var(--fontsize-body-s)', color: 'var(--color-black-70)' }}>
                {opt.description}
              </p>
            </div>
          ))}
        </fieldset>
        <CollectionForm
          idPrefix="edit-collection"
          mode={mode}
          isSwap={isSwap}
          setIsSwap={setIsSwap}
          isShare={isShare}
          setIsShare={setIsShare}
          newsletterEnabled={newsletterEnabled}
          setNewsletterEnabled={setNewsletterEnabled}
          requireMinimumSwapItems={requireMinimumSwapItems}
          setRequireMinimumSwapItems={setRequireMinimumSwapItems}
          allowedThingTypes={allowedThingTypes}
          setAllowedThingTypes={setAllowedThingTypes}
          rentalDurations={rentalDurations}
          setRentalDurations={setRentalDurations}
          rentalWeekdays={rentalWeekdays}
          setRentalWeekdays={setRentalWeekdays}
          visibility={visibility}
          setVisibility={setVisibility}
          errors={{ ...errors, allowedThingTypes: allowedTypesError }}
          theeemeColor01={tc.color_01}
        />
        <TagInput
          tags={tags}
          onChange={setTags}
          label={t('createCollection.tagsLabel')}
          placeholder={t('createCollection.tagsPlaceholder')}
          helperText={t('createCollection.tagsHelper')}
        />
        <Select
                language="en"
          id="edit-collection-digest"
          texts={{ label: t('editCollection.digestLabel') }}
          helper={t('editCollection.digestHelper')}
          options={DIGEST_OPTIONS}
          value={digestFrequency}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setDigestFrequency(selectedOptions[0].value);
            }
          }}
        />
        <Select
          language="en"
          id="edit-collection-language"
          texts={{ label: t('collectionLanguage.label') }}
          helper={t('collectionLanguage.helper')}
          options={SUPPORTED_LANGUAGES.map((l) => ({ label: l.name, value: l.code }))}
          value={language}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setLanguage(selectedOptions[0].value);
            }
          }}
        />
        <ImageUpload
          id="edit-collection-thumbnail"
          label={t('upload.thumbnailLabel')}
          value={thumbnail}
          onChange={setThumbnail}
          currentUrl={thumbnailUrl}
          folder="oiueei/collections"
        />
        <PdfUpload
          id="edit-collection-welcome-doc"
          label={t('upload.welcomeDocLabel')}
          onChange={setWelcomeDoc}
          currentUrl={welcomeDocUrl}
          helperText={t('upload.welcomeDocHelper')}
        />
      </div>
      <div className="form-actions">
        <Button disabled={submitting} onClick={handleSubmit} style={{ ...btnStyle, width: '100%' }}>
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
        <Button variant="secondary" fullWidth disabled={submitting} onClick={() => {
          navigate(`/collections/${code}/delete`, { state: { backPath: `/collections/${code}/edit`, backLabel: headline || t('common.collection') } });
        }} style={{
          '--background-color': 'var(--color-white)',
          '--border-color': tc.color_01 ? `var(--color-${tc.color_01})` : undefined,
          '--color': tc.color_04 ? `var(--color-${tc.color_04})` : undefined,
          '--background-color-hover': tc.color_01 ? `var(--color-${tc.color_01})` : undefined,
          '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
          marginTop: 'var(--spacing-s)',
        }}>
          {t('common.delete')}
        </Button>
      </div>
      <div style={{ marginTop: 'var(--spacing-xl)', borderTop: '1px solid var(--color-black-20)', paddingTop: 'var(--spacing-m)' }}>
        <h2>{t('pause.sectionHeading')}</h2>
        <p>{t('pause.sectionHelper')}</p>
        {!isPaused && (
          <div className="form-grid">
            <TextArea
              id="pause-message"
              label={t('pause.messageLabel')}
              helperText={`${pauseMessage.length}/256 — ${t('pause.messageHelper')}`}
              value={pauseMessage}
              onChange={(e) => setPauseMessage(e.target.value)}
              maxLength={256}
            />
          </div>
        )}
        {isPaused && (
          <blockquote style={{ borderLeft: `4px solid ${tc.color_01 ? `var(--color-${tc.color_01})` : 'var(--color-black-50)'}`, paddingLeft: 'var(--spacing-m)', margin: 'var(--spacing-m) 0', fontStyle: 'italic' }}>
            {pauseMessage}
          </blockquote>
        )}
        {!isPaused && !pauseMessage.trim() && (
          <p style={{ marginTop: 'var(--spacing-s)', fontSize: 'var(--fontsize-body-s)', color: 'var(--color-black-60)' }}>
            {t('pause.messageRequiredHint')}
          </p>
        )}
        <div style={{ marginTop: 'var(--spacing-m)' }}>
          <Button
            variant="secondary"
            fullWidth
            disabled={pauseSubmitting || (!isPaused && !pauseMessage.trim())}
            onClick={handlePauseToggle}
            style={btnSecondaryStyle}
          >
            {pauseSubmitting
              ? (isPaused ? t('pause.resuming') : t('pause.pausing'))
              : (isPaused ? t('pause.resumeButton') : t('pause.pauseButton'))}
          </Button>
        </div>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
