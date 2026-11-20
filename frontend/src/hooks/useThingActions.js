import { useTranslation } from 'react-i18next';
import { DATE_TYPES } from '../constants/things';
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
 * - `joinCollectionCode` / `joinedGroupName` / `onJoined` — forwarded to
 *   {@link useThingBooking}: the one group a refused "not a member" request may
 *   join the reader to before asking again.
 * - `onThingChange` / `setToast` / `initialRequested`
 *   / `fetchOnEndless` / `activateSuccessMessage` / `collectionCode` — forwarded to
 *   {@link useThingBooking} (card vs page seeds differ).
 *
 * `bookingKeepsStatus` is derived here (`needsPage || is_endless`, identical in
 * both views) so callers don't repeat it.
 *
 * Returns everything {@link useThingBooking} returns, plus: `isOwner`,
 * `canManage`, `isCollectionOwner`, `isDateBased`, `needsPage`,
 * `canDelete`, `hasPendingBookings`, `showButton`, `isMine`, `buttonDisabled`,
 * `loginButtonDisabled`, `buttonLabel`.
 *
 * **`canManage`** is the backend's `thing.can_manage` — true for the owner, or
 * a curator of a PROPRIETARY collection the thing sits in, who runs its
 * catalogue and bookings the same as the founder (2026-09). The owner-button
 * matrix, the delete button and the "hide the reserve button from staff" guard
 * all key on it now, not on `isOwner`. `isOwner` is kept for the few genuinely
 * owner-only bits (the "transfer ownership?" confirm copy).
 */
export default function useThingActions(
  thing,
  userCode,
  {
    isPaused = false,
    canAct = true,
    loginToAct = false,
    collectionOwner = null,
    onThingChange = () => {},
    setToast = () => {},
    initialRequested = false,
    fetchOnEndless = false,
    activateSuccessMessage = null,
    collectionCode = null,
    joinCollectionCode = null,
    joinedGroupName = '',
    onJoined,
  } = {}
) {
  const { t } = useTranslation();

  const isOwner = thing?.owner === userCode;
  // The backend field; `isOwner` is the floor for a payload that predates it.
  const canManage = thing?.can_manage === true || isOwner;
  const isDateBased = DATE_TYPES.includes(thing?.type);
  // `needsPage` drives whether the reserve button navigates to a follow-up form
  // (date-based picks dates) or POSTs directly. `bookingKeepsStatus`
  // drives whether accepting a hold keeps the thing circulating — endless GIFT/SELL
  // keep their status but reserve via a direct POST, so the two must stay separate.
  const needsPage = isDateBased;
  const bookingKeepsStatus = needsPage || !!thing?.is_endless;
  // Accepting hands the thing over for good: a GIFT or SELL that isn't endless.
  // `accept_booking` flips it INACTIVE, adds the requester to `deal` and writes a
  // ThingTransfer, so the owner no longer has it. A loan or rental comes back and
  // an endless gift never runs out, so neither transfers anything.
  //
  // This is the inverse of `bookingKeepsStatus` by construction, and it MUST be
  // returned below: `ThingPage` has been destructuring it since it was written,
  // the hook never provided it, so it read `undefined` and the "Transfer
  // ownership?" confirm — copy, three locales and all — has never once rendered.
  const acceptTransfersOwnership = !bookingKeepsStatus;
  const isCollectionOwner = (collectionOwner || thing?.collection_owner) === userCode;
  const canDelete = isCollectionOwner || canManage;

  const booking = useThingBooking(thing, {
    canManage,
    onThingChange,
    setToast,
    initialRequested,
    fetchOnEndless,
    bookingKeepsStatus,
    activateSuccessMessage,
    collectionCode,
    joinCollectionCode,
    joinedGroupName,
    onJoined,
  });
  const { submitting, requested, bookings } = booking;

  const hasPendingBookings = bookings.some((b) => b.status === 'PENDING');
  // `canAct` covers a member; `loginToAct` shows the buttons to an anonymous
  // visitor on a public collection (each click routes to the join page).
  // Hidden from anyone who manages the thing — staff answer requests, they
  // don't make them.
  const showButton = (canAct || loginToAct) && !canManage && thing?.status !== 'INACTIVE';
  // The current viewer holds the pending booking (locally requested, or returned
  // by the serializer). Only they see "waiting"; everyone else sees the reason
  // the disabled button can't be used — so the cause travels with the control.
  const isMine = requested || !!thing?.my_pending_booking;
  // NB: a pending booking of the viewer's own does NOT disable the button here.
  // That term was SHARE-only (one transfer request per person) and left with it —
  // a date-based thing must stay requestable for a second, non-overlapping range.
  const buttonDisabled = isPaused || thing?.status === 'TAKEN' || submitting || requested;
  // Anonymous (loginToAct) buttons only gate on pause/TAKEN — the click routes to
  // the join page, so submitting/requested don't apply.
  const loginButtonDisabled = isPaused || thing?.status === 'TAKEN';
  const buttonLabel = submitting
    ? t('common.sending')
    : isMine
      ? t('thingCard.waitingForConfirmation')
      : thing?.status === 'TAKEN'
        ? t('thingCard.notAvailable')
        : isPaused
          ? t('thingCard.paused')
          : t(`thingCard.action.${thing?.type}`, { defaultValue: t('thingCard.hold') });

  return {
    ...booking,
    isOwner,
    canManage,
    isCollectionOwner,
    isDateBased,
    needsPage,
    acceptTransfersOwnership,
    canDelete,
    hasPendingBookings,
    showButton,
    isMine,
    buttonDisabled,
    loginButtonDisabled,
    buttonLabel,
  };
}
