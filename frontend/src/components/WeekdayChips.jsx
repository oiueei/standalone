import { useTranslation } from 'react-i18next';
import useTheeeme from '../hooks/useTheeeme';
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
 * A **selected** chip is filled with the palette in force (`useTheeeme`): `color_01`
 * fills it, `color_06` is its text — the same pairing the primary button
 * uses, so the contrast is the one `paletteContrast.test.js` already guarantees
 * (>= 4.5:1 across all 12 curated palettes). When `color_06` is absent the text
 * falls back to white; that only reads on a dark `color_01` (bus, tram), and every
 * palette that can be in force has both.
 */
export default function WeekdayChips({
  labelId,
  labelKey,
  helperKey,
  weekdays = [],
  setWeekdays = () => {},
}) {
  const { t, i18n } = useTranslation();
  const { tc } = useTheeeme();
  const color01 = tc.color_01;
  const color06 = tc.color_06;

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
