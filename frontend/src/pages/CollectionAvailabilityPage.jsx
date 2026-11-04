import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextArea, Select, Button, Notification, ToggleButton } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';
import PageLayout from '../components/PageLayout';
import FieldNotice from '../components/FieldNotice';
import ClosedDatesField from '../components/ClosedDatesField';
import WeekdayChips from '../components/WeekdayChips';
import OpeningHoursField from '../components/OpeningHoursField';
import RadioOptionGroup from '../components/RadioOptionGroup';
import BoundedDayInput from '../components/BoundedDayInput';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import NotFoundPage from './NotFoundPage';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { useCollectionBase } from '../hooks/useCollectionBase';
import { useLocalized, localizedCounter, localizedHelper } from '../utils/localized';
import {
  RENTAL_DURATION_PRESETS,
  durationLabel,
  closedDatesToDisplay,
  hasOpeningHours,
} from '../utils/rental';
import hdsLang from '../utils/hdsLang';

// The examples are code samples the owner copies, so they read the same in any
// language (the keys are the language codes the server accepts).
const REQUEST_INFO_EXAMPLE =
  '{"es": "La recogida es solo los martes.", "ca": "La recollida és només els dimarts."}';
const POLICY_EXAMPLE =
  '{"es": "Se devuelve al comprobar que se entrega correctamente", "ca": "Es retorna en comprovar que es lliura correctament"}';
const OPENING_HOURS_EXAMPLE =
  '{"0": [["10:00","14:00"],["16:00","20:00"]], "1": [["12:00","16:00"]]}';

/**
 * When the collection can be asked for: the note on the request page, the closed
 * days and the rules of a loan or rental (library) or of a reservation (shed).
 * A stall has no request page, so it has no such page either.
 *
 * It sends only the fields of its kind in a partial update, and only once the
 * collection has loaded; every value comes from what was loaded. Unit, hours and
 * minutes travel together: the server checks the hours as soon as a request
 * touches the unit or the minutes.
 */
export default function CollectionAvailabilityPage() {
  const { t, i18n } = useTranslation();
  const L = useLocalized();
  const { code } = useParams();
  const base = useCollectionBase(code);
  const navigate = useNavigate();
  const { btnStyle, tc } = useTheeeme();
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [kind, setKind] = useState('');
  const [headline, setHeadline] = useState('');
  const [requestInfo, setRequestInfo] = useState('');
  const [closedDates, setClosedDates] = useState('');
  const [rentalDurations, setRentalDurations] = useState([]);
  const [rentalWeekdays, setRentalWeekdays] = useState([]);
  const [depositPolicy, setDepositPolicy] = useState('');
  const [reservationUnit, setReservationUnit] = useState('DAY');
  const [reservationMaxDays, setReservationMaxDays] = useState(1);
  const [reservationHorizonDays, setReservationHorizonDays] = useState(90);
  const [reservationMaxActivePerMember, setReservationMaxActivePerMember] = useState(10);
  const [reservationAsksPhone, setReservationAsksPhone] = useState(false);
  const [reservationMinMinutes, setReservationMinMinutes] = useState(60);
  const [reservationMaxMinutes, setReservationMaxMinutes] = useState(180);
  const [openingHours, setOpeningHours] = useState({});
  // False while the opening-hours JSON on screen does not parse: saving is refused
  // then, rather than sending the last good value.
  const [openingHoursValid, setOpeningHoursValid] = useState(true);
  const reportHoursValidity = useCallback((valid) => setOpeningHoursValid(valid), []);
  const [savedPalette, setSavedPalette] = useState(null);
  useCollectionTheeeme(savedPalette?.colors, savedPalette?.koro);
  const [savedLanguage, setSavedLanguage] = useState('');
  const [savedTexts, setSavedTexts] = useState([]);
  useCollectionLanguage(savedLanguage, savedTexts);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  useDocumentTitle(
    headline
      ? t('titles.collectionAvailability', { headline: L(headline) })
      : t('titles.collectionAvailabilityDefault')
  );

  useEffect(() => {
    const load = async () => {
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`);
        if (res.ok) {
          const data = await res.json();
          setKind(data.kind || '');
          setHeadline(data.headline || '');
          setRequestInfo(data.request_info || '');
          setClosedDates(closedDatesToDisplay(data.closed_dates));
          setRentalDurations(data.rental_durations || []);
          setRentalWeekdays(data.rental_weekdays || []);
          setDepositPolicy(data.deposit_policy || '');
          setReservationUnit(data.reservation_unit || 'DAY');
          setReservationMaxDays(data.reservation_max_days ?? 1);
          setReservationHorizonDays(data.reservation_horizon_days ?? 90);
          setReservationMaxActivePerMember(data.reservation_max_active_per_member ?? 10);
          setReservationAsksPhone(!!data.reservation_asks_phone);
          setReservationMinMinutes(data.reservation_min_minutes ?? 60);
          setReservationMaxMinutes(data.reservation_max_minutes ?? 180);
          setOpeningHours(data.opening_hours || {});
          setSavedPalette({ colors: data.theeeme_colors, koro: data.koro });
          setSavedLanguage(data.language || '');
          setSavedTexts([data.headline, data.description]);
          setLoaded(true);
        } else {
          setToast({ type: 'error', messageKey: 'editCollection.errorLoading' });
        }
      } catch {
        setToast({ type: 'error', messageKey: 'common.connectionError' });
      } finally {
        setLoading(false);
      }
    };
    load();
  }, [code]);

  const isShed = kind === 'SHED';
  const isLibrary = kind === 'LIBRARY';
  const requestInfoCount = localizedCounter(requestInfo, 512);
  const depositCount = localizedCounter(depositPolicy, 256);

  const handleSubmit = async () => {
    if (!loaded || requestInfoCount.over || (isLibrary && depositCount.over)) return;
    // A toast, not an inline error: it names the field and is visible wherever the
    // page has been scrolled to.
    if (isShed && reservationUnit === 'HOUR' && !openingHoursValid) {
      setToast({ type: 'error', message: t('openingHours.invalidOnSave') });
      return;
    }
    // An hourly space with no time range can never be booked; the server refuses it
    // too (`opening_hours_required`).
    if (isShed && reservationUnit === 'HOUR' && !hasOpeningHours(openingHours)) {
      setToast({ type: 'error', message: t('openingHours.requiredOnSave') });
      return;
    }
    setSubmitting(true);
    setToast(null);
    const body = {
      request_info: requestInfo.trim(),
      closed_dates: closedDates,
      rental_weekdays: rentalWeekdays,
    };
    if (isLibrary) {
      body.rental_durations = rentalDurations;
      body.deposit_policy = depositPolicy.trim();
    }
    if (isShed) {
      body.reservation_horizon_days = reservationHorizonDays;
      body.reservation_max_active_per_member = reservationMaxActivePerMember;
      body.reservation_asks_phone = reservationAsksPhone;
      body.reservation_unit = reservationUnit;
      if (reservationUnit === 'HOUR') {
        body.reservation_min_minutes = reservationMinMinutes;
        body.reservation_max_minutes = reservationMaxMinutes;
        body.opening_hours = openingHours;
      } else {
        body.reservation_max_days = reservationMaxDays;
      }
    }
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/`, {
        method: 'PATCH',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        navigate(base);
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else if (res.status === 400) {
        const message = await extractApiError(res);
        setToast({ type: 'error', message: message || t('editCollection.errorSaving') });
      } else {
        setToast({ type: 'error', message: t('editCollection.errorSaving') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  if (loading) return <LoadingSpinner />;
  // A stall has no request page to configure: it is not a page of the app.
  if (loaded && !isLibrary && !isShed) return <NotFoundPage />;

  const toggleTheme = tc.color_01
    ? { '--toggle-button-color': `var(--color-${tc.color_01})` }
    : undefined;

  return (
    <PageLayout backTo={base} backLabel={L(headline) || t('common.collection')}>
      <h1 className="page-title-xl">{t('collectionSettings.availability')}</h1>
      <div className="form-grid">
        <div>
          <FieldNotice
            id="availability-request-info-notice"
            label={t('requestInfo.label')}
            example={REQUEST_INFO_EXAMPLE}
            after={t('requestInfo.helper')}
          >
            {t('localized.requestInfoNotice')}
          </FieldNotice>
          <TextArea
            id="availability-request-info"
            label={t('requestInfo.label')}
            value={requestInfo}
            onChange={(e) => setRequestInfo(e.target.value)}
            invalid={requestInfoCount.over}
            errorText={requestInfoCount.over ? t('requestInfo.maxLength') : undefined}
            helperText={localizedHelper(requestInfo, 512, t)}
          />
        </div>
        <ClosedDatesField
          id="availability-closed-dates"
          value={closedDates}
          onChange={setClosedDates}
        />
        {isLibrary && (
          <>
            <Select
              multiSelect
              id="availability-rental-durations"
              texts={{
                label: t('rental.durationsLabel'),
                placeholder: t('rental.durationsPlaceholder'),
                assistive: t('rental.durationsHelper'),
                language: hdsLang(i18n.language),
              }}
              options={RENTAL_DURATION_PRESETS.map((p) => ({
                label: t(p.key),
                value: String(p.days),
              }))}
              value={rentalDurations.map((d) => ({ label: durationLabel(d, t), value: String(d) }))}
              onChange={(opts) =>
                setRentalDurations(opts.map((o) => Number(o.value)).sort((a, b) => a - b))
              }
            />
            <WeekdayChips
              labelId="availability-rental-weekdays-label"
              labelKey="rental.weekdaysLabel"
              helperKey="rental.weekdaysHelper"
              weekdays={rentalWeekdays}
              setWeekdays={setRentalWeekdays}
              color01={tc.color_01}
              color06={tc.color_06}
            />
            <div>
              <FieldNotice
                id="availability-deposit-notice"
                label={t('rental.depositPolicyLabel')}
                example={POLICY_EXAMPLE}
                after={t('rental.depositPolicyHelper')}
              >
                {t('localized.policyNotice')}
              </FieldNotice>
              <TextArea
                id="availability-deposit-policy"
                label={t('rental.depositPolicyLabel')}
                value={depositPolicy}
                onChange={(e) => setDepositPolicy(e.target.value)}
                invalid={depositCount.over}
                helperText={localizedHelper(depositPolicy, 256, t)}
              />
            </div>
          </>
        )}
        {isShed && (
          <>
            <BoundedDayInput
              id="availability-reservation-horizon-days"
              label={t('reservation.horizonLabel')}
              helperText={t('reservation.horizonHelper')}
              min={1}
              max={365}
              fallback={90}
              value={reservationHorizonDays}
              onChange={setReservationHorizonDays}
            />
            <BoundedDayInput
              id="availability-reservation-max-active"
              label={t('reservation.maxActiveLabel')}
              helperText={t('reservation.maxActiveHelper')}
              min={1}
              max={50}
              fallback={10}
              value={reservationMaxActivePerMember}
              onChange={setReservationMaxActivePerMember}
            />
            <ToggleButton
              id="availability-reservation-asks-phone"
              variant="inline"
              label={t('reservation.asksPhoneFull')}
              checked={reservationAsksPhone}
              onChange={(val) => setReservationAsksPhone(!val)}
              theme={toggleTheme}
            />
            <RadioOptionGroup
              idPrefix="availability-reservation-unit"
              name="availability-reservation-unit"
              label={t('reservation.unitLabel')}
              options={[
                { value: 'DAY', label: t('reservation.unitDay') },
                { value: 'HOUR', label: t('reservation.unitHour') },
              ]}
              value={reservationUnit}
              onChange={setReservationUnit}
            />
            {reservationUnit === 'HOUR' ? (
              <>
                <BoundedDayInput
                  id="availability-reservation-min-minutes"
                  label={t('reservation.minMinutesLabel')}
                  helperText={t('reservation.minMinutesHelper')}
                  min={1}
                  max={720}
                  fallback={60}
                  value={reservationMinMinutes}
                  onChange={setReservationMinMinutes}
                />
                <BoundedDayInput
                  id="availability-reservation-max-minutes"
                  label={t('reservation.maxMinutesLabel')}
                  helperText={t('reservation.maxMinutesHelper')}
                  min={1}
                  max={720}
                  fallback={180}
                  value={reservationMaxMinutes}
                  onChange={setReservationMaxMinutes}
                />
                <div>
                  <FieldNotice
                    id="availability-opening-hours-notice"
                    label={t('openingHours.label')}
                    example={OPENING_HOURS_EXAMPLE}
                    after={t('openingHours.noticeAfter')}
                  >
                    {t('openingHours.noticeBefore')}
                  </FieldNotice>
                  <OpeningHoursField
                    id="availability-opening-hours"
                    value={openingHours}
                    onChange={setOpeningHours}
                    onValidityChange={reportHoursValidity}
                  />
                  {/* An hourly space with no opening hours is closed every day; it does
                      not block the save on its own (someone may be about to write them). */}
                  {openingHoursValid && !hasOpeningHours(openingHours) && (
                    <Notification
                      type="alert"
                      size="small"
                      style={{ marginTop: 'var(--spacing-s)' }}
                    >
                      {t('openingHours.noneOpen')}
                    </Notification>
                  )}
                </div>
              </>
            ) : (
              <>
                <BoundedDayInput
                  id="availability-reservation-max-days"
                  label={t('reservation.maxDaysLabel')}
                  helperText={t('reservation.maxDaysHelper')}
                  min={1}
                  max={7}
                  fallback={1}
                  value={reservationMaxDays}
                  onChange={setReservationMaxDays}
                />
                <WeekdayChips
                  labelId="availability-reservation-weekdays-label"
                  labelKey="reservation.weekdaysLabel"
                  helperKey="reservation.weekdaysHelper"
                  weekdays={rentalWeekdays}
                  setWeekdays={setRentalWeekdays}
                  color01={tc.color_01}
                  color06={tc.color_06}
                />
              </>
            )}
          </>
        )}
      </div>
      <div className="form-actions">
        <Button
          disabled={submitting || !loaded}
          onClick={handleSubmit}
          style={{ ...btnStyle, width: '100%' }}
        >
          {submitting ? t('common.saving') : t('common.save')}
        </Button>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
