import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button } from 'hds-react';
import { TYPE_VALUES, FEE_TYPES, DETAIL_TYPES } from '../constants/things';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import ThingForm from '../components/ThingForm';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

export default function EditThingPage() {
  const { t } = useTranslation();
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');
  const { tc, btnStyle, btnSecondaryStyle } = useTheeeme();

  const [loading, setLoading] = useState(true);
  const [thingType, setThingType] = useState('');
  const [headline, setHeadline] = useState('');
  useEffect(() => { document.title = headline ? t('titles.editThing', { headline }) : t('titles.editThingDefault'); }, [headline, t]);
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [thumbnailUrl, setThumbnailUrl] = useState('');
  const [fee, setFee] = useState('');
  const [availability, setAvailability] = useState('');
  const [location, setLocation] = useState('');
  const [condition, setCondition] = useState('');
  const [isEndless, setIsEndless] = useState(false);
  const [gallery, setGallery] = useState([]);
  const [tags, setTags] = useState([]);
  const [collectionTags, setCollectionTags] = useState([]);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const [thingCollectionCode, setThingCollectionCode] = useState(code || '');
  const [thingCollectionHeadline, setThingCollectionHeadline] = useState('');

  useEffect(() => {
    const fetchThing = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/`);
        if (res.ok) {
          const data = await res.json();
          setThingType(data.type);
          setHeadline(data.headline || '');
          setDescription(data.description || '');
          setThumbnail(data.thumbnail || '');
          setThumbnailUrl(data.thumbnail_url || '');
          setFee(data.fee != null ? data.fee : '');
          setAvailability(data.availability || '');
          setLocation(data.location || '');
          setCondition(data.condition || '');
          if (data.gallery && data.gallery.length) {
            const urls = data.gallery_urls || [];
            setGallery(data.gallery.map((publicId, i) => ({ publicId, url: urls[i] })));
          }
          if (data.tags) setTags(data.tags);
          if (data.collection_tags) setCollectionTags(data.collection_tags);
          if (data.is_endless) setIsEndless(true);
          if (!code && data.collection_code) setThingCollectionCode(data.collection_code);
          if (data.collection_headline) setThingCollectionHeadline(data.collection_headline);
        } else {
          setToast({ type: 'error', message: t('editThing.errorLoading') });
        }
      } catch {
        setToast({ type: 'error', message: t('common.connectionError') });
      } finally {
        setLoading(false);
      }
    };
    fetchThing();
  }, [userCode, thingCode, navigate, code, t]);

  const returnPath = thingCollectionCode ? `/collections/${thingCollectionCode}` : '/';
  const returnLabel = thingCollectionHeadline || (thingCollectionCode ? t('common.collection') : t('common.home'));

  const validate = () => {
    const newErrors = {};
    if (!headline.trim()) newErrors.headline = t('addThing.titleRequired');
    if (headline.length > 64) newErrors.headline = t('addThing.maxHeadline');
    if (FEE_TYPES.includes(thingType) && (fee === '' || fee === undefined)) {
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

    const body = { type: thingType, headline: headline.trim() };
    body.description = description.trim() || '';
    body.thumbnail = thumbnail || '';
    if (FEE_TYPES.includes(thingType) && fee !== '') {
      body.fee = fee;
    }
    if (DETAIL_TYPES.includes(thingType)) {
      body.availability = availability || '';
      body.location = location.trim();
      body.condition = condition || '';
    }
    body.gallery = gallery.map((g) => g.publicId);
    body.tags = tags;
    if (['GIFT_THING', 'SELL_THING'].includes(thingType)) {
      body.is_endless = isEndless;
    }

    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(returnPath);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('editThing.errorSaving') });
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

  const typeOptions = TYPE_VALUES.map((v) => ({ label: t('types.' + v), value: v }));

  return (
    <PageLayout backTo={returnPath} backLabel={returnLabel}>
        <h1 className="page-title-xl">{t('editThing.pageTitle')}</h1>
      <div className="form-grid">
        <ThingForm
          idPrefix="edit-thing"
          theeemeColor01={tc.color_01}
          errors={errors}
          typeOptions={typeOptions}
          type={thingType}
          setType={setThingType}
          isEndless={isEndless}
          setIsEndless={setIsEndless}
          headline={headline}
          setHeadline={setHeadline}
          description={description}
          setDescription={setDescription}
          fee={fee}
          setFee={setFee}
          feeStep={0.01}
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
          thumbnailUrl={thumbnailUrl}
          gallery={gallery}
          setGallery={setGallery}
        />
      </div>
      <div className="form-actions">
        <Button fullWidth disabled={submitting} onClick={handleSubmit} style={btnStyle}>
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
        <Button variant="secondary" fullWidth disabled={submitting} onClick={() => {
          const deletePath = thingCollectionCode
            ? `/collections/${thingCollectionCode}/things/${thingCode}/delete`
            : `/things/${thingCode}/delete`;
          navigate(deletePath, { state: { backPath: returnPath, backLabel: returnLabel } });
        }} style={{ ...btnSecondaryStyle, marginTop: 'var(--spacing-s)' }}>
          {t('common.delete')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
