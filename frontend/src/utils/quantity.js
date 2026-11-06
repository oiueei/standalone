/**
 * A thing's name as a request for several of it writes it: "6 × Arduino starter kit"
 * (`common.quantityTimes`). With one — or a payload from before the quantity existed —
 * it is the name as it was. Shared by the two request lists, the inbox and the thing's
 * own list of bookings, so the four read the same.
 */
export const withQuantity = (t, headline, quantity) =>
  Number(quantity) > 1
    ? t('common.quantityTimes', { count: Number(quantity), headline })
    : headline;
