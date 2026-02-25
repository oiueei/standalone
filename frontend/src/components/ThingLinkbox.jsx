import { useEffect, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { Button, Linkbox, Notification, Tag } from 'hds-react';
import placeholderImg from '../assets/image-s.png';

const TYPE_LABELS = {
  GIFT_THING: 'Gift',
  SELL_THING: 'Sale',
  ORDER_THING: 'Order',
  RENT_THING: 'Rental',
  LEND_THING: 'Lend',
  SHARE_THING: 'Share',
};

const DATE_TYPES = ['LEND_THING', 'RENT_THING', 'SHARE_THING'];
const ORDER_TYPE = 'ORDER_THING';
const DIRECT_TYPES = ['GIFT_THING', 'SELL_THING'];

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
    const token = localStorage.getItem('token');
    if (!token) return;
    fetch(`/api/v1/things/${thing.code}/calendar/`, {
      headers: { 'Authorization': `Bearer ${token}` },
    })
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
    const token = localStorage.getItem('token');
    if (!token) return;

    setSubmitting(true);
    setToast(null);
    try {
      const res = await fetch(`/api/v1/things/${thing.code}/request/`, {
        method: 'POST',
        headers: {
          'Authorization': `Bearer ${token}`,
          'Content-Type': 'application/json',
        },
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
      <div style={{ display: 'flex', flexWrap: 'wrap', gap: '0.25rem' }}>
        <Tag>{TYPE_LABELS[thing.type] || thing.type}</Tag>
        {isOwner && thing.status === 'TAKEN' && (
          <Tag theme={{ '--tag-background': '#fff4e5', '--tag-color': '#b54708' }}>Taken</Tag>
        )}
        {isOwner && thing.status === 'INACTIVE' && (
          <Tag theme={{ '--tag-background': '#e8e8e8', '--tag-color': '#525252' }}>Inactive</Tag>
        )}
        {isOwner && !thing.available && (
          <Tag theme={{ '--tag-background': '#f5e6e6', '--tag-color': '#b01038' }}>Unavailable</Tag>
        )}
        {isOwner && thing.pending_questions > 0 && (
          <Tag theme={{ '--tag-background': '#fff4e5', '--tag-color': '#b54708' }}>Pending questions</Tag>
        )}
      </div>
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
            onClick={async () => {
              const token = localStorage.getItem('token');
              setBookingAction(true);
              try {
                const res = await fetch(`/api/v1/bookings/${thing.pending_booking}/accept/`, {
                  method: 'POST',
                  headers: { 'Authorization': `Bearer ${token}` },
                });
                if (res.ok) {
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
                  const data = await res.json().catch(() => ({}));
                  setToast({ type: 'error', message: data.error || 'Error confirming hold.' });
                }
              } catch {
                setToast({ type: 'error', message: 'Connection error.' });
              } finally {
                setBookingAction(false);
              }
            }}
          >
            Confirm hold
          </Button>
          <Button
            variant="danger"
            disabled={bookingAction}
            onClick={async () => {
              const token = localStorage.getItem('token');
              setBookingAction(true);
              try {
                const res = await fetch(`/api/v1/bookings/${thing.pending_booking}/reject/`, {
                  method: 'POST',
                  headers: { 'Authorization': `Bearer ${token}` },
                });
                if (res.ok) {
                  const rejectedCode = thing.pending_booking;
                  setBookings((prev) => {
                    const remaining = prev.filter((b) => b.code !== rejectedCode);
                    const nextPending = remaining.find((b) => b.status === 'PENDING');
                    onUpdateThing(thing.code, { status: 'ACTIVE', pending_booking: nextPending ? nextPending.code : null });
                    return remaining;
                  });
                  setToast({ type: 'success', message: 'Hold cancelled.' });
                } else {
                  const data = await res.json().catch(() => ({}));
                  setToast({ type: 'error', message: data.error || 'Error cancelling hold.' });
                }
              } catch {
                setToast({ type: 'error', message: 'Connection error.' });
              } finally {
                setBookingAction(false);
              }
            }}
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
      {toast && (
        <Notification
          label={toast.type === 'success' ? 'Done' : 'Error'}
          type={toast.type}
          position="top-right"
          autoClose
          dismissible
          closeButtonLabelText="Close"
          onClose={() => setToast(null)}
        >
          {toast.message}
        </Notification>
      )}
    </Linkbox>
  );
}
