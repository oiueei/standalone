/**
 * Shared constants for thing types used across the frontend.
 * Display labels are handled by i18n — use t('types.GIFT_THING') etc.
 */

export const TYPE_VALUES = [
  'GIFT_THING', 'SELL_THING', 'ORDER_THING', 'RENT_THING', 'LEND_THING', 'SHARE_THING', 'EVENT_THING', 'WISH_THING', 'ASSET_THING', 'SWAP_THING', 'APPOINTMENT_THING',
];

export const SHARE_TYPE = 'SHARE_THING';
export const SWAP_TYPE = 'SWAP_THING';
export const EVENT_TYPE = 'EVENT_THING';
export const WISH_TYPE = 'WISH_THING';
export const ASSET_TYPE = 'ASSET_THING';
export const APPOINTMENT_TYPE = 'APPOINTMENT_THING';

export const DATE_TYPES = ['LEND_THING', 'RENT_THING', 'ASSET_THING', 'APPOINTMENT_THING'];
export const ORDER_TYPE = 'ORDER_THING';
export const FEE_TYPES = ['SELL_THING', 'RENT_THING', 'ORDER_THING'];

export const DETAIL_TYPES = ['GIFT_THING', 'SELL_THING', 'LEND_THING', 'SHARE_THING'];

export const AVAILABILITY_VALUES = ['IMMEDIATE', 'NEXT_WEEK', 'END_OF_MONTH', 'NEXT_MONTH'];

export const CONDITION_VALUES = ['NEW', 'GOOD', 'FAIR', 'USED', 'WELL_USED', 'ALMOST_JUNK'];

export const TAG_THEMES = {
  taken: { '--tag-background': '#fff4e5', '--tag-color': '#b54708' },
  inactive: { '--tag-background': '#e8e8e8', '--tag-color': '#525252' },
  pending: { '--tag-background': '#fff4e5', '--tag-color': '#b54708' },
};
