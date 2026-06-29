import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Notification, StatusLabel, Tag, Table, IconCrossCircle } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import TooltipButton from '../components/TooltipButton';
import useTheeeme from '../hooks/useTheeeme';

// Booking status is a semantic state — HDS StatusLabel owns this (no hardcoded
// green/red hex). The thing *type* stays a plain Tag (it's a category, not a state).
const STATUS_TYPES = {
  PENDING: 'alert',
  ACCEPTED: 'success',
  REJECTED: 'error',
  CANCELLED: 'neutral',
  EXPIRED: 'neutral',
};

export default function MyBookingsPage() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const { tc, btnSecondaryStyle } = useTheeeme();
  const [bookings, setBookings] = useState(null);
  const [next, setNext] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [cancelling, setCancelling] = useState(null);
  useEffect(() => { document.title = t('titles.myBookings'); }, [t]);

  const STATUS_LABELS = {
    PENDING: t('myBookings.statusPending'),
    ACCEPTED: t('myBookings.statusConfirmed'),
    REJECTED: t('myBookings.statusRejected'),
    CANCELLED: t('myBookings.statusCancelled'),
    EXPIRED: t('myBookings.statusExpired'),
  };

  useEffect(() => {
    const fetchBookings = async () => {
      try {
        const res = await apiFetch('/api/v1/my-bookings/');
        if (res.ok) {
          const data = await res.json();
          setBookings(data.results);
          setNext(data.next || null);
        } else {
          setError(t('myBookings.errorLoading'));
        }
      } catch {
        setError(t('common.connectionError'));
      }
    };
    fetchBookings();
  }, [navigate, t]);

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
        setToast({ type: 'success', message: t('myBookings.requestCancelled') });
      } else {
        setToast({ type: 'error', message: t('myBookings.errorCancelling') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setCancelling(null);
    }
  };

  const loadMore = async () => {
    if (!next || loadingMore) return;
    setLoadingMore(true);
    try {
      // `next` is an absolute DRF URL; strip the origin so it goes through the
      // Vite proxy in dev and stays same-origin (sends auth cookies) everywhere.
      const path = next.replace(/^https?:\/\/[^/]+/, '');
      const res = await apiFetch(path);
      if (res.ok) {
        const data = await res.json();
        setBookings((prev) => [...prev, ...(data.results || [])]);
        setNext(data.next || null);
      }
    } finally {
      setLoadingMore(false);
    }
  };

  if (error) {
    return (
      <div className="page-container">
        <Notification label={t('common.error')} type="error">{error}</Notification>
      </div>
    );
  }

  if (!bookings) {
    return <LoadingSpinner />;
  }

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
            {t('myBookings.requested', { date: new Date(row._created).toLocaleDateString(i18n.language) })}
          </p>
          <p style={{ margin: 'var(--spacing-2-xs) 0 0', fontSize: 'var(--fontsize-body-s)' }}>
            {row._startDate && row._endDate
              ? `${new Date(row._startDate).toLocaleDateString(i18n.language)} — ${new Date(row._endDate).toLocaleDateString(i18n.language)}`
              : <span style={{ color: 'var(--color-black-40)' }}>{t('myBookings.noDates')}</span>}
          </p>
        </div>
      ),
    },
    {
      key: '_status',
      headerName: 'Status',
      transform: (row) => (
        <div style={{ display: 'flex', flexDirection: 'column', gap: 'var(--spacing-2-xs)' }}>
          <Tag>{t('types.' + row._type)}</Tag>
          <StatusLabel type={STATUS_TYPES[row._status] || 'neutral'}>
            {STATUS_LABELS[row._status] || row._status}
          </StatusLabel>
          {row._status === 'EXPIRED' && (
            <p style={{ margin: 0, fontSize: 'var(--fontsize-body-s)', color: 'var(--color-black-60)' }}>
              {t('myBookings.expiredHelper')}
            </p>
          )}
        </div>
      ),
    },
    {
      key: '_actions',
      headerName: '',
      transform: (row) => row._status === 'PENDING' ? (
        <TooltipButton
          tooltip={t('myBookings.cancelTooltip')}
          onClick={() => handleCancel(row._code)}
          disabled={cancelling === row._code}
        >
          <IconCrossCircle aria-hidden />
        </TooltipButton>
      ) : null,
    },
  ];

  return (
    <PageLayout title={t('myBookings.pageTitle')} backTo="/" backLabel={t('common.home')}>

        {bookings.length === 0 ? (
          <p>{t('myBookings.noBookings')}</p>
        ) : (
          <>
            {(() => {
              const pendingRows = rows.filter((r) => r._status === 'PENDING');
              const otherRows = rows.filter((r) => r._status !== 'PENDING');
              return (
                <>
                  <h2>{t('myBookings.statusPending')}</h2>
                  <div className="spacer-s" />
                  {pendingRows.length === 0 ? (
                    <p className="text-muted">{t('myBookings.noPending')}</p>
                  ) : (
                    <Table cols={cols} rows={pendingRows} indexKey="_id" renderIndexCol={false} dense theme={tc.color_03 ? { '--header-background-color': `var(--color-${tc.color_03})` } : undefined} />
                  )}
                  {otherRows.length > 0 && (
                    <>
                      <div className="spacer-xl" />
                      <h2>{t('myBookings.pastRequests')}</h2>
                      <div className="spacer-s" />
                      <Table cols={cols} rows={otherRows} indexKey="_id" renderIndexCol={false} dense theme={tc.color_03 ? { '--header-background-color': `var(--color-${tc.color_03})` } : undefined} />
                    </>
                  )}
                </>
              );
            })()}
          </>
        )}

        {next && (
          <>
            <div className="spacer-s" />
            <Button variant="secondary" onClick={loadMore} disabled={loadingMore} style={btnSecondaryStyle}>
              {t('common.loadMore')}
            </Button>
          </>
        )}

        <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
