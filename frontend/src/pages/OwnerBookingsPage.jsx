import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import {
  Button,
  Notification,
  StatusLabel,
  Tag,
  IconBell,
  IconCheck,
  IconCrossCircle,
} from 'hds-react';
import ThemedDialog from '../components/ThemedDialog';
import { DATE_TYPES } from '../constants/things';
import { apiFetch, codedErrorMessage } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import StatusRegion from '../components/StatusRegion';
import Toast from '../components/Toast';
import TooltipButton from '../components/TooltipButton';
import useTheeeme from '../hooks/useTheeeme';
import { useLocalized } from '../utils/localized';
import { formatDate, formatBookingWhen } from '../utils/rental';
import { markMixedVerbs } from '../utils/bookingRows';
import { phoneHref } from '../utils/phone';
import ButtonLink from '../components/ButtonLink';
import CancelReservationDialog from '../components/CancelReservationDialog';
import ResponsiveTable from '../components/ResponsiveTable';
import { collectionThingPath } from '../utils/collectionPath';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { errorKey, translateError } from '../utils/errorKey';
import { withQuantity } from '../utils/quantity';

/**
 * The owner's side of MyBookingsPage: every request made on their things, in one
 * place, answerable from here.
 *
 * The asymmetry this closes: a requester has always had /my-bookings, while an
 * owner had only the email, an inbox banner, or opening each collection in turn.
 * An owner with five collections had no single answer to "who is waiting on me?".
 * `GET /api/v1/owner-bookings/` existed and was documented all along — nothing in
 * the frontend called it.
 *
 * Mirrors MyBookingsPage deliberately (same table shape, same pending/past split,
 * same pager) so the two sides of a booking read the same way; the differences
 * are the column showing who asked rather than who owns, and the actions being
 * accept/reject rather than cancel.
 *
 * On a phone each row is a card (`ResponsiveTable`) and the
 * decisions are buttons with their words on them, where the table has the ✓ and ⊗
 * icons that name themselves in a tooltip. Both faces call the same handlers
 * (`acceptRow`, `rejectRow`, `setCancelRow`, `handleRemindReturn`), so the
 * transfer-of-ownership dialog and the reservation-cancel dialog stand in front
 * of a card exactly as they stand in front of the icon.
 *
 * A loan or rental that is past its return date carries one more action,
 * "remind them to return it" (`can_remind_return`, which the server decides:
 * overdue, and not lent again since). It is one nudge a day per booking, so the
 * action greys out once it has gone and the row says when.
 */
const STATUS_TYPES = {
  PENDING: 'alert',
  ACCEPTED: 'success',
  REJECTED: 'error',
  CANCELLED: 'neutral',
  EXPIRED: 'neutral',
};

export default function OwnerBookingsPage() {
  const { t } = useTranslation();
  const L = useLocalized();
  const { btnStyle, btnSecondaryStyle, tableTheme } = useTheeeme();
  const [bookings, setBookings] = useState(null);
  const [next, setNext] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  const [acting, setActing] = useState(null);
  // The booking whose return reminder was just sent: its row says so in a live
  // region, once. What stays is the grey "Reminded on …" line, which comes from
  // the booking itself and survives a reload.
  const [remindedNow, setRemindedNow] = useState(null);
  // The row whose acceptance would hand the thing over for good, pending
  // confirmation. Accepting a GIFT or SELL that isn't endless flips it INACTIVE,
  // adds the requester to `deal` and writes a ThingTransfer — the owner no
  // longer has it, and there is no undo. A loan, a rental and an endless
  // gift all come back or never run out, so those accept straight away.
  const [transferRow, setTransferRow] = useState(null);
  // A member's confirmed reservation waiting on the curator's confirm before it
  // is cancelled: it tells them, frees the slot and cannot be undone
  // (CancelReservationDialog). Declining a *pending* request stays one click.
  const [cancelRow, setCancelRow] = useState(null);
  useDocumentTitle(t('titles.ownerBookings'));

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
        const res = await apiFetch('/api/v1/owner-bookings/');
        if (res.ok) {
          const data = await res.json();
          setBookings(data.results);
          setNext(data.next || null);
        } else {
          setError(errorKey('ownerBookings.errorLoading'));
        }
      } catch {
        setError(errorKey('common.connectionError'));
      }
    };
    fetchBookings();
  }, [t]);

  const handleAction = async (bookingCode, action) => {
    setActing(bookingCode);
    try {
      const res = await apiFetch(`/api/v1/bookings/${bookingCode}/${action}/`, { method: 'POST' });
      if (res.ok) {
        setBookings((prev) =>
          prev.map((b) =>
            b.code === bookingCode
              ? { ...b, status: action === 'accept' ? 'ACCEPTED' : 'REJECTED' }
              : b
          )
        );
        setToast({
          type: 'success',
          message: action === 'accept' ? t('ownerBookings.accepted') : t('ownerBookings.rejected'),
        });
      } else {
        setToast({ type: 'error', message: t('ownerBookings.errorActing') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setActing(null);
    }
  };

  // "Remind them to return it": mails the borrower of a loan that is overdue,
  // in the name of whoever presses. The server allows one a day per booking and
  // says so with a coded 429, which `requestErrors` words; anything else is the
  // page's own generic line.
  const handleRemindReturn = async (bookingCode) => {
    setActing(bookingCode);
    try {
      const res = await apiFetch(`/api/v1/bookings/${bookingCode}/remind-return/`, {
        method: 'POST',
      });
      if (res.ok) {
        setBookings((prev) =>
          prev.map((b) =>
            b.code === bookingCode ? { ...b, return_reminded_at: new Date().toISOString() } : b
          )
        );
        setRemindedNow(bookingCode);
      } else {
        const data = await res.json().catch(() => null);
        setToast({
          type: 'error',
          message: codedErrorMessage(data) || t('ownerBookings.errorActing'),
        });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setActing(null);
    }
  };

  // The owner may cancel a member's confirmed reservation that hasn't started
  // (they need the space). Same endpoint as the guest's cancel; the backend
  // branches on the thing type and notifies the other party.
  const handleCancelReservation = async (bookingCode) => {
    setActing(bookingCode);
    try {
      const res = await apiFetch(`/api/v1/bookings/${bookingCode}/cancel/`, { method: 'POST' });
      if (res.ok) {
        setBookings((prev) =>
          prev.map((b) => (b.code === bookingCode ? { ...b, status: 'CANCELLED' } : b))
        );
        setToast({ type: 'success', message: t('ownerBookings.reservationCancelled') });
      } else {
        setToast({ type: 'error', message: t('ownerBookings.errorActing') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setActing(null);
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

  if (!bookings) return <LoadingSpinner />;

  const rows = bookings.map((b) => ({
    _id: b.code,
    _code: b.code,
    _type: b.thing_type,
    _status: b.status,
    _thingCode: b.thing_code,
    _thingHeadline: withQuantity(t, L(b.thing_headline) || b.thing_code, b.quantity),
    _collectionCode: b.collection_code,
    _collectionKind: b.collection_kind,
    _collectionHeadline: L(b.collection_headline),
    _requesterName: b.requester_name,
    _requesterEmail: b.requester_email,
    _contactPhone: b.contact_phone,
    _startDate: b.start_date,
    _endDate: b.end_date,
    _when: formatBookingWhen(b),
    _created: b.created,
    _projectNote: b.project_note,
    // The founder of a network sees every entity's requests and may only reject
    // the ones that are not theirs; an older payload without the field decides.
    _canDecide: b.can_decide !== false,
    _canRemindReturn: !!b.can_remind_return,
    _returnRemindedAt: b.return_reminded_at,
    _transfersOwnership: !DATE_TYPES.includes(b.thing_type) && !b.thing_is_endless,
  }));

  const todayIso = new Date().toISOString().slice(0, 10);
  const isFutureReservation = (row) =>
    row._type === 'RESERVE_THING' && row._status === 'ACCEPTED' && row._startDate >= todayIso;

  // What accepting and declining do, once, for the table's icons and the card's
  // buttons alike. Accepting a hand-over asks first (`transferRow`).
  const acceptRow = (row) =>
    row._transfersOwnership ? setTransferRow(row) : handleAction(row._code, 'accept');
  const rejectRow = (row) => handleAction(row._code, 'reject');

  // Reminded today, by the browser's calendar: the action waits for tomorrow.
  // (The server's day is the one that decides; this only keeps a press the
  // server would refuse from being offered.)
  const remindedToday = (row) =>
    !!row._returnRemindedAt && formatDate(row._returnRemindedAt) === formatDate(new Date());

  // The live region under the action. It exists on every row that has the
  // action, so the message is announced when it lands in it.
  const remindStatus = (row) => (
    <StatusRegion>
      {remindedNow === row._code && (
        <p className="table-cell-line--muted">{t('ownerBookings.remindReturnSent')}</p>
      )}
    </StatusRegion>
  );

  const cols = [
    {
      key: '_thing',
      headerName: t('myBookings.colThing'),
      transform: (row) => (
        <div className="table-cell-lines">
          <Link
            to={
              row._collectionCode
                ? collectionThingPath(row._collectionCode, row._collectionKind, row._thingCode)
                : `/things/${row._thingCode}`
            }
          >
            {row._thingHeadline}
          </Link>
          {/* Which group this request is about. The page pools requests across
              every PROPRIETARY collection the viewer curates, so a co-curator
              of more than one needs it to tell the rows apart. */}
          {row._collectionHeadline && (
            <p className="table-cell-line--muted">{row._collectionHeadline}</p>
          )}
        </div>
      ),
    },
    {
      key: '_whoWhen',
      headerName: t('ownerBookings.colWhoWhen'),
      transform: (row) => (
        <div className="table-cell-lines">
          {/* Always shown: a requester who never set a name arrives as '' from
              `requester_name` (the serializer never puts their address in the name's
              place), and dropping the line entirely loses "who asked".
              `common.aMember` is the same stand-in the inbox and the cards use. */}
          <p>
            {t('ownerBookings.requestedBy', {
              name: row._requesterName || t('common.aMember'),
            })}
          </p>
          {/* And the address itself, under the name, as a link: the
              reader runs this thing, and the request email already carries it to them
              — the exception to never naming anyone by their address, the reader holds
              it. It arrives in
              `requester_email`; the line is left out when it comes empty. Not a card's
              own line: `ResponsiveTable` paints the card from this same cell. */}
          {row._requesterEmail && (
            <p>
              <a href={`mailto:${row._requesterEmail}`}>{row._requesterEmail}</a>
            </p>
          )}
          {/* The optional contact phone, only while the server still serves it (it
              comes empty from the day after the booking). The link dials the digits
              and the +; the text is shown as it was typed. */}
          {row._contactPhone && (
            <p>
              <a href={`tel:${phoneHref(row._contactPhone)}`}>{row._contactPhone}</a>
            </p>
          )}
          <p>
            {t('myBookings.requested', {
              date: formatDate(row._created),
            })}
          </p>
          <p>{row._when || t('myBookings.noDates')}</p>
          {row._returnRemindedAt && (
            <p className="table-cell-line--muted">
              {t('ownerBookings.remindedOn', { date: formatDate(row._returnRemindedAt) })}
            </p>
          )}
          {row._projectNote && (
            <p className="table-cell-line--note">
              {t('reservation.noteFrom', { note: row._projectNote })}
            </p>
          )}
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
        </div>
      ),
    },
    {
      key: '_actions',
      // Named for a screen reader only: the buttons below say what they do,
      // and an empty <th> leaves the column nameless (axe empty-table-header).
      headerName: <span className="sr-only">{t('common.colActions')}</span>,
      transform: (row) =>
        row._status === 'PENDING' ? (
          <div style={{ display: 'flex', gap: 'var(--spacing-xs)', justifyContent: 'flex-end' }}>
            {row._canDecide && (
              <TooltipButton
                tooltip={t('ownerBookings.acceptTooltip')}
                onClick={() => acceptRow(row)}
                disabled={acting === row._code}
              >
                <IconCheck aria-hidden />
              </TooltipButton>
            )}
            <TooltipButton
              tooltip={t('ownerBookings.rejectTooltip')}
              onClick={() => rejectRow(row)}
              disabled={acting === row._code}
            >
              <IconCrossCircle aria-hidden />
            </TooltipButton>
          </div>
        ) : isFutureReservation(row) ? (
          <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
            <Button
              variant="supplementary"
              size="small"
              iconStart={<IconCrossCircle aria-hidden />}
              onClick={() => setCancelRow(row)}
              disabled={acting === row._code}
              style={btnSecondaryStyle}
            >
              {t('ownerBookings.cancelReservation')}
            </Button>
          </div>
        ) : row._canRemindReturn ? (
          <div>
            <div style={{ display: 'flex', justifyContent: 'flex-end' }}>
              <TooltipButton
                tooltip={t('ownerBookings.remindReturn')}
                onClick={() => handleRemindReturn(row._code)}
                disabled={acting === row._code || remindedToday(row)}
              >
                <IconBell aria-hidden />
              </TooltipButton>
            </div>
            {remindStatus(row)}
          </div>
        ) : null,
      // The card's face: the same decisions as buttons that say what they do.
      cardTransform: (row) =>
        row._status === 'PENDING' ? (
          <div className="button-row-wide">
            {row._canDecide && (
              <Button
                style={btnStyle}
                onClick={() => acceptRow(row)}
                disabled={acting === row._code}
              >
                {t('ownerBookings.acceptTooltip')}
              </Button>
            )}
            <Button
              variant="secondary"
              style={btnSecondaryStyle}
              onClick={() => rejectRow(row)}
              disabled={acting === row._code}
            >
              {t('ownerBookings.rejectTooltip')}
            </Button>
          </div>
        ) : isFutureReservation(row) ? (
          <div className="button-row-wide">
            <Button
              variant="secondary"
              style={btnSecondaryStyle}
              onClick={() => setCancelRow(row)}
              disabled={acting === row._code}
            >
              {t('ownerBookings.cancelReservation')}
            </Button>
          </div>
        ) : row._canRemindReturn ? (
          <>
            <div className="button-row-wide">
              <Button
                variant="secondary"
                style={btnSecondaryStyle}
                onClick={() => handleRemindReturn(row._code)}
                disabled={acting === row._code || remindedToday(row)}
              >
                {t('ownerBookings.remindReturn')}
              </Button>
            </div>
            {remindStatus(row)}
          </>
        ) : null,
    },
  ];

  // Each table decides on its own whether its rows carry the verb's label: only when
  // it mixes verbs.
  const pendingRows = markMixedVerbs(rows.filter((r) => r._status === 'PENDING'));
  const otherRows = markMixedVerbs(rows.filter((r) => r._status !== 'PENDING'));

  return (
    <PageLayout title={t('ownerBookings.pageTitle')} backTo="/" backLabel={t('common.home')}>
      {bookings.length === 0 ? (
        <div>
          <p>{t('ownerBookings.noBookings')}</p>
          <div className="spacer-m" />
          {/* Its own copy, not the requester page's "Browse collections": it leads
              to Home, where the owner's collections are. */}
          <div className="button-row-wide">
            <ButtonLink to="/" style={btnStyle}>
              {t('ownerBookings.emptyCta')}
            </ButtonLink>
          </div>
        </div>
      ) : (
        <>
          <h2>{t('ownerBookings.waitingOnYou')}</h2>
          <div className="spacer-s" />
          {pendingRows.length === 0 ? (
            <p className="text-muted">{t('ownerBookings.noPending')}</p>
          ) : (
            <ResponsiveTable
              cols={cols}
              caption={<span className="sr-only">{t('ownerBookings.captionPending')}</span>}
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
              {/* The reminder goes out with the presser's address as Reply-To, the
                  one place a manager's address reaches a borrower — so it is said
                  before the press, as the broadcast box says it. */}
              {otherRows.some((r) => r._canRemindReturn) && (
                <>
                  <p className="text-muted">{t('ownerBookings.remindReturnNotice')}</p>
                  <div className="spacer-s" />
                </>
              )}
              <ResponsiveTable
                cols={cols}
                caption={<span className="sr-only">{t('ownerBookings.captionPast')}</span>}
                rows={otherRows}
                indexKey="_id"
                renderIndexCol={false}
                dense
                theme={tableTheme}
              />
            </>
          )}
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

      {transferRow && (
        <ThemedDialog
          id="transfer-confirm"
          aria-labelledby="transfer-confirm-title"
          isOpen
          close={() => setTransferRow(null)}
          closeButtonLabelText={t('common.close')}
        >
          <ThemedDialog.Header
            id="transfer-confirm-title"
            title={t('thingCard.transferConfirmTitle')}
          />
          <ThemedDialog.Content>
            <p>{t('thingCard.transferConfirmBody')}</p>
            <p style={{ marginBottom: 0 }}>
              <strong>{transferRow._thingHeadline}</strong>
              {` — ${t('ownerBookings.requestedBy', {
                name: transferRow._requesterName || t('common.aMember'),
              })}`}
            </p>
          </ThemedDialog.Content>
          <ThemedDialog.ActionButtons>
            <Button
              style={btnStyle}
              disabled={acting === transferRow._code}
              onClick={() => {
                const row = transferRow;
                setTransferRow(null);
                handleAction(row._code, 'accept');
              }}
            >
              {t('thingCard.transferConfirm')}
            </Button>
            <Button
              variant="secondary"
              style={btnSecondaryStyle}
              onClick={() => setTransferRow(null)}
            >
              {t('common.cancel')}
            </Button>
          </ThemedDialog.ActionButtons>
        </ThemedDialog>
      )}

      {cancelRow && (
        <CancelReservationDialog
          row={cancelRow}
          who={t('ownerBookings.requestedBy', {
            name: cancelRow._requesterName || t('common.aMember'),
          })}
          body={t('ownerBookings.cancelReservationConfirmBody')}
          confirmLabel={t('ownerBookings.cancelReservation')}
          busy={acting === cancelRow._code}
          onConfirm={() => {
            const row = cancelRow;
            setCancelRow(null);
            handleCancelReservation(row._code);
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
