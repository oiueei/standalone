import { useTranslation } from 'react-i18next';
import { WEEKDAY_VALUES, weekdayLabel, weekdayNarrow } from '../utils/rental';

/**
 * The `[L M X J V S D]` weekday toggle row shared by the Availability page of a
 * library (pickup / return days), the same page of a shed (days the space is open) and
 * the network point's page. Only the label copy and the label `id` differ.
 *
 * Accessible toggle `<button>`s: `aria-pressed`, the full weekday name as
 * `aria-label` / `title`, the narrow single letter as the visible face. Values
 * are Python weekday numbers (0=Mon … 6=Sun) — what the backend stores — and are
 * kept sorted however the chips were clicked. Controlled: `weekdays` +
 * `setWeekdays` are owned by the caller.
 *
 * `color01` / `color06` are theeeme token names for a **selected** chip:
 * `color01` fills it, `color06` is its text — the same pairing the primary button
 * uses, so the contrast is the one `paletteContrast.test.js` already guarantees
 * (>= 4.5:1 across all 12 curated palettes). When `color06` is absent the text
 * falls back to white; that only reads on a dark `color01` (bus, tram), so
 * callers with a theeeme in hand should always pass it.
 */
export default function WeekdayChips({
  labelId,
  labelKey,
  helperKey,
  weekdays = [],
  setWeekdays = () => {},
  color01,
  color06,
}) {
  const { t, i18n } = useTranslation();

  return (
    <div className="weekday-field">
      <p className="weekday-field-label" id={labelId}>
        {t(labelKey)}
      </p>
      <div className="weekday-chips" role="group" aria-labelledby={labelId}>
        {WEEKDAY_VALUES.map((w) => {
          const selected = weekdays.includes(w);
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
                setWeekdays(
                  selected
                    ? weekdays.filter((x) => x !== w)
                    : [...weekdays, w].sort((a, b) => a - b)
                )
              }
              style={
                selected && color01
                  ? {
                      backgroundColor: `var(--color-${color01})`,
                      borderColor: `var(--color-${color01})`,
                      color: color06 ? `var(--color-${color06})` : 'var(--color-white)',
                    }
                  : undefined
              }
            >
              {weekdayNarrow(w, i18n.language)}
            </button>
          );
        })}
      </div>
      <p className="weekday-field-helper">{t(helperKey)}</p>
    </div>
  );
}
