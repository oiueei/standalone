import { Fragment, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, IconTicket, IconEuroSign, IconCalendar, IconLocation, IconShield, IconHome, IconGroup, IconSwapUser } from 'hds-react';
import { DATE_TYPES, ORDER_TYPE, EVENT_TYPE, WISH_TYPE, SHARE_TYPE, ASSET_TYPE, SWAP_TYPE, APPOINTMENT_TYPE } from '../constants/things';
import { apiFetch } from '../services/api';
import MarkdownText from './MarkdownText';
import ThingTags from './ThingTags';
import Toast from './Toast';

export default function ThingLinkbox({ thing, userCode, collectionCode, collectionHeadline, collectionOwner, collectionMode, minimalist, isPaused, onDelete, onRemoveFromCollection, onUpdateThing }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [requested, setRequested] = useState(
    thing.type === 'SHARE_THING' && !!thing.my_pending_booking
  );
  const [toast, setToast] = useState(null);
  const [bookingAction, setBookingAction] = useState(false);
  const [activePendingCode, setActivePendingCode] = useState(thing.pending_booking);

  const isOwner = thing.owner === userCode;
  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--background-color': tc.color_02 ? `var(--color-${tc.color_02})` : undefined,
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_04})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
  } : undefined;
  const isEvent = thing.type === EVENT_TYPE;
  const isWish = thing.type === WISH_TYPE;
  const isShare = thing.type === SHARE_TYPE;
  const isSwap = thing.type === SWAP_TYPE;
  const isDateBased = DATE_TYPES.includes(thing.type);
  const isOrder = thing.type === ORDER_TYPE;
  const needsPage = isDateBased || isOrder || isSwap || thing.is_endless;
  const isCollectionOwner = (collectionOwner || thing.collection_owner) === userCode;
  const canDelete = isCollectionOwner || (isOwner && (!isShare || thing.transfer_count === 0));
  const [attendSubmitting, setAttendSubmitting] = useState(false);
  const [isAttending, setIsAttending] = useState(false);
  const [attendeeCount, setAttendeeCount] = useState(thing.attendee_count || 0);
  const [helpSubmitting, setHelpSubmitting] = useState(false);
  const [isHelping, setIsHelping] = useState(false);
  const [helperCount, setHelperCount] = useState(thing.helper_count || 0);

  useEffect(() => {
    if (isEvent && thing.deal) {
      setIsAttending(thing.deal.includes(userCode));
    }
    if (isWish && thing.deal) {
      setIsHelping(thing.deal.includes(userCode));
    }
  }, [isEvent, isWish, thing.deal, userCode]);

  const [bookings, setBookings] = useState([]);

  const isAsset = thing.type === ASSET_TYPE;
  const isAppointment = thing.type === APPOINTMENT_TYPE;

  useEffect(() => {
    const shouldFetch = isOwner
      ? (isDateBased || isOrder || isSwap || thing.status === 'TAKEN' || thing.is_endless)
      : (isAsset || isAppointment);
    if (!shouldFetch) return;
    apiFetch(`/api/v1/things/${thing.code}/calendar/`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const future = data.filter((b) => {
          if (!b.end_date && !b.delivery_date) return true; // GIFT/SELL: no dates, always current
          const d = new Date(b.end_date || b.delivery_date);
          d.setHours(0, 0, 0, 0);
          return d >= today;
        });
        const firstPending = future.find((b) => b.status === 'PENDING');
        setBookings(future);
        setActivePendingCode(firstPending?.code || null);
      })
      .catch(() => {});
  }, [thing.code, thing.status, isOwner, isDateBased, isOrder, isSwap, isAsset, isAppointment]);

  const handleRequest = async () => {
    setSubmitting(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/request/`, {
        method: 'POST',
        body: JSON.stringify({}),
      });
      if (res.ok) {
        setRequested(true);
        setToast({ type: 'success', message: t('thingPage.holdRequested') });
      } else if (res.status === 400) {
        setToast({ type: 'error', message: t('thingPage.invalidRequest') });
      } else {
        setToast({ type: 'error', message: t('thingPage.errorSendingRequest') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };


  const handleActivate = async () => {
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/activate/`, { method: 'POST' });
      if (res.ok) {
        onUpdateThing(thing.code, { status: 'ACTIVE', deal: [] });
      } else {
        setToast({ type: 'error', message: t('thingPage.errorReactivatingThing') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    }
  };

  const handleBookingAction = async (action, bookingCode) => {
    const code = bookingCode || activePendingCode;
    setBookingAction(code);
    try {
      const res = await apiFetch(`/api/v1/bookings/${code}/${action}/`, { method: 'POST' });
      if (res.ok) {
        if (needsPage) {
          // Date-based / order: thing stays ACTIVE, update bookings list and active pending pointer
          if (action === 'accept') {
            const updated = bookings.map((b) => b.code === code ? { ...b, status: 'ACCEPTED' } : b);
            const nextPending = updated.find((b) => b.code !== code && b.status === 'PENDING');
            setBookings(updated);
            setActivePendingCode(nextPending?.code || null);
            onUpdateThing(thing.code, { pending_booking: nextPending?.code || null });
          } else {
            const remaining = bookings.filter((b) => b.code !== code);
            const nextPending = remaining.find((b) => b.status === 'PENDING');
            setBookings(remaining);
            setActivePendingCode(nextPending?.code || null);
            onUpdateThing(thing.code, { pending_booking: nextPending?.code || null });
          }
          setToast({ type: 'success', message: action === 'accept' ? t('thingPage.holdConfirmed') : t('thingPage.holdCancelled') });
        } else {
          // GIFT / SELL: thing status changes
          if (action === 'accept') {
            const updated = bookings.map((b) => b.code === code ? { ...b, status: 'ACCEPTED' } : b);
            const nextPending = updated.find((b) => b.code !== code && b.status === 'PENDING');
            setBookings(updated);
            setActivePendingCode(nextPending?.code || null);
            onUpdateThing(thing.code, { status: 'INACTIVE', pending_booking: nextPending?.code || null });
          } else {
            const remaining = bookings.filter((b) => b.code !== code);
            const nextPending = remaining.find((b) => b.status === 'PENDING');
            setBookings(remaining);
            setActivePendingCode(nextPending?.code || null);
            onUpdateThing(thing.code, { status: 'ACTIVE', pending_booking: nextPending?.code || null });
          }
          setToast({ type: 'success', message: action === 'accept' ? t('thingPage.holdConfirmed') : t('thingPage.holdCancelled') });
        }
      } else {
        setToast({ type: 'error', message: action === 'accept' ? t('thingPage.errorConfirmingHold') : t('thingPage.errorCancellingHold') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setBookingAction(null);
    }
  };

  const handleAttend = async () => {
    setAttendSubmitting(true);
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/attend/`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setIsAttending(data.attending);
        setAttendeeCount(data.attendee_count);
      } else {
        setToast({ type: 'error', message: t('common.connectionError') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setAttendSubmitting(false);
    }
  };

  const handleOfferHelp = async () => {
    setHelpSubmitting(true);
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/offer-help/`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setIsHelping(data.offering);
        setHelperCount(data.helper_count);
      } else {
        setToast({ type: 'error', message: t('common.connectionError') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setHelpSubmitting(false);
    }
  };

  const showButton = !isOwner && thing.status !== 'INACTIVE';
  const buttonDisabled = isPaused || thing.status === 'TAKEN' || submitting || requested;

  const editPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/edit`
    : `/things/${thing.code}/edit`;

  const deletePath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/delete`
    : `/things/${thing.code}/delete`;

  const deleteBackPath = collectionCode ? `/collections/${collectionCode}` : '/';
  const deleteBackLabel = collectionCode ? (collectionHeadline || t('common.collection')) : t('common.home');

  const thingPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}`
    : `/things/${thing.code}`;

  const requestPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/request`
    : `/things/${thing.code}/request`;

  if (minimalist) {
    return (
      <div className="thing-card-minimalist">
        {thing.thumbnail_url && (
          <img
            src={thing.thumbnail_url}
            alt={thing.headline}
            className="thing-card-image-minimalist"
          />
        )}
        <p className="thing-card-caption">{thing.headline}</p>
        <div className="thing-card-buttons">
          {isOwner && thing.status === 'ACTIVE' && activePendingCode && (
            <>
              <Button fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('accept', activePendingCode)} style={btnStyle}>
                {t('thingCard.confirmHold')}
              </Button>
              <Button variant="secondary" fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('reject', activePendingCode)} style={btnSecondaryStyle}>
                {t('thingCard.cancelHold')}
              </Button>
            </>
          )}
          {isOwner && thing.status === 'TAKEN' && (
            <>
              <Button fullWidth disabled={bookingAction} onClick={() => handleBookingAction('accept')} style={btnStyle}>
                {t('thingCard.confirmHold')}
              </Button>
              <Button variant="secondary" fullWidth disabled={bookingAction} onClick={() => handleBookingAction('reject')} style={btnSecondaryStyle}>
                {t('thingCard.cancelHold')}
              </Button>
            </>
          )}
          {isOwner && thing.status === 'INACTIVE' && (
            <Button fullWidth onClick={handleActivate} style={btnStyle}>
              {t('thingCard.reactivate')}
            </Button>
          )}
          {isOwner && thing.status === 'ACTIVE' && !activePendingCode && canDelete && (
            <Button variant="secondary" fullWidth style={btnSecondaryStyle} onClick={() => navigate(deletePath, { state: { backPath: deleteBackPath, backLabel: deleteBackLabel } })}>
              {t('common.delete')}
            </Button>
          )}
          {showButton && !isEvent && !isWish && (
            <Button
              fullWidth
              disabled={buttonDisabled}
              style={btnStyle}
              onClick={isSwap ? () => navigate(requestPath, { state: { backPath: collectionCode ? `/collections/${collectionCode}` : '/', backLabel: collectionCode ? (collectionHeadline || t('common.collection')) : t('common.home') } }) : handleRequest}
            >
              {submitting ? t('common.sending') : (thing.status === 'TAKEN' || requested) ? t('thingCard.waitingForConfirmation') : isSwap ? t('swap.swapButton') : t('thingCard.hold')}
            </Button>
          )}
        </div>
        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    );
  }

  return (
    <div className="thing-card">
      {thing.thumbnail_url && (
        <Link to={thingPath}>
          <img
            src={thing.thumbnail_url}
            alt={thing.headline}
            className="thing-card-image"
          />
        </Link>
      )}
      <div className="thing-card-body">
        {collectionMode === 'COMMUNITY' && (
          <p className="thing-card-meta">
            {thing.owner_name}{thing.created && ` · ${new Date(thing.created).toLocaleDateString('es', { day: '2-digit', month: '2-digit' })}`}
          </p>
        )}
        <h3 className="thing-card-headline">
          <Link to={thingPath} className="thing-card-link">{thing.headline}</Link>
        </h3>
        {thing.description && (
          <MarkdownText text={thing.description} className="thing-card-description" />
        )}
        <div className="thing-card-info">
          {!isEvent && (
            <div className="thing-card-info-row">
              <IconTicket size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('thingPage.typeLabel')}</span>
              <span>{t('types.' + thing.type)}</span>
            </div>
          )}
          {thing.fee && (
            <div className="thing-card-info-row">
              <IconEuroSign size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('thingPage.priceLabel')}</span>
              <span>{thing.fee} €</span>
            </div>
          )}
          {thing.availability && (
            <div className="thing-card-info-row">
              <IconCalendar size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('thingPage.availabilityLabel')}</span>
              <span>{t('availability.' + thing.availability)}</span>
            </div>
          )}
          {thing.location && (
            <div className="thing-card-info-row">
              <IconLocation size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('thingPage.locationLabel')}</span>
              <span>{thing.location}</span>
            </div>
          )}
          {!isEvent && thing.condition && (
            <div className="thing-card-info-row">
              <IconShield size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('thingPage.conditionLabel')}</span>
              <span>{t('condition.' + thing.condition)}</span>
            </div>
          )}
          {thing.event_date && (
            <div className="thing-card-info-row">
              <IconCalendar size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('events.eventDate')}:</span>
              <span>{new Date(thing.event_date).toLocaleDateString(i18n.language, { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          )}
          {isAsset && thing.booking_unit && (
            <div className="thing-card-info-row">
              <IconCalendar size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('asset.bookingUnit')}</span>
              <span>{thing.booking_unit === 'HOUR' ? t('asset.unitHour') : t('asset.unitDay')}</span>
            </div>
          )}
          {isAppointment && thing.slot_duration && (
            <div className="thing-card-info-row">
              <IconCalendar size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('appointment.slotDuration')}</span>
              <span>{t('appointment.minutes', { count: thing.slot_duration })}</span>
            </div>
          )}
          {isEvent && (
            <div className="thing-card-info-row">
              <IconGroup size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('events.attendeesHeading')}:</span>
              <span>{attendeeCount}</span>
            </div>
          )}
          {isWish && (
            <div className="thing-card-info-row">
              <IconHome size="m" aria-hidden="true" />
              <span>{t('wishes.helperCount', { count: helperCount })}</span>
            </div>
          )}
          {thing.transfer_count > 0 && (
            <div className="thing-card-info-row">
              <IconSwapUser size="m" aria-hidden="true" />
              <span>{t(`transfers.${
                thing.type === 'LEND_THING' ? 'lendCount' :
                thing.type === 'RENT_THING' ? 'rentCount' :
                thing.type === 'SHARE_THING' ? 'shareCount' :
                thing.type === 'SWAP_THING' ? 'swapCount' :
                thing.type === 'ORDER_THING' ? 'orderCount' :
                'changesCount'
              }`, { count: thing.transfer_count })}</span>
            </div>
          )}
        </div>
        {(isOwner || isAsset || isAppointment) && bookings.length > 0 && (() => {
          const pendingCount = bookings.filter((b) => b.status === 'PENDING').length;
          return (
            <ul className="thing-card-bookings">
              {bookings.map((b) => {
                const isActive = isOwner && b.code === activePendingCode;
                const showStar = isActive && pendingCount > 1;
                return (
                  <li key={b.code} style={{ fontWeight: isActive ? 'bold' : 'normal' }}>
                    {isOwner && b.requester_name && <>{b.requester_name}. </>}
                    {b.created && <>{new Date(b.created).toLocaleDateString(i18n.language, { day: 'numeric', month: 'short' })}. </>}
                    {b.start_date && b.end_date && !b.start_time && <>{new Date(b.start_date).toLocaleDateString(i18n.language)} – {new Date(b.end_date).toLocaleDateString(i18n.language)}</>}
                    {b.start_date && b.start_time && b.end_time && <>{new Date(b.start_date).toLocaleDateString(i18n.language)} {b.start_time.slice(0, 5)}–{b.end_time.slice(0, 5)}</>}
                    {b.delivery_date && <>{new Date(b.delivery_date).toLocaleDateString(i18n.language)}, {t('thingCard.qty')} {b.quantity}</>}
                    {b.offered_thing_headlines && b.offered_thing_headlines.length > 0 && (
                      <><br />{t('swap.offeredItems')}: {b.offered_thing_headlines.join(', ')}</>
                    )}
                    {' '}
                    <span style={{ color: b.status === 'ACCEPTED' ? 'var(--color-success)' : 'var(--color-alert-dark)' }}>
                      ({b.status === 'ACCEPTED' ? t('thingCard.confirmed') : t('thingCard.pending')}){showStar ? ' *' : ''}
                    </span>
                  </li>
                );
              })}
            </ul>
          );
        })()}
        <div className="thing-card-buttons">
          {isOwner && thing.status === 'ACTIVE' && (
            <>
              {needsPage && activePendingCode && (
                <>
                  <Button fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('accept', activePendingCode)} style={btnStyle}>
                    {t('thingCard.confirmHold')}
                  </Button>
                  <Button variant="secondary" fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('reject', activePendingCode)} style={btnSecondaryStyle}>
                    {t('thingCard.cancelHold')}
                  </Button>
                </>
              )}
              <Link to={editPath} style={{ display: 'contents' }}>
                {needsPage && activePendingCode ? (
                  <Button fullWidth variant="secondary" style={btnSecondaryStyle}>{t('common.edit')}</Button>
                ) : (
                  <Button fullWidth style={btnStyle}>{t('common.edit')}</Button>
                )}
              </Link>
              {!bookings.some((b) => b.status === 'PENDING') && canDelete && (
                <Button variant="secondary" fullWidth style={btnSecondaryStyle} onClick={() => navigate(deletePath, { state: { backPath: deleteBackPath, backLabel: deleteBackLabel } })}>
                  {t('common.delete')}
                </Button>
              )}
            </>
          )}
          {isOwner && thing.status === 'TAKEN' && (
            <>
              <Button fullWidth disabled={bookingAction} onClick={() => handleBookingAction('accept')} style={btnStyle}>
                {t('thingCard.confirmHold')}
              </Button>
              <Button variant="secondary" fullWidth disabled={bookingAction} onClick={() => handleBookingAction('reject')} style={btnSecondaryStyle}>
                {t('thingCard.cancelHold')}
              </Button>
              <Link to={editPath} style={{ display: 'contents' }}>
                <Button variant="secondary" fullWidth style={btnSecondaryStyle}>{t('common.edit')}</Button>
              </Link>
            </>
          )}
          {isOwner && thing.status === 'INACTIVE' && (
            <>
              <Button fullWidth onClick={handleActivate} style={btnStyle}>
                {t('thingCard.reactivate')}
              </Button>
              <Link to={editPath} style={{ display: 'contents' }}>
                <Button variant="secondary" fullWidth style={btnSecondaryStyle}>{t('common.edit')}</Button>
              </Link>
              {canDelete && (
                <Button
                  variant="secondary"
                  fullWidth
                  style={btnSecondaryStyle}
                  onClick={() => navigate(deletePath, { state: { backPath: deleteBackPath, backLabel: deleteBackLabel } })}
                >
                  {t('common.delete')}
                </Button>
              )}
            </>
          )}
          {showButton && isEvent && (
            <Button
              fullWidth
              disabled={attendSubmitting}
              style={isAttending ? btnSecondaryStyle : btnStyle}
              variant={isAttending ? 'secondary' : 'primary'}
              onClick={handleAttend}
            >
              {isAttending ? t('events.attending') : t('events.attend')}
            </Button>
          )}
          {showButton && isWish && (
            <Button
              fullWidth
              disabled={helpSubmitting}
              style={isHelping ? btnSecondaryStyle : btnStyle}
              variant={isHelping ? 'secondary' : 'primary'}
              onClick={handleOfferHelp}
            >
              {isHelping ? t('wishes.helping') : t('wishes.offerHelp')}
            </Button>
          )}
          {showButton && !isEvent && !isWish && (
            <Button
              fullWidth
              disabled={buttonDisabled}
              style={btnStyle}
              onClick={isAppointment
                ? () => navigate(thingPath, { state: { backPath: collectionCode ? `/collections/${collectionCode}` : '/', backLabel: collectionCode ? (collectionHeadline || t('common.collection')) : t('common.home') } })
                : needsPage ? () => navigate(requestPath, { state: { backPath: collectionCode ? `/collections/${collectionCode}` : '/', backLabel: collectionCode ? (collectionHeadline || t('common.collection')) : t('common.home') } }) : handleRequest}
            >
              {submitting ? t('common.sending') : (thing.status === 'TAKEN' || requested) ? t('thingCard.waitingForConfirmation') : isSwap ? t('swap.swapButton') : t('thingCard.hold')}
            </Button>
          )}
          {isCollectionOwner && !isOwner && (
            <Button
              variant="secondary"
              fullWidth
              style={btnSecondaryStyle}
              onClick={() => navigate(deletePath, { state: { backPath: deleteBackPath, backLabel: deleteBackLabel } })}
            >
              {t('common.delete')}
            </Button>
          )}
        </div>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
