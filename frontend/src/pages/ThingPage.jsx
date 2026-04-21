import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Button,
  Fieldset,
  Highlight,
  IconCalendar,
  IconEuroSign,
  IconLocation,
  IconShield,
  IconGroup,
  IconTicket,
  Koros,
  Notification,
  TextArea,
} from 'hds-react';
import { DATE_TYPES, ORDER_TYPE, EVENT_TYPE, WISH_TYPE, SHARE_TYPE, ASSET_TYPE, SWAP_TYPE, APPOINTMENT_TYPE } from '../constants/things';
import { apiFetch } from '../services/api';

const isDateType = (type) => DATE_TYPES.includes(type);
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import ThingTags from '../components/ThingTags';
import Toast from '../components/Toast';
import MarkdownText from '../components/MarkdownText';
import WeeklySchedule from '../components/WeeklySchedule';

export default function ThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const userCode = localStorage.getItem('userCode');

  const [thing, setThing] = useState(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  useEffect(() => { document.title = thing ? t('titles.thing', { headline: thing.headline }) : t('titles.thingDefault'); }, [thing, t]);

  // Reservation state
  const [submitting, setSubmitting] = useState(false);
  const [requested, setRequested] = useState(false);
  const [bookingAction, setBookingAction] = useState(false);
  const [bookings, setBookings] = useState([]);
  const [activePendingCode, setActivePendingCode] = useState(null);

  // FAQ state
  const [faqs, setFaqs] = useState([]);
  const [faqQuestion, setFaqQuestion] = useState('');
  const [faqSubmitting, setFaqSubmitting] = useState(false);
  const [answerTexts, setAnswerTexts] = useState({});
  const [answerSubmitting, setAnswerSubmitting] = useState({});

  // Transfer state
  const [transfers, setTransfers] = useState(null);

  // Stats state (for ASSET_THING)
  const [stats, setStats] = useState(null);

  // Event state
  const [attendees, setAttendees] = useState(null);
  const [isAttending, setIsAttending] = useState(false);
  const [attendSubmitting, setAttendSubmitting] = useState(false);

  // Wish state
  const [helpers, setHelpers] = useState(null);
  const [isHelping, setIsHelping] = useState(false);
  const [helpSubmitting, setHelpSubmitting] = useState(false);

  useEffect(() => {
    if (!userCode) {
      navigate('/login');
      return;
    }

    const fetchThing = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/`);
        if (res.ok) {
          setThing(await res.json());
        } else if (res.status === 403) {
          setError(t('thingPage.noPermission'));
        } else if (res.status === 404) {
          setError(t('thingPage.notFound'));
        } else {
          setError(t('thingPage.errorLoading'));
        }
      } catch {
        setError(t('common.connectionError'));
      }
    };

    const fetchFaqs = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/faq/`);
        if (res.ok) {
          const data = await res.json();
          setFaqs(data.results || data);
        }
      } catch { /* silently fail */ }
    };

    const fetchTransfers = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/transfers/`);
        if (res.ok) {
          setTransfers(await res.json());
        }
      } catch { /* silently fail */ }
    };

    const fetchAttendees = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/attendees/`);
        if (res.ok) {
          setAttendees(await res.json());
        }
      } catch { /* silently fail */ }
    };

    const fetchHelpers = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/helpers/`);
        if (res.ok) {
          setHelpers(await res.json());
        }
      } catch { /* silently fail */ }
    };

    const fetchStats = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/stats/`);
        if (res.ok) {
          setStats(await res.json());
        }
      } catch { /* silently fail */ }
    };

    fetchThing();
    fetchFaqs();
    fetchTransfers();
    fetchAttendees();
    fetchHelpers();
    fetchStats();
  }, [userCode, thingCode, navigate, t]);

  useEffect(() => {
    if (thing && thing.type === EVENT_TYPE && thing.deal) {
      setIsAttending(thing.deal.includes(userCode));
    }
    if (thing && thing.type === WISH_TYPE && thing.deal) {
      setIsHelping(thing.deal.includes(userCode));
    }
  }, [thing, userCode]);

  useEffect(() => {
    if (!thing || !userCode) return;
    const isAssetThing = thing.type === ASSET_TYPE;
    const isAppointmentThing = thing.type === APPOINTMENT_TYPE;
    const ownerView = thing.owner === userCode;
    if (!ownerView && !isAssetThing && !isAppointmentThing) return;
    const isDateBased = isDateType(thing.type);
    const isOrder = thing.type === ORDER_TYPE;
    const isSwapThing = thing.type === SWAP_TYPE;
    if (ownerView && !isDateBased && !isOrder && !isSwapThing && thing.status !== 'TAKEN') return;
    apiFetch(`/api/v1/things/${thing.code}/calendar/`)
      .then((res) => (res.ok ? res.json() : []))
      .then((data) => {
        const today = new Date();
        today.setHours(0, 0, 0, 0);
        const future = data.filter((b) => {
          if (!b.end_date && !b.delivery_date) return true;
          const d = new Date(b.end_date || b.delivery_date);
          d.setHours(0, 0, 0, 0);
          return d >= today;
        });
        const firstPending = future.find((b) => b.status === 'PENDING');
        setBookings(future);
        setActivePendingCode(firstPending?.code || null);
      })
      .catch(() => {});
  }, [thing, userCode]);

  if (error) {
    return (
      <div className="page-container">
        <Notification label={t('common.error')} type="error">{error}</Notification>
      </div>
    );
  }

  if (!thing) {
    return <LoadingSpinner />;
  }

  const isOwner = thing.owner === userCode;
  const isCollectionOwner = thing.collection_owner === userCode;
  const isEvent = thing.type === EVENT_TYPE;
  const isWish = thing.type === WISH_TYPE;
  const isShare = thing.type === SHARE_TYPE;
  const isSwap = thing.type === SWAP_TYPE;
  const isAsset = thing.type === ASSET_TYPE;
  const isAppointment = thing.type === APPOINTMENT_TYPE;
  const isDateBased = isDateType(thing.type);
  const isOrder = thing.type === ORDER_TYPE;
  const needsPage = isDateBased || isOrder || isSwap;
  const hasPendingBookings = bookings.some((b) => b.status === 'PENDING');
  const canHide = isOwner;
  const canDelete = isCollectionOwner || (isOwner && (!isShare || thing.transfer_count === 0));
  const showButton = !isOwner && thing.status !== 'INACTIVE';
  const buttonDisabled = thing.status === 'TAKEN' || submitting || requested || (isShare && !!thing.my_pending_booking);

  const editPath = code
    ? `/collections/${code}/things/${thing.code}/edit`
    : `/things/${thing.code}/edit`;

  const collectionCode = code || thing.collection_code;
  const backPath = collectionCode ? `/collections/${collectionCode}` : '/';
  const backLabel = thing.collection_headline || (collectionCode ? t('common.collection') : t('common.home'));

  const requestPath = code
    ? `/collections/${code}/things/${thing.code}/request`
    : `/things/${thing.code}/request`;

  const deletePath = code
    ? `/collections/${code}/things/${thing.code}/delete`
    : `/things/${thing.code}/delete`;

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
        setToast({ type: 'success', message: t('thingPage.holdRequested') });
      } else if (res.status === 400) {
        setToast({ type: 'error', message: t('thingPage.invalidRequest') });
      } else {
        setToast({ type: 'error', message: t('thingPage.errorSendingRequest') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setSubmitting(false);
    }
  };

  const handleHide = async () => {
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/hide/`, { method: 'POST' });
      if (res.ok) {
        setThing((prev) => ({ ...prev, status: 'INACTIVE' }));
        setToast({ type: 'success', message: t('thingPage.thingHidden') });
      } else {
        setToast({ type: 'error', message: t('thingPage.errorHidingThing') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    }
  };

  const handleActivate = async () => {
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/activate/`, { method: 'POST' });
      if (res.ok) {
        setThing((prev) => ({ ...prev, status: 'ACTIVE', deal: [] }));
        setToast({ type: 'success', message: t('thingPage.thingReactivated') });
      } else {
        setToast({ type: 'error', message: t('thingPage.errorReactivatingThing') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    }
  };

  const handleBookingAction = async (action) => {
    const code = activePendingCode;
    setBookingAction(true);
    try {
      const res = await apiFetch(`/api/v1/bookings/${code}/${action}/`, { method: 'POST' });
      if (res.ok) {
        const isDateBased = isDateType(thing.type);
        const isOrder = thing.type === ORDER_TYPE;
        if (isDateBased || isOrder) {
          if (action === 'accept') {
            const updated = bookings.map((b) => b.code === code ? { ...b, status: 'ACCEPTED' } : b);
            const nextPending = updated.find((b) => b.code !== code && b.status === 'PENDING');
            setBookings(updated);
            setActivePendingCode(nextPending?.code || null);
          } else {
            const remaining = bookings.filter((b) => b.code !== code);
            const nextPending = remaining.find((b) => b.status === 'PENDING');
            setBookings(remaining);
            setActivePendingCode(nextPending?.code || null);
          }
        } else {
          if (action === 'accept') {
            const updated = bookings.map((b) => b.code === code ? { ...b, status: 'ACCEPTED' } : b);
            const nextPending = updated.find((b) => b.code !== code && b.status === 'PENDING');
            setBookings(updated);
            setActivePendingCode(nextPending?.code || null);
            setThing((prev) => ({ ...prev, status: 'INACTIVE', pending_booking: nextPending?.code || null }));
          } else {
            const remaining = bookings.filter((b) => b.code !== code);
            const nextPending = remaining.find((b) => b.status === 'PENDING');
            setBookings(remaining);
            setActivePendingCode(nextPending?.code || null);
            setThing((prev) => ({ ...prev, status: 'ACTIVE', pending_booking: nextPending?.code || null }));
          }
        }
        setToast({ type: 'success', message: action === 'accept' ? t('thingPage.holdConfirmed') : t('thingPage.holdCancelled') });
      } else {
        setToast({ type: 'error', message: action === 'accept' ? t('thingPage.errorConfirmingHold') : t('thingPage.errorCancellingHold') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setBookingAction(false);
    }
  };

  const handleAttend = async () => {
    setAttendSubmitting(true);
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/attend/`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setIsAttending(data.attending);
        setAttendees((prev) => prev ? { ...prev, attendee_count: data.attendee_count } : prev);
        // Re-fetch attendees list
        const atRes = await apiFetch(`/api/v1/things/${thing.code}/attendees/`);
        if (atRes.ok) setAttendees(await atRes.json());
      } else {
        setToast({ type: 'error', message: t('common.connectionError') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setAttendSubmitting(false);
    }
  };

  const handleOfferHelp = async () => {
    setHelpSubmitting(true);
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/offer-help/`, { method: 'POST' });
      if (res.ok) {
        const data = await res.json();
        setIsHelping(data.offering);
        setHelpers((prev) => prev ? { ...prev, helper_count: data.helper_count } : prev);
        // Re-fetch helpers list
        const hlpRes = await apiFetch(`/api/v1/things/${thing.code}/helpers/`);
        if (hlpRes.ok) setHelpers(await hlpRes.json());
      } else {
        setToast({ type: 'error', message: t('common.connectionError') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setHelpSubmitting(false);
    }
  };

  const handleAskQuestion = async () => {
    if (!faqQuestion.trim()) return;
    setFaqSubmitting(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/faq/`, {
        method: 'POST',
        body: JSON.stringify({ question: faqQuestion.trim() }),
      });
      if (res.ok) {
        const newFaq = await res.json();
        setFaqs((prev) => [...prev, newFaq]);
        setFaqQuestion('');
        setToast({ type: 'success', message: t('thingPage.questionSent') });
      } else {
        setToast({ type: 'error', message: t('thingPage.errorSendingQuestion') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setFaqSubmitting(false);
    }
  };

  const handleAnswer = async (faqCode) => {
    const answer = (answerTexts[faqCode] || '').trim();
    if (!answer) return;
    setAnswerSubmitting((prev) => ({ ...prev, [faqCode]: true }));
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/faq/${faqCode}/answer/`, {
        method: 'POST',
        body: JSON.stringify({ answer }),
      });
      if (res.ok) {
        const updated = await res.json();
        setFaqs((prev) => prev.map((f) => (f.code === faqCode ? { ...f, ...updated } : f)));
        setAnswerTexts((prev) => ({ ...prev, [faqCode]: '' }));
        setToast({ type: 'success', message: t('thingPage.answerSent') });
      } else {
        setToast({ type: 'error', message: t('thingPage.errorSendingAnswer') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setAnswerSubmitting((prev) => ({ ...prev, [faqCode]: false }));
    }
  };

  const handleToggleVisibility = async (faq) => {
    const action = faq.is_visible ? 'hide' : 'show';
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/faq/${faq.code}/${action}/`, {
        method: 'POST',
      });
      if (res.ok) {
        setFaqs((prev) =>
          prev.map((f) => (f.code === faq.code ? { ...f, is_visible: !faq.is_visible } : f))
        );
      } else {
        setToast({ type: 'error', message: action === 'hide' ? t('thingPage.errorHidingQuestion') : t('thingPage.errorShowingQuestion') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    }
  };

  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--background-color': tc.color_02 ? `var(--color-${tc.color_02})` : undefined,
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_04})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
  } : undefined;

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
          <BackLink to={backPath} label={backLabel} />
        </div>
        <Koros
          className="form-hero-koros"
          type={localStorage.getItem('koro') || 'basic'}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">

      <div className="form-grid">
        {thing.thumbnail_url && (
          <img
            src={thing.thumbnail_url}
            alt={thing.headline}
            className="detail-image"
          />
        )}

        <ThingTags thing={thing} isOwner={isOwner} showType={false} />

        <p className="thing-card-meta">
          {new Date(thing.created).toLocaleDateString(i18n.language)}
          {thing.owner_name && ` — ${thing.owner_name}`}
        </p>

        <h1 className="page-title">{thing.headline}</h1>

        {thing.description && <MarkdownText text={thing.description} />}

        {thing.document_urls && thing.document_urls.length > 0 && (
          <div className="document-downloads">
            <h3>{t('documents.heading')}</h3>
            <ul className="document-list">
              {thing.document_urls.map((doc, i) => (
                <li key={i} className="document-list-item">
                  <a href={doc.url} target="_blank" rel="noopener noreferrer">{doc.filename}</a>
                </li>
              ))}
            </ul>
          </div>
        )}

        <div className="thing-card-info">
          {!isEvent && (
            <div className="thing-card-info-row">
              <IconTicket size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('thingPage.typeLabel')}</span>
              <span>{t('types.' + thing.type)}</span>
            </div>
          )}
          {thing.fee && (
            <div className="thing-card-info-row">
              <IconEuroSign size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('thingPage.priceLabel')}</span>
              <span>{thing.fee} €</span>
            </div>
          )}
          {thing.availability && (
            <div className="thing-card-info-row">
              <IconCalendar size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('thingPage.availabilityLabel')}</span>
              <span>{t('availability.' + thing.availability)}</span>
            </div>
          )}
          {thing.location && (
            <div className="thing-card-info-row">
              <IconLocation size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('thingPage.locationLabel')}</span>
              <span>{thing.location}</span>
            </div>
          )}
          {!isEvent && thing.condition && (
            <div className="thing-card-info-row">
              <IconShield size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('thingPage.conditionLabel')}</span>
              <span>{t('condition.' + thing.condition)}</span>
            </div>
          )}
          {thing.event_date && (
            <div className="thing-card-info-row">
              <IconCalendar size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('events.eventDate')}:</span>
              <span>{new Date(thing.event_date).toLocaleDateString(i18n.language, { day: 'numeric', month: 'long', year: 'numeric', hour: '2-digit', minute: '2-digit' })}</span>
            </div>
          )}
          {thing.type === ASSET_TYPE && thing.booking_unit && (
            <div className="thing-card-info-row">
              <IconCalendar size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('asset.bookingUnit')}</span>
              <span>{thing.booking_unit === 'HOUR' ? t('asset.unitHour') : t('asset.unitDay')}</span>
            </div>
          )}
          {isAppointment && thing.slot_duration && (
            <div className="thing-card-info-row">
              <IconCalendar size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('appointment.slotDuration')}</span>
              <span>{t('appointment.minutes', { count: thing.slot_duration })}</span>
            </div>
          )}
          {isEvent && attendees && (
            <div className="thing-card-info-row">
              <IconGroup size="m" aria-hidden="true" />
              <span className="thing-card-info-label">{t('events.attendeesHeading')}:</span>
              <span>{attendees.attendee_count}</span>
            </div>
          )}
        </div>

        {/* Weekly schedule for APPOINTMENT_THING */}
        {isAppointment && thing.slot_duration && (
          <WeeklySchedule
            thingCode={thing.code}
            isOwner={isOwner}
            requestPath={requestPath}
          />
        )}


        {/* Owner / shared-asset/appointment bookings list */}
        {(isOwner || isAsset || isAppointment) && bookings.length > 0 && (() => {
          const pendingCount = bookings.filter((b) => b.status === 'PENDING').length;
          return (
            <ul className="thing-card-bookings">
              {bookings.map((b) => {
                const isActive = b.code === activePendingCode;
                const showStar = isActive && pendingCount > 1;
                return (
                  <li key={b.code} style={{ fontWeight: isActive ? 'bold' : 'normal' }}>
                    {b.requester_name && <>{b.requester_name}. </>}
                    {b.created && <>{new Date(b.created).toLocaleDateString(i18n.language, { day: 'numeric', month: 'short' })}. </>}
                    {b.start_date && b.end_date && (
                      <>
                        {new Date(b.start_date).toLocaleDateString(i18n.language)} – {new Date(b.end_date).toLocaleDateString(i18n.language)}
                        {b.start_time && b.end_time && <> ({b.start_time.slice(0, 5)}–{b.end_time.slice(0, 5)})</>}
                      </>
                    )}
                    {b.delivery_date && <>{new Date(b.delivery_date).toLocaleDateString(i18n.language)}, {t('thingCard.qty')} {b.quantity}</>}
                    {b.offered_thing_headlines && b.offered_thing_headlines.length > 0 && (
                      <><br />{t('swap.offeredItems')}: {b.offered_thing_headlines.join(', ')}</>
                    )}
                    {' '}
                    <span style={{ color: b.status === 'ACCEPTED' ? 'var(--color-success)' : 'var(--color-alert-dark)' }}>
                      ({b.status === 'ACCEPTED' ? t('thingCard.confirmed') : t('thingCard.pending')}){showStar ? ' *' : ''}
                    </span>
                  </li>
                );
              })}
            </ul>
          );
        })()}

        {/* Owner actions */}
        {isOwner && thing.status === 'ACTIVE' && (
          <div className="button-col">
            {needsPage && activePendingCode && (
              <>
                <Button fullWidth disabled={bookingAction} onClick={() => handleBookingAction('accept')} style={btnStyle}>
                  {t('thingCard.confirmHold')}
                </Button>
                <Button fullWidth variant="secondary" disabled={bookingAction} onClick={() => handleBookingAction('reject')} style={btnSecondaryStyle}>
                  {t('thingCard.cancelHold')}
                </Button>
              </>
            )}
            <Link to={editPath} style={{ display: 'contents' }}>
              {needsPage && activePendingCode ? (
                <Button fullWidth variant="secondary" style={btnSecondaryStyle}>{t('common.edit')}</Button>
              ) : (
                <Button fullWidth style={btnStyle}>{t('common.edit')}</Button>
              )}
            </Link>
            {!hasPendingBookings && canHide && (
              <Button fullWidth variant="secondary" style={btnSecondaryStyle} onClick={handleHide}>{t('thingPage.hide')}</Button>
            )}
          </div>
        )}

        {isOwner && thing.status === 'TAKEN' && (
          <div className="button-col">
            <Button fullWidth disabled={bookingAction} onClick={() => handleBookingAction('accept')} style={btnStyle}>
              {t('thingCard.confirmHold')}
            </Button>
            <Button fullWidth variant="secondary" disabled={bookingAction} onClick={() => handleBookingAction('reject')} style={btnSecondaryStyle}>
              {t('thingCard.cancelHold')}
            </Button>
            <Link to={editPath} style={{ display: 'contents' }}>
              <Button fullWidth variant="secondary" style={btnSecondaryStyle}>{t('common.edit')}</Button>
            </Link>
          </div>
        )}

        {isOwner && thing.status === 'INACTIVE' && (
          <div className="button-row">
            <Button style={{ ...btnStyle, width: '100%' }} onClick={handleActivate}>
              {t('thingCard.reactivate')}
            </Button>
            <Link to={editPath} style={{ display: 'contents' }}>
              <Button variant="secondary" style={{ ...btnSecondaryStyle, width: '100%' }}>{t('common.edit')}</Button>
            </Link>
            {canDelete && (
              <Button
                variant="secondary"
                style={{ ...btnSecondaryStyle, width: '100%' }}
                onClick={() => navigate(deletePath, { state: { backPath, backLabel } })}
              >
                {t('common.delete')}
              </Button>
            )}
          </div>
        )}

        {isCollectionOwner && !isOwner && (
          <div className="button-row">
            <Button
              variant="secondary"
              style={{ ...btnSecondaryStyle, width: '100%' }}
              onClick={() => navigate(deletePath, { state: { backPath, backLabel } })}
            >
              {t('common.delete')}
            </Button>
          </div>
        )}

        {/* Attend button for event things */}
        {showButton && isEvent && (
          <Button
            fullWidth
            disabled={attendSubmitting}
            style={isAttending ? btnSecondaryStyle : btnStyle}
            variant={isAttending ? 'secondary' : 'primary'}
            onClick={handleAttend}
          >
            {isAttending ? t('events.attending') : t('events.attend')}
          </Button>
        )}

        {/* Offer help button for wish things */}
        {showButton && isWish && (
          <Button
            fullWidth
            disabled={helpSubmitting}
            style={isHelping ? btnSecondaryStyle : btnStyle}
            variant={isHelping ? 'secondary' : 'primary'}
            onClick={handleOfferHelp}
          >
            {isHelping ? t('wishes.helping') : t('wishes.offerHelp')}
          </Button>
        )}

        {/* Reservation button for non-event/non-wish invited users */}
        {showButton && !isEvent && !isWish && (
          <Button
            fullWidth
            disabled={buttonDisabled}
            style={btnStyle}
            onClick={needsPage ? () => navigate(requestPath, { state: { backPath: code ? `/collections/${code}/things/${thing.code}` : `/things/${thing.code}`, backLabel: thing.headline } }) : handleRequest}
          >
            {submitting ? t('common.sending') : buttonDisabled ? t('thingCard.waitingForConfirmation') : isSwap ? t('swap.swapButton') : t('thingCard.hold')}
          </Button>
        )}

        {/* Attendees section for event things */}
        {isEvent && attendees && (
          <>
            <div className="spacer-m" />
            <hr />
            <div className="spacer-m" />
            <h2>{t('events.attendeesHeading')}</h2>
            <p>{t('events.attendeeCount', { count: attendees.attendee_count })}</p>
            {attendees.attendees.length > 0 ? (
              <ul className="thing-card-bookings">
                {attendees.attendees.map((a) => (
                  <li key={a.code}>{a.name}</li>
                ))}
              </ul>
            ) : (
              <p>{t('events.noAttendees')}</p>
            )}
          </>
        )}

        {/* Helpers section for wish things */}
        {isWish && helpers && (
          <>
            <div className="spacer-m" />
            <hr />
            <div className="spacer-m" />
            <h2>{t('wishes.helpersHeading')}</h2>
            <p>{t('wishes.helperCount', { count: helpers.helper_count })}</p>
            {helpers.helpers.length > 0 ? (
              <ul className="thing-card-bookings">
                {helpers.helpers.map((h) => (
                  <li key={h.code}>{h.name}</li>
                ))}
              </ul>
            ) : (
              <p>{t('wishes.noHelpers')}</p>
            )}
          </>
        )}

        {/* FAQs Section */}
        <div className="spacer-m" />
        <hr />
        <div className="spacer-m" />
        <h2>{t('thingPage.faqHeading')}</h2>

        {faqs.length === 0 ? (
          <p>{t('thingPage.noQuestions')}</p>
        ) : (
          <div className="faq-grid">
            {faqs.map((faq) => (
              <div
                key={faq.code}
                style={{ opacity: faq.is_visible === false ? 0.6 : 1 }}
              >
                <Highlight
                  text={faq.question}
                  reference={faq.answer || undefined}
                />
                {!faq.answer && isOwner && (
                  <>
                  <div className="spacer-m" />
                  <div className="summary-grid">
                    <TextArea
                      id={`faq-reply-${faq.code}`}
                      label={t('thingPage.replyLabel')}
                      value={answerTexts[faq.code] || ''}
                      onChange={(e) =>
                        setAnswerTexts((prev) => ({ ...prev, [faq.code]: e.target.value }))
                      }
                    />
                    <div className="spacer-m" />
                    <div className="faq-actions" style={{ flexDirection: 'column', width: '100%' }}>
                      <Button
                        fullWidth
                        disabled={answerSubmitting[faq.code] || !(answerTexts[faq.code] || '').trim()}
                        onClick={() => handleAnswer(faq.code)}
                        style={btnStyle}
                      >
                        {answerSubmitting[faq.code] ? t('common.sending') : t('thingPage.replyLabel')}
                      </Button>
                      <Button
                        variant="secondary"
                        fullWidth
                        onClick={() => handleToggleVisibility(faq)}
                        style={btnSecondaryStyle}
                      >
                        {faq.is_visible === false ? t('thingPage.show') : t('thingPage.hide')}
                      </Button>
                      {faq.is_visible === false && (
                        <span className="faq-meta">
                          {t('thingPage.hidden')}
                        </span>
                      )}
                    </div>
                  </div>
                  </>
                )}
                {faq.answer && isOwner && (
                  <div className="faq-actions">
                    <Button
                      variant="secondary"
                      onClick={() => handleToggleVisibility(faq)}
                      style={btnSecondaryStyle}
                    >
                      {faq.is_visible === false ? t('thingPage.show') : t('thingPage.hide')}
                    </Button>
                    {faq.is_visible === false && (
                      <span className="faq-meta">
                        {t('thingPage.hidden')}
                      </span>
                    )}
                  </div>
                )}
              </div>
            ))}
          </div>
        )}


        <div className="spacer-m" />
        {!isOwner && (
          <div className="summary-grid section-mt">
            <TextArea
              id="thing-faq-question"
              label={t('thingPage.faqLabel')}
              value={faqQuestion}
              onChange={(e) => setFaqQuestion(e.target.value)}
              placeholder={t('thingPage.faqPlaceholder')}
            />
            <Button
              disabled={faqSubmitting || !faqQuestion.trim()}
              onClick={handleAskQuestion}
              style={{ ...btnStyle, width: '100%' }}
            >
              {faqSubmitting ? t('common.sending') : t('thingPage.sendQuestion')}
            </Button>
          </div>
        )}

        {/* Journey / Transfer history */}
        {transfers && transfers.total_transfers > 0 && (
          <>
            <div className="spacer-m" />
            <hr />
            <div className="spacer-m" />
            {transfers.is_share_in_community ? (
              <>
                <h2>{t('transfers.shareHistoryHeading')}</h2>
                {transfers.original_owner_name && (
                  <p className="share-original-owner">
                    <strong>{t('transfers.originallySharedBy', { name: transfers.original_owner_name })}</strong>
                  </p>
                )}
                <p>{t('transfers.sharedByCount', { count: transfers.unique_homes })}</p>
                <div className="share-timeline">
                  {transfers.transfers.map((tr) => (
                    <div key={tr.code} className="share-timeline-entry">
                      <strong>{tr.to_user_name}</strong>
                      {' — '}
                      {new Date(tr.lent_date).toLocaleDateString(i18n.language)}
                      {tr.returned_date && (
                        <> · {t('transfers.returnedOn', { date: new Date(tr.returned_date).toLocaleDateString(i18n.language) })}</>
                      )}
                    </div>
                  ))}
                </div>
              </>
            ) : (
              <>
                <h2>{t('transfers.heading')}</h2>
                <p>{t('transfers.journeyCount', { count: transfers.unique_homes })}</p>
                {transfers.current_holder_name && (
                  <p><strong>{t('transfers.currentlyWith', { name: transfers.current_holder_name })}</strong></p>
                )}
                <ul className="thing-card-bookings">
                  {transfers.transfers.map((tr) => (
                    <li key={tr.code}>
                      {tr.from_user_name} {t('transfers.to')} {tr.to_user_name}
                      {' — '}
                      {t('transfers.lentOn', { date: new Date(tr.lent_date).toLocaleDateString(i18n.language) })}
                      {tr.returned_date && (
                        <> · {t('transfers.returnedOn', { date: new Date(tr.returned_date).toLocaleDateString(i18n.language) })}</>
                      )}
                    </li>
                  ))}
                </ul>
              </>
            )}
          </>
        )}

        {/* Usage statistics for ASSET_THING */}
        {isAsset && stats && (
          <>
            <div className="spacer-m" />
            <hr />
            <div className="spacer-m" />
            <h2>{t('asset.statsHeading')}</h2>
            {stats.total_bookings === 0 ? (
              <p>{t('asset.noStats')}</p>
            ) : (
              <>
                <p>
                  {t('asset.totalBookings', { count: stats.total_bookings })}
                  {' · '}
                  {t('asset.uniqueUsers', { count: stats.unique_users })}
                </p>
                {stats.monthly_usage && stats.monthly_usage.length > 0 && (
                  <>
                    <h3>{t('asset.monthlyHeading')}</h3>
                    <ul className="thing-card-bookings">
                      {stats.monthly_usage.map((m, i) => (
                        <li key={i}>
                          {new Date(m.month).toLocaleDateString(i18n.language, { month: 'long', year: 'numeric' })}
                          {' — '}
                          {m.user_name}: {t('asset.bookingsLabel', { count: m.bookings })}
                        </li>
                      ))}
                    </ul>
                  </>
                )}
              </>
            )}
          </>
        )}
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
