/**
 * Shared constants for thing types used across the frontend.
 */

export const TYPE_OPTIONS = [
  { label: 'Gift', value: 'GIFT_THING' },
  { label: 'Sale', value: 'SELL_THING' },
  { label: 'Order', value: 'ORDER_THING' },
  { label: 'Rental', value: 'RENT_THING' },
  { label: 'Lend', value: 'LEND_THING' },
  { label: 'Share', value: 'SHARE_THING' },
];

export const TYPE_LABELS = Object.fromEntries(
  TYPE_OPTIONS.map((o) => [o.value, o.label])
);

export const DATE_TYPES = ['LEND_THING', 'RENT_THING', 'SHARE_THING'];
export const ORDER_TYPE = 'ORDER_THING';
export const FEE_TYPES = ['SELL_THING', 'RENT_THING', 'ORDER_THING'];

export const DETAIL_TYPES = ['GIFT_THING', 'SELL_THING', 'LEND_THING', 'SHARE_THING'];

export const AVAILABILITY_OPTIONS = [
  { label: 'Immediate', value: 'IMMEDIATE' },
  { label: 'Next week', value: 'NEXT_WEEK' },
  { label: 'End of month', value: 'END_OF_MONTH' },
  { label: 'Next month', value: 'NEXT_MONTH' },
];

export const AVAILABILITY_LABELS = Object.fromEntries(
  AVAILABILITY_OPTIONS.map((o) => [o.value, o.label])
);

export const CONDITION_OPTIONS = [
  { label: 'New', value: 'NEW' },
  { label: 'Good condition', value: 'GOOD' },
  { label: 'Fair', value: 'FAIR' },
  { label: 'Used', value: 'USED' },
  { label: 'Well used', value: 'WELL_USED' },
  { label: 'Almost junk', value: 'ALMOST_JUNK' },
];

export const CONDITION_LABELS = Object.fromEntries(
  CONDITION_OPTIONS.map((o) => [o.value, o.label])
);

export const TAG_THEMES = {
  taken: { '--tag-background': '#fff4e5', '--tag-color': '#b54708' },
  inactive: { '--tag-background': '#e8e8e8', '--tag-color': '#525252' },
  unavailable: { '--tag-background': '#f5e6e6', '--tag-color': '#b01038' },
  pending: { '--tag-background': '#fff4e5', '--tag-color': '#b54708' },
};
