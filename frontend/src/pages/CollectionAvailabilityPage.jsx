import { useCallback, useState } from 'react';
import { useParams } from 'react-router';
import { useTranslation } from 'react-i18next';
import { TextArea, Select, Button, Notification, ToggleButton } from 'hds-react';
import PageLayout from '../components/PageLayout';
import FieldNotice from '../components/FieldNotice';
import ClosedDatesField from '../components/ClosedDatesField';
import WeekdayChips from '../components/WeekdayChips';
import OpeningHoursField from '../components/OpeningHoursField';
import RadioOptionGroup from '../components/RadioOptionGroup';
import BoundedNumberInput from '../components/BoundedNumberInput';
import LoadingSpinner from '../components/LoadingSpinner';
import CollectionFormRefusal from '../components/CollectionFormRefusal';
import Toast from '../components/Toast';
import NotFoundPage from './NotFoundPage';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionForm from '../hooks/useCollectionForm';
import useDocumentTitle from '../hooks/useDocumentTitle';
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
  const { btnStyle, toggleTheme } = useTheeeme();
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
  const { loading, loaded, refusal, base, save, submitting, toast, setToast } = useCollectionForm(
    code,
    {
      onLoad: (data) => {
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
      },
    }
  );
  useDocumentTitle(
    headline
      ? t('titles.collectionAvailability', { headline: L(headline) })
      : t('titles.collectionAvailabilityDefault')
  );

  const isShed = kind === 'SHED';
  const isLibrary = kind === 'LIBRARY';
  const requestInfoCount = localizedCounter(requestInfo, 512);
  const depositCount = localizedCounter(depositPolicy, 256);

  // Past a limit the button is disabled and the field says why; the early return in
  // `handleSubmit` is only a defence.
  const tooLong = requestInfoCount.over || (isLibrary && depositCount.over);

  const handleSubmit = () => {
    if (!loaded || tooLong) return;
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
    save(body);
  };

  if (loading) return <LoadingSpinner />;
  if (refusal) return <CollectionFormRefusal refusal={refusal} base={base} />;
  // A stall has no request page to configure: it is not a page of the app.
  if (loaded && !isLibrary && !isShed) return <NotFoundPage />;

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
                errorText={depositCount.over ? t('rental.depositPolicyMaxLength') : undefined}
                helperText={localizedHelper(depositPolicy, 256, t)}
              />
            </div>
          </>
        )}
        {isShed && (
          <>
            <BoundedNumberInput
              id="availability-reservation-horizon-days"
              label={t('reservation.horizonLabel')}
              helperText={t('reservation.horizonHelper')}
              min={1}
              max={365}
              fallback={90}
              value={reservationHorizonDays}
              onChange={setReservationHorizonDays}
            />
            <BoundedNumberInput
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
                <BoundedNumberInput
                  id="availability-reservation-min-minutes"
                  label={t('reservation.minMinutesLabel')}
                  helperText={t('reservation.minMinutesHelper')}
                  min={1}
                  max={720}
                  fallback={60}
                  value={reservationMinMinutes}
                  onChange={setReservationMinMinutes}
                />
                <BoundedNumberInput
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
                <BoundedNumberInput
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
                />
              </>
            )}
          </>
        )}
      </div>
      <div className="form-actions">
        <Button
          disabled={submitting || !loaded || tooLong}
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
