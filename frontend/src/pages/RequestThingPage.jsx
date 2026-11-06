import { useEffect, useRef, useState } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button, Notification, NumberInput, TextArea, TextInput } from 'hds-react';
import { DATE_TYPES, amountTimes, hasAmount } from '../constants/things';
import {
  isPickupDisabled,
  reservationPickupDisabled,
  freePickupDisabled,
  freeReturnDisabled,
  derivedReturnDate,
  isoToDisplay,
  displayToIso,
  formatDate,
  formatRequestedWhen,
  reservationMaxDays,
} from '../utils/rental';
import { apiFetch, apiErrorMessage, codedErrorMessage } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import DemoNotice from '../components/DemoNotice';
import MarkdownText from '../components/MarkdownText';
import Toast from '../components/Toast';
import StatusRegion from '../components/StatusRegion';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import { useLocalized } from '../utils/localized';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import useDocumentTitle from '../hooks/useDocumentTitle';
import useHourlyReservation from '../hooks/useHourlyReservation';
import JoinGroupNudge from '../components/request/JoinGroupNudge';
import RequestSuccess from '../components/request/RequestSuccess';
import NetworkPointLine from '../components/NetworkPointLine';
import DepositPolicy from '../components/DepositPolicy';
import ConstrainedRentalFields from '../components/request/ConstrainedRentalFields';
import DayReservationFields from '../components/request/DayReservationFields';
import HourlyReservationFields from '../components/request/HourlyReservationFields';
import FreeRentalFields from '../components/request/FreeRentalFields';

export default function RequestThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const userCode = localStorage.getItem('userCode');
  const { btnStyle, btnSecondaryStyle } = useTheeeme();
  const backPath = location.state?.backPath || '/';
  const backLabel = location.state?.backLabel || t('common.back');

  const [thing, setThing] = useState(null);
  const L = useLocalized();
  const headline = L(thing?.headline);
  const isReservation = thing?.type === 'RESERVE_THING';
  useCollectionLanguage(thing?.collection_language, [thing?.headline, thing?.description]);
  useCollectionTheeeme(thing?.collection_theeeme_colors, thing?.collection_koro);
  useDocumentTitle(
    !thing
      ? t('titles.holdDefault')
      : isReservation
        ? t('titles.reserveThing', { headline })
        : t('titles.holdThing', { headline })
  );
  // Date field state lives in the DISPLAY format (DD/MM/YYYY, what the DateInputs
  // emit); it converts to ISO at the consumption boundaries (POST body, derived
  // return date) via displayToIso.
  const [startDate, setStartDate] = useState(isoToDisplay(location.state?.prefillDate) || '');
  const [endDate, setEndDate] = useState('');
  const [duration, setDuration] = useState('');
  // A loan or rental of a thing with several identical units: how many are asked for.
  // Kept as typed (the field can be empty for a moment); `askedQuantity` is what it
  // means.
  const [quantity, setQuantity] = useState(1);
  const [projectNote, setProjectNote] = useState('');
  // The optional contact phone: only on a reservation whose collection asks for it.
  const [contactPhone, setContactPhone] = useState('');
  const [phoneError, setPhoneError] = useState('');
  const [attempted, setAttempted] = useState(false);
  const [submitting, setSubmitting] = useState(false);
  const [blockedPeriods, setBlockedPeriods] = useState([]);
  const [toast, setToast] = useState(null);
  const [success, setSuccess] = useState(false);
  // What was actually booked, restated in the success notice — read off the
  // body that went out, so it is the request's own dates, not the form's.
  const [bookedWhen, setBookedWhen] = useState('');
  // RESERVE_THING's "you need to be a member of this group to reserve" (403)
  // can only happen on a PUBLIC collection (can_view already gated everything
  // else, and a non-member reaches it only there), so joining is always
  // genuinely possible — so don't hand the reader a second button for
  // a step that was never really a choice, just join them (the signed-in half
  // of login-to-act, CollectionPage's own handleJoin) and retry the exact
  // same reservation, transparently, from inside handleSubmit. `notMemberError`
  // (+ the manual "Join this group" fallback button) only ever shows if that
  // auto-join itself fails — a real problem the reader does need to act on.
  const [notMemberError, setNotMemberError] = useState('');
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState(false);
  // The group an automatic (or fallback) join just made the reader a member
  // of — said out loud afterwards. Not asking first is deliberate; not telling
  // them at all left someone in a group, its digest and its curator's roster
  // without knowing, above all when the retried reservation then failed.
  const [joinedGroup, setJoinedGroup] = useState('');
  // Which thing the load failed for — same reason as the delete pages: a boolean
  // needs clearing at the top of the effect, which is a render spent undoing the
  // previous one.
  const [failedCode, setFailedCode] = useState(null);
  const error = failedCode === thingCode;

  useEffect(() => {
    if (!userCode) return;
    // In a collection's context, read the thing *through* that collection: its
    // rules (unit, hours, lengths, horizon) and note come back from the same
    // collection the POST below names in `collection_code`, so the form can't
    // show one group's rules while the server applies another's.
    const query = code ? `?collection=${encodeURIComponent(code)}` : '';
    apiFetch(`/api/v1/things/${thingCode}/${query}`)
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (data) {
          setThing(data);
          setFailedCode(null);
        } else {
          setFailedCode(thingCode);
        }
      })
      .catch(() => setFailedCode(thingCode));
  }, [userCode, thingCode, code]);

  // Several identical ones to a loan or a rental: the field, and what it asks for.
  const hasQuantity = !!thing && thing.type !== 'RESERVE_THING' && thing.units > 1;
  const askedQuantity = hasQuantity
    ? Math.min(thing.units, Math.max(1, Math.round(Number(quantity)) || 1))
    : 1;
  // What the dates were when the calendar was last asked for, read by the effect below
  // when a new answer comes in — a ref, so the request is not made again for each date.
  const datesRef = useRef({});

  useEffect(() => {
    if (!userCode || !thing || !DATE_TYPES.includes(thing.type)) return;
    // `for=request`: a curator who books is shown what a member is — the stretches in
    // which every unit is taken — not the bookings with names. With several units,
    // `quantity` is how many are wanted: the days with fewer free come back as taken.
    const asking = askedQuantity > 1 ? `&quantity=${askedQuantity}` : '';
    apiFetch(`/api/v1/things/${thingCode}/calendar/?for=request${asking}`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        setBlockedPeriods(data);
        // The dates already chosen stay only if they are still free for that many
        // (as a change of the length empties the pickup).
        const { startDate: start, endDate: end, rules } = datesRef.current;
        if (!rules) return;
        const startIso = displayToIso(start);
        const startBlocked = startIso && rules.pickupBlocked(startIso, data);
        if (startBlocked) setStartDate('');
        if (!rules.constrained && displayToIso(end)) {
          if (startBlocked || rules.returnBlocked(displayToIso(end), startIso, data)) {
            setEndDate('');
          }
        }
      })
      .catch(() => {});
  }, [userCode, thingCode, thing, askedQuantity]);

  // Per-collection rental rules (#7): a set of fixed lengths + allowed weekdays.
  const rentalDurations = thing?.rental_durations || [];
  const rentalWeekdays = thing?.rental_weekdays || [];
  // Holidays / closures — no handoff (LEND/RENT) or reservation span on one.
  const closedDates = thing?.closed_dates || [];
  const isConstrainedRental =
    !!thing && DATE_TYPES.includes(thing.type) && !isReservation && rentalDurations.length > 0;

  // RESERVE: the renter picks a pickup date + a length of 1..reservation_max_days.
  // The Select is omitted (length fixed to 1) when the collection caps it at 1.
  const reservationMax = reservationMaxDays(thing);
  // HOUR-unit RESERVE: day → duration → start time, which owns its choices.
  const hourly = useHourlyReservation({ thing, startDate, blockedPeriods });

  // With a single fixed length there is nothing to choose, so it *is* the answer
  // until the renter picks otherwise — the pickup picker is usable straight away
  // (#4). Derived rather than written into state once the thing loads: that
  // effect rendered an empty picker, committed it, and only then filled it in,
  // and in between the form's own validation called itself incomplete. What the
  // renter picks always wins; the single option only stands in before they have
  // touched the control.
  const soleDuration = isReservation
    ? reservationMax === 1
      ? '1'
      : ''
    : isConstrainedRental && rentalDurations.length === 1
      ? String(rentalDurations[0])
      : '';
  const chosenDuration = duration || soleDuration;

  // Pickup validity and blocked-date checks are pure, timezone-safe, unit-tested
  // helpers in utils/rental.js; bind them to the current rental state here.
  const pickupDisabled = (date) =>
    isReservation
      ? reservationPickupDisabled(date, {
          rentalWeekdays,
          blockedPeriods,
          duration: chosenDuration,
          closedDates,
        })
      : isPickupDisabled(date, {
          rentalWeekdays,
          blockedPeriods,
          duration: chosenDuration,
          closedDates,
        });
  // The free form (LEND/RENT with no fixed lengths) has two pickers, and each follows
  // the rules the server and the card use: the weekdays the collection allows at both
  // ends, and the chained handovers — the pickup is out on [s, e) of a
  // booking, the return is out when the stretch from the pickup runs over one. The
  // return is judged against the pickup chosen so far.
  const freePickupBlocked = (date) =>
    freePickupDisabled(date, { rentalWeekdays, blockedPeriods, closedDates });
  const freeReturnBlocked = (date) =>
    freeReturnDisabled(date, {
      pickup: displayToIso(startDate),
      rentalWeekdays,
      blockedPeriods,
      closedDates,
    });

  // How the dates are judged, kept where the calendar effect above can read it: a
  // change of quantity brings a new calendar, and the dates chosen under the old one are
  // dropped if they no longer fit.
  useEffect(() => {
    datesRef.current = {
      startDate,
      endDate,
      rules: {
        constrained: isConstrainedRental,
        pickupBlocked: (iso, periods) =>
          isConstrainedRental
            ? isPickupDisabled(iso, {
                rentalWeekdays,
                blockedPeriods: periods,
                duration: chosenDuration,
                closedDates,
              })
            : freePickupDisabled(iso, { rentalWeekdays, blockedPeriods: periods, closedDates }),
        returnBlocked: (iso, pickup, periods) =>
          freeReturnDisabled(iso, { pickup, rentalWeekdays, blockedPeriods: periods, closedDates }),
      },
    };
  });

  // The request body, built fresh from current form state — `null` when a
  // required field is still empty. A function, not a one-off inline block, so
  // both the normal submit and the manual "Join this group" fallback (a
  // *separate* click, its own later render) build it the same way — the
  // fallback used to replay whatever body the earlier failed attempt had
  // captured, which could book a date the reader had since changed on screen.
  const buildReservationBody = () => {
    // Sent only when the field is on screen and holds something.
    const phone =
      thing?.collection_reservation_asks_phone && contactPhone.trim()
        ? { contact_phone: contactPhone.trim() }
        : {};
    const isDateBased = thing && DATE_TYPES.includes(thing.type);
    let body = null;
    if (isReservation && hourly.isHourly) {
      // Pickup date + a chosen slot; the backend derives end_date = start + 1
      // and auto-confirms.
      const slot = hourly.slot();
      if (!slot) return null;
      body = {
        start_date: slot.date,
        start_time: slot.start,
        end_time: slot.end,
        project_note: projectNote.trim(),
        ...phone,
      };
    } else if (isReservation) {
      // Pickup date + a length of 1..reservation_max_days; the backend derives
      // the end date and auto-confirms.
      const startIso = displayToIso(startDate);
      if (!chosenDuration || !startIso) return null;
      body = {
        start_date: startIso,
        duration_days: Number(chosenDuration),
        project_note: projectNote.trim(),
        ...phone,
      };
    } else if (isDateBased) {
      if (isConstrainedRental) {
        // Renter picks a fixed length + a pickup date; the return date is derived
        // as pickup + length (a week rental comes back on the same weekday).
        const startIso = displayToIso(startDate);
        if (!chosenDuration || !startIso) return null;
        const end = derivedReturnDate(startIso, chosenDuration);
        body = { start_date: startIso, end_date: end };
        if (hasQuantity) body.quantity = askedQuantity;
      } else {
        const startIso = displayToIso(startDate);
        const endIso = displayToIso(endDate);
        if (!startIso || !endIso) return null;
        body = { start_date: startIso, end_date: endIso };
        if (hasQuantity) body.quantity = askedQuantity;
      }
    }
    // Pass the collection context so the backend applies that collection's
    // rental rules (harmless for other flows / collections without rules).
    if (body && code) body.collection_code = code;
    return body;
  };

  // Shared by the first attempt's non-403 branches and the retry after an
  // auto-join below — a business-rule failure reads the same either way.
  const showRequestError = async (res) => {
    if (res.status === 429) {
      setToast({ type: 'error', message: t('common.tooManyAttempts') });
    } else if (res.status === 400) {
      // A rule refusal comes coded and is said in the reader's language
      // (apiErrorMessage); anything else is the server's own text.
      const data = await res.json();
      if (data?.contact_phone) {
        // A field error belongs on the field, not in a toast.
        setPhoneError(t('reservation.phoneInvalid'));
        return;
      }
      setToast({ type: 'error', message: apiErrorMessage(data) || t('thingPage.invalidRequest') });
    } else if (res.status === 403) {
      const data = await res.json();
      setToast({ type: 'error', message: apiErrorMessage(data) || t('request.errorSending') });
    } else if (res.status === 409) {
      // "That time is already taken" for an hourly slot, "those dates"
      // otherwise — and this page's own copy for anything uncoded.
      const data = await res.json().catch(() => null);
      setToast({ type: 'error', message: codedErrorMessage(data) || t('request.dateOverlap') });
    } else {
      setToast({ type: 'error', message: t('request.errorSending') });
    }
  };

  // The one collection an automatic join may ever target: the one the server
  // resolved this thing to (`thing.collection_code`, read through
  // `?collection=` on the collection-context route) — never the route's `code`
  // on its own. The route is whatever link the reader followed, and nothing
  // checks it names a collection this thing lives in: joining it as written
  // let a link like `/collections/<someone's PUBLIC group>/things/<a real
  // space>/request` join the reader to that group on one Reserve click, and
  // hand its curator their email address in the roster. When the route names a collection the server
  // didn't resolve to, there is no join at all — the reason is shown instead.
  const joinableCollection = () => {
    const resolved = thing?.collection_code;
    if (!resolved || (code && code !== resolved)) return null;
    return resolved;
  };

  // The signed-in half of login-to-act (CollectionPage's own handleJoin,
  // reused): a PUBLIC collection's own member roster is one POST away for
  // someone who already has an account.
  //
  // Only ever called for the backend's `code: "not_a_member"` marker (see
  // handleSubmit) — every verb answers it now, since asking for anything is
  // being part of the group — which can only fire on a PUBLIC collection — can_view
  // already gated everything else, and a non-member reaches it only there —
  // so joining is always genuinely possible. Membership was never really a
  // choice being offered, so it isn't asked for: join, then retry the
  // reservation, transparently. `notMemberError` + the manual
  // fallback button only ever show if this auto-join itself fails.
  const joinThenRetry = async (body, fallbackMessage) => {
    const collectionCode = joinableCollection();
    if (!collectionCode) {
      setNotMemberError(fallbackMessage || t('request.errorSending'));
      return;
    }
    setJoining(true);
    setJoinError(false);
    try {
      let joinRes;
      try {
        joinRes = await apiFetch(`/api/v1/collections/${collectionCode}/join/`, {
          method: 'POST',
        });
      } catch {
        joinRes = null;
      }
      if (!joinRes?.ok) {
        setJoinError(true);
        setNotMemberError(fallbackMessage || t('request.errorSending'));
        return;
      }
      setNotMemberError('');
      // `joinableCollection` is `thing.collection_code`, so this headline is
      // the group that was just joined.
      setJoinedGroup(L(thing?.collection_headline) || '');
      try {
        const retryRes = await apiFetch(`/api/v1/things/${thingCode}/request/`, {
          method: 'POST',
          body: JSON.stringify(body),
        });
        if (retryRes.ok) {
          setBookedWhen(formatRequestedWhen(body));
          setSuccess(true);
        } else {
          await showRequestError(retryRes);
        }
      } catch {
        setToast({ type: 'error', message: t('common.connectionError') });
      }
    } finally {
      setJoining(false);
    }
  };

  const handleSubmit = async () => {
    setAttempted(true);
    const body = buildReservationBody();
    if (!body) {
      hourly.focusMissingChoice();
      return;
    }

    setSubmitting(true);
    setToast(null);
    setNotMemberError('');
    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/request/`, {
        method: 'POST',
        body: JSON.stringify(body),
      });
      if (res.ok) {
        setBookedWhen(formatRequestedWhen(body));
        setSuccess(true);
      } else if (res.status === 403) {
        // Only this specific marker means "not a member" — any *other* 403
        // (e.g. the thing going INACTIVE while this form was open) must not
        // be mistaken for it and silently join the reader to a group over an
        // unrelated error. And only when there is a collection it is safe to
        // join (`joinableCollection`, above).
        const data = await res.json();
        if (data.code === 'not_a_member' && joinableCollection()) {
          await joinThenRetry(body, apiErrorMessage(data));
        } else {
          setToast({ type: 'error', message: apiErrorMessage(data) || t('request.errorSending') });
        }
      } else {
        await showRequestError(res);
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  // The manual fallback — shown only when the automatic join above itself
  // failed. Rebuilds the body fresh rather than replaying the failed
  // attempt's — the reader may well have changed the date while this was
  // showing, and a fixed old body would confirm the wrong one.
  const handleJoinGroup = () => {
    const body = buildReservationBody();
    if (!body) {
      setAttempted(true);
      return;
    }
    return joinThenRetry(body, notMemberError);
  };

  // A length picked in the constrained-rental or the day-reservation Select: the
  // dates that are open depend on it, so the pickup date is cleared with it.
  const chooseLength = (value) => {
    setDuration(value);
    setStartDate('');
  };

  // The optional contact phone (when the shed asks) and the optional project note — the
  // same fields in the DAY and HOUR flows, one or the other on screen, never both (their
  // ids stay distinct anyway). The phone comes first: it is asked for a reason the label
  // gives, and the note is the free text that closes the form.
  const projectNoteField = (id) => (
    <>
      {thing?.collection_reservation_asks_phone && (
        <TextInput
          id={`${id}-phone`}
          type="tel"
          autoComplete="tel"
          maxLength={32}
          label={t('reservation.phoneLabel')}
          value={contactPhone}
          onChange={(e) => {
            setContactPhone(e.target.value);
            setPhoneError('');
          }}
          invalid={!!phoneError}
          errorText={phoneError || undefined}
        />
      )}
      <TextArea
        id={id}
        label={t('reservation.projectNoteLabel')}
        helperText={t('reservation.projectNoteHelper', { remaining: 512 - projectNote.length })}
        maxLength={512}
        value={projectNote}
        onChange={(e) => setProjectNote(e.target.value)}
      />
    </>
  );

  if (error) {
    return (
      <PageLayout title={t('common.error')} backTo={backPath} backLabel={backLabel}>
        <Notification label={t('thingPage.errorLoading')} type="error" />
      </PageLayout>
    );
  }

  if (!thing) return <LoadingSpinner />;

  const isDateBased = DATE_TYPES.includes(thing.type);

  return (
    <PageLayout
      heroClassName="form-hero--request"
      title={
        isReservation
          ? t('reservation.pageTitle', { headline })
          : t('request.pageTitle', { headline })
      }
      description={
        thing.collection_request_info ? (
          <MarkdownText text={L(thing.collection_request_info)} />
        ) : undefined
      }
      backTo={backPath}
      backLabel={backLabel}
    >
      {thing.collection_is_onboarding && <DemoNotice />}
      {notMemberError && (
        <JoinGroupNudge
          message={notMemberError}
          joining={joining}
          joinError={joinError}
          onJoin={handleJoinGroup}
        />
      )}
      {/* The join stands even when the retried reservation fails (the slot
          was taken meanwhile, say), and then there is no success message to
          carry it — so it has a notice of its own. Rendered unconditionally,
          the condition inside: see StatusRegion.jsx. */}
      <StatusRegion>
        {joinedGroup && !success && (
          <Notification type="info" label={t('reservation.joinedLabel')}>
            {t(isReservation ? 'reservation.joinedGroup' : 'request.joinedGroup', {
              group: joinedGroup,
            })}
          </Notification>
        )}
      </StatusRegion>
      {success ? (
        <RequestSuccess
          isReservation={isReservation}
          headline={headline}
          bookedWhen={bookedWhen}
          joinedGroup={joinedGroup}
          backPath={backPath}
          backLabel={backLabel}
        />
      ) : (
        <>
          <NetworkPointLine point={thing.network_point} />
          {hasAmount(thing.fee) &&
            (askedQuantity > 1 ? (
              <p>
                {t('request.priceTotal', {
                  count: askedQuantity,
                  unit: t('request.priceValue', { fee: thing.fee }),
                  total: t('request.priceValue', { fee: amountTimes(thing.fee, askedQuantity) }),
                })}
              </p>
            ) : (
              <p>
                <strong>{t('request.priceLabel')}</strong>{' '}
                {t('request.priceValue', { fee: thing.fee })}
              </p>
            ))}
          <div className="spacer-m" />
          {isDateBased && (
            <>
              <Notification
                type={thing.available_today ? 'success' : 'info'}
                size="small"
                label={t('thingPage.availabilityLabel')}
                notificationAriaLabel={t('thingPage.availabilityLabel')}
              >
                {thing.available_today
                  ? t('request.availableToday')
                  : thing.next_available
                    ? t('request.firstFreeDay', { date: formatDate(thing.next_available) })
                    : t('request.noFreeDaysSoon')}
                {thing.units > 1 && thing.units_free_today > 0 && (
                  <div>
                    {t('thingPage.unitsFreeToday', {
                      free: thing.units_free_today,
                      units: thing.units,
                    })}
                  </div>
                )}
              </Notification>
              <div className="spacer-s" />
            </>
          )}
          {hasQuantity && (
            <>
              <NumberInput
                id="request-quantity"
                label={t('request.quantityLabel')}
                helperText={t('request.quantityHelp', { units: thing.units })}
                value={quantity === '' ? '' : Number(quantity)}
                onChange={(e) => setQuantity(e.target.value)}
                min={1}
                max={thing.units}
                step={1}
              />
              <div className="spacer-s" />
            </>
          )}
          {isDateBased && isConstrainedRental && (
            <ConstrainedRentalFields
              durations={rentalDurations}
              chosenDuration={chosenDuration}
              onDuration={chooseLength}
              startDate={startDate}
              onStartDate={setStartDate}
              attempted={attempted}
              pickupDisabled={pickupDisabled}
            />
          )}
          {isReservation && !hourly.isHourly && (
            <DayReservationFields
              thing={thing}
              chosenDuration={chosenDuration}
              onDuration={chooseLength}
              startDate={startDate}
              onStartDate={setStartDate}
              attempted={attempted}
              pickupDisabled={pickupDisabled}
            >
              {projectNoteField('reservation-project-note')}
            </DayReservationFields>
          )}
          {isReservation && hourly.isHourly && (
            <HourlyReservationFields
              thing={thing}
              hourly={hourly}
              startDate={startDate}
              onStartDate={setStartDate}
              attempted={attempted}
            >
              {projectNoteField('reservation-project-note-hourly')}
            </HourlyReservationFields>
          )}
          {isDateBased && !isConstrainedRental && !isReservation && (
            <FreeRentalFields
              startDate={startDate}
              onStartDate={setStartDate}
              endDate={endDate}
              onEndDate={setEndDate}
              attempted={attempted}
              pickupBlocked={freePickupBlocked}
              returnBlocked={freeReturnBlocked}
            />
          )}

          <div className="spacer-xs" />
          {/* What is handed over and what comes back, read last: right above the button that asks. */}
          <div>
            {hasAmount(thing.deposit) &&
              (askedQuantity > 1 ? (
                <p>
                  {t('request.depositTotal', {
                    count: askedQuantity,
                    unit: `${thing.deposit} €`,
                    total: `${amountTimes(thing.deposit, askedQuantity)} €`,
                  })}{' '}
                  {t('thingPage.depositRefundableNote')}
                </p>
              ) : (
                <p>
                  <strong>{t('thingPage.depositLabel')}</strong> {thing.deposit} €{' '}
                  {t('thingPage.depositRefundableNote')}
                </p>
              ))}
            <DepositPolicy thing={thing} />
          </div>
          <div className="form-grid">
            {/* Said before the press (DESIGN §6): whoever runs the thing is sent the
                requester's name and email with the request, so
                the person finds it out here, not by being written to. The address
                itself is not shown — the page does not hold the user, and does not
                earn one more request for it. Only here: not in the join-the-group
                nudge above, and not once the request has gone. */}
            <p className="text-muted" style={{ margin: 0 }}>
              {isReservation ? t('reservation.contactShared') : t('request.contactShared')}
            </p>
            <Button fullWidth disabled={submitting} onClick={handleSubmit} style={btnStyle}>
              {submitting
                ? t('common.sending')
                : t(`thingCard.action.${thing?.type}`, { defaultValue: t('thingCard.hold') })}
            </Button>
            <Button
              variant="secondary"
              fullWidth
              onClick={() => navigate(backPath)}
              style={btnSecondaryStyle}
            >
              {t('common.cancel')}
            </Button>
          </div>

          <Toast toast={toast} onClose={() => setToast(null)} />
        </>
      )}
    </PageLayout>
  );
}
