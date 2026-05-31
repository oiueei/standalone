import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Checkbox, DateInput, Koros, Notification, NumberInput, Select, TextInput } from 'hds-react';
import { DATE_TYPES, ORDER_TYPE, ASSET_TYPE, SWAP_TYPE, APPOINTMENT_TYPE } from '../constants/things';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import Toast from '../components/Toast';

const TODAY = new Date();
TODAY.setHours(0, 0, 0, 0);
const MAX_DATE = new Date(TODAY);
MAX_DATE.setDate(MAX_DATE.getDate() + 90);

export default function RequestThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const userCode = localStorage.getItem('userCode');
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.back');

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
    }
  }, [userCode, navigate]);

  const [thing, setThing] = useState(null);
  useEffect(() => { document.title = thing ? t('titles.holdThing', { headline: thing.headline }) : t('titles.holdDefault'); }, [thing, t]);
  const [startDate, setStartDate] = useState(location.state?.prefillDate || '');
  const [endDate, setEndDate] = useState('');
  const [deliveryDate, setDeliveryDate] = useState('');
  const [quantity, setQuantity] = useState(1);
  const [startTime, setStartTime] = useState(location.state?.prefillStartTime || '');
  const [endTime, setEndTime] = useState(location.state?.prefillEndTime || '');
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [blockedPeriods, setBlockedPeriods] = useState([]);
  const [toast, setToast] = useState(null);
  const [success, setSuccess] = useState(false);
  const [ownSwapThings, setOwnSwapThings] = useState([]);
  const [selectedOfferings, setSelectedOfferings] = useState([]);

  useEffect(() => {
    if (!userCode) return;
    apiFetch(`/api/v1/things/${thingCode}/`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) setThing(data);
      })
      .catch(() => {});
  }, [userCode, thingCode, code]);

  useEffect(() => {
    if (!userCode || !thing || thing.type !== SWAP_TYPE) return;
    apiFetch('/api/v1/things/')
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        const items = (data.results || data).filter(
          (t) => t.type === SWAP_TYPE && t.code !== thingCode && t.status === 'ACTIVE' && t.collection_code === thing.collection_code
        );
        setOwnSwapThings(items);
      })
      .catch(() => {});
  }, [userCode, thing, thingCode]);

  useEffect(() => {
    if (!userCode || !thing || !DATE_TYPES.includes(thing.type)) return;
    apiFetch(`/api/v1/things/${thingCode}/calendar/`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => setBlockedPeriods(data))
      .catch(() => {});
  }, [userCode, thingCode, thing]);

  const isDateBlocked = (date) => {
    if (blockedPeriods.some((period) => {
      const start = new Date(period.start_date);
      const end = new Date(period.end_date);
      start.setHours(0, 0, 0, 0);
      end.setHours(0, 0, 0, 0);
      const d = new Date(date);
      d.setHours(0, 0, 0, 0);
      return d >= start && d <= end;
    })) return true;
    if (thing && thing.type === APPOINTMENT_TYPE && thing.availability_schedule?.length) {
      const scheduledDays = [...new Set(thing.availability_schedule.flatMap((w) => w.days))];
      const jsDay = new Date(date).getDay();
      const isoDay = jsDay === 0 ? 7 : jsDay;
      return !scheduledDays.includes(isoDay);
    }
    return false;
  };

  const toMinutes = (timeStr) => {
    const [h, m] = timeStr.split(':').map(Number);
    return h * 60 + m;
  };

  const fromMinutes = (mins) =>
    `${String(Math.floor(mins / 60)).padStart(2, '0')}:${String(mins % 60).padStart(2, '0')}`;

  const hourlyOptions = Array.from({ length: 24 }, (_, i) => {
    const time = fromMinutes(i * 60);
    return { label: time, value: time };
  });

  const getAvailableSlots = (date) => {
    if (!thing || !date || thing.type !== APPOINTMENT_TYPE || !thing.availability_schedule?.length) return [];
    const jsDay = new Date(date).getDay();
    const isoDay = jsDay === 0 ? 7 : jsDay;
    const duration = thing.slot_duration || 60;
    const slots = [];
    for (const window of thing.availability_schedule) {
      if (!window.days.includes(isoDay)) continue;
      const start = toMinutes(window.start_time);
      const end = toMinutes(window.end_time);
      for (let m = start; m + duration <= end; m += duration) {
        const slotStart = fromMinutes(m);
        const slotEnd = fromMinutes(m + duration);
        const taken = blockedPeriods.some((p) => {
          if (p.start_date !== date) return false;
          return toMinutes(p.start_time.slice(0, 5)) < m + duration && toMinutes(p.end_time.slice(0, 5)) > m;
        });
        if (!taken) slots.push({ label: `${slotStart} – ${slotEnd}`, start: slotStart, end: slotEnd });
      }
    }
    return slots;
  };

  const handleSubmit = async () => {
    setAttempted(true);

    const isDateBased = thing && DATE_TYPES.includes(thing.type);
    const isOrder = thing && thing.type === ORDER_TYPE;
    const isHourly = thing && (thing.type === APPOINTMENT_TYPE || (thing.type === ASSET_TYPE && thing.booking_unit === 'HOUR'));
    const isSwap = thing && thing.type === SWAP_TYPE;

    let body = {};
    if (isSwap) {
      if (selectedOfferings.length === 0) return;
      body = { offered_thing_codes: selectedOfferings };
    } else if (isHourly) {
      if (!startDate || !startTime || !endTime) return;
      body = { start_date: startDate, start_time: startTime, end_time: endTime };
    } else if (isDateBased) {
      if (!startDate || !endDate) return;
      body = { start_date: startDate, end_date: endDate };
    } else if (isOrder) {
      if (!deliveryDate || quantity < 1) return;
      if (quantity > 99) {
        setToast({ type: 'error', message: t('request.maxQuantity') });
        return;
      }
      body = { delivery_date: deliveryDate, quantity };
    }

    setSubmitting(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/request/`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setSuccess(true);
      } else if (res.status === 400) {
        const data = await res.json();
        let message = data.detail;
        if (!message) {
          const errors = Object.values(data).flat();
          if (errors.some((e) => String(e).includes('99'))) {
            message = t('request.maxQuantity');
          } else {
            message = errors.join(' ') || t('thingPage.invalidRequest');
          }
        }
        setToast({ type: 'error', message });
      } else if (res.status === 409) {
        setToast({ type: 'error', message: t('request.dateOverlap') });
      } else {
        setToast({ type: 'error', message: t('request.errorSending') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  if (!thing) return null;

  const isDateBased = DATE_TYPES.includes(thing.type);
  const isOrder = thing.type === ORDER_TYPE;
  const isHourly = thing.type === APPOINTMENT_TYPE || (thing.type === ASSET_TYPE && thing.booking_unit === 'HOUR');
  const isSwap = thing.type === SWAP_TYPE;

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
    '--color': `var(--color-${tc.color_04})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
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
        <div className="form-hero-content" style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <BackLink to={backPath} label={backLabel} />
          <h1 className="form-hero-title">{t('request.pageTitle', { headline: thing.headline })}</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
      {success ? (
        <>
          <Notification label={t('request.successLabel')} type="success">
            {t('request.successMessage')}
          </Notification>
          <div className="spacer-m" />
          <Button variant="secondary" fullWidth onClick={() => navigate(backPath)} style={btnSecondaryStyle}>
            {t('request.backTo', { label: backLabel })}
          </Button>
        </>
      ) : (
      <>
      {thing.fee && <p><strong>{t('request.priceLabel')}</strong> {t('request.priceValue', { fee: thing.fee })}</p>}
      <div className="spacer-m" />
      {isSwap && (
        <div className="summary-grid section-mt">
          <h2>{t('swap.offerItems')}</h2>
          <p>{t('swap.selectItems')}</p>
          <div className="spacer-xs" />
          {ownSwapThings.length === 0 ? (
            <p>{t('swap.noItemsToOffer')}</p>
          ) : (
            ownSwapThings.map((item) => (
              <Checkbox
                key={item.code}
                id={`swap-offer-${item.code}`}
                label={item.headline}
                checked={selectedOfferings.includes(item.code)}
                onChange={(e) => {
                  if (e.target.checked) {
                    setSelectedOfferings((prev) => [...prev, item.code]);
                  } else {
                    setSelectedOfferings((prev) => prev.filter((c) => c !== item.code));
                  }
                }}
              />
            ))
          )}
          {attempted && selectedOfferings.length === 0 && (
            <p style={{ color: 'var(--color-error)' }}>{t('swap.offerItems')}</p>
          )}
        </div>
      )}
      {isHourly && (
        <div className="summary-grid section-mt">
          <DateInput
            id="request-start-date"
            label={t('request.startLabel')}
            value={startDate}
            onChange={(value) => { setStartDate(value); setStartTime(''); setEndTime(''); }}
            dateFormat="yyyy-MM-dd"
            language="en"
            required
            invalid={attempted && !startDate}
            errorText={attempted && !startDate ? t('request.startRequired') : undefined}
            minDate={TODAY}
            maxDate={MAX_DATE}
            dateOutsideRangeErrorText={t('request.dateRange')}
            isDateDisabledBy={isDateBlocked}
          />
          <div className="spacer-xxxs" />
          {thing?.type === APPOINTMENT_TYPE ? (
            <>
              <Select
                id="request-slot"
                label={t('appointment.selectSlot')}
                language="en"
                value={startTime && endTime ? [{ label: `${startTime} – ${endTime}`, value: `${startTime}_${endTime}` }] : []}
                options={getAvailableSlots(startDate).map((s) => ({ label: s.label, value: `${s.start}_${s.end}` }))}
                onChange={(selected) => {
                  if (selected && selected.length > 0) {
                    const [s, e] = selected[0].value.split('_');
                    setStartTime(s);
                    setEndTime(e);
                  } else {
                    setStartTime('');
                    setEndTime('');
                  }
                }}
                invalid={attempted && (!startTime || !endTime)}
                error={attempted && (!startTime || !endTime) ? t('appointment.slotRequired') : ''}
                disabled={!startDate}
                placeholder={startDate ? t('appointment.selectSlotPlaceholder') : t('appointment.selectDateFirst')}
              />
            </>
          ) : (
            <>
              <Select
                id="request-start-time"
                label={t('asset.startTime')}
                language="en"
                value={startTime ? [{ label: startTime, value: startTime }] : []}
                options={hourlyOptions}
                onChange={(sel) => { const v = sel?.length > 0 ? sel[0].value : ''; setStartTime(v); if (endTime && v >= endTime) setEndTime(''); }}
                invalid={attempted && !startTime}
                error={attempted && !startTime ? t('asset.startTime') : ''}
                placeholder={t('asset.selectTimePlaceholder')}
              />
              <div className="spacer-xxxs" />
              <Select
                id="request-end-time"
                label={t('asset.endTime')}
                language="en"
                value={endTime ? [{ label: endTime, value: endTime }] : []}
                options={startTime ? hourlyOptions.filter((o) => o.value > startTime) : hourlyOptions}
                onChange={(sel) => { setEndTime(sel?.length > 0 ? sel[0].value : ''); }}
                invalid={attempted && !endTime}
                error={attempted && !endTime ? t('asset.endTime') : ''}
                disabled={!startTime}
                placeholder={t('asset.selectTimePlaceholder')}
              />
            </>
          )}
        </div>
      )}
      {isDateBased && !isHourly && (
        <div className="summary-grid section-mt">
          <DateInput
            id="request-start-date"
            label={t('request.startLabel')}
            value={startDate}
            onChange={(value) => setStartDate(value)}
            dateFormat="yyyy-MM-dd"
            language="en"
            required
            invalid={attempted && !startDate}
            errorText={attempted && !startDate ? t('request.startRequired') : undefined}
            minDate={TODAY}
            maxDate={MAX_DATE}
            dateOutsideRangeErrorText={t('request.dateRange')}
            isDateDisabledBy={isDateBlocked}
            malformedDateErrorText={t('request.dateOverlap')}
          />
          <div className="spacer-xxxs" />
          <DateInput
            id="request-end-date"
            label={t('request.endLabel')}
            value={endDate}
            onChange={(value) => setEndDate(value)}
            dateFormat="yyyy-MM-dd"
            language="en"
            required
            invalid={attempted && !endDate}
            errorText={attempted && !endDate ? t('request.endRequired') : undefined}
            minDate={TODAY}
            maxDate={MAX_DATE}
            dateOutsideRangeErrorText={t('request.dateRange')}
            isDateDisabledBy={isDateBlocked}
            malformedDateErrorText={t('request.dateOverlap')}
          />
        </div>
      )}

      {isOrder && (
        <div className="summary-grid section-mt">
          <DateInput
            id="request-delivery-date"
            label={t('request.deliveryLabel')}
            value={deliveryDate}
            onChange={(value) => setDeliveryDate(value)}
            dateFormat="yyyy-MM-dd"
            language="en"
            required
            invalid={attempted && !deliveryDate}
            errorText={attempted && !deliveryDate ? t('request.deliveryRequired') : undefined}
            minDate={TODAY}
            maxDate={MAX_DATE}
            dateOutsideRangeErrorText={t('request.dateRange')}
          />
          <div className="spacer-xxxs" />
          <NumberInput
            id="request-quantity"
            label={t('request.quantityLabel')}
            value={quantity}
            onChange={(e) => setQuantity(Number(e.target.value))}
            min={1}
            step={1}
          />
        </div>
      )}

      <div className="spacer-xs" />
      <div className="form-grid">
        <Button fullWidth disabled={submitting || (isSwap && selectedOfferings.length === 0)} onClick={handleSubmit} style={btnStyle}>
          {submitting ? t('common.sending') : isSwap ? t('swap.swapButton') : t('thingCard.hold')}
        </Button>
        <Button variant="secondary" fullWidth onClick={() => navigate(backPath)} style={btnSecondaryStyle}>
          {t('common.cancel')}
        </Button>
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
      </>
      )}
      </div>
    </div>
  );
}
