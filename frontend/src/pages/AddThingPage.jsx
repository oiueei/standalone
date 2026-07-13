import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Notification } from 'hds-react';
import { TYPE_VALUES, FEE_TYPES, DETAIL_TYPES, WISH_TYPE, SHARE_TYPE, SWAP_TYPE } from '../constants/things';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import ThingForm from '../components/ThingForm';
import BulkAddCsv from '../components/BulkAddCsv';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';
import { useLocalized, localizedCounter } from '../utils/localized';

export default function AddThingPage() {
  const { t } = useTranslation();
  // Owner content (headlines, tags) may carry one text per language.
  const L = useLocalized();
  const { code } = useParams();
  const navigate = useNavigate();
  const routerLocation = useLocation();
  // When set, this Add flow is answering a wish ("Tengo esto"): on save we link
  // the new listing back to the wish as a HAVE_THIS response.
  const respondWishCode = routerLocation.state?.respondWishCode;

  const userCode = localStorage.getItem('userCode');
  useEffect(() => { document.title = t('titles.addThing'); }, [t]);

  // Deep-link from the collection empty state: /add#bulk-add scrolls to the CSV importer.
  useEffect(() => {
    if (routerLocation.hash === '#bulk-add') {
      document.getElementById('bulk-add')?.scrollIntoView({ behavior: 'smooth' });
    }
  }, [routerLocation.hash]);

  const [collectionHeadline, setCollectionHeadline] = useState('');
  const [collectionMode, setCollectionMode] = useState('');
  const [isSwapCollection, setIsSwapCollection] = useState(false);
  const [isShareCollection, setIsShareCollection] = useState(false);
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
  const [submitAttempted, setSubmitAttempted] = useState(false);
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

  const computeErrors = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('addThing.titleRequired');
    else if (localizedCounter(headline, 64).over) newErrors.headline = t('addThing.maxHeadline');
    if (localizedCounter(description, 256).over) newErrors.description = t('addThing.maxDescription');
    if (FEE_TYPES.includes(type) && (fee === '' || fee === undefined)) {
      newErrors.fee = t('addThing.priceRequired');
    }
    if (location.length > 32) newErrors.location = t('addThing.maxLocation');
    return newErrors;
  };

  // Errors surface only after the first submit attempt, then recompute on every
  // render so fixing a field clears its error immediately (live validation).
  const errors = submitAttempted ? computeErrors() : {};

  const handleSubmit = async () => {
    setSubmitAttempted(true);
    if (Object.keys(computeErrors()).length > 0) return;
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
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('addThing.errorCreating') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  // Theeeme colors from localStorage (set by HomePage on login)
  const { tc, btnStyle } = useTheeeme();

  const typeOptions = (() => {
    // Swap-only / share-only collections accept their forced offer type plus
    // wishes (a wish coexists with the offer pool). Offer both so a member can
    // post either — except in respond mode, where a wish can't answer a wish.
    if (isSwapCollection) return respondWishCode ? [SWAP_TYPE] : [SWAP_TYPE, WISH_TYPE];
    if (isShareCollection) return respondWishCode ? [SHARE_TYPE] : [SHARE_TYPE, WISH_TYPE];
    return TYPE_VALUES.filter((v) => {
      if (v === SWAP_TYPE) return false;
      // Cannot answer a wish by offering another wish.
      if (respondWishCode && v === WISH_TYPE) return false;
      if ((v === WISH_TYPE || v === SHARE_TYPE) && collectionMode !== 'COMMUNITY') return false;
      // Per-collection allowlist (set on Create/Edit). Empty = no restriction.
      if (collectionAllowedTypes.length > 0 && !collectionAllowedTypes.includes(v)) return false;
      return true;
    });
  })().map((v) => ({ label: t('types.' + v), value: v }));

  return (
    <PageLayout
      backTo={`/collections/${code}`}
      backLabel={L(collectionHeadline) || t('common.collection')}
    >
        <h1 className="page-title-xl">{t('addThing.pageTitle')}</h1>
        {respondWishCode && (
          <Notification type="info" label={t('wishes.kind.haveThis')} style={{ marginBottom: 'var(--spacing-m)' }}>
            {t('wishes.respondingWithListing')}
          </Notification>
        )}
      <div className="form-grid">
          <ThingForm
            idPrefix="add-thing"
            theeemeColor01={tc.color_01}
            errors={errors}
            typeOptions={typeOptions}
            showTypeSelector={!((isSwapCollection || isShareCollection) && respondWishCode)}
            type={type}
            setType={setType}
            isEndless={isEndless}
            setIsEndless={setIsEndless}
            showNotifyGroup={type === WISH_TYPE && !respondWishCode}
            notifyGroup={notifyGroup}
            setNotifyGroup={setNotifyGroup}
            headline={headline}
            setHeadline={setHeadline}
            description={description}
            setDescription={setDescription}
            fee={fee}
            setFee={setFee}
            availability={availability}
            setAvailability={setAvailability}
            condition={condition}
            setCondition={setCondition}
            location={location}
            setLocation={setLocation}
            collectionTags={collectionTags}
            tags={tags}
            setTags={setTags}
            imageLabel={t('upload.thumbnailLabel')}
            thumbnail={thumbnail}
            setThumbnail={setThumbnail}
            gallery={gallery}
            setGallery={setGallery}
          />
      </div>

      <div className="form-actions">
        <Button style={{ ...btnStyle, width: '100%' }} disabled={submitting} onClick={handleSubmit}>
          {submitting ? t('common.creating') : t('common.create')}
        </Button>
      </div>

      {!respondWishCode && (
        <section id="bulk-add" className="bulk-add-section">
          <h2>{t('bulkAdd.heading')}</h2>
          <BulkAddCsv collectionCode={code} onImported={() => navigate(`/collections/${code}`)} />
        </section>
      )}

      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
