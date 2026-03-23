import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Card } from 'hds-react';
import { DATE_TYPES, ORDER_TYPE, TYPE_LABELS, AVAILABILITY_LABELS, CONDITION_LABELS } from '../constants/things';
import { apiFetch } from '../services/api';
import ThingTags from './ThingTags';
import Toast from './Toast';
import placeholderImg from '../assets/image-s.png';

export default function ThingLinkbox({ thing, userCode, collectionCode, collectionHeadline, collectionInactive, onDelete, onRemoveFromCollection, onUpdateThing }) {
  const navigate = useNavigate();
  const [submitting, setSubmitting] = useState(false);
  const [requested, setRequested] = useState(false);
  const [toast, setToast] = useState(null);
  const [bookingAction, setBookingAction] = useState(false);

  const isOwner = thing.owner === userCode;
  const isDateBased = DATE_TYPES.includes(thing.type);
  const isOrder = thing.type === ORDER_TYPE;
  const needsPage = isDateBased || isOrder;

  const [bookings, setBookings] = useState([]);

  useEffect(() => {
    if (!isOwner || (!isDateBased && !isOrder)) return;
    apiFetch(`/api/v1/things/${thing.code}/calendar/`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const future = data.filter((b) => {
          const d = new Date(b.end_date || b.delivery_date);
          d.setHours(0, 0, 0, 0);
          return d >= today;
        });
        setBookings(future);
      })
      .catch(() => {});
  }, [thing.code, isOwner, isDateBased, isOrder]);

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
        setToast({ type: 'success', message: 'Request sent.' });
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

  const handleBookingAction = async (action) => {
    setBookingAction(true);
    try {
      const res = await apiFetch(`/api/v1/bookings/${thing.pending_booking}/${action}/`, {
        method: 'POST',
      });
      if (res.ok) {
        if (action === 'accept') {
          const acceptedCode = thing.pending_booking;
          setBookings((prev) => {
            const updated = prev.map((b) =>
              b.code === acceptedCode ? { ...b, status: 'ACCEPTED' } : b
            );
            const nextPending = updated.find((b) => b.code !== acceptedCode && b.status === 'PENDING');
            onUpdateThing(thing.code, { status: 'INACTIVE', pending_booking: nextPending ? nextPending.code : null });
            return updated;
          });
          setToast({ type: 'success', message: 'Hold confirmed.' });
        } else {
          const rejectedCode = thing.pending_booking;
          setBookings((prev) => {
            const remaining = prev.filter((b) => b.code !== rejectedCode);
            const nextPending = remaining.find((b) => b.status === 'PENDING');
            onUpdateThing(thing.code, { status: 'ACTIVE', pending_booking: nextPending ? nextPending.code : null });
            return remaining;
          });
          setToast({ type: 'success', message: 'Hold cancelled.' });
        }
      } else {
        const data = await res.json().catch(() => ({}));
        setToast({ type: 'error', message: data.error || `Error ${action === 'accept' ? 'confirming' : 'cancelling'} hold.` });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setBookingAction(false);
    }
  };

  const showButton = !isOwner && thing.status !== 'INACTIVE' && !collectionInactive;
  const buttonDisabled = thing.status === 'TAKEN' || submitting || requested;

  const editPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/edit`
    : `/things/${thing.code}/edit`;

  const thingPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}`
    : `/things/${thing.code}`;

  const requestPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/request`
    : `/things/${thing.code}/request`;

  return (
    <Card className="thing-card">
      <Link to={thingPath}>
        <img src={thing.thumbnail_url || placeholderImg} alt={thing.headline} className="thing-card-image" />
      </Link>
      <div className="thing-card-body">
        <ThingTags thing={thing} isOwner={isOwner} showType={false} />
        <p className="thing-card-meta">
          {new Date(thing.created).toLocaleDateString('en-GB')}
        </p>
        <h3 className="thing-card-headline">
          <Link to={thingPath} className="thing-card-link">{thing.headline}</Link>
        </h3>
        {thing.description && (
          <p className="thing-card-description">{thing.description}</p>
        )}
        <div className="thing-card-info">
          <div className="thing-card-info-row">
            <span className="thing-card-info-label">Type</span>
            <span>{TYPE_LABELS[thing.type] || thing.type}</span>
          </div>
          {thing.fee && (
            <div className="thing-card-info-row">
              <span className="thing-card-info-label">Price</span>
              <span>{thing.fee} €</span>
            </div>
          )}
          {thing.availability && (
            <div className="thing-card-info-row">
              <span className="thing-card-info-label">Availability</span>
              <span>{AVAILABILITY_LABELS[thing.availability] || thing.availability}</span>
            </div>
          )}
          {thing.location && (
            <div className="thing-card-info-row">
              <span className="thing-card-info-label">Location</span>
              <span>{thing.location}</span>
            </div>
          )}
          {thing.condition && (
            <div className="thing-card-info-row">
              <span className="thing-card-info-label">Condition</span>
              <span>{CONDITION_LABELS[thing.condition] || thing.condition}</span>
            </div>
          )}
        </div>
        {isOwner && bookings.length > 0 && (
          <ul className="thing-card-bookings">
            {bookings.map((b) => (
              <li key={b.code}>
                {b.requester_name && <strong>{b.requester_name}: </strong>}
                {b.start_date && b.end_date && <>{b.start_date} — {b.end_date}</>}
                {b.delivery_date && <>{b.delivery_date}, qty {b.quantity}</>}
                {' '}
                <span style={{ color: b.status === 'ACCEPTED' ? 'var(--color-success)' : 'var(--color-alert-dark)', fontWeight: b.code === thing.pending_booking ? 'bold' : 'normal' }}>
                  ({b.status === 'ACCEPTED' ? 'Confirmed' : 'Pending'}){b.code === thing.pending_booking ? ' *' : ''}
                </span>
              </li>
            ))}
          </ul>
        )}
        <div className="thing-card-buttons">
          {isOwner && (
            <Link to={editPath} style={{ display: 'contents' }}>
              <Button variant="secondary" fullWidth>Edit</Button>
            </Link>
          )}
          {isOwner && thing.pending_booking && (
            <>
              <Button fullWidth disabled={bookingAction} onClick={() => handleBookingAction('accept')}>
                Confirm hold
              </Button>
              <Button variant="secondary" fullWidth disabled={bookingAction} onClick={() => handleBookingAction('reject')}>
                Cancel hold
              </Button>
            </>
          )}
          {isOwner && collectionCode && onRemoveFromCollection && (
            <Button
              variant="secondary"
              fullWidth
              onClick={async () => {
                try {
                  const res = await apiFetch(`/api/v1/collections/${collectionCode}/remove-thing/`, {
                    method: 'POST',
                    body: JSON.stringify({ thing_code: thing.code }),
                  });
                  if (res.ok) onRemoveFromCollection(thing.code);
                  else setToast({ type: 'error', message: 'Error removing thing.' });
                } catch {
                  setToast({ type: 'error', message: 'Connection error.' });
                }
              }}
            >
              Remove from collection
            </Button>
          )}
          {showButton && (
            <Button
              fullWidth
              disabled={buttonDisabled}
              onClick={needsPage ? () => navigate(requestPath, { state: { backPath: collectionCode ? `/collections/${collectionCode}` : '/', backLabel: collectionCode ? (collectionHeadline || 'Collection') : 'Home' } }) : handleRequest}
            >
              {submitting ? 'Sending...' : requested ? 'Requested' : 'Hold'}
            </Button>
          )}
        </div>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </Card>
  );
}
