import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Linkbox } from 'hds-react';
import { DATE_TYPES, ORDER_TYPE } from '../constants/things';
import { apiFetch } from '../services/api';
import ThingTags from './ThingTags';
import Toast from './Toast';
import placeholderImg from '../assets/image-s.png';

export default function ThingLinkbox({ thing, userCode, collectionCode, collectionHeadline, onDelete, onUpdateThing }) {
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

  const showButton = !isOwner && thing.status !== 'INACTIVE';
  const buttonDisabled = thing.status === 'TAKEN' || submitting || requested;

  const editPath = collectionCode
    ? `/collections/${collectionCode}/edit-thing/${thing.code}`
    : `/things/${thing.code}/edit`;

  const thingPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}`
    : `/things/${thing.code}`;

  const requestPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/request`
    : `/things/${thing.code}/request`;

  return (
    <Linkbox
      className="linkbox-no-arrow"
      href={thingPath}
      onClick={(e) => { e.preventDefault(); navigate(thingPath); }}
      imgProps={{ src: thing.thumbnail_url || placeholderImg, alt: thing.headline, className: 'thing-thumbnail' }}
      linkAriaLabel={`View ${thing.headline}`}
      linkboxAriaLabel={thing.headline}
      border
    >
      <ThingTags thing={thing} isOwner={isOwner} />
      <h3 className="linkbox-heading" style={{ margin: '0.5rem 0 0' }}>{thing.headline}</h3>
      {thing.description && <p style={{ margin: '0.25rem 0 0' }}>{thing.description}</p>}
      <p><strong>Created:</strong> {new Date(thing.created).toLocaleDateString('en-GB')}</p>
      {thing.fee && <p><strong>Price:</strong> {thing.fee} EUR</p>}
      {isOwner && bookings.length > 0 && (
        <div style={{ marginTop: '0.5rem' }}>
          <strong>Bookings:</strong>
          <ul style={{ margin: '0.25rem 0 0', paddingLeft: '1.25rem', fontSize: '0.9rem' }}>
            {bookings.map((b) => (
              <li key={b.code}>
                {b.start_date && b.end_date && (
                  <>{b.start_date} — {b.end_date}</>
                )}
                {b.delivery_date && (
                  <>{b.delivery_date}, qty {b.quantity}</>
                )}
                {' '}
                <span style={{ color: b.status === 'ACCEPTED' ? '#007a64' : '#b54708', fontWeight: b.code === thing.pending_booking ? 'bold' : 'normal' }}>
                  ({b.status === 'ACCEPTED' ? 'Confirmed' : 'Pending'}){b.code === thing.pending_booking ? ' *' : ''}
                </span>
              </li>
            ))}
          </ul>
        </div>
      )}
      {isOwner && (
        <Link to={editPath} onClick={(e) => e.stopPropagation()}>
          <Button>Edit</Button>
        </Link>
      )}
      {isOwner && thing.pending_booking && (
        <div style={{ display: 'flex', gap: '0.5rem', marginTop: '0.5rem' }} onClick={(e) => e.stopPropagation()}>
          <Button
            disabled={bookingAction}
            onClick={() => handleBookingAction('accept')}
          >
            Confirm hold
          </Button>
          <Button
            variant="danger"
            disabled={bookingAction}
            onClick={() => handleBookingAction('reject')}
          >
            Cancel hold
          </Button>
        </div>
      )}
      {showButton && (
        <div onClick={(e) => e.stopPropagation()}>
          <Button
            disabled={buttonDisabled}
            onClick={needsPage ? () => navigate(requestPath, { state: { backPath: collectionCode ? `/collections/${collectionCode}` : '/', backLabel: collectionCode ? (collectionHeadline || 'Collection') : 'Home' } }) : handleRequest}
          >
            {submitting ? 'Sending...' : 'Hold'}
          </Button>
        </div>
      )}
      <Toast toast={toast} onClose={() => setToast(null)} />
    </Linkbox>
  );
}
