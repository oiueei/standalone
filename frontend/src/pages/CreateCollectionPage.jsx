import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Select, Button, RadioButton } from 'hds-react';
import { isLockedToSingleType, reconcileAllowedTypes } from '../constants/things';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import CollectionForm from '../components/CollectionForm';
import ImageUpload from '../components/ImageUpload';
import PdfUpload from '../components/PdfUpload';
import { SUPPORTED_LANGUAGES } from '../i18n';
import TagInput from '../components/TagInput';
import LocalizedInfo from '../components/LocalizedInfo';
import { localizedCounter } from '../utils/localized';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

export default function CreateCollectionPage() {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  useEffect(() => { document.title = t('titles.newCollection'); }, [t]);
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.home');
  const { tc: theeemeColors, btnStyle } = useTheeeme();

  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [mode, setMode] = useState('PROPRIETARY');
  const [visibility, setVisibility] = useState('PRIVATE');
  const [isSwap, setIsSwap] = useState(false);
  const [isShare, setIsShare] = useState(false);
  const [newsletterEnabled, setNewsletterEnabled] = useState(false);
  const [requireMinimumSwapItems, setRequireMinimumSwapItems] = useState(false);
  const [allowedThingTypes, setAllowedThingTypes] = useState([]);
  const [rentalDurations, setRentalDurations] = useState([]);
  const [rentalWeekdays, setRentalWeekdays] = useState([]);
  const [tags, setTags] = useState([]);
  const [thumbnail, setThumbnail] = useState('');
  // The group's email language. Defaults to whatever the owner is reading the app
  // in; each member's own preference still wins over it.
  const [language, setLanguage] = useState(i18n.resolvedLanguage || i18n.language);
  const [welcomeDoc, setWelcomeDoc] = useState('');
  const [errors, setErrors] = useState({});

  const MODE_OPTIONS = [
    { label: t('createCollection.modeProprietary'), description: t('createCollection.modeProprietaryDesc'), value: 'PROPRIETARY' },
    { label: t('createCollection.modeCommunity'), description: t('createCollection.modeCommunityDesc'), value: 'COMMUNITY' },
  ];

  const locked = isLockedToSingleType({ isSwap, isShare });
  const [submitting, setSubmitting] = useState(false);
  const [submitAttempted, setSubmitAttempted] = useState(false);
  const [toast, setToast] = useState(null);

  // Live "pick at least one" feedback once a submit has been attempted (P1-5):
  // the error clears the moment the user picks a type, without nagging earlier.
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
    // Visibility follows the mode default on create: a community is born public,
    // a proprietary list private. The owner can still flip the toggle afterwards.
    setVisibility(newMode === 'COMMUNITY' ? 'PUBLIC' : 'PRIVATE');
    if (newMode !== 'COMMUNITY') { setIsSwap(false); setIsShare(false); setNewsletterEnabled(false); }
    // Keep the still-valid part of the selection instead of wiping it (P1-5).
    setAllowedThingTypes((prev) => reconcileAllowedTypes(prev, nextFlags));
  };

  const validate = () => {
    setSubmitAttempted(true);
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('createCollection.titleRequired');
    if (localizedCounter(headline, 64).over) newErrors.headline = t('createCollection.maxHeadline');
    if (localizedCounter(description, 256).over) newErrors.description = t('createCollection.maxDescription');
    setErrors(newErrors);
    // Locked selects (swap, share) auto-fill, so they pass by construction.
    const allowedTypesOk = locked || allowedThingTypes.length > 0;
    return Object.keys(newErrors).length === 0 && allowedTypesOk;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = {
      headline: headline.trim(),
      mode,
      visibility,
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
    if (description.trim()) body.description = description.trim();
    try {
      const res = await apiFetch('/api/v1/collections/', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        const data = await res.json();
        navigate(`/collections/${data.code}`);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('createCollection.errorCreating') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  return (
    <PageLayout backTo={backPath} backLabel={backLabel}>
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
            helperText={localizedCounter(headline, 64).text}
          />
          <TextArea
            id="create-collection-description"
            label={t('createCollection.descriptionLabel')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            invalid={!!errors.description}
            errorText={errors.description}
            helperText={localizedCounter(description, 256).text}
          />
          <LocalizedInfo id="create-collection-localized-info" />
          <fieldset style={{ border: 'none', padding: 0, margin: 0 }}>
            <legend style={{ fontWeight: 700, fontSize: 'var(--fontsize-body-m)', marginBottom: 'var(--spacing-2-xs)', padding: 0 }}>
              {t('createCollection.modeLabel')}
            </legend>
            {MODE_OPTIONS.map((opt) => (
              <div key={opt.value} style={{ marginBottom: 'var(--spacing-xs)' }}>
                <RadioButton
                  id={`create-collection-mode-${opt.value.toLowerCase()}`}
                  name="create-collection-mode"
                  value={opt.value}
                  label={opt.label}
                  checked={mode === opt.value}
                  onChange={() => handleModeChange(opt.value)}
                  aria-describedby={`create-collection-mode-${opt.value.toLowerCase()}-desc`}
                />
                <p id={`create-collection-mode-${opt.value.toLowerCase()}-desc`} style={{ margin: '0 0 0 var(--spacing-l)', fontSize: 'var(--fontsize-body-s)', color: 'var(--color-black-70)' }}>
                  {opt.description}
                </p>
              </div>
            ))}
          </fieldset>
          <CollectionForm
            idPrefix="create-collection"
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
            theeemeColor01={theeemeColors.color_01}
          />
          <div>
            <TagInput
              tags={tags}
              onChange={setTags}
              label={t('createCollection.tagsLabel')}
              placeholder={t('createCollection.tagsPlaceholder')}
              helperText={t('createCollection.tagsHelper')}
            />
            <LocalizedInfo id="create-collection-tags-info" variant="tags" />
          </div>
          <Select
            language="en"
            id="create-collection-language"
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
            id="create-collection-thumbnail"
            label={t('upload.thumbnailLabel')}
            value={thumbnail}
            onChange={setThumbnail}
            folder="oiueei/collections"
          />
          <PdfUpload
            id="create-collection-welcome-doc"
            label={t('upload.welcomeDocLabel')}
            onChange={setWelcomeDoc}
            helperText={t('upload.welcomeDocHelper')}
          />
        </div>
        <div className="form-actions">
          <Button
            fullWidth
            disabled={submitting}
            onClick={handleSubmit}
            style={btnStyle}
          >
            {submitting ? t('common.creating') : t('common.create')}
          </Button>
        </div>
        <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
