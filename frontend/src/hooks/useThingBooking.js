import { useEffect, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { DATE_TYPES } from '../constants/things';
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
 * - `canManage`           — gates the owner-calendar fetch (owner, or a
 *                           PROPRIETARY collection's curator — both get the
 *                           requester-detail calendar from the backend).
 * - `onThingChange(patch)`— apply a partial update to the underlying thing
 *                           (ThingPage feeds `setThing`, ThingLinkbox `onUpdateThing`).
 * - `setToast`            — toast setter from the consuming view.
 * - `initialRequested`    — initial "already requested" flag (ThingLinkbox seeds it
 *                           from the thing's pending booking; ThingPage starts false).
 * - `fetchOnEndless`      — also fetch the calendar for endless GIFT/SELL (ThingLinkbox).
 * - `bookingKeepsStatus`  — when true, accept/reject keeps `thing.status` (the
 *                           date-based and endless flows); when false it flips it
 *                           (GIFT/SELL).
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
export default function useThingBooking(
  thing,
  {
    canManage = false,
    onThingChange = () => {},
    setToast = () => {},
    initialRequested = false,
    fetchOnEndless = false,
    bookingKeepsStatus = false,
    activateSuccessMessage = null,
    collectionCode = null,
    joinCollectionCode = null,
    joinedGroupName = '',
    onJoined = () => {},
  } = {}
) {
  const { t } = useTranslation();

  const [submitting, setSubmitting] = useState(false);
  const [requested, setRequested] = useState(initialRequested);
  const [bookingAction, setBookingAction] = useState(null);
  const [bookings, setBookings] = useState([]);
  // The booking a manager's Confirm / Decline answers. It is known from the first
  // paint: the thing itself carries `pending_booking`, so the code never waits for
  // the owner's calendar. Once the calendar (or an accept/decline) has said which
  // booking is the first pending, that answer wins; `undefined` means "not said yet".
  const [decidedPendingCode, setActivePendingCode] = useState(undefined);
  const activePendingCode =
    decidedPendingCode !== undefined ? decidedPendingCode : thing?.pending_booking || null;
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
  // Manager-only (owner, or a PROPRIETARY collection's curator), and null for
  // everyone else — which is also the signal to fetch.
  const embeddedBookings = thing?.bookings;

  // The owner's bookings now ride along on the thing itself (serializer field
  // `bookings`, owner-only). Reading them costs no request at all, which is the
  // point: this effect used to GET /things/{code}/calendar/ once per card, so
  // an owner opening a 30-item lending library fired 30 parallel requests on
  // the page they visit most (DESIGN §7). The fetch stays as the fallback for
  // any caller whose thing came from somewhere that doesn't embed them.
  const seededCodeRef = useRef(null);

  useEffect(() => {
    const shouldLoad =
      canManage && (isDateBased || status === 'TAKEN' || (fetchOnEndless && isEndless));
    if (!shouldLoad || !code) return undefined;

    const futureOnly = (rows) =>
      rows.filter((b) => {
        if (!b.end_date) return true; // GIFT/SELL: no dates, always current
        const d = new Date(b.end_date);
        d.setHours(0, 0, 0, 0);
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        return d >= today;
      });

    const seed = (rows) => {
      const future = futureOnly(rows);
      setBookings(future);
      setActivePendingCode(future.find((b) => b.status === 'PENDING')?.code || null);
    };

    if (Array.isArray(embeddedBookings)) {
      // Seed once per thing, never on every re-render. The parent hands back a
      // fresh `thing` object after each accept/reject (setCollection maps a new
      // array), and re-seeding from it would overwrite the list that
      // `handleBookingAction` has just updated locally — the decision would
      // visibly undo itself.
      if (seededCodeRef.current !== code) {
        seededCodeRef.current = code;
        seed(embeddedBookings);
      }
      return undefined;
    }

    const controller = new AbortController();
    apiFetch(`/api/v1/things/${code}/calendar/`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        if (controller.signal.aborted) return;
        seed(data);
      })
      .catch(() => {});
    return () => controller.abort();
    // `embeddedBookings` is deliberately absent: the ref above owns re-seeding,
    // and depending on an array identity that changes every render would defeat it.
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [code, status, isEndless, canManage, isDateBased, fetchOnEndless]);

  const postRequest = () =>
    apiFetch(`/api/v1/things/${code}/request/`, {
      method: 'POST',
      body: JSON.stringify(collectionCode ? { collection_code: collectionCode } : {}),
    });

  // What a refused request says; shared by the first attempt and the retry that
  // follows an automatic join.
  const showRequestError = async (res) => {
    if (res.status === 429) {
      setToast({ type: 'error', message: t('common.tooManyAttempts') });
    } else if (res.status === 400) {
      const detail = await extractApiError(res);
      setToast({ type: 'error', message: detail || t('thingPage.invalidRequest') });
    } else {
      setToast({ type: 'error', message: t('thingPage.errorSendingRequest') });
    }
  };

  // Asking for a thing is being part of the group that lists it: the server says
  // `not_a_member` to someone who only reads a PUBLIC group, and — as the request
  // page does for a loan — they are joined and the request is sent once more.
  // Only for that marker (any other 403 never joins anybody), only into the
  // collection the caller vouches for (`joinCollectionCode`), and if the join
  // itself is refused (the day's joins, the member ceiling) its reason is shown
  // and nothing is asked.
  const joinThenRetry = async () => {
    const joinRes = await apiFetch(`/api/v1/collections/${joinCollectionCode}/join/`, {
      method: 'POST',
    });
    if (!joinRes.ok) {
      const detail = await extractApiError(joinRes);
      setToast({ type: 'error', message: detail || t('thingPage.errorSendingRequest') });
      return;
    }
    onJoined(joinCollectionCode);
    const retry = await postRequest();
    if (retry.ok) {
      setRequested(true);
      setToast({
        type: 'success',
        message: `${t('thingPage.holdRequested')} ${t('request.joinedGroup', {
          group: joinedGroupName || t('common.collection'),
        })}`,
      });
    } else {
      await showRequestError(retry);
    }
  };

  const handleRequest = async () => {
    if (requestLockRef.current) return;
    requestLockRef.current = true;
    setSubmitting(true);
    setToast(null);
    try {
      const res = await postRequest();
      if (res.ok) {
        setRequested(true);
        setToast({ type: 'success', message: t('thingPage.holdRequested') });
      } else if (res.status === 403 && joinCollectionCode) {
        const data = await res.json().catch(() => null);
        if (data?.code === 'not_a_member') await joinThenRetry();
        else await showRequestError(res);
      } else {
        await showRequestError(res);
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

  // The thing as the server sees it for this reader now, or `null` if it cannot be
  // had. Read through the collection the reader is browsing, like `ThingPage`'s own
  // fetch, so `can_manage` is computed against it.
  const reloadThing = async () => {
    try {
      const query = collectionCode ? `?collection=${encodeURIComponent(collectionCode)}` : '';
      const res = await apiFetch(`/api/v1/things/${code}/${query}`);
      return res.ok ? await res.json() : null;
    } catch {
      return null;
    }
  };

  const handleBookingAction = async (action, bookingCode) => {
    // Nobody to answer: no request, no lock, no state.
    const targetCode = bookingCode || activePendingCode;
    if (!targetCode || bookingLockRef.current) return;
    bookingLockRef.current = true;
    setBookingAction(targetCode);
    setBookingActionVerb(action);
    try {
      const res = await apiFetch(`/api/v1/bookings/${targetCode}/${action}/`, { method: 'POST' });
      if (res.ok) {
        if (action === 'accept') {
          const updated = bookings.map((b) =>
            b.code === targetCode ? { ...b, status: 'ACCEPTED' } : b
          );
          const nextPending = updated.find((b) => b.code !== targetCode && b.status === 'PENDING');
          setBookings(updated);
          setActivePendingCode(nextPending?.code || null);
          onThingChange(
            bookingKeepsStatus
              ? { pending_booking: nextPending?.code || null }
              : { status: 'INACTIVE', pending_booking: nextPending?.code || null }
          );
        } else {
          const remaining = bookings.filter((b) => b.code !== targetCode);
          const nextPending = remaining.find((b) => b.status === 'PENDING');
          setBookings(remaining);
          setActivePendingCode(nextPending?.code || null);
          onThingChange(
            bookingKeepsStatus
              ? { pending_booking: nextPending?.code || null }
              : { status: 'ACTIVE', pending_booking: nextPending?.code || null }
          );
        }
        setToast({
          type: 'success',
          message:
            action === 'accept' ? t('thingPage.holdConfirmed') : t('thingPage.holdCancelled'),
        });
      } else {
        // A 403 here is the server saying this reader no longer runs the thing —
        // a co-curator demoted since the page was loaded, whose buttons are still
        // on screen. Say why and reload the thing, so the controls that are no
        // longer theirs disappear; if the thing cannot be reloaded the sentence
        // would be untrue, so the generic error stands.
        const fresh = res.status === 403 ? await reloadThing() : null;
        if (fresh) {
          onThingChange(fresh);
          setToast({ type: 'error', message: t('thingPage.noLongerDecides') });
        } else {
          setToast({
            type: 'error',
            message:
              action === 'accept'
                ? t('thingPage.errorConfirmingHold')
                : t('thingPage.errorCancellingHold'),
          });
        }
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
