import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Button,
  Fieldset,
  Highlight,
  IconCalendar,
  IconEuroSign,
  IconLocation,
  IconShield,
  IconTicket,
  Koros,
  Notification,
  TextArea,
} from 'hds-react';
import { DATE_TYPES, ORDER_TYPE, TYPE_LABELS, AVAILABILITY_LABELS, CONDITION_LABELS } from '../constants/things';
import { apiFetch } from '../services/api';

const isDateType = (type) => DATE_TYPES.includes(type);
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import ThingTags from '../components/ThingTags';
import Toast from '../components/Toast';
import placeholderS from '../assets/image-s.png';
import placeholderM from '../assets/image-m.png';
import placeholderL from '../assets/image-l.png';

export default function ThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const userCode = localStorage.getItem('userCode');

  const [thing, setThing] = useState(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  useEffect(() => { document.title = thing ? `${thing.headline} — OIUEEI` : 'Thing — OIUEEI'; }, [thing]);

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
          setError('You do not have permission to view this thing.');
        } else if (res.status === 404) {
          setError('Thing not found.');
        } else {
          setError('Error loading thing.');
        }
      } catch {
        setError('Connection error.');
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

    fetchThing();
    fetchFaqs();
  }, [userCode, thingCode, navigate]);

  useEffect(() => {
    if (!thing || !userCode || thing.owner !== userCode) return;
    const isDateBased = isDateType(thing.type);
    const isOrder = thing.type === ORDER_TYPE;
    if (!isDateBased && !isOrder && thing.status !== 'TAKEN') return;
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
        <Notification label="Error" type="error">{error}</Notification>
      </div>
    );
  }

  if (!thing) {
    return <LoadingSpinner />;
  }

  const isOwner = thing.owner === userCode;
  const isDateBased = isDateType(thing.type);
  const isOrder = thing.type === ORDER_TYPE;
  const needsPage = isDateBased || isOrder;
  const hasPendingBookings = bookings.some((b) => b.status === 'PENDING');
  const showButton = !isOwner && thing.status !== 'INACTIVE';
  const buttonDisabled = thing.status === 'TAKEN' || submitting || requested;

  const editPath = code
    ? `/collections/${code}/things/${thing.code}/edit`
    : `/things/${thing.code}/edit`;

  const collectionCode = code || thing.collection_code;
  const backPath = collectionCode ? `/collections/${collectionCode}` : '/';
  const backLabel = thing.collection_headline || (collectionCode ? 'Collection' : 'Home');

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
        setToast({ type: 'success', message: 'Hold requested — you\'ll hear back soon.' });
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

  const handleHide = async () => {
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/hide/`, { method: 'POST' });
      if (res.ok) {
        setThing((prev) => ({ ...prev, status: 'INACTIVE' }));
        setToast({ type: 'success', message: 'Thing hidden.' });
      } else {
        setToast({ type: 'error', message: 'Error hiding thing.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    }
  };

  const handleActivate = async () => {
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/activate/`, { method: 'POST' });
      if (res.ok) {
        setThing((prev) => ({ ...prev, status: 'ACTIVE', deal: [] }));
        setToast({ type: 'success', message: 'Thing reactivated.' });
      } else {
        setToast({ type: 'error', message: 'Error reactivating thing.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
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
        setToast({ type: 'success', message: action === 'accept' ? 'Hold confirmed.' : 'Hold cancelled.' });
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
        setToast({ type: 'success', message: 'Question sent.' });
      } else {
        const data = await res.json().catch(() => ({}));
        setToast({ type: 'error', message: data.detail || 'Error sending question.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
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
        setToast({ type: 'success', message: 'Answer sent.' });
      } else {
        const data = await res.json().catch(() => ({}));
        setToast({ type: 'error', message: data.detail || 'Error sending answer.' });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
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
        setToast({ type: 'error', message: `Error ${action === 'hide' ? 'hiding' : 'showing'} the question.` });
      }
    } catch {
      setToast({ type: 'error', message: 'Connection error.' });
    }
  };

  const tc = JSON.parse(localStorage.getItem('theeemeColors') || '{}');
  const btnStyle = tc.color_01 ? {
    '--background-color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
    '--color': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
    '--border-color': `var(--color-${tc.color_01})`,
  } : undefined;
  const btnSecondaryStyle = tc.color_01 ? {
    '--border-color': `var(--color-${tc.color_01})`,
    '--color': `var(--color-${tc.color_01})`,
    '--background-color-hover': `var(--color-${tc.color_01})`,
    '--color-hover': tc.color_05 ? `var(--color-${tc.color_05})` : 'var(--color-white)',
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
        <div className="form-hero-content" style={tc.color_04 ? { '--hero-text-color': `var(--color-${tc.color_04})` } : undefined}>
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
        <img
          src={thing.thumbnail_url || placeholderS}
          srcSet={!thing.thumbnail_url ? `${placeholderS} 1x, ${placeholderM} 2x, ${placeholderL} 3x` : undefined}
          alt={thing.headline}
          className="detail-image"
        />

        <ThingTags thing={thing} isOwner={isOwner} showType={false} />

        <p className="thing-card-meta">
          {new Date(thing.created).toLocaleDateString('en-GB')}
          {thing.owner_name && ` — ${thing.owner_name}`}
        </p>

        <h1 className="page-title">{thing.headline}</h1>

        {thing.description && <p>{thing.description}</p>}

        <div className="thing-card-info">
          <div className="thing-card-info-row">
            <IconTicket size="m" aria-hidden="true" />
            <span className="thing-card-info-label">Type.</span>
            <span>{TYPE_LABELS[thing.type] || thing.type}</span>
          </div>
          {thing.fee && (
            <div className="thing-card-info-row">
              <IconEuroSign size="m" aria-hidden="true" />
              <span className="thing-card-info-label">Price.</span>
              <span>{thing.fee} €</span>
            </div>
          )}
          {thing.availability && (
            <div className="thing-card-info-row">
              <IconCalendar size="m" aria-hidden="true" />
              <span className="thing-card-info-label">Availability.</span>
              <span>{AVAILABILITY_LABELS[thing.availability] || thing.availability}</span>
            </div>
          )}
          {thing.location && (
            <div className="thing-card-info-row">
              <IconLocation size="m" aria-hidden="true" />
              <span className="thing-card-info-label">Location.</span>
              <span>{thing.location}</span>
            </div>
          )}
          {thing.condition && (
            <div className="thing-card-info-row">
              <IconShield size="m" aria-hidden="true" />
              <span className="thing-card-info-label">Condition.</span>
              <span>{CONDITION_LABELS[thing.condition] || thing.condition}</span>
            </div>
          )}
        </div>

        {thing.pictures_urls && thing.pictures_urls.length > 0 && (
          <div>
            <h2>Photos</h2>
            <div className="gallery-row">
              {thing.pictures_urls.map((url, i) => (
                <img
                  key={i}
                  src={url}
                  alt={`${thing.headline} photo ${i + 1}`}
                  className="gallery-image"
                />
              ))}
            </div>
          </div>
        )}

        {/* Owner bookings list */}
        {isOwner && bookings.length > 0 && (() => {
          const pendingCount = bookings.filter((b) => b.status === 'PENDING').length;
          return (
            <ul className="thing-card-bookings">
              {bookings.map((b) => {
                const isActive = b.code === activePendingCode;
                const showStar = isActive && pendingCount > 1;
                return (
                  <li key={b.code} style={{ fontWeight: isActive ? 'bold' : 'normal' }}>
                    {b.requester_name && <>{b.requester_name}. </>}
                    {b.created && <>{new Date(b.created).toLocaleDateString('en-GB', { day: 'numeric', month: 'short' })}. </>}
                    {b.start_date && b.end_date && <>{b.start_date} – {b.end_date}</>}
                    {b.delivery_date && <>{b.delivery_date}, qty {b.quantity}</>}
                    {' '}
                    <span style={{ color: b.status === 'ACCEPTED' ? 'var(--color-success)' : 'var(--color-alert-dark)' }}>
                      ({b.status === 'ACCEPTED' ? 'Confirmed' : 'Pending'}){showStar ? ' *' : ''}
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
                  Confirm hold
                </Button>
                <Button fullWidth variant="secondary" disabled={bookingAction} onClick={() => handleBookingAction('reject')} style={btnSecondaryStyle}>
                  Cancel hold
                </Button>
              </>
            )}
            <Link to={editPath} style={{ display: 'contents' }}>
              {needsPage && activePendingCode ? (
                <Button fullWidth variant="secondary" style={btnSecondaryStyle}>Edit</Button>
              ) : (
                <Button fullWidth style={btnStyle}>Edit</Button>
              )}
            </Link>
            {!hasPendingBookings && (
              <Button fullWidth variant="secondary" style={btnSecondaryStyle} onClick={handleHide}>Hide</Button>
            )}
          </div>
        )}

        {isOwner && thing.status === 'TAKEN' && (
          <div className="button-col">
            <Button fullWidth disabled={bookingAction} onClick={() => handleBookingAction('accept')} style={btnStyle}>
              Confirm hold
            </Button>
            <Button fullWidth variant="secondary" disabled={bookingAction} onClick={() => handleBookingAction('reject')} style={btnSecondaryStyle}>
              Cancel hold
            </Button>
            <Link to={editPath} style={{ display: 'contents' }}>
              <Button fullWidth variant="secondary" style={btnSecondaryStyle}>Edit</Button>
            </Link>
          </div>
        )}

        {isOwner && thing.status === 'INACTIVE' && (
          <div className="button-row">
            <Button style={{ ...btnStyle, width: '100%' }} onClick={handleActivate}>
              Reactivate
            </Button>
            <Link to={editPath} style={{ display: 'contents' }}>
              <Button variant="secondary" style={{ ...btnSecondaryStyle, width: '100%' }}>Edit</Button>
            </Link>
            <Button
              variant="secondary"
              style={{ '--border-color': 'var(--color-error)', '--color': 'var(--color-error)', width: '100%' }}
              onClick={() => navigate(deletePath, { state: { backPath, backLabel } })}
            >
              Delete
            </Button>
          </div>
        )}

        {/* Reservation button for invited users */}
        {showButton && (
          <Button
            fullWidth
            disabled={buttonDisabled}
            style={btnStyle}
            onClick={needsPage ? () => navigate(requestPath, { state: { backPath: code ? `/collections/${code}/things/${thing.code}` : `/things/${thing.code}`, backLabel: thing.headline } }) : handleRequest}
          >
            {submitting ? 'Sending...' : buttonDisabled ? 'Waiting for confirmation' : 'Hold'}
          </Button>
        )}

        {/* FAQs Section */}
        <div className="spacer-m" />
        <hr />
        <div className="spacer-m" />
        <h2>Questions or comments?</h2>

        {faqs.length === 0 ? (
          <p>No questions yet.</p>
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
                      label="Reply"
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
                        {answerSubmitting[faq.code] ? 'Sending...' : 'Reply'}
                      </Button>
                      <Button
                        variant="secondary"
                        fullWidth
                        onClick={() => handleToggleVisibility(faq)}
                        style={btnSecondaryStyle}
                      >
                        {faq.is_visible === false ? 'Show' : 'Hide'}
                      </Button>
                      {faq.is_visible === false && (
                        <span className="faq-meta">
                          (Hidden)
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
                      {faq.is_visible === false ? 'Show' : 'Hide'}
                    </Button>
                    {faq.is_visible === false && (
                      <span className="faq-meta">
                        (Hidden)
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
              label="Question"
              value={faqQuestion}
              onChange={(e) => setFaqQuestion(e.target.value)}
              placeholder="Write your question here..."
            />
            <Button
              disabled={faqSubmitting || !faqQuestion.trim()}
              onClick={handleAskQuestion}
              style={{ ...btnStyle, width: '100%' }}
            >
              {faqSubmitting ? 'Sending...' : 'Send question'}
            </Button>
          </div>
        )}
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
      </div>
    </div>
  );
}
