import { useEffect, useState } from 'react';
import { useNavigate, Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button, Notification, StatusLabel, Tag, IconCrossCircle } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import Toast from '../components/Toast';
import TooltipButton from '../components/TooltipButton';
import useTheeeme from '../hooks/useTheeeme';
import { useLocalized } from '../utils/localized';
import { formatDate, formatBookingWhen } from '../utils/rental';
import { markMixedVerbs } from '../utils/bookingRows';
import ButtonLink from '../components/ButtonLink';
import CancelReservationDialog from '../components/CancelReservationDialog';
import ResponsiveTable from '../components/ResponsiveTable';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { errorKey, translateError } from '../utils/errorKey';
import { withQuantity } from '../utils/quantity';

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
  const { t } = useTranslation();
  // Owner content (headlines, tags) may carry one text per language.
  const L = useLocalized();
  const { btnStyle, btnSecondaryStyle, tableTheme } = useTheeeme();
  const [bookings, setBookings] = useState(null);
  const [next, setNext] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [cancelling, setCancelling] = useState(null);
  // A confirmed reservation waiting on the member's confirm before it is
  // cancelled — see CancelReservationDialog. A pending request of their own
  // still withdraws on one press.
  const [cancelRow, setCancelRow] = useState(null);
  useDocumentTitle(t('titles.myBookings'));

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
          setError(errorKey('myBookings.errorLoading'));
        }
      } catch {
        setError(errorKey('common.connectionError'));
      }
    };
    fetchBookings();
  }, [navigate, t]);

  const handleCancel = async (bookingCode, { reservation = false } = {}) => {
    setCancelling(bookingCode);
    try {
      const res = await apiFetch(`/api/v1/bookings/${bookingCode}/cancel/`, {
        method: 'POST',
      });
      if (res.ok) {
        setBookings((prev) =>
          prev.map((b) => (b.code === bookingCode ? { ...b, status: 'CANCELLED' } : b))
        );
        setToast({
          type: 'success',
          message: reservation
            ? t('myBookings.reservationCancelled')
            : t('myBookings.requestCancelled'),
        });
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
      } else {
        // A refused page used to fall out of here silently — the button
        // re-enabled and nothing else happened, so the reader was left pressing
        // a control that visibly did nothing.
        setToast({ type: 'error', message: t('common.loadMoreError') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setLoadingMore(false);
    }
  };

  if (error) {
    return (
      <PageLayout title={t('common.error')} backTo="/" backLabel={t('common.home')}>
        <Notification label={t('common.error')} type="error">
          {translateError(t, error)}
        </Notification>
      </PageLayout>
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
    _thingHeadline: withQuantity(t, L(b.thing_headline) || b.thing_code, b.quantity),
    _ownerName: b.owner_name,
    _startDate: b.start_date,
    _endDate: b.end_date,
    _when: formatBookingWhen(b),
    _created: b.created,
    _projectNote: b.project_note,
  }));

  const todayIso = new Date().toISOString().slice(0, 10);
  // A confirmed reservation that hasn't started is "current", not "past" — and
  // the requester can still cancel it (frees the slot; the owner is told).
  const isFutureReservation = (row) =>
    row._type === 'RESERVE_THING' && row._status === 'ACCEPTED' && row._startDate >= todayIso;

  // What cancelling does, once, for the table's icon and the card's button alike:
  // a reservation that is coming up asks first, a pending request goes at once.
  const cancelAction = (row) =>
    isFutureReservation(row) ? setCancelRow(row) : handleCancel(row._code);
  const cancelLabel = (row) =>
    isFutureReservation(row) ? t('myBookings.cancelReservation') : t('myBookings.cancelTooltip');
  const canCancel = (row) => row._status === 'PENDING' || isFutureReservation(row);

  const cols = [
    {
      key: '_thing',
      headerName: t('myBookings.colThing'),
      transform: (row) => (
        <div className="table-cell-lines">
          <Link to={`/things/${row._thingCode}`}>{row._thingHeadline}</Link>
          {row._ownerName && <p className="table-cell-line--muted">{row._ownerName}</p>}
        </div>
      ),
    },
    {
      key: '_when',
      headerName: t('myBookings.colWhen'),
      transform: (row) => (
        <div className="table-cell-lines">
          <p>
            {t('myBookings.requested', {
              date: formatDate(row._created),
            })}
          </p>
          <p>{row._when || t('myBookings.noDates')}</p>
        </div>
      ),
    },
    {
      key: '_status',
      headerName: t('myBookings.colStatus'),
      transform: (row) => (
        <div className="table-status-cell">
          {row._showType && <Tag>{t('types.' + row._type)}</Tag>}
          <StatusLabel type={STATUS_TYPES[row._status] || 'neutral'}>
            {STATUS_LABELS[row._status] || row._status}
          </StatusLabel>
          {row._status === 'EXPIRED' && (
            <p
              style={{
                margin: 0,
                fontSize: 'var(--fontsize-body-s)',
                color: 'var(--color-black-60)',
              }}
            >
              {t('myBookings.expiredHelper')}
            </p>
          )}
        </div>
      ),
    },
    {
      key: '_actions',
      // Named for a screen reader only: the buttons below say what they do,
      // and an empty <th> leaves the column nameless (axe empty-table-header).
      headerName: <span className="sr-only">{t('common.colActions')}</span>,
      transform: (row) =>
        canCancel(row) ? (
          <TooltipButton
            tooltip={cancelLabel(row)}
            onClick={() => cancelAction(row)}
            disabled={cancelling === row._code}
          >
            <IconCrossCircle aria-hidden />
          </TooltipButton>
        ) : null,
      // The card's face: the same cancel as a button that says what it does.
      cardTransform: (row) =>
        canCancel(row) ? (
          <div className="button-row-wide">
            <Button
              variant="secondary"
              style={btnSecondaryStyle}
              onClick={() => cancelAction(row)}
              disabled={cancelling === row._code}
            >
              {cancelLabel(row)}
            </Button>
          </div>
        ) : null,
    },
  ];

  return (
    <PageLayout title={t('myBookings.pageTitle')} backTo="/" backLabel={t('common.home')}>
      {bookings.length === 0 ? (
        <div>
          <p>{t('myBookings.noBookings')}</p>
          <div className="spacer-m" />
          <div className="button-row-wide">
            <ButtonLink to="/" style={btnStyle}>
              {t('myBookings.goHome')}
            </ButtonLink>
          </div>
        </div>
      ) : (
        <>
          {(() => {
            // Each table decides on its own whether its rows carry the verb's label:
            // only when it mixes verbs.
            const pendingRows = markMixedVerbs(
              rows.filter((r) => r._status === 'PENDING' || isFutureReservation(r))
            );
            const otherRows = markMixedVerbs(
              rows.filter((r) => !(r._status === 'PENDING' || isFutureReservation(r)))
            );
            const topHeading = rows.some((r) => r._type === 'RESERVE_THING')
              ? t('myBookings.currentHeading')
              : t('myBookings.statusPending');
            return (
              <>
                <h2>{topHeading}</h2>
                <div className="spacer-s" />
                {pendingRows.length === 0 ? (
                  <p className="text-muted">{t('myBookings.noPending')}</p>
                ) : (
                  <ResponsiveTable
                    cols={cols}
                    caption={<span className="sr-only">{t('myBookings.captionPending')}</span>}
                    rows={pendingRows}
                    indexKey="_id"
                    renderIndexCol={false}
                    dense
                    theme={tableTheme}
                  />
                )}
                {otherRows.length > 0 && (
                  <>
                    <div className="spacer-xl" />
                    <h2>{t('myBookings.pastRequests')}</h2>
                    <div className="spacer-s" />
                    <ResponsiveTable
                      cols={cols}
                      caption={<span className="sr-only">{t('myBookings.captionPast')}</span>}
                      rows={otherRows}
                      indexKey="_id"
                      renderIndexCol={false}
                      dense
                      theme={tableTheme}
                    />
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
          {/* A pager is a loose action button like any other: in a wide row, so on a
              phone it is the width of the screen. */}
          <div className="button-row-wide">
            <Button
              variant="secondary"
              onClick={loadMore}
              disabled={loadingMore}
              style={btnSecondaryStyle}
            >
              {t('common.loadMore')}
            </Button>
          </div>
        </>
      )}

      {cancelRow && (
        <CancelReservationDialog
          row={cancelRow}
          body={t('myBookings.cancelReservationConfirmBody')}
          confirmLabel={t('myBookings.cancelReservation')}
          busy={cancelling === cancelRow._code}
          onConfirm={() => {
            const row = cancelRow;
            setCancelRow(null);
            handleCancel(row._code, { reservation: true });
          }}
          onClose={() => setCancelRow(null)}
          btnStyle={btnStyle}
          btnSecondaryStyle={btnSecondaryStyle}
        />
      )}

      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
