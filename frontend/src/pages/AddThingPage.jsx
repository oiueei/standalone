import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Select,
  TextInput,
  TextArea,
  NumberInput,
  Button,
  Notification,
  ToggleButton,
} from 'hds-react';
import { TYPE_VALUES, FEE_TYPES, DETAIL_TYPES, WISH_TYPE, SHARE_TYPE, SWAP_TYPE, AVAILABILITY_VALUES, CONDITION_VALUES } from '../constants/things';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import Toast from '../components/Toast';
import ImageUpload from '../components/ImageUpload';
import GalleryUpload from '../components/GalleryUpload';
import DocumentUpload from '../components/DocumentUpload';
import useTheeeme from '../hooks/useTheeeme';

export default function AddThingPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const navigate = useNavigate();
  const routerLocation = useLocation();
  // When set, this Add flow is answering a wish ("Tengo esto"): on save we link
  // the new listing back to the wish as a HAVE_THIS response.
  const respondWishCode = routerLocation.state?.respondWishCode;

  const userCode = localStorage.getItem('userCode');
  useEffect(() => { document.title = t('titles.addThing'); }, [t]);

  const [collectionHeadline, setCollectionHeadline] = useState('');
  const [collectionMode, setCollectionMode] = useState('');
  const [isSwapCollection, setIsSwapCollection] = useState(false);
  const [isShareCollection, setIsShareCollection] = useState(false);
  const [isMinimalistCollection, setIsMinimalistCollection] = useState(false);
  const [type, setType] = useState('GIFT_THING');
  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [fee, setFee] = useState('');
  const [availability, setAvailability] = useState('');
  const [location, setLocation] = useState('');
  const [condition, setCondition] = useState('');
  const [isEndless, setIsEndless] = useState(false);
  const [notifyGroup, setNotifyGroup] = useState(true);
  const [gallery, setGallery] = useState([]);
  const [documents, setDocuments] = useState([]);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  const [collectionAllowedTypes, setCollectionAllowedTypes] = useState([]);
  const [collectionTags, setCollectionTags] = useState([]);
  const [tags, setTags] = useState([]);

  useEffect(() => {
    if (!userCode) return;
    apiFetch(`/api/v1/collections/${code}/`)
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => {
        setCollectionHeadline(data.headline || '');
        setCollectionMode(data.mode || '');
        if (data.is_swap) {
          setIsSwapCollection(true);
          setType('SWAP_THING');
        }
        if (data.is_share) {
          setIsShareCollection(true);
          setType('SHARE_THING');
        }
        if (data.is_minimalist) {
          setIsMinimalistCollection(true);
        }
        const allowed = data.allowed_thing_types || [];
        setCollectionAllowedTypes(allowed);
        setCollectionTags(data.tags || []);
        // If the allowlist names a single type, pre-select it so the form
        // immediately shows the right downstream fields.
        if (allowed.length === 1) {
          setType(allowed[0]);
        }
      })
      .catch(() => {});
  }, [userCode, code]);

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('addThing.titleRequired');
    if (headline.length > 64) newErrors.headline = t('addThing.maxHeadline');
    if (FEE_TYPES.includes(type) && (fee === '' || fee === undefined)) {
      newErrors.fee = t('addThing.priceRequired');
    }
    if (location.length > 32) newErrors.location = t('addThing.maxLocation');
    setErrors(newErrors);
    return Object.keys(newErrors).length === 0;
  };

  const handleSubmit = async () => {
    if (!validate()) return;
    setSubmitting(true);
    setToast(null);

    const body = {
      type,
      headline: headline.trim(),
      collection_code: code,
    };
    if (thumbnail) body.thumbnail = thumbnail;
    if (description.trim()) body.description = description.trim();
    if (FEE_TYPES.includes(type) && fee !== '') {
      body.fee = fee;
    }
    if (DETAIL_TYPES.includes(type)) {
      if (availability) body.availability = availability;
      if (location.trim()) body.location = location.trim();
      if (condition) body.condition = condition;
    }
    if (documents.length > 0) {
      body.documents = documents;
    }
    if (gallery.length > 0) {
      body.gallery = gallery.map((g) => g.publicId);
    }
    if (tags.length > 0) {
      body.tags = tags;
    }
    if (['GIFT_THING', 'SELL_THING'].includes(type) && isEndless) {
      body.is_endless = true;
    }
    if (type === WISH_TYPE && !respondWishCode) {
      body.notify_group = notifyGroup;
    }

    try {
      const res = await apiFetch('/api/v1/things/', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        if (respondWishCode) {
          // Link the new listing to the wish as a "Tengo esto" answer.
          const created = await res.json();
          const linkRes = await apiFetch(`/api/v1/things/${respondWishCode}/responses/`, {
            method: 'POST',
            body: JSON.stringify({ kind: 'HAVE_THIS', thing_code: created.code }),
          });
          if (!linkRes.ok) {
            setToast({ type: 'error', message: t('wishes.errorResponding') });
            return;
          }
          navigate(routerLocation.state?.backPath || `/collections/${code}`);
        } else {
          navigate(`/collections/${code}`);
        }
      } else {
        setToast({ type: 'error', message: t('addThing.errorCreating') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  // Theeeme colors from localStorage (set by HomePage on login)
  const { tc, btnStyle } = useTheeeme();

  return (
    <PageLayout
      backTo={`/collections/${code}`}
      backLabel={collectionHeadline || t('common.collection')}
    >
        <h1 className="page-title-xl">{t('addThing.pageTitle')}</h1>
        {respondWishCode && (
          <Notification type="info" label={t('wishes.kind.haveThis')} style={{ marginBottom: 'var(--spacing-m)' }}>
            {t('wishes.respondingWithListing')}
          </Notification>
        )}
      <div className="form-grid">
          {!isSwapCollection && !isShareCollection && (
            <Select
                language="en"
              id="add-thing-type"
              texts={{ label: t('addThing.typeLabel') }}
              options={TYPE_VALUES.filter(v => {
                if (v === SWAP_TYPE) return false;
                // Cannot answer a wish by offering another wish.
                if (respondWishCode && v === WISH_TYPE) return false;
                if ((v === WISH_TYPE || v === SHARE_TYPE) && collectionMode !== 'COMMUNITY') return false;
                if (isMinimalistCollection && !['GIFT_THING', SHARE_TYPE, SWAP_TYPE].includes(v)) return false;
                // Per-collection allowlist (set on Create/Edit). Empty = no restriction.
                if (collectionAllowedTypes.length > 0 && !collectionAllowedTypes.includes(v)) return false;
                return true;
              }).map(v => ({ label: t('types.' + v), value: v }))}
              value={type}
              onChange={(selectedOptions) => {
                if (selectedOptions.length > 0) {
                  setType(selectedOptions[0].value);
                }
              }}
            />
          )}
          {['GIFT_THING', 'SELL_THING'].includes(type) && (
            <div className="toggle-left">
              <ToggleButton
                id="add-thing-is-endless"
                label={t('endless.label')}
                checked={isEndless}
                onChange={(val) => setIsEndless(!val)}
                variant="inline"
                theme={tc.color_01 ? { '--toggle-button-color': `var(--color-${tc.color_01})` } : undefined}
              />
            </div>
          )}
          {type === WISH_TYPE && !respondWishCode && (
            <div className="toggle-left">
              <ToggleButton
                id="add-thing-notify-group"
                label={t('wishes.notifyGroup')}
                checked={notifyGroup}
                onChange={(val) => setNotifyGroup(!val)}
                variant="inline"
                theme={tc.color_01 ? { '--toggle-button-color': `var(--color-${tc.color_01})` } : undefined}
              />
            </div>
          )}
          <TextInput
            id="add-thing-headline"
            label={t('addThing.titleLabel')}
            value={headline}
            onChange={(e) => setHeadline(e.target.value)}
            required
            invalid={!!errors.headline}
            errorText={errors.headline}
            helperText={`${headline.length}/64`}
          />
          <TextArea
            id="add-thing-description"
            label={t('addThing.descriptionLabel')}
            value={description}
            onChange={(e) => setDescription(e.target.value)}
            helperText={`${description.length}/256`}
          />
          {FEE_TYPES.includes(type) && !isMinimalistCollection && (
            <NumberInput
              id="add-thing-fee"
              label={t('addThing.priceLabel')}
              value={fee === '' ? '' : Number(fee)}
              onChange={(e) => setFee(e.target.value)}
              min={0}
              unit="EUR"
              required
              invalid={!!errors.fee}
              errorText={errors.fee}
            />
          )}
          {FEE_TYPES.includes(type) && DETAIL_TYPES.includes(type) && !isMinimalistCollection && (
            <div className="spacer-xxxx" />
          )}
          {DETAIL_TYPES.includes(type) && !isMinimalistCollection && (
            <>
              <Select
                language="en"
                id="add-thing-availability"
                texts={{ label: t('addThing.availabilityLabel') }}
                options={AVAILABILITY_VALUES.map(v => ({ label: t('availability.' + v), value: v }))}
                value={availability}
                onChange={(sel) => setAvailability(sel.length > 0 ? sel[0].value : '')}
                clearable
              />
              <Select
                language="en"
                id="add-thing-condition"
                texts={{ label: t('addThing.conditionLabel') }}
                options={CONDITION_VALUES.map(v => ({ label: t('condition.' + v), value: v }))}
                value={condition}
                onChange={(sel) => setCondition(sel.length > 0 ? sel[0].value : '')}
                clearable
              />
              <TextInput
                id="add-thing-location"
                label={t('addThing.locationLabel')}
                value={location}
                onChange={(e) => setLocation(e.target.value)}
                helperText={`${location.length}/32`}
                invalid={!!errors.location}
                errorText={errors.location}
              />
            </>
          )}
          {collectionTags.length > 0 && (
            <Select
              language="en"
              multiSelect
              id="add-thing-tags"
              texts={{
                label: t('addThing.tagsLabel'),
                placeholder: t('addThing.tagsPlaceholder'),
                assistive: t('addThing.tagsHelper'),
              }}
              options={collectionTags.map((tg) => ({ label: tg, value: tg }))}
              value={tags.map((tg) => ({ label: tg, value: tg }))}
              onChange={(opts) => setTags(opts.map((o) => o.value))}
            />
          )}
          <ImageUpload
            id="add-thing-thumbnail"
            label={isMinimalistCollection ? t('minimalist.photoRequired') : t('upload.thumbnailLabel')}
            value={thumbnail}
            onChange={setThumbnail}
            folder="oiueei/things"
          />
          {!isMinimalistCollection && (
            <GalleryUpload items={gallery} onChange={setGallery} />
          )}
          {!isMinimalistCollection && (
            <DocumentUpload
              documents={documents}
              onChange={setDocuments}
            />
          )}
      </div>

      <div className="form-actions">
        <Button style={{ ...btnStyle, width: '100%' }} disabled={submitting} onClick={handleSubmit}>
          {submitting ? t('common.creating') : t('common.create')}
        </Button>
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
