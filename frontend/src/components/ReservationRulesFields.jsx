import { useCallback, useEffect, useState } from 'react';
import { NumberInput, Notification, ToggleButton } from 'hds-react';
import { useTranslation } from 'react-i18next';
import WeekdayChips from './WeekdayChips';
import OpeningHoursField from './OpeningHoursField';
import RadioOptionGroup from './RadioOptionGroup';
import { hasOpeningHours } from '../utils/rental';

/**
 * One bounded whole-number field. HDS `NumberInput` is controlled, so a field
 * bound straight to `Math.min(max, Math.max(min, n))` snaps to the bound on
 * every keystroke — you cannot clear "3" to type "5", and an empty field jumps
 * to 1. This keeps a local draft string so the field can be emptied, or briefly
 * hold a half-typed value, while editing.
 *
 * **The parent hears every whole number as it appears, not only on blur**.
 * It used to hear a value only when the field lost focus, so
 * anything that saves without a blur first — the +/- stepper, which moves focus
 * to its own button and never touches the input, or a keyboard Save — sent the
 * number the page had loaded while the field on screen showed the new one: "how
 * far ahead can they book" would not stay saved. A whole number is a real answer
 * the moment it exists, so it is committed at once, clamped to the bounds (an
 * out-of-range one snaps in view rather than sitting on screen as something the
 * page will not save). What stays a draft is exactly what is not yet an answer:
 * an empty field, a decimal, a lone minus sign — and blur settles those, with
 * the fallback for an empty one. The parent still only hears a number that
 * differs from the one it holds.
 */
function BoundedDayInput({ id, label, helperText, min, max, fallback, value, onChange }) {
  const [draft, setDraft] = useState(String(value));
  // Re-sync when the value arrives from outside — e.g. the Edit form finishing
  // its load. Our own commits set `draft` first, so this is then a no-op.
  useEffect(() => {
    setDraft(String(value));
  }, [value]);

  const commit = () => {
    const n = Math.round(Number(draft));
    const fixed =
      draft.trim() !== '' && Number.isFinite(n) ? Math.min(max, Math.max(min, n)) : fallback;
    setDraft(String(fixed));
    if (fixed !== value) onChange(fixed);
  };

  const handleChange = (e) => {
    const raw = e.target.value;
    // Not an answer yet (empty, "3.", "-"): keep typing, blur will settle it.
    if (!/^-?\d+$/.test(raw.trim())) {
      setDraft(raw);
      return;
    }
    const fixed = Math.min(max, Math.max(min, Number(raw)));
    setDraft(String(fixed));
    if (fixed !== value) onChange(fixed);
  };

  return (
    <NumberInput
      id={id}
      label={label}
      helperText={helperText}
      min={min}
      max={max}
      step={1}
      value={draft === '' ? '' : Number(draft)}
      onChange={handleChange}
      onBlur={commit}
    />
  );
}

export default function ReservationRulesFields({
  idPrefix,
  reservationUnit = 'DAY',
  setReservationUnit,
  reservationMaxDays = 1,
  setReservationMaxDays,
  reservationHorizonDays = 90,
  setReservationHorizonDays,
  reservationMaxActivePerMember = 10,
  setReservationMaxActivePerMember,
  reservationAsksPhone = false,
  setReservationAsksPhone = () => {},
  reservationMinMinutes = 60,
  setReservationMinMinutes,
  reservationMaxMinutes = 180,
  setReservationMaxMinutes,
  openingHours = {},
  setOpeningHours,
  // Undefined falls through to OpeningHoursField's own stable no-op default;
  // an inline `() => {}` here would be a new function every render.
  setOpeningHoursValid,
  rentalWeekdays = [],
  setRentalWeekdays,
  theeemeColor01,
  theeemeColor06,
}) {
  const { t } = useTranslation();
  // Whether the hours field can hand over what is on screen. While it cannot (the
  // JSON does not parse) its own error speaks, and the warning below stays quiet.
  const [hoursReadable, setHoursReadable] = useState(true);
  const reportValidity = useCallback(
    (valid) => {
      setHoursReadable(valid);
      setOpeningHoursValid?.(valid);
    },
    [setOpeningHoursValid]
  );

  return (
    <>
      <RadioOptionGroup
        idPrefix={`${idPrefix}-reservation-unit`}
        name={`${idPrefix}-reservation-unit`}
        label={t('reservation.unitLabel')}
        options={[
          { value: 'DAY', label: t('reservation.unitDay') },
          { value: 'HOUR', label: t('reservation.unitHour') },
        ]}
        value={reservationUnit}
        onChange={setReservationUnit}
      />
      <BoundedDayInput
        id={`${idPrefix}-reservation-horizon-days`}
        label={t('reservation.horizonLabel')}
        helperText={t('reservation.horizonHelper')}
        min={1}
        max={365}
        fallback={90}
        value={reservationHorizonDays}
        onChange={setReservationHorizonDays}
      />
      <BoundedDayInput
        id={`${idPrefix}-reservation-max-active`}
        label={t('reservation.maxActiveLabel')}
        helperText={t('reservation.maxActiveHelper')}
        min={1}
        max={50}
        fallback={10}
        value={reservationMaxActivePerMember}
        onChange={setReservationMaxActivePerMember}
      />
      {/* Whether the request page offers an optional contact phone. Title and
          explanation are one label, as in the other inline switches. */}
      <ToggleButton
        id={`${idPrefix}-reservation-asks-phone`}
        variant="inline"
        label={t('reservation.asksPhoneFull')}
        checked={reservationAsksPhone}
        onChange={(val) => setReservationAsksPhone(!val)}
        theme={
          theeemeColor01 ? { '--toggle-button-color': `var(--color-${theeemeColor01})` } : undefined
        }
      />
      {reservationUnit === 'HOUR' ? (
        <>
          <BoundedDayInput
            id={`${idPrefix}-reservation-min-minutes`}
            label={t('reservation.minMinutesLabel')}
            helperText={t('reservation.minMinutesHelper')}
            min={1}
            max={720}
            fallback={60}
            value={reservationMinMinutes}
            onChange={setReservationMinMinutes}
          />
          <BoundedDayInput
            id={`${idPrefix}-reservation-max-minutes`}
            label={t('reservation.maxMinutesLabel')}
            helperText={t('reservation.maxMinutesHelper')}
            min={1}
            max={720}
            fallback={180}
            value={reservationMaxMinutes}
            onChange={setReservationMaxMinutes}
          />
          <OpeningHoursField
            id={`${idPrefix}-opening-hours`}
            value={openingHours}
            onChange={setOpeningHours}
            onValidityChange={reportValidity}
          />
          {/* An hourly space with no opening hours is closed every day, and nothing
              else says so: the member sees an all-grey calendar. It does not block the
              save — someone may be about to write the hours. */}
          {hoursReadable && !hasOpeningHours(openingHours) && (
            <Notification type="alert" size="small" style={{ marginTop: 'var(--spacing-s)' }}>
              {t('openingHours.noneOpen')}
            </Notification>
          )}
        </>
      ) : (
        <>
          <BoundedDayInput
            id={`${idPrefix}-reservation-max-days`}
            label={t('reservation.maxDaysLabel')}
            helperText={t('reservation.maxDaysHelper')}
            min={1}
            max={7}
            fallback={1}
            value={reservationMaxDays}
            onChange={setReservationMaxDays}
          />
          <WeekdayChips
            labelId={`${idPrefix}-reservation-weekdays-label`}
            labelKey="reservation.weekdaysLabel"
            helperKey="reservation.weekdaysHelper"
            weekdays={rentalWeekdays}
            setWeekdays={setRentalWeekdays}
            color01={theeemeColor01}
            color06={theeemeColor06}
          />
        </>
      )}
    </>
  );
}
