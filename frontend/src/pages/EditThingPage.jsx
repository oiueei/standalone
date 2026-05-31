import { useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Select,
  TextInput,
  TextArea,
  NumberInput,
  Button,
  DateInput,
  Koros,
  ToggleButton,
} from 'hds-react';
import { TYPE_VALUES, FEE_TYPES, DETAIL_TYPES, EVENT_TYPE, ASSET_TYPE, APPOINTMENT_TYPE, AVAILABILITY_VALUES, CONDITION_VALUES } from '../constants/things';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import ImageUpload from '../components/ImageUpload';
import DocumentUpload from '../components/DocumentUpload';

export default function EditThingPage() {
  const { t } = useTranslation();
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');
  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;

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
  const [eventDate, setEventDate] = useState('');
  const [eventTime, setEventTime] = useState('');
  const [bookingUnit, setBookingUnit] = useState('DAY');
  const [slotDuration, setSlotDuration] = useState(30);
  const [scheduleWindows, setScheduleWindows] = useState([{ days: [], start_time: '09:00', end_time: '17:00' }]);
  const [isEndless, setIsEndless] = useState(false);
  const [documents, setDocuments] = useState([]);
  const [errors, setErrors] = useState({});
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  const [thingCollectionCode, setThingCollectionCode] = useState(code || '');
  const [thingCollectionHeadline, setThingCollectionHeadline] = useState('');

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
      return;
    }
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
          if (data.event_date) {
            const d = new Date(data.event_date);
            setEventDate(d.toISOString().slice(0, 10));
            setEventTime(d.toISOString().slice(11, 16));
          }
          if (data.documents) setDocuments(data.documents);
          if (data.booking_unit) setBookingUnit(data.booking_unit);
          if (data.slot_duration) setSlotDuration(data.slot_duration);
          if (data.availability_schedule && data.availability_schedule.length > 0) {
            setScheduleWindows(data.availability_schedule);
          }
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
    if (thingType === EVENT_TYPE) {
      body.event_date = eventDate ? new Date(`${eventDate}T${eventTime || '00:00'}`).toISOString() : null;
    }
    if (thingType === ASSET_TYPE) {
      body.booking_unit = bookingUnit;
    }
    if (thingType === APPOINTMENT_TYPE) {
      body.slot_duration = slotDuration;
      body.availability_schedule = scheduleWindows.filter((w) => w.days.length > 0);
    }
    body.documents = documents.length > 0 ? documents : null;
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
      } else {
        setToast({ type: 'error', message: t('editThing.errorSaving') });
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
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <BackLink to={returnPath} label={returnLabel} />
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <h1 className="page-title-xl">{t('editThing.pageTitle')}</h1>
      <div className="form-grid">
        <Select
                language="en"
          id="edit-thing-type"
          texts={{ label: t('addThing.typeLabel') }}
          options={TYPE_VALUES.map(v => ({ label: t('types.' + v), value: v }))}
          value={thingType}
          onChange={(selectedOptions) => {
            if (selectedOptions.length > 0) {
              setThingType(selectedOptions[0].value);
            }
          }}
        />
        {['GIFT_THING', 'SELL_THING'].includes(thingType) && (
          <div className="toggle-left">
            <ToggleButton
              id="edit-thing-is-endless"
              label={t('endless.label')}
              checked={isEndless}
              onChange={(val) => setIsEndless(!val)}
              variant="inline"
              theme={tc.color_01 ? { '--toggle-button-color': `var(--color-${tc.color_01})` } : undefined}
            />
          </div>
        )}
        <TextInput
          id="edit-thing-headline"
          label={t('addThing.titleLabel')}
          value={headline}
          onChange={(e) => setHeadline(e.target.value)}
          required
          invalid={!!errors.headline}
          errorText={errors.headline}
          helperText={`${headline.length}/64`}
        />
        <TextArea
          id="edit-thing-description"
          label={t('addThing.descriptionLabel')}
          value={description}
          onChange={(e) => setDescription(e.target.value)}
          helperText={`${description.length}/256`}
        />
        {thingType === EVENT_TYPE && (
          <>
            <DateInput
              id="edit-thing-event-date"
              label={t('events.eventDate')}
              value={eventDate}
              onChange={(value) => setEventDate(value)}
              dateFormat="yyyy-MM-dd"
              language="en"
            />
            <TextInput
              id="edit-thing-event-time"
              label={t('events.eventTime')}
              type="time"
              value={eventTime}
              onChange={(e) => setEventTime(e.target.value)}
            />
          </>
        )}
        {thingType === ASSET_TYPE && (
          <Select
                language="en"
            id="edit-thing-booking-unit"
            texts={{ label: t('asset.bookingUnit') }}
            options={[
              { label: t('asset.unitDay'), value: 'DAY' },
              { label: t('asset.unitHour'), value: 'HOUR' },
            ]}
            value={bookingUnit}
            onChange={(sel) => sel.length > 0 && setBookingUnit(sel[0].value)}
          />
        )}
        {thingType === APPOINTMENT_TYPE && (
          <>
            <Select
                language="en"
              id="edit-thing-slot-duration"
              texts={{ label: t('appointment.durationLabel') }}
              options={[
                { label: t('appointment.duration15'), value: '15' },
                { label: t('appointment.duration30'), value: '30' },
                { label: t('appointment.duration60'), value: '60' },
              ]}
              value={String(slotDuration)}
              onChange={(sel) => sel.length > 0 && setSlotDuration(Number(sel[0].value))}
            />
            <h3>{t('appointment.schedule')}</h3>
            <div className="schedule-windows">
              {scheduleWindows.map((window, idx) => (
                <div key={idx} className="schedule-window">
                  <div className="schedule-days">
                    <Select
                      multiSelect
                      language="en"
                      id={`edit-schedule-days-${idx}`}
                      texts={{
                        label: t('appointment.days'),
                        placeholder: t('appointment.daysPlaceholder'),
                      }}
                      options={[1, 2, 3, 4, 5, 6, 7].map((day) => ({
                        label: t('appointment.' + ['mon', 'tue', 'wed', 'thu', 'fri', 'sat', 'sun'][day - 1]),
                        value: String(day),
                      }))}
                      value={window.days.map(String)}
                      onChange={(selected) => {
                        const updated = [...scheduleWindows];
                        updated[idx] = {
                          ...updated[idx],
                          days: selected.map((s) => Number(s.value)).sort((a, b) => a - b),
                        };
                        setScheduleWindows(updated);
                      }}
                    />
                  </div>
                  <div className="schedule-times">
                    <TextInput
                      id={`edit-schedule-start-${idx}`}
                      label={t('appointment.startTime')}
                      type="time"
                      value={window.start_time}
                      onChange={(e) => {
                        const updated = [...scheduleWindows];
                        updated[idx] = { ...updated[idx], start_time: e.target.value };
                        setScheduleWindows(updated);
                      }}
                    />
                    <TextInput
                      id={`edit-schedule-end-${idx}`}
                      label={t('appointment.endTime')}
                      type="time"
                      value={window.end_time}
                      onChange={(e) => {
                        const updated = [...scheduleWindows];
                        updated[idx] = { ...updated[idx], end_time: e.target.value };
                        setScheduleWindows(updated);
                      }}
                    />
                    {scheduleWindows.length > 1 && (
                      <Button
                        variant="secondary"
                        size="small"
                        onClick={() => setScheduleWindows(scheduleWindows.filter((_, i) => i !== idx))}
                      >
                        {t('appointment.removeWindow')}
                      </Button>
                    )}
                  </div>
                </div>
              ))}
            </div>
            <Button
              variant="secondary"
              size="small"
              onClick={() => setScheduleWindows([...scheduleWindows, { days: [], start_time: '09:00', end_time: '17:00' }])}
            >
              {t('appointment.addWindow')}
            </Button>
          </>
        )}
        {FEE_TYPES.includes(thingType) && (
          <NumberInput
            id="edit-thing-fee"
            label={t('addThing.priceLabel')}
            value={fee === '' ? '' : Number(fee)}
            onChange={(e) => setFee(e.target.value)}
            min={0}
            step={0.01}
            unit="EUR"
            required
            invalid={!!errors.fee}
            errorText={errors.fee}
          />
        )}
        {FEE_TYPES.includes(thingType) && DETAIL_TYPES.includes(thingType) && (
          <div className="spacer-xxxx" />
        )}
        {DETAIL_TYPES.includes(thingType) && (
          <>
            <Select
                language="en"
              id="edit-thing-availability"
              texts={{ label: t('addThing.availabilityLabel') }}
              options={AVAILABILITY_VALUES.map(v => ({ label: t('availability.' + v), value: v }))}
              value={availability}
              onChange={(sel) => setAvailability(sel.length > 0 ? sel[0].value : '')}
              clearable
            />
            <Select
                language="en"
              id="edit-thing-condition"
              texts={{ label: t('addThing.conditionLabel') }}
              options={CONDITION_VALUES.map(v => ({ label: t('condition.' + v), value: v }))}
              value={condition}
              onChange={(sel) => setCondition(sel.length > 0 ? sel[0].value : '')}
              clearable
            />
            <TextInput
              id="edit-thing-location"
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
          id="edit-thing-thumbnail"
          label={t('upload.thumbnailLabel')}
          value={thumbnail}
          onChange={setThumbnail}
          currentUrl={thumbnailUrl}
          folder="oiueei/things"
        />
        <DocumentUpload
          documents={documents}
          onChange={setDocuments}
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
      <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
