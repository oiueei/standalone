import { useEffect, useState } from 'react';
import { useNavigate, useLocation } from 'react-router-dom';
import { useTranslation, Trans } from 'react-i18next';
import { TextInput, TextArea, Select, Button, Notification, IconInfoCircle, ToggleButton } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
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

  // Type lists per mode/album combination. SWAP_THING is excluded everywhere
  // because it requires `is_swap=True`, which forces the value via its flag.
  const PROPRIETARY_TYPES = [
    'GIFT_THING', 'SELL_THING', 'ORDER_THING', 'RENT_THING',
    'LEND_THING',
  ];
  const COMMUNITY_TYPES = [
    'GIFT_THING', 'SELL_THING', 'ORDER_THING', 'RENT_THING', 'LEND_THING',
    'SHARE_THING', 'WISH_THING',
  ];
  const COMMUNITY_MINIMALIST_TYPES = ['GIFT_THING', 'SHARE_THING'];

  // is_swap, is_share and PROPRIETARY+album force a single type via their
  // flag — the multi-select still renders, but locked and pre-filled, same
  // visual pattern as PROPRIETARY+album (commit be9d789).
  const isLockedToSingleType = (
    (mode === 'PROPRIETARY' && isMinimalist)
    || (mode === 'COMMUNITY' && (isSwap || isShare))
  );
  const ALLOWED_TYPES_OPTIONS = (() => {
    if (mode === 'PROPRIETARY') {
      return isMinimalist
        ? [{ label: t('types.GIFT_THING'), value: 'GIFT_THING' }]
        : PROPRIETARY_TYPES.map((v) => ({ label: t('types.' + v), value: v }));
    }
    if (isSwap) return [{ label: t('types.SWAP_THING'), value: 'SWAP_THING' }];
    if (isShare) return [{ label: t('types.SHARE_THING'), value: 'SHARE_THING' }];
    const list = isMinimalist ? COMMUNITY_MINIMALIST_TYPES : COMMUNITY_TYPES;
    return list.map((v) => ({ label: t('types.' + v), value: v }));
  })();
  const [showModeInfo, setShowModeInfo] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('createCollection.titleRequired');
    if (headline.length > 64) newErrors.headline = t('createCollection.maxHeadline');
    // "Pick at least one" only applies when the user can pick — locked
    // selects (album, swap, share) auto-fill, so they pass by construction.
    if (!isLockedToSingleType && allowedThingTypes.length === 0) {
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
          {mode === 'COMMUNITY' && (
            <div className="toggle-left">
              <ToggleButton
                id="create-collection-swap"
                label={t('swap.enableSwap')}
                checked={isSwap}
                onChange={(val) => {
                  const next = !val;
                  setIsSwap(next);
                  // Turning ON swap clears the mutually-exclusive share flag;
                  // turning OFF clears the swap-specific minimum-items rule.
                  if (next) { setIsShare(false); } else { setRequireMinimumSwapItems(false); }
                  // is_swap forces the type — auto-fill SWAP_THING so the
                  // locked select shows it. Toggling off resets so the user
                  // re-picks from the wider community set.
                  setAllowedThingTypes(next ? ['SWAP_THING'] : []);
                }}
                variant="inline"
                theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
              />
            </div>
          )}
          {mode === 'COMMUNITY' && isSwap && (
            <div className="toggle-left">
              <ToggleButton
                id="create-collection-swap-minimum"
                label={<>{t('swap.requireMinimumLabel')}<br/><span style={{ fontSize: 'var(--fontsize-body-s)', fontWeight: 400, color: 'var(--color-black-70)' }}>{t('swap.requireMinimumHelper')}</span></>}
                checked={requireMinimumSwapItems}
                onChange={(val) => setRequireMinimumSwapItems(!val)}
                variant="inline"
                theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
              />
            </div>
          )}
          {mode === 'COMMUNITY' && (
            <div className="toggle-left">
              <ToggleButton
                id="create-collection-share"
                label={t('share.enableShare')}
                checked={isShare}
                onChange={(val) => {
                  const next = !val;
                  setIsShare(next);
                  // Turning ON share clears the mutually-exclusive swap flag;
                  // turning OFF clears the share-only newsletter setting.
                  if (next) setIsSwap(false); else setNewsletterEnabled(false);
                  setAllowedThingTypes(next ? ['SHARE_THING'] : []);
                }}
                variant="inline"
                theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
              />
            </div>
          )}
          {mode === 'COMMUNITY' && isShare && (
            <div className="toggle-left">
              <ToggleButton
                id="create-collection-newsletter"
                label={t('newsletter.enableNewsletter')}
                checked={newsletterEnabled}
                onChange={(val) => setNewsletterEnabled(!val)}
                variant="inline"
                theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
              />
            </div>
          )}
          <div className="toggle-left">
            <ToggleButton
              id="create-collection-minimalist"
              label={t('minimalist.enableMinimalist')}
              checked={isMinimalist}
              onChange={(val) => {
                const next = !val;
                setIsMinimalist(next);
                // PROPRIETARY+album → only GIFT_THING is valid, auto-fill it
                // and lock the input. COMMUNITY+album narrows the list to
                // [GIFT, SHARE] but leaves selection to the user — reset so
                // they explicitly pick from the new (smaller) set.
                if (mode === 'PROPRIETARY') {
                  setAllowedThingTypes(next ? ['GIFT_THING'] : []);
                } else {
                  setAllowedThingTypes([]);
                }
              }}
              variant="inline"
              theme={theeemeColors.color_01 ? { '--toggle-button-color': `var(--color-${theeemeColors.color_01})` } : undefined}
            />
          </div>
          <div className={isLockedToSingleType ? 'multiselect-locked' : undefined}>
            <Select
              language="en"
              multiSelect
              id="create-collection-allowed-thing-types"
              texts={{
                label: t('createCollection.allowedTypesLabel'),
                placeholder: t('createCollection.allowedTypesPlaceholder'),
                assistive: (() => {
                  if (mode === 'PROPRIETARY' && isMinimalist) return t('createCollection.allowedTypesAlbumHelper');
                  if (mode === 'COMMUNITY' && isSwap) return t('createCollection.allowedTypesSwapHelper');
                  if (mode === 'COMMUNITY' && isShare) return t('createCollection.allowedTypesShareHelper');
                  return t('createCollection.allowedTypesHelper');
                })(),
                error: errors.allowedThingTypes,
              }}
              options={ALLOWED_TYPES_OPTIONS}
              value={allowedThingTypes.map((v) => ({
                label: t('types.' + v),
                value: v,
              }))}
              onChange={(opts) => setAllowedThingTypes(opts.map((o) => o.value))}
              disabled={isLockedToSingleType}
              invalid={!!errors.allowedThingTypes}
            />
          </div>
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
