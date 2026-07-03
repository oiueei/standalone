// Rental-rule helpers (#7). Collections can offer a set of fixed rental lengths
// (in days) and restrict pickup/return to certain weekdays.

// Day-length presets an owner can offer, each with an i18n label key.
export const RENTAL_DURATION_PRESETS = [
  { days: 1, key: 'rental.d1' },
  { days: 2, key: 'rental.d2' },
  { days: 3, key: 'rental.d3' },
  { days: 7, key: 'rental.w1' },
  { days: 14, key: 'rental.w2' },
  { days: 21, key: 'rental.w3' },
  { days: 30, key: 'rental.m1' },
];

const KEY_BY_DAYS = Object.fromEntries(RENTAL_DURATION_PRESETS.map((p) => [p.days, p.key]));

// i18n label for a stored day-length (falls back to "{n}" for any non-preset value).
export const durationLabel = (days, t) => (KEY_BY_DAYS[days] ? t(KEY_BY_DAYS[days]) : String(days));

// Weekday values in Python's numbering (0=Mon … 6=Sun), matching the backend.
export const WEEKDAY_VALUES = [0, 1, 2, 3, 4, 5, 6];

// Localised weekday name for a Python weekday index. 2024-01-01 was a Monday, so
// we offset from it — no need for 49 hand-translated weekday strings.
export const weekdayLabel = (pyWeekday, lang) =>
  new Date(2024, 0, 1 + pyWeekday).toLocaleDateString(lang, { weekday: 'long' });

// Narrow single-letter weekday for the chip face (es → L M X J V S D). The full
// name still rides along as the chip's aria-label / title for accessibility.
export const weekdayNarrow = (pyWeekday, lang) =>
  new Date(2024, 0, 1 + pyWeekday).toLocaleDateString(lang, { weekday: 'narrow' });

// JS Date.getDay() (0=Sun … 6=Sat) → Python weekday (0=Mon … 6=Sun).
export const jsToPyWeekday = (jsDay) => (jsDay + 6) % 7;

// Date + N days (returns a new Date at local midnight).
export const addDays = (date, n) => {
  const d = new Date(date);
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + n);
  return d;
};
