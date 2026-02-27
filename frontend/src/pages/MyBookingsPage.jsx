import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Button, Notification, Tag } from 'hds-react';
import { apiFetch } from '../services/api';
import { TYPE_LABELS, TAG_THEMES } from '../constants/things';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';

const STATUS_LABELS = {
  PENDING: 'Pending',
  ACCEPTED: 'Confirmed',
  REJECTED: 'Rejected',
  CANCELLED: 'Cancelled',
  EXPIRED: 'Expired',
};

const STATUS_THEMES = {
  PENDING: TAG_THEMES.pending,
  ACCEPTED: { '--tag-background': '#e8f5e9', '--tag-color': '#1b5e20' },
  REJECTED: { '--tag-background': '#f5e6e6', '--tag-color': '#b01038' },
  CANCELLED: TAG_THEMES.inactive,
  EXPIRED: TAG_THEMES.inactive,
};

export default function MyBookingsPage() {
  const navigate = useNavigate();
  const [bookings, setBookings] = useState(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [cancelling, setCancelling] = useState(null);

  useEffect(() => {
    const userCode = localStorage.getItem('userCode');
    if (!userCode) {
      navigate('/login');
      return;
    }

    const fetchBookings = async () => {
      try {
        const res = await apiFetch('/api/v1/my-bookings/');
        if (res.ok) {
          const data = await res.json();
          setBookings(data.results);
        } else {
          setError('Error loading bookings.');
        }
      } catch {
        setError('Connection error.');
      }
    };
    fetchBookings();
  }, [navigate]);

  const handleCancel = async (bookingCode) => {
    setCancelling(bookingCode);
    try {
      const res = await apiFetch(`/api/v1/bookings/${bookingCode}/cancel/`, {
        method: 'POST',
      });
      if (res.ok) {
        setBookings((prev) =>
          prev.map((b) => b.code === bookingCode ? { ...b, status: 'CANCELLED' } : b)
        );
        setToast({ type: 'success', message: 'Request cancelled.' });
      } else {
        const data = await res.json().catch(() => ({}));
        setToast({ type: 'error', message: data.error || 'Error cancelling request.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    } finally {
      setCancelling(null);
    }
  };

  if (error) {
    return (
      <div className="page-container">
        <Notification label="Error" type="error">{error}</Notification>
      </div>
    );
  }

  if (!bookings) {
    return <LoadingSpinner />;
  }

  return (
    <div className="page-container">
      <BackLink to="/" label="Home" />
      <h1 className="page-title">My requests</h1>

      {bookings.length === 0 ? (
        <p>You have no booking requests yet.</p>
      ) : (
        <div className="bookings-list">
          {bookings.map((b) => (
            <div key={b.code} className="booking-card">
              <div className="gallery-row" style={{ gap: 'var(--spacing-2-xs)', marginBottom: 'var(--spacing-xs)' }}>
                <Tag>{TYPE_LABELS[b.thing_type] || b.thing_type}</Tag>
                <Tag theme={STATUS_THEMES[b.status]}>{STATUS_LABELS[b.status] || b.status}</Tag>
              </div>

              <h3 style={{ margin: 0 }}>
                <Link to={`/things/${b.thing_code}`}>{b.thing_headline || b.thing_code}</Link>
              </h3>

              <p className="text-muted" style={{ margin: 'var(--spacing-2-xs) 0 0' }}>
                {b.owner_name && <>Owner: {b.owner_name}</>}
              </p>

              {b.start_date && b.end_date && (
                <p style={{ margin: 'var(--spacing-2-xs) 0 0' }}>{b.start_date} — {b.end_date}</p>
              )}
              {b.delivery_date && (
                <p style={{ margin: 'var(--spacing-2-xs) 0 0' }}>Delivery: {b.delivery_date}, qty {b.quantity}</p>
              )}

              <p className="faq-meta">
                Requested {new Date(b.created).toLocaleDateString('en-GB')}
              </p>

              {b.status === 'PENDING' && (
                <Button
                  variant="danger"
                  size="small"
                  disabled={cancelling === b.code}
                  onClick={() => handleCancel(b.code)}
                  style={{ marginTop: 'var(--spacing-xs)' }}
                >
                  {cancelling === b.code ? 'Cancelling...' : 'Cancel request'}
                </Button>
              )}
            </div>
          ))}
        </div>
      )}

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
