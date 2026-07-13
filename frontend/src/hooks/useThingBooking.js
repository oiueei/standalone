import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { DATE_TYPES, SWAP_TYPE } from '../constants/things';
import { apiFetch, extractApiError } from '../services/api';

/**
 * Booking/reservation engine shared by ThingPage and ThingLinkbox.
 *
 * Both views duplicated the same reservation state, the owner-calendar fetch and
 * the three async handlers (request a hold, reactivate, accept/reject a booking).
 * This hook owns all of it; the two views keep only their own JSX and the small
 * behavioural differences are passed in as options (so the rendered behaviour is
 * unchanged for each consumer).
 *
 * The calendar fetch is now guarded by an `AbortController` and re-runs by
 * `thing.code` — an in-flight fetch for a previous thing can no longer land its
 * result on a newer one.
 *
 * Options:
 * - `isOwner`             — gates the owner-calendar fetch.
 * - `onThingChange(patch)`— apply a partial update to the underlying thing
 *                           (ThingPage feeds `setThing`, ThingLinkbox `onUpdateThing`).
 * - `setToast`            — toast setter from the consuming view.
 * - `initialActivePending`— initial active pending booking code (ThingLinkbox seeds
 *                           it from `thing.pending_booking`; ThingPage starts null).
 * - `initialRequested`    — initial "already requested" flag (ThingLinkbox folds the
 *                           SHARE pending-booking in here; ThingPage starts false).
 * - `fetchOnEndless`      — also fetch the calendar for endless GIFT/SELL (ThingLinkbox).
 * - `bookingKeepsStatus`  — when true, accept/reject keeps `thing.status` (date/order/
 *                           swap/endless flows); when false it flips it (GIFT/SELL).
 * - `activateSuccessMessage` — toast shown after a successful reactivate (ThingPage only).
 * - `collectionCode`      — the collection the requester is browsing, sent with the
 *                           request. A thing can live in several, so this is what
 *                           decides which one the owner's notification belongs to
 *                           (the backend approximates only when it's absent — the
 *                           standalone /things/:code page has no collection).
 *
 * Returns `{ submitting, requested, bookingAction, bookings, activePendingCode,
 * handleRequest, handleActivate, handleBookingAction }`.
 */
export default function useThingBooking(thing, {
  isOwner = false,
  onThingChange = () => {},
  setToast = () => {},
  initialActivePending = null,
  initialRequested = false,
  fetchOnEndless = false,
  bookingKeepsStatus = false,
  activateSuccessMessage = null,
  collectionCode = null,
} = {}) {
  const { t } = useTranslation();

  const [submitting, setSubmitting] = useState(false);
  const [requested, setRequested] = useState(initialRequested);
  const [bookingAction, setBookingAction] = useState(null);
  const [bookings, setBookings] = useState([]);
  const [activePendingCode, setActivePendingCode] = useState(initialActivePending);
  const [activating, setActivating] = useState(false);
  const [bookingActionVerb, setBookingActionVerb] = useState(null);

  // Synchronous re-entrancy locks: `disabled`/`submitting` only updates after a
  // re-render, so a fast double-click could fire two requests before that lands.
  const requestLockRef = useRef(false);
  const activateLockRef = useRef(false);
  const bookingLockRef = useRef(false);

  const code = thing?.code;
  const type = thing?.type;
  const status = thing?.status;
  const isEndless = thing?.is_endless;
  const isDateBased = DATE_TYPES.includes(type);
  const isSwap = type === SWAP_TYPE;

  useEffect(() => {
    const shouldFetch = isOwner
      && (isDateBased || isSwap || status === 'TAKEN' || (fetchOnEndless && isEndless));
    if (!shouldFetch || !code) return undefined;
    const controller = new AbortController();
    apiFetch(`/api/v1/things/${code}/calendar/`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (controller.signal.aborted) return;
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const future = data.filter((b) => {
          if (!b.end_date) return true; // GIFT/SELL: no dates, always current
          const d = new Date(b.end_date);
          d.setHours(0, 0, 0, 0);
          return d >= today;
        });
        const firstPending = future.find((b) => b.status === 'PENDING');
        setBookings(future);
        setActivePendingCode(firstPending?.code || null);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [code, status, isEndless, isOwner, isDateBased, isSwap, fetchOnEndless]);

  const handleRequest = async () => {
    if (requestLockRef.current) return;
    requestLockRef.current = true;
    setSubmitting(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${code}/request/`, {
        method: 'POST',
        body: JSON.stringify(collectionCode ? { collection_code: collectionCode } : {}),
      });
      if (res.ok) {
        setRequested(true);
        setToast({ type: 'success', message: t('thingPage.holdRequested') });
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else if (res.status === 400) {
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('thingPage.invalidRequest') });
      } else {
        setToast({ type: 'error', message: t('thingPage.errorSendingRequest') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
      requestLockRef.current = false;
    }
  };

  const handleActivate = async () => {
    if (activateLockRef.current) return;
    activateLockRef.current = true;
    setActivating(true);
    try {
      const res = await apiFetch(`/api/v1/things/${code}/activate/`, { method: 'POST' });
      if (res.ok) {
        onThingChange({ status: 'ACTIVE', deal: [] });
        if (activateSuccessMessage) {
          setToast({ type: 'success', message: activateSuccessMessage });
        }
      } else {
        setToast({ type: 'error', message: t('thingPage.errorReactivatingThing') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setActivating(false);
      activateLockRef.current = false;
    }
  };

  const handleBookingAction = async (action, bookingCode) => {
    if (bookingLockRef.current) return;
    bookingLockRef.current = true;
    const targetCode = bookingCode || activePendingCode;
    setBookingAction(targetCode);
    setBookingActionVerb(action);
    try {
      const res = await apiFetch(`/api/v1/bookings/${targetCode}/${action}/`, { method: 'POST' });
      if (res.ok) {
        if (action === 'accept') {
          const updated = bookings.map((b) => (b.code === targetCode ? { ...b, status: 'ACCEPTED' } : b));
          const nextPending = updated.find((b) => b.code !== targetCode && b.status === 'PENDING');
          setBookings(updated);
          setActivePendingCode(nextPending?.code || null);
          onThingChange(bookingKeepsStatus
            ? { pending_booking: nextPending?.code || null }
            : { status: 'INACTIVE', pending_booking: nextPending?.code || null });
        } else {
          const remaining = bookings.filter((b) => b.code !== targetCode);
          const nextPending = remaining.find((b) => b.status === 'PENDING');
          setBookings(remaining);
          setActivePendingCode(nextPending?.code || null);
          onThingChange(bookingKeepsStatus
            ? { pending_booking: nextPending?.code || null }
            : { status: 'ACTIVE', pending_booking: nextPending?.code || null });
        }
        setToast({ type: 'success', message: action === 'accept' ? t('thingPage.holdConfirmed') : t('thingPage.holdCancelled') });
      } else {
        setToast({ type: 'error', message: action === 'accept' ? t('thingPage.errorConfirmingHold') : t('thingPage.errorCancellingHold') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setBookingAction(null);
      setBookingActionVerb(null);
      bookingLockRef.current = false;
    }
  };

  return {
    submitting,
    requested,
    bookingAction,
    bookingActionVerb,
    activating,
    bookings,
    activePendingCode,
    handleRequest,
    handleActivate,
    handleBookingAction,
  };
}
