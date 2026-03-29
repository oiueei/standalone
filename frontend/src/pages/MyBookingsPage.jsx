import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { Notification, Tag, Koros, Table, IconCrossCircle } from 'hds-react';
import { apiFetch } from '../services/api';
import { TYPE_LABELS, TAG_THEMES } from '../constants/things';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import TooltipButton from '../components/TooltipButton';

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
  useEffect(() => { document.title = 'My requests — OIUEEI'; }, []);

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

  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');

  const rows = bookings.map((b) => ({
    _id: b.code,
    _code: b.code,
    _type: b.thing_type,
    _status: b.status,
    _thingCode: b.thing_code,
    _thingHeadline: b.thing_headline || b.thing_code,
    _ownerName: b.owner_name,
    _startDate: b.start_date,
    _endDate: b.end_date,
    _deliveryDate: b.delivery_date,
    _quantity: b.quantity,
    _created: b.created,
  }));

  const cols = [
    {
      key: '_thing',
      headerName: 'Thing',
      transform: (row) => (
        <div>
          <Link to={`/things/${row._thingCode}`}>{row._thingHeadline}</Link>
          {row._ownerName && (
            <p style={{ margin: 'var(--spacing-2-xs) 0 0', fontSize: 'var(--fontsize-body-s)', color: 'var(--color-black-60)' }}>
              {row._ownerName}
            </p>
          )}
          <p style={{ margin: 'var(--spacing-2-xs) 0 0', fontSize: 'var(--fontsize-body-s)', color: 'var(--color-black-50)' }}>
            Requested {new Date(row._created).toLocaleDateString('en-GB')}
          </p>
          <p style={{ margin: 'var(--spacing-2-xs) 0 0', fontSize: 'var(--fontsize-body-s)' }}>
            {row._startDate && row._endDate
              ? `${row._startDate} — ${row._endDate}`
              : row._deliveryDate
              ? `Delivery ${row._deliveryDate}, qty ${row._quantity}`
              : <span style={{ color: 'var(--color-black-40)' }}>—</span>}
          </p>
        </div>
      ),
    },
    {
      key: '_status',
      headerName: 'Status',
      transform: (row) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2-xs)' }}>
          <Tag>{TYPE_LABELS[row._type] || row._type}</Tag>
          <Tag theme={STATUS_THEMES[row._status]}>{STATUS_LABELS[row._status] || row._status}</Tag>
        </div>
      ),
    },
    {
      key: '_actions',
      headerName: '',
      transform: (row) => row._status === 'PENDING' ? (
        <TooltipButton
          tooltip="Cancel this booking request"
          onClick={() => handleCancel(row._code)}
          disabled={cancelling === row._code}
        >
          <IconCrossCircle aria-hidden />
        </TooltipButton>
      ) : null,
    },
  ];

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_04})` } : undefined}>
          <BackLink to="/" label="Home" />
          <h1 className="form-hero-title">My requests</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">
        <div className="spacer-m" />

        {bookings.length === 0 ? (
          <p>You have no booking requests yet.</p>
        ) : (
          <>
            {(() => {
              const pendingRows = rows.filter((r) => r._status === 'PENDING');
              const otherRows = rows.filter((r) => r._status !== 'PENDING');
              return (
                <>
                  <h2>Pending</h2>
                  <div className="spacer-s" />
                  {pendingRows.length === 0 ? (
                    <p className="text-muted">No pending requests.</p>
                  ) : (
                    <Table cols={cols} rows={pendingRows} indexKey="_id" renderIndexCol={false} dense theme={tc.color_03 ? { '--header-background-color': `var(--color-${tc.color_03})` } : undefined} />
                  )}
                  {otherRows.length > 0 && (
                    <>
                      <div className="spacer-xl" />
                      <h2>Confirmed</h2>
                      <div className="spacer-s" />
                      <Table cols={cols} rows={otherRows} indexKey="_id" renderIndexCol={false} dense theme={tc.color_03 ? { '--header-background-color': `var(--color-${tc.color_03})` } : undefined} />
                    </>
                  )}
                </>
              );
            })()}
          </>
        )}

        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
