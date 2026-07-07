import { useEffect, useState } from 'react';
import { useParams, useNavigate, useLocation, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Checkbox, DateInput, Notification, Select } from 'hds-react';
import { DATE_TYPES, SWAP_TYPE } from '../constants/things';
import { durationLabel, isPickupDisabled, isDateBlocked, derivedReturnDate } from '../utils/rental';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import useTheeeme from '../hooks/useTheeeme';

const TODAY = new Date();
TODAY.setHours(0, 0, 0, 0);
const MAX_DATE = new Date(TODAY);
MAX_DATE.setDate(MAX_DATE.getDate() + 90);

export default function RequestThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { t, i18n } = useTranslation();
  const userCode = localStorage.getItem('userCode');
  const { btnStyle, btnSecondaryStyle } = useTheeeme();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.back');

  const [thing, setThing] = useState(null);
  useEffect(() => { document.title = thing ? t('titles.holdThing', { headline: thing.headline }) : t('titles.holdDefault'); }, [thing, t]);
  const [startDate, setStartDate] = useState(location.state?.prefillDate || '');
  const [endDate, setEndDate] = useState('');
  const [duration, setDuration] = useState('');
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [blockedPeriods, setBlockedPeriods] = useState([]);
  const [toast, setToast] = useState(null);
  const [success, setSuccess] = useState(false);
  const [error, setError] = useState(false);
  const [ownSwapThings, setOwnSwapThings] = useState([]);
  const [selectedOfferings, setSelectedOfferings] = useState([]);

  useEffect(() => {
    if (!userCode) return;
    setError(false);
    apiFetch(`/api/v1/things/${thingCode}/`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => (data ? setThing(data) : setError(true)))
      .catch(() => setError(true));
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

  // Per-collection rental rules (#7): a set of fixed lengths + allowed weekdays.
  const rentalDurations = thing?.rental_durations || [];
  const rentalWeekdays = thing?.rental_weekdays || [];
  const isConstrainedRental = !!thing && DATE_TYPES.includes(thing.type) && rentalDurations.length > 0;

  // Pickup validity and blocked-date checks are pure, timezone-safe, unit-tested
  // helpers in utils/rental.js; bind them to the current rental state here.
  const pickupDisabled = (date) =>
    isPickupDisabled(date, { rentalWeekdays, blockedPeriods, duration });
  const dateBlocked = (date) => isDateBlocked(date, blockedPeriods);

  const handleSubmit = async () => {
    setAttempted(true);

    const isDateBased = thing && DATE_TYPES.includes(thing.type);
    const isSwap = thing && thing.type === SWAP_TYPE;

    let body = {};
    if (isSwap) {
      if (selectedOfferings.length === 0) return;
      body = { offered_thing_codes: selectedOfferings };
    } else if (isDateBased) {
      if (isConstrainedRental) {
        // Renter picks a fixed length + a pickup date; the return date is derived
        // as pickup + length (a week rental comes back on the same weekday).
        if (!duration || !startDate) return;
        const end = derivedReturnDate(startDate, duration);
        body = { start_date: startDate, end_date: end };
      } else {
        if (!startDate || !endDate) return;
        body = { start_date: startDate, end_date: endDate };
      }
    }
    // Pass the collection context so the backend applies that collection's rental
    // rules (harmless for other flows / collections without rules).
    if (code) body.collection_code = code;

    setSubmitting(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/request/`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setSuccess(true);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else if (res.status === 400) {
        const data = await res.json();
        let message = data.detail;
        if (!message) {
          const errors = Object.values(data).flat();
          message = errors.join(' ') || t('thingPage.invalidRequest');
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

  if (error) {
    return (
      <PageLayout title={t('common.error')} backTo={backPath} backLabel={backLabel}>
        <Notification label={t('thingPage.errorLoading')} type="error" />
      </PageLayout>
    );
  }

  if (!thing) return <LoadingSpinner />;

  const isDateBased = DATE_TYPES.includes(thing.type);
  const isSwap = thing.type === SWAP_TYPE;

  return (
    <PageLayout
      title={t('request.pageTitle', { headline: thing.headline })}
      backTo={backPath}
      backLabel={backLabel}
    >
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
            <p>
              {t('swap.noItemsToOffer')}{' '}
              {code && <Link to={`/collections/${code}/add`}>{t('swap.addItemToOffer')}</Link>}
            </p>
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
            <p id="swap-offer-error" role="alert" style={{ color: 'var(--color-error)' }}>
              {t('swap.selectAtLeastOne')}
            </p>
          )}
        </div>
      )}
      {isDateBased && (
        <>
          <Notification
            type={thing.available_today ? 'success' : 'info'}
            size="small"
            label={t('thingPage.availabilityLabel')}
          >
            {`${t('thingPage.availabilityLabel')} ${thing.available_today
              ? t('availability.IMMEDIATE')
              : thing.next_available
                ? t('availability.nextAvailable', { date: new Date(thing.next_available).toLocaleDateString(i18n.language, { day: 'numeric', month: 'numeric' }) })
                : t('availability.noneSoon')}`}
          </Notification>
          <div className="spacer-s" />
        </>
      )}
      {isDateBased && isConstrainedRental && (
        <div className="summary-grid section-mt">
          <Select
            language="en"
            id="request-duration"
            texts={{
              label: t('rental.chooseDuration'),
              placeholder: t('rental.chooseDurationPlaceholder'),
              error: attempted && !duration ? t('rental.durationRequired') : undefined,
            }}
            options={rentalDurations.map((d) => ({ label: durationLabel(d, t), value: String(d) }))}
            value={duration ? [{ label: durationLabel(Number(duration), t), value: duration }] : []}
            onChange={(opts) => { setDuration(opts.length ? opts[0].value : ''); setStartDate(''); }}
            invalid={attempted && !duration}
          />
          <div className="spacer-xxxs" />
          <DateInput
            id="request-pickup-date"
            label={t('rental.pickupLabel')}
            value={startDate}
            onChange={(value) => setStartDate(value)}
            dateFormat="yyyy-MM-dd"
            language="en"
            required
            disabled={!duration}
            invalid={attempted && !startDate}
            errorText={attempted && !startDate ? t('request.startRequired') : undefined}
            minDate={TODAY}
            maxDate={MAX_DATE}
            dateOutsideRangeErrorText={t('request.dateRange')}
            isDateDisabledBy={pickupDisabled}
            malformedDateErrorText={t('request.dateOverlap')}
          />
          {startDate && duration && (
            <p className="thing-card-meta" style={{ marginTop: 'var(--spacing-2-xs)' }}>
              {t('rental.returnBy', { date: derivedReturnDate(startDate, duration) })}
            </p>
          )}
        </div>
      )}
      {isDateBased && !isConstrainedRental && (
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
            isDateDisabledBy={dateBlocked}
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
            isDateDisabledBy={dateBlocked}
            malformedDateErrorText={t('request.dateOverlap')}
          />
        </div>
      )}

      <div className="spacer-xs" />
      <div className="form-grid">
        <Button fullWidth disabled={submitting || (isSwap && selectedOfferings.length === 0)} onClick={handleSubmit} style={btnStyle}>
          {submitting ? t('common.sending') : isSwap ? t('swap.swapButton') : t(`thingCard.action.${thing?.type}`, { defaultValue: t('thingCard.hold') })}
        </Button>
        <Button variant="secondary" fullWidth onClick={() => navigate(backPath)} style={btnSecondaryStyle}>
          {t('common.cancel')}
        </Button>
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
      </>
      )}
    </PageLayout>
  );
}
