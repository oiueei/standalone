import { Fragment, useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, IconTicket, IconEuroSign, IconCalendar, IconLocation, IconShield } from 'hds-react';
import { DATE_TYPES, ORDER_TYPE, TYPE_LABELS, AVAILABILITY_LABELS, CONDITION_LABELS } from '../constants/things';
import { apiFetch } from '../services/api';
import ThingTags from './ThingTags';
import Toast from './Toast';
import placeholderS from '../assets/image-s.png';
import placeholderM from '../assets/image-m.png';
import placeholderL from '../assets/image-l.png';

export default function ThingLinkbox({ thing, userCode, collectionCode, collectionHeadline, onDelete, onRemoveFromCollection, onUpdateThing }) {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [requested, setRequested] = useState(false);
  const [toast, setToast] = useState(null);
  const [bookingAction, setBookingAction] = useState(false);
  const [activePendingCode, setActivePendingCode] = useState(thing.pending_booking);

  const isOwner = thing.owner === userCode;
  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
  } : undefined;
  const isDateBased = DATE_TYPES.includes(thing.type);
  const isOrder = thing.type === ORDER_TYPE;
  const needsPage = isDateBased || isOrder;

  const [bookings, setBookings] = useState([]);

  useEffect(() => {
    if (!isOwner || (!isDateBased && !isOrder && thing.status !== 'TAKEN')) return;
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
  }, [thing.code, thing.status, isOwner, isDateBased, isOrder]);

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
        setToast({ type: 'success', message: 'Hold requested — you\'ll hear back soon.' });
      } else if (res.status === 400) {
        const data = await res.json();
        setToast({ type: 'error', message: data.detail || 'Invalid request.' });
      } else {
        setToast({ type: 'error', message: 'Error sending request.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setSubmitting(false);
    }
  };

  const handleHide = async () => {
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/hide/`, { method: 'POST' });
      if (res.ok) {
        onUpdateThing(thing.code, { status: 'INACTIVE' });
      } else {
        setToast({ type: 'error', message: 'Error hiding thing.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    }
  };

  const handleActivate = async () => {
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/activate/`, { method: 'POST' });
      if (res.ok) {
        onUpdateThing(thing.code, { status: 'ACTIVE', deal: [] });
      } else {
        setToast({ type: 'error', message: 'Error reactivating thing.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
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
          setToast({ type: 'success', message: action === 'accept' ? 'Hold confirmed.' : 'Hold cancelled.' });
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
          setToast({ type: 'success', message: action === 'accept' ? 'Hold confirmed.' : 'Hold cancelled.' });
        }
      } else {
        const data = await res.json().catch(() => ({}));
        setToast({ type: 'error', message: data.error || `Error ${action === 'accept' ? 'confirming' : 'cancelling'} hold.` });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setBookingAction(null);
    }
  };

  const showButton = !isOwner && thing.status !== 'INACTIVE';
  const buttonDisabled = thing.status === 'TAKEN' || submitting || requested;

  const editPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/edit`
    : `/things/${thing.code}/edit`;

  const deletePath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/delete`
    : `/things/${thing.code}/delete`;

  const deleteBackPath = collectionCode ? `/collections/${collectionCode}` : '/';
  const deleteBackLabel = collectionCode ? (collectionHeadline || 'Collection') : 'Home';

  const thingPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}`
    : `/things/${thing.code}`;

  const requestPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/request`
    : `/things/${thing.code}/request`;

  return (
    <div className="thing-card">
      <Link to={thingPath}>
        <img
          src={thing.thumbnail_url || placeholderS}
          srcSet={!thing.thumbnail_url ? `${placeholderS} 1x, ${placeholderM} 2x, ${placeholderL} 3x` : undefined}
          alt={thing.headline}
          className="thing-card-image"
        />
      </Link>
      <div className="thing-card-body">
        <h3 className="thing-card-headline">
          <Link to={thingPath} className="thing-card-link">{thing.headline}</Link>
        </h3>
        {thing.description && (
          <p className="thing-card-description">{thing.description}</p>
        )}
        <div className="thing-card-info">
          <div className="thing-card-info-row">
            <IconTicket size="m" aria-hidden="true" />
            <span className="thing-card-info-label">Type.</span>
            <span>{TYPE_LABELS[thing.type] || thing.type}</span>
          </div>
          {thing.fee && (
            <div className="thing-card-info-row">
              <IconEuroSign size="m" aria-hidden="true" />
              <span className="thing-card-info-label">Price.</span>
              <span>{thing.fee} €</span>
            </div>
          )}
          {thing.availability && (
            <div className="thing-card-info-row">
              <IconCalendar size="m" aria-hidden="true" />
              <span className="thing-card-info-label">Availability.</span>
              <span>{AVAILABILITY_LABELS[thing.availability] || thing.availability}</span>
            </div>
          )}
          {thing.location && (
            <div className="thing-card-info-row">
              <IconLocation size="m" aria-hidden="true" />
              <span className="thing-card-info-label">Location.</span>
              <span>{thing.location}</span>
            </div>
          )}
          {thing.condition && (
            <div className="thing-card-info-row">
              <IconShield size="m" aria-hidden="true" />
              <span className="thing-card-info-label">Condition.</span>
              <span>{CONDITION_LABELS[thing.condition] || thing.condition}</span>
            </div>
          )}
        </div>
        {isOwner && bookings.length > 0 && (() => {
          const pendingCount = bookings.filter((b) => b.status === 'PENDING').length;
          return (
            <ul className="thing-card-bookings">
              {bookings.map((b) => {
                const isActive = b.code === activePendingCode;
                const showStar = isActive && pendingCount > 1;
                return (
                  <li key={b.code} style={{ fontWeight: isActive ? 'bold' : 'normal' }}>
                    {b.requester_name && <>{b.requester_name}. </>}
                    {b.created && <>{new Date(b.created).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}. </>}
                    {b.start_date && b.end_date && <>{b.start_date} – {b.end_date}</>}
                    {b.delivery_date && <>{b.delivery_date}, qty {b.quantity}</>}
                    {' '}
                    <span style={{ color: b.status === 'ACCEPTED' ? 'var(--color-success)' : 'var(--color-alert-dark)' }}>
                      ({b.status === 'ACCEPTED' ? 'Confirmed' : 'Pending'}){showStar ? ' *' : ''}
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
                    Confirm hold
                  </Button>
                  <Button variant="secondary" fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('reject', activePendingCode)} style={btnSecondaryStyle}>
                    Cancel hold
                  </Button>
                </>
              )}
              <Link to={editPath} style={{ display: 'contents' }}>
                {needsPage && activePendingCode ? (
                  <Button fullWidth variant="secondary" style={btnSecondaryStyle}>Edit</Button>
                ) : (
                  <Button fullWidth style={btnStyle}>Edit</Button>
                )}
              </Link>
              {!bookings.some((b) => b.status === 'PENDING') && (
                <Button variant="secondary" fullWidth style={btnSecondaryStyle} onClick={handleHide}>
                  Hide
                </Button>
              )}
            </>
          )}
          {isOwner && thing.status === 'TAKEN' && (
            <>
              <Button fullWidth disabled={bookingAction} onClick={() => handleBookingAction('accept')} style={btnStyle}>
                Confirm hold
              </Button>
              <Button variant="secondary" fullWidth disabled={bookingAction} onClick={() => handleBookingAction('reject')} style={btnSecondaryStyle}>
                Cancel hold
              </Button>
              <Link to={editPath} style={{ display: 'contents' }}>
                <Button variant="secondary" fullWidth style={btnSecondaryStyle}>Edit</Button>
              </Link>
            </>
          )}
          {isOwner && thing.status === 'INACTIVE' && (
            <>
              <Button fullWidth onClick={handleActivate} style={btnStyle}>
                Reactivate
              </Button>
              <Link to={editPath} style={{ display: 'contents' }}>
                <Button variant="secondary" fullWidth style={btnSecondaryStyle}>Edit</Button>
              </Link>
              <Button
                variant="secondary"
                fullWidth
                style={btnSecondaryStyle}
                onClick={() => navigate(deletePath, { state: { backPath: deleteBackPath, backLabel: deleteBackLabel } })}
              >
                Delete
              </Button>
            </>
          )}
          {showButton && (
            <Button
              fullWidth
              disabled={buttonDisabled}
              style={btnStyle}
              onClick={needsPage ? () => navigate(requestPath, { state: { backPath: collectionCode ? `/collections/${collectionCode}` : '/', backLabel: collectionCode ? (collectionHeadline || 'Collection') : 'Home' } }) : handleRequest}
            >
              {submitting ? 'Sending...' : buttonDisabled ? 'Waiting for confirmation' : 'Hold'}
            </Button>
          )}
        </div>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
