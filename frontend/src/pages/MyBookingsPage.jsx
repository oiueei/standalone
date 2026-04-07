import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Notification, Tag, Koros, Table, IconCrossCircle } from 'hds-react';
import { apiFetch } from '../services/api';
import { TAG_THEMES } from '../constants/things';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import TooltipButton from '../components/TooltipButton';

const STATUS_THEMES = {
  PENDING: TAG_THEMES.pending,
  ACCEPTED: { '--tag-background': '#e8f5e9', '--tag-color': '#1b5e20' },
  REJECTED: { '--tag-background': '#f5e6e6', '--tag-color': '#b01038' },
  CANCELLED: TAG_THEMES.inactive,
  EXPIRED: TAG_THEMES.inactive,
};

export default function MyBookingsPage() {
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const [bookings, setBookings] = useState(null);
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
            {t('myBookings.requested', { date: new Date(row._created).toLocaleDateString(i18n.language) })}
          </p>
          <p style={{ margin: 'var(--spacing-2-xs) 0 0', fontSize: 'var(--fontsize-body-s)' }}>
            {row._startDate && row._endDate
              ? `${new Date(row._startDate).toLocaleDateString(i18n.language)} — ${new Date(row._endDate).toLocaleDateString(i18n.language)}`
              : row._deliveryDate
              ? t('myBookings.delivery', { date: new Date(row._deliveryDate).toLocaleDateString(i18n.language), quantity: row._quantity })
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
          <Tag theme={STATUS_THEMES[row._status]}>{STATUS_LABELS[row._status] || row._status}</Tag>
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
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className="form-hero"
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}>
          <BackLink to="/" label={t('common.home')} />
          <h1 className="form-hero-title">{t('myBookings.pageTitle')}</h1>
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">

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

        <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
