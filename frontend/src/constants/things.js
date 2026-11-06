/**
 * Shared constants for thing types used across the frontend.
 * Display labels are handled by i18n — use t('types.GIFT_THING') etc.
 */

/**
 * How many identical ones a shed's space has, as it goes to the server: a whole number
 * from 1 to 20, whatever is left in the field (empty, a decimal, out of range) —
 * `Thing.units`.
 */
export const clampUnits = (value) => {
  const n = Math.round(Number(value));
  return Number.isFinite(n) && n >= 1 ? Math.min(20, n) : 1;
};

/** Whether a thing of this kind of collection can have several identical ones: a shed's
 *  space (booked at the same time) and a library's thing (lent out at the same time). */
export const kindHasUnits = (kind) => kind === 'SHED' || kind === 'LIBRARY';

/** A price or a deposit times how many are asked for, written the way the amount came
 *  ("5.00" gives "30.00", "5" gives "30"): the total the request page shows. */
export const amountTimes = (value, count) => {
  const total = Number(value) * count;
  return String(value).includes('.') ? total.toFixed(2) : String(Math.round(total * 100) / 100);
};

// Types booked by date. RESERVE is date-based too (pickup date + duration), so
// its reserve button navigates to RequestThingPage like LEND/RENT.
export const DATE_TYPES = ['LEND_THING', 'RENT_THING', 'RESERVE_THING'];

// A rental has a condition and a place like a loan does (and its availability, live,
// from the calendar), so RENT joins LEND here.
export const DETAIL_TYPES = [
  'GIFT_THING',
  'SELL_THING',
  'LEND_THING',
  'RENT_THING',
  'RESERVE_THING',
];

export const AVAILABILITY_VALUES = ['IMMEDIATE', 'NEXT_WEEK', 'END_OF_MONTH', 'NEXT_MONTH'];

export const CONDITION_VALUES = ['NEW', 'GOOD', 'FAIR', 'USED', 'WELL_USED', 'ALMOST_JUNK'];

// The verbs each kind of collection holds, the browser's copy of the server's
// `KIND_THING_TYPES`: a stall gives or sells, a library lends or rents out, a shed
// books. A collection's `allowed_thing_types` is always within its kind's.
export const KIND_THING_TYPES = {
  STALL: ['GIFT_THING', 'SELL_THING'],
  LIBRARY: ['LEND_THING', 'RENT_THING'],
  SHED: ['RESERVE_THING'],
};

/**
 * Whether a price or a deposit is something to show. The API sends them as text
 * (`"0.00"`), and any non-empty text is truthy in JS, so a bare `thing.deposit &&`
 * showed "Deposit. 0.00 €". The rule is the one `deriveThingType` uses: only an
 * amount above zero counts; `null`, `""` and `"0.00"` do not. The forms do not use
 * it: a zero typed there is still seen and saved.
 */
export function hasAmount(value) {
  return Number(value) > 0;
}

/**
 * The verb a thing takes in a `kind` collection: it follows the price. A stall gives
 * (no price) or sells (a price), a library lends or rents out, a shed books. The
 * browser's copy of the server's `derive_thing_type`, used to decide what the form
 * shows and what the policy is asked about — the server puts the verb itself, and
 * the form never sends one.
 */
export function deriveThingType(kind, fee) {
  const [free, paid] = KIND_THING_TYPES[kind] || KIND_THING_TYPES.STALL;
  return paid && hasAmount(fee) ? paid : free;
}

/** The kind of collection a verb belongs to (`undefined` for none). */
export function kindOfThingType(type) {
  return Object.keys(KIND_THING_TYPES).find((kind) => KIND_THING_TYPES[kind].includes(type));
}

// The status tags' colours. Tokens wherever HDS has the colour; the amber pair
// (requested / pending questions) stays hex because HDS has no amber text
// colour of this contrast on a light amber ground.
export const TAG_THEMES = {
  taken: { '--tag-background': '#fff4e5', '--tag-color': '#b54708' },
  inactive: { '--tag-background': 'var(--color-black-10)', '--tag-color': 'var(--color-black-70)' },
  pending: { '--tag-background': '#fff4e5', '--tag-color': '#b54708' },
  // Owner-defined collection tags assigned to a thing — neutral bussi tint,
  // distinct from the amber status tags and grey inactive tag.
  custom: { '--tag-background': 'var(--color-bus-light)', '--tag-color': 'var(--color-bus)' },
  // "New" signal — summer yellow + black text, AA contrast,
  // warm rather than alarming.
  fresh: { '--tag-background': 'var(--color-summer)', '--tag-color': 'var(--color-black-90)' },
};
