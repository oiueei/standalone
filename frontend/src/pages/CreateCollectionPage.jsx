import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import { TextInput, TextArea, Select, Button, Notification, IconInfoCircle } from 'hds-react';
import { isLockedToSingleType } from '../constants/things';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import CollectionForm from '../components/CollectionForm';
import ImageUpload from '../components/ImageUpload';
import TagInput from '../components/TagInput';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

export default function CreateCollectionPage() {
  const { t } = useTranslation();
  const navigate = useNavigate();
  useEffect(() => { document.title = t('titles.newCollection'); }, [t]);
  const location = useLocation();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.home');
  const { tc: theeemeColors } = useTheeeme();

  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [mode, setMode] = useState('PROPRIETARY');
  const [isSwap, setIsSwap] = useState(false);
  const [isShare, setIsShare] = useState(false);
  const [newsletterEnabled, setNewsletterEnabled] = useState(false);
  const [isMinimalist, setIsMinimalist] = useState(false);
  const [requireMinimumSwapItems, setRequireMinimumSwapItems] = useState(false);
  const [allowedThingTypes, setAllowedThingTypes] = useState([]);
  const [tags, setTags] = useState([]);
  const [thumbnail, setThumbnail] = useState('');
  const [errors, setErrors] = useState({});

  const MODE_OPTIONS = [
    { label: t('createCollection.modeProprietary'), value: 'PROPRIETARY' },
    { label: t('createCollection.modeCommunity'), value: 'COMMUNITY' },
  ];

  const locked = isLockedToSingleType({ mode, isSwap, isShare, isMinimalist });
  const [showModeInfo, setShowModeInfo] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('createCollection.titleRequired');
    if (headline.length > 64) newErrors.headline = t('createCollection.maxHeadline');
    // "Pick at least one" only applies when the user can pick — locked
    // selects (album, swap, share) auto-fill, so they pass by construction.
    if (!locked && allowedThingTypes.length === 0) {
      newErrors.allowedThingTypes = t('createCollection.allowedTypesAtLeastOne');
    }
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
      newsletter_enabled: newsletterEnabled && isShare && mode === 'COMMUNITY',
      is_minimalist: isMinimalist,
      swap_minimum_items:
        requireMinimumSwapItems && isSwap && mode === 'COMMUNITY' ? 3 : 0,
      allowed_thing_types: allowedThingTypes,
      tags,
      thumbnail: thumbnail || '',
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
            helperText={`${headline.length}/64`}
          />
          <TextArea
            id="create-collection-description"
            label={t('createCollection.descriptionLabel')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            helperText={`${description.length}/256`}
          />
          <div>
            <div style={{ display: 'flex', alignItems: 'center', gap: 'var(--spacing-xs)', marginBottom: 'var(--spacing-2-xs)' }}>
              <span style={{ fontWeight: 700, fontSize: 'var(--fontsize-body-m)' }}>
                {t('createCollection.modeLabel')}
              </span>
              <button
                type="button"
                onClick={() => setShowModeInfo((v) => !v)}
                style={{ background: 'none', border: 'none', cursor: 'pointer', display: 'inline-flex', alignItems: 'center', gap: 'var(--spacing-2-xs)', padding: 0, color: theeemeColors.color_01 ? `var(--color-${theeemeColors.color_01})` : 'var(--color-bus)', fontSize: 'var(--fontsize-body-s)', whiteSpace: 'nowrap' }}
                aria-expanded={showModeInfo}
              >
                <IconInfoCircle size="small" aria-hidden />
                {t('createCollection.modeInfoLabel')}
              </button>
            </div>
            <Select
              language="en"
              id="create-collection-mode"
              texts={{ label: '' }}
              aria-label={t('createCollection.modeLabel')}
              options={MODE_OPTIONS}
              value={mode}
              onChange={(selectedOptions) => {
                if (selectedOptions.length > 0) {
                  const newMode = selectedOptions[0].value;
                  setMode(newMode);
                  if (newMode !== 'COMMUNITY') { setIsSwap(false); setIsShare(false); setNewsletterEnabled(false); setIsMinimalist(false); }
                  // Reset the allowlist on mode change — v1 only wires it for PROPRIETARY.
                  setAllowedThingTypes([]);
                }
              }}
            />
            {showModeInfo && (
              <Notification
                type="info"
                dismissible
                closeButtonLabelText={t('common.close')}
                onClose={() => setShowModeInfo(false)}
                style={{ marginTop: 'var(--spacing-2-xs)' }}
              >
                <Trans i18nKey="createCollection.modeInfoText" components={{ bold: <strong /> }} />
              </Notification>
            )}
          </div>
          <CollectionForm
            idPrefix="create-collection"
            mode={mode}
            isSwap={isSwap}
            setIsSwap={setIsSwap}
            isShare={isShare}
            setIsShare={setIsShare}
            newsletterEnabled={newsletterEnabled}
            setNewsletterEnabled={setNewsletterEnabled}
            isMinimalist={isMinimalist}
            setIsMinimalist={setIsMinimalist}
            requireMinimumSwapItems={requireMinimumSwapItems}
            setRequireMinimumSwapItems={setRequireMinimumSwapItems}
            allowedThingTypes={allowedThingTypes}
            setAllowedThingTypes={setAllowedThingTypes}
            errors={errors}
            theeemeColor01={theeemeColors.color_01}
          />
          <TagInput
            tags={tags}
            onChange={setTags}
            label={t('createCollection.tagsLabel')}
            placeholder={t('createCollection.tagsPlaceholder')}
            helperText={t('createCollection.tagsHelper')}
          />
          <ImageUpload
            id="create-collection-thumbnail"
            label={t('upload.thumbnailLabel')}
            value={thumbnail}
            onChange={setThumbnail}
            folder="oiueei/collections"
          />
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
    </PageLayout>
  );
}
