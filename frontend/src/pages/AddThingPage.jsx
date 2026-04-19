import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Select,
  TextInput,
  TextArea,
  NumberInput,
  Button,
  Koros,
} from 'hds-react';
import { TYPE_VALUES, FEE_TYPES, DETAIL_TYPES, EVENT_TYPE, WISH_TYPE, SHARE_TYPE, ASSET_TYPE, AVAILABILITY_VALUES, CONDITION_VALUES } from '../constants/things';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';
import ImageUpload from '../components/ImageUpload';

export default function AddThingPage() {
  const { t } = useTranslation();
  const { code } = useParams();
  const navigate = useNavigate();

  const userCode = localStorage.getItem('userCode');
  useEffect(() => { document.title = t('titles.addThing'); }, [t]);

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
    }
  }, [userCode, navigate]);

  const [collectionHeadline, setCollectionHeadline] = useState('');
  const [collectionMode, setCollectionMode] = useState('');
  const [type, setType] = useState('GIFT_THING');
  const [headline, setHeadline] = useState('');
  const [description, setDescription] = useState('');
  const [thumbnail, setThumbnail] = useState('');
  const [fee, setFee] = useState('');
  const [availability, setAvailability] = useState('');
  const [location, setLocation] = useState('');
  const [condition, setCondition] = useState('');
  const [eventDate, setEventDate] = useState('');
  const [bookingUnit, setBookingUnit] = useState('DAY');
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);

  useEffect(() => {
    if (!userCode) return;
    apiFetch(`/api/v1/collections/${code}/`)
      .then((res) => (res.ok ? res.json() : {}))
      .then((data) => {
        setCollectionHeadline(data.headline || '');
        setCollectionMode(data.mode || '');
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
    if (type === EVENT_TYPE && eventDate) {
      body.event_date = new Date(eventDate).toISOString();
    }
    if (type === ASSET_TYPE) {
      body.booking_unit = bookingUnit;
    }

    try {
      const res = await apiFetch('/api/v1/things/', {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(`/collections/${code}`);
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
  const tc = (() => {
    try { return JSON.parse(localStorage.getItem('theeemeColors')) || {}; } catch { return {}; }
  })();
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <BackLink to={`/collections/${code}`} label={collectionHeadline || t('common.collection')} />
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <h1 className="page-title-xl">{t('addThing.pageTitle')}</h1>
      <div className="form-grid">
          <Select
            id="add-thing-type"
            texts={{ label: t('addThing.typeLabel') }}
            options={TYPE_VALUES.filter(v => (v !== WISH_TYPE && v !== SHARE_TYPE) || collectionMode === 'COMMUNITY').map(v => ({ label: t('types.' + v), value: v }))}
            value={type}
            onChange={(selectedOptions) => {
              if (selectedOptions.length > 0) {
                setType(selectedOptions[0].value);
              }
            }}
          />
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
          {type === EVENT_TYPE && (
            <TextInput
              id="add-thing-event-date"
              label={t('events.eventDate')}
              type="datetime-local"
              value={eventDate}
              onChange={(e) => setEventDate(e.target.value)}
            />
          )}
          {type === ASSET_TYPE && (
            <Select
              id="add-thing-booking-unit"
              texts={{ label: t('asset.bookingUnit') }}
              options={[
                { label: t('asset.unitDay'), value: 'DAY' },
                { label: t('asset.unitHour'), value: 'HOUR' },
              ]}
              value={bookingUnit}
              onChange={(sel) => sel.length > 0 && setBookingUnit(sel[0].value)}
            />
          )}
          {FEE_TYPES.includes(type) && (
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
          {FEE_TYPES.includes(type) && DETAIL_TYPES.includes(type) && (
            <div className="spacer-xxxx" />
          )}
          {DETAIL_TYPES.includes(type) && (
            <>
              <Select
                id="add-thing-availability"
                texts={{ label: t('addThing.availabilityLabel') }}
                options={AVAILABILITY_VALUES.map(v => ({ label: t('availability.' + v), value: v }))}
                value={availability}
                onChange={(sel) => setAvailability(sel.length > 0 ? sel[0].value : '')}
                clearable
              />
              <Select
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
          <ImageUpload
            id="add-thing-thumbnail"
            label={t('upload.thumbnailLabel')}
            value={thumbnail}
            onChange={setThumbnail}
            folder="oiueei/things"
          />
      </div>

      <div className="form-actions">
        <Button style={{ ...btnStyle, width: '100%' }} disabled={submitting} onClick={handleSubmit}>
          {submitting ? t('common.creating') : t('common.create')}
        </Button>
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
