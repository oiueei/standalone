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

// Parse a value to a Date at LOCAL midnight. A 'YYYY-MM-DD' string is split into
// its components so it lands on the intended local day — new Date('YYYY-MM-DD')
// parses as UTC midnight and shifts back a day in UTC-negative timezones (the
// flagship rental return-date bug). A Date (or anything else) is normalised to
// local midnight.
export const parseLocalDate = (value) => {
  if (typeof value === 'string') {
    const m = /^(\d{4})-(\d{2})-(\d{2})/.exec(value);
    if (m) return new Date(Number(m[1]), Number(m[2]) - 1, Number(m[3]));
  }
  const d = new Date(value);
  d.setHours(0, 0, 0, 0);
  return d;
};

// Date + N days (returns a new Date at local midnight).
export const addDays = (date, n) => {
  const d = parseLocalDate(date);
  d.setDate(d.getDate() + n);
  return d;
};

// 'YYYY-MM-DD' for a Date, built from local components (never UTC).
export const toISODate = (d) => {
  const yyyy = d.getFullYear();
  const mm = String(d.getMonth() + 1).padStart(2, '0');
  const dd = String(d.getDate()).padStart(2, '0');
  return `${yyyy}-${mm}-${dd}`;
};

// Weekday rule: allowed when unrestricted, or the date's Python weekday is listed.
export const weekdayAllowed = (date, rentalWeekdays) =>
  rentalWeekdays.length === 0 || rentalWeekdays.includes(jsToPyWeekday(parseLocalDate(date).getDay()));

// Is `date` inside any blocked [start_date, end_date] period (both ends inclusive)?
export const isDateBlocked = (date, blockedPeriods) => {
  const d = parseLocalDate(date);
  return blockedPeriods.some((period) => {
    const start = parseLocalDate(period.start_date);
    const end = parseLocalDate(period.end_date);
    return d >= start && d <= end;
  });
};

// Any day in [pickup, pickup+len] (pickup → return, inclusive) already booked?
export const rangeBlocked = (pickup, len, blockedPeriods) => {
  for (let i = 0; i <= len; i += 1) {
    if (isDateBlocked(addDays(pickup, i), blockedPeriods)) return true;
  }
  return false;
};

// Disable a pickup day when it — or, once a length is chosen, its return day or any
// day in between — breaks the weekday rule or overlaps an existing booking. The
// return day is pickup + length: a one-week rental picked up on a Wednesday is
// returned the NEXT Wednesday, so a single allowed weekday stays satisfiable.
export const isPickupDisabled = (date, { rentalWeekdays, blockedPeriods, duration }) => {
  if (!weekdayAllowed(date, rentalWeekdays)) return true;
  if (isDateBlocked(date, blockedPeriods)) return true;
  if (duration) {
    const len = Number(duration);
    if (!weekdayAllowed(addDays(date, len), rentalWeekdays)) return true;
    if (rangeBlocked(date, len, blockedPeriods)) return true;
  }
  return false;
};

// Derived return date (ISO string) for a pickup date + fixed length in days.
export const derivedReturnDate = (pickup, days) => toISODate(addDays(pickup, Number(days)));
