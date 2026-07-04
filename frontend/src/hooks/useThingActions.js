import { useTranslation } from 'react-i18next';
import { DATE_TYPES, WISH_TYPE, SHARE_TYPE, SWAP_TYPE } from '../constants/things';
import useThingBooking from './useThingBooking';

/**
 * Owner-button-matrix + reservation view-model shared by ThingPage and
 * ThingLinkbox. Wraps {@link useThingBooking} (the calendar fetch + async
 * handlers) and adds the derived flags and the button label/disabled logic both
 * views computed identically inline.
 *
 * The genuine card-vs-page and member-vs-anonymous differences are passed as
 * options so the returned view-model is a faithful superset of what each view
 * built before:
 *
 * - `isPaused`        — collection is paused (ThingLinkbox on a paused
 *                       collection; ThingPage passes false — no pause there).
 * - `canAct`          — the viewer may act (ThingPage passes `isAuthenticated`;
 *                       ThingLinkbox defaults true and uses `loginToAct` below).
 * - `loginToAct`      — anonymous-on-public mode: buttons show but each click
 *                       should route to the collection's `/join` page.
 * - `collectionOwner` — explicit collection owner code (ThingLinkbox prop);
 *                       falls back to `thing.collection_owner`.
 * - `onThingChange` / `setToast` / `initialActivePending` / `initialRequested`
 *   / `fetchOnEndless` / `activateSuccessMessage` — forwarded to
 *   {@link useThingBooking} (card vs page seeds differ).
 *
 * `bookingKeepsStatus` is derived here (`needsPage || is_endless`, identical in
 * both views) so callers don't repeat it.
 *
 * Returns everything {@link useThingBooking} returns, plus: `isOwner`,
 * `isCollectionOwner`, `isWish`, `isShare`, `isSwap`, `isDateBased`, `needsPage`,
 * `canDelete`, `hasPendingBookings`, `showButton`, `swapMinimum`, `swapOwnCount`,
 * `swapMinimumNotMet`, `swapItemsMissing`, `isMine`, `buttonDisabled`,
 * `loginButtonDisabled`, `buttonLabel`.
 */
export default function useThingActions(thing, userCode, {
  isPaused = false,
  canAct = true,
  loginToAct = false,
  collectionOwner = null,
  onThingChange = () => {},
  setToast = () => {},
  initialActivePending = null,
  initialRequested = false,
  fetchOnEndless = false,
  activateSuccessMessage = null,
} = {}) {
  const { t } = useTranslation();

  const isOwner = thing?.owner === userCode;
  const isWish = thing?.type === WISH_TYPE;
  const isShare = thing?.type === SHARE_TYPE;
  const isSwap = thing?.type === SWAP_TYPE;
  const isDateBased = DATE_TYPES.includes(thing?.type);
  // `needsPage` drives whether the reserve button navigates to a follow-up form
  // (date-based picks dates, swap picks items) or POSTs directly. `bookingKeepsStatus`
  // drives whether accepting a hold keeps the thing circulating — endless GIFT/SELL
  // keep their status but reserve via a direct POST, so the two must stay separate.
  const needsPage = isDateBased || isSwap;
  const bookingKeepsStatus = needsPage || !!thing?.is_endless;
  const isCollectionOwner = (collectionOwner || thing?.collection_owner) === userCode;
  const canDelete = isCollectionOwner || (isOwner && (!isShare || thing?.transfer_count === 0));

  const booking = useThingBooking(thing, {
    isOwner,
    onThingChange,
    setToast,
    initialActivePending,
    initialRequested,
    fetchOnEndless,
    bookingKeepsStatus,
    activateSuccessMessage,
  });
  const { submitting, requested, bookings } = booking;

  const hasPendingBookings = bookings.some((b) => b.status === 'PENDING');
  // `canAct` covers a member; `loginToAct` shows the buttons to an anonymous
  // visitor on a public collection (each click routes to the join page).
  const showButton = (canAct || loginToAct) && !isOwner && thing?.status !== 'INACTIVE';
  const swapMinimum = thing?.collection_swap_minimum_items || 0;
  const swapOwnCount = thing?.my_swap_count_in_collection || 0;
  const swapMinimumNotMet = isSwap && swapMinimum > 0 && swapOwnCount < swapMinimum;
  const swapItemsMissing = swapMinimumNotMet ? swapMinimum - swapOwnCount : 0;
  // The current viewer holds the pending booking (locally requested, or returned
  // by the serializer). Only they see "waiting"; everyone else sees the reason
  // the disabled button can't be used — so the cause travels with the control.
  const isMine = requested || !!thing?.my_pending_booking;
  const buttonDisabled =
    isPaused
    || thing?.status === 'TAKEN'
    || submitting
    || requested
    || (isShare && !!thing?.my_pending_booking)
    || swapMinimumNotMet;
  // Anonymous (loginToAct) buttons only gate on pause/TAKEN — the click routes to
  // the join page, so submitting/requested/swap-minimum don't apply.
  const loginButtonDisabled = isPaused || thing?.status === 'TAKEN';
  const buttonLabel = submitting
    ? t('common.sending')
    : isMine
      ? t('thingCard.waitingForConfirmation')
      : thing?.status === 'TAKEN'
        ? t('thingCard.notAvailable')
        : isPaused
          ? t('thingCard.paused')
          : swapMinimumNotMet
            ? t('thingCard.needMoreItems', { count: swapItemsMissing })
            : t(`thingCard.action.${thing?.type}`, { defaultValue: t('thingCard.hold') });

  return {
    ...booking,
    isOwner,
    isCollectionOwner,
    isWish,
    isShare,
    isSwap,
    isDateBased,
    needsPage,
    canDelete,
    hasPendingBookings,
    showButton,
    swapMinimum,
    swapOwnCount,
    swapMinimumNotMet,
    swapItemsMissing,
    isMine,
    buttonDisabled,
    loginButtonDisabled,
    buttonLabel,
  };
}
