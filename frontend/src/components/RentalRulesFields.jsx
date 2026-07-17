import { Select } from 'hds-react';
import { useTranslation } from 'react-i18next';
import {
  RENTAL_DURATION_PRESETS,
  WEEKDAY_VALUES,
  durationLabel,
  weekdayLabel,
  weekdayNarrow,
} from '../utils/rental';

/**
 * The rental-rules fields (#7) for a collection that lends or rents items: the
 * fixed-durations multi-select plus the pickup/return weekday chip row.
 *
 * Extracted from CollectionForm so it can live inside the collection form's
 * "More options" accordion (O1) while the identity cluster stays visible. A
 * swap/share-only collection can't hold LEND/RENT things, so the pages render
 * this only when neither flag is on (they already know `isSwap`/`isShare`).
 *
 * Controlled: value + setter owned by the page. `idPrefix` is
 * `create-collection` / `edit-collection`; `theeemeColor01` is the theeeme
 * `color_01` token name (the selected weekday chip's fill).
 */
export default function RentalRulesFields({
  idPrefix,
  rentalDurations = [],
  setRentalDurations = () => {},
  rentalWeekdays = [],
  setRentalWeekdays = () => {},
  theeemeColor01,
}) {
  const { t, i18n } = useTranslation();

  return (
    <>
      <Select
        language="en"
        multiSelect
        id={`${idPrefix}-rental-durations`}
        texts={{
          label: t('rental.durationsLabel'),
          placeholder: t('rental.durationsPlaceholder'),
          assistive: t('rental.durationsHelper'),
        }}
        options={RENTAL_DURATION_PRESETS.map((p) => ({ label: t(p.key), value: String(p.days) }))}
        value={rentalDurations.map((d) => ({ label: durationLabel(d, t), value: String(d) }))}
        onChange={(opts) => setRentalDurations(opts.map((o) => Number(o.value)).sort((a, b) => a - b))}
      />
      <div className="weekday-field">
        <p className="weekday-field-label" id={`${idPrefix}-rental-weekdays-label`}>
          {t('rental.weekdaysLabel')}
        </p>
        <div
          className="weekday-chips"
          role="group"
          aria-labelledby={`${idPrefix}-rental-weekdays-label`}
        >
          {WEEKDAY_VALUES.map((w) => {
            const selected = rentalWeekdays.includes(w);
            const full = weekdayLabel(w, i18n.language);
            return (
              <button
                key={w}
                type="button"
                className={`weekday-chip${selected ? ' selected' : ''}`}
                aria-pressed={selected}
                aria-label={full}
                title={full}
                onClick={() =>
                  setRentalWeekdays(
                    selected
                      ? rentalWeekdays.filter((x) => x !== w)
                      : [...rentalWeekdays, w].sort((a, b) => a - b)
                  )
                }
                style={selected && theeemeColor01
                  ? { backgroundColor: `var(--color-${theeemeColor01})`, borderColor: `var(--color-${theeemeColor01})`, color: 'var(--color-white)' }
                  : undefined}
              >
                {weekdayNarrow(w, i18n.language)}
              </button>
            );
          })}
        </div>
        <p className="weekday-field-helper">{t('rental.weekdaysHelper')}</p>
      </div>
    </>
  );
}
