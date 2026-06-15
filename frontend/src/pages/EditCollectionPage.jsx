import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { TextInput, TextArea, Select, Button, Koros, ToggleButton } from 'hds-react';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import ImageUpload from '../components/ImageUpload';
import TagInput from '../components/TagInput';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';

export default function EditCollectionPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');
  const [loading, setLoading] = useState(true);
  const [headline, setHeadline] = useState('');
  useEffect(() => { document.title = headline ? t('titles.editCollection', { headline }) : t('titles.editCollectionDefault'); }, [headline, t]);
  const [description, setDescription] = useState('');
  const [status, setStatus] = useState('ACTIVE');
  const [mode, setMode] = useState('PROPRIETARY');
  const [digestFrequency, setDigestFrequency] = useState('NONE');
  const [isSwap, setIsSwap] = useState(false);
  const [isShare, setIsShare] = useState(false);
  const [newsletterEnabled, setNewsletterEnabled] = useState(false);
  const [isMinimalist, setIsMinimalist] = useState(false);
  const [requireMinimumSwapItems, setRequireMinimumSwapItems] = useState(false);
  const [allowedThingTypes, setAllowedThingTypes] = useState([]);
  const [tags, setTags] = useState([]);
  const [thumbnail, setThumbnail] = useState('');
  const [thumbnailUrl, setThumbnailUrl] = useState('');
  const [pauseMessage, setPauseMessage] = useState('');
  const [isPaused, setIsPaused] = useState(false);
  const [pauseSubmitting, setPauseSubmitting] = useState(false);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const STATUS_OPTIONS = [
    { label: t('editCollection.statusActive'), value: 'ACTIVE' },
    { label: t('editCollection.statusInactive'), value: 'INACTIVE' },
  ];

  const MODE_OPTIONS = [
    { label: t('editCollection.modeProprietary'), value: 'PROPRIETARY' },
    { label: t('editCollection.modeCommunity'), value: 'COMMUNITY' },
  ];

  const DIGEST_OPTIONS = [
    { label: t('editCollection.digestNone'), value: 'NONE' },
    { label: t('editCollection.digestWeekly'), value: 'WEEKLY' },
    { label: t('editCollection.digestMonthly'), value: 'MONTHLY' },
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
          setDigestFrequency(data.digest_frequency || 'NONE');
          setIsSwap(data.is_swap || false);
          setIsShare(data.is_share || false);
          setNewsletterEnabled(data.newsletter_enabled || false);
          setIsMinimalist(data.is_minimalist || false);
          setRequireMinimumSwapItems((data.swap_minimum_items || 0) > 0);
          setAllowedThingTypes(data.allowed_thing_types || []);
          setTags(data.tags || []);
          setThumbnail(data.thumbnail || '');
          setThumbnailUrl(data.thumbnail_url || '');
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
  }, [userCode, code, navigate, t]);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('editCollection.titleRequired');
    if (headline.length > 64) newErrors.headline = t('editCollection.maxHeadline');
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
      description: description.trim(),
      status,
      mode,
      digest_frequency: digestFrequency,
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

    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(`/collections/${code}`);
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

  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--background-color': 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': tc.color_04 ? `var(--color-${tc.color_04})` : undefined,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
  } : undefined;

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
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
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
        <Select
                language="en"
          id="edit-collection-mode"
          texts={{ label: t('editCollection.modeLabel') }}
          helper={t('editCollection.modeHelper')}
          options={MODE_OPTIONS}
          value={mode}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              const newMode = selectedOptions[0].value;
              setMode(newMode);
              if (newMode !== 'COMMUNITY') { setIsSwap(false); setIsShare(false); setNewsletterEnabled(false); setIsMinimalist(false); setRequireMinimumSwapItems(false); }
              // Reset the allowlist on mode change — v1 only wires it for PROPRIETARY.
              setAllowedThingTypes([]);
            }
          }}
        />
        {mode === 'COMMUNITY' && (
          <div className="toggle-left">
            <ToggleButton
              id="edit-collection-swap"
              label={t('swap.enableSwap')}
              checked={isSwap}
              onChange={(val) => {
                const next = !val;
                setIsSwap(next);
                // Turning ON swap clears the mutually-exclusive share flag;
                // turning OFF clears the swap-specific minimum-items rule.
                if (next) { setIsShare(false); } else { setRequireMinimumSwapItems(false); }
                setAllowedThingTypes(next ? ['SWAP_THING'] : []);
              }}
              variant="inline"
              theme={tc.color_01 ? { '--toggle-button-color': `var(--color-${tc.color_01})` } : undefined}
            />
          </div>
        )}
        {mode === 'COMMUNITY' && isSwap && (
          <div className="toggle-left">
            <ToggleButton
              id="edit-collection-swap-minimum"
              label={<>{t('swap.requireMinimumLabel')}<br/><span style={{ fontSize: 'var(--fontsize-body-s)', fontWeight: 400, color: 'var(--color-black-70)' }}>{t('swap.requireMinimumHelper')}</span></>}
              checked={requireMinimumSwapItems}
              onChange={(val) => setRequireMinimumSwapItems(!val)}
              variant="inline"
              theme={tc.color_01 ? { '--toggle-button-color': `var(--color-${tc.color_01})` } : undefined}
            />
          </div>
        )}
        {mode === 'COMMUNITY' && (
          <div className="toggle-left">
            <ToggleButton
              id="edit-collection-share"
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
              theme={tc.color_01 ? { '--toggle-button-color': `var(--color-${tc.color_01})` } : undefined}
            />
          </div>
        )}
        {mode === 'COMMUNITY' && isShare && (
          <div className="toggle-left">
            <ToggleButton
              id="edit-collection-newsletter"
              label={t('newsletter.enableNewsletter')}
              checked={newsletterEnabled}
              onChange={(val) => setNewsletterEnabled(!val)}
              variant="inline"
              theme={tc.color_01 ? { '--toggle-button-color': `var(--color-${tc.color_01})` } : undefined}
            />
          </div>
        )}
        <div className="toggle-left">
          <ToggleButton
            id="edit-collection-minimalist"
            label={t('minimalist.enableMinimalist')}
            checked={isMinimalist}
            onChange={(val) => {
              const next = !val;
              setIsMinimalist(next);
              if (mode === 'PROPRIETARY') {
                setAllowedThingTypes(next ? ['GIFT_THING'] : []);
              } else {
                setAllowedThingTypes([]);
              }
            }}
            variant="inline"
            theme={tc.color_01 ? { '--toggle-button-color': `var(--color-${tc.color_01})` } : undefined}
          />
        </div>
        <div className={isLockedToSingleType ? 'multiselect-locked' : undefined}>
          <Select
            language="en"
            multiSelect
            id="edit-collection-allowed-thing-types"
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
        <ImageUpload
          id="edit-collection-thumbnail"
          label={t('upload.thumbnailLabel')}
          value={thumbnail}
          onChange={setThumbnail}
          currentUrl={thumbnailUrl}
          folder="oiueei/collections"
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
      </div>
    </div>
  );
}
