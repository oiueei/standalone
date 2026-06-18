/**
 * Shared constants for thing types used across the frontend.
 * Display labels are handled by i18n — use t('types.GIFT_THING') etc.
 */

export const TYPE_VALUES = [
  'GIFT_THING', 'SELL_THING', 'ORDER_THING', 'RENT_THING', 'LEND_THING', 'SHARE_THING', 'WISH_THING', 'SWAP_THING',
];

export const SHARE_TYPE = 'SHARE_THING';
export const SWAP_TYPE = 'SWAP_THING';
export const WISH_TYPE = 'WISH_THING';

// Wish "Contestar" answer kinds. HAVE_THIS reuses the publish-listing flow;
// KNOW_WHERE / CAN_MAKE open a short form (RespondWishPage), keyed by slug.
export const WISH_RESPONSE_KINDS = ['HAVE_THIS', 'KNOW_WHERE', 'CAN_MAKE'];
export const WISH_KIND_SLUGS = { KNOW_WHERE: 'know-where', CAN_MAKE: 'can-make' };
export const WISH_KIND_BY_SLUG = { 'know-where': 'KNOW_WHERE', 'can-make': 'CAN_MAKE' };
export const WISH_KIND_I18N = {
  HAVE_THIS: 'haveThis',
  KNOW_WHERE: 'knowWhere',
  CAN_MAKE: 'canMake',
};

export const DATE_TYPES = ['LEND_THING', 'RENT_THING'];
export const ORDER_TYPE = 'ORDER_THING';
export const FEE_TYPES = ['SELL_THING', 'RENT_THING', 'ORDER_THING'];

export const DETAIL_TYPES = ['GIFT_THING', 'SELL_THING', 'LEND_THING', 'SHARE_THING'];

export const AVAILABILITY_VALUES = ['IMMEDIATE', 'NEXT_WEEK', 'END_OF_MONTH', 'NEXT_MONTH'];

export const CONDITION_VALUES = ['NEW', 'GOOD', 'FAIR', 'USED', 'WELL_USED', 'ALMOST_JUNK'];

// Collection allow-lists per mode/album combination, shared by the Create and
// Edit collection forms. SWAP_THING is excluded everywhere because it requires
// `is_swap=True`, which forces the value via its flag.
export const PROPRIETARY_TYPES = [
  'GIFT_THING', 'SELL_THING', 'ORDER_THING', 'RENT_THING', 'LEND_THING',
];
export const COMMUNITY_TYPES = [
  'GIFT_THING', 'SELL_THING', 'ORDER_THING', 'RENT_THING', 'LEND_THING',
  'SHARE_THING', 'WISH_THING',
];
export const COMMUNITY_MINIMALIST_TYPES = ['GIFT_THING', 'SHARE_THING'];

// is_swap, is_share and PROPRIETARY+album each force a single allowed type via
// their flag — the multi-select still renders, but locked and pre-filled.
export const isLockedToSingleType = ({ mode, isSwap, isShare, isMinimalist }) => (
  (mode === 'PROPRIETARY' && isMinimalist)
  || (mode === 'COMMUNITY' && (isSwap || isShare))
);

// The set of thing types valid for a given mode/flag combination. Locked
// combinations (swap, share, PROPRIETARY+album) collapse to a single type.
export const allowedTypesFor = ({ mode, isSwap, isShare, isMinimalist }) => {
  if (mode === 'PROPRIETARY') return isMinimalist ? ['GIFT_THING'] : PROPRIETARY_TYPES;
  if (isSwap) return ['SWAP_THING'];
  if (isShare) return ['SHARE_THING'];
  return isMinimalist ? COMMUNITY_MINIMALIST_TYPES : COMMUNITY_TYPES;
};

// When the mode/flags change, keep the selection the user already made instead of
// wiping it (P1-5): locked combinations snap to their forced single type, while
// unlocked ones keep the still-valid intersection of the previous selection.
export const reconcileAllowedTypes = (prev, next) => {
  const valid = allowedTypesFor(next);
  if (isLockedToSingleType(next)) return [...valid];
  return prev.filter((t) => valid.includes(t));
};

export const TAG_THEMES = {
  taken: { '--tag-background': '#fff4e5', '--tag-color': '#b54708' },
  inactive: { '--tag-background': '#e8e8e8', '--tag-color': '#525252' },
  pending: { '--tag-background': '#fff4e5', '--tag-color': '#b54708' },
  // Owner-defined collection tags assigned to a thing — neutral bussi tint,
  // distinct from the amber status tags and grey inactive tag.
  custom: { '--tag-background': '#eef0ff', '--tag-color': '#0000bf' },
};
