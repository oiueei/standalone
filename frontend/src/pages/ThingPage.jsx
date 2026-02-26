import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import {
  Button,
  Fieldset,
  Highlight,
  Notification,
  TextArea,
} from 'hds-react';
import { DATE_TYPES, ORDER_TYPE } from '../constants/things';
import { apiFetch } from '../services/api';
import BackLink from '../components/BackLink';
import LoadingSpinner from '../components/LoadingSpinner';
import ThingTags from '../components/ThingTags';
import Toast from '../components/Toast';
import placeholderImg from '../assets/image-s.png';

export default function ThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const token = localStorage.getItem('token');
  const userCode = localStorage.getItem('userCode');

  const [thing, setThing] = useState(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);

  // Reservation state
  const [submitting, setSubmitting] = useState(false);
  const [requested, setRequested] = useState(false);
  const [bookingAction, setBookingAction] = useState(false);

  // FAQ state
  const [faqs, setFaqs] = useState([]);
  const [faqQuestion, setFaqQuestion] = useState('');
  const [faqSubmitting, setFaqSubmitting] = useState(false);
  const [answerTexts, setAnswerTexts] = useState({});
  const [answerSubmitting, setAnswerSubmitting] = useState({});

  useEffect(() => {
    if (!token) {
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
  }, [token, thingCode, navigate]);

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
  const needsPage = DATE_TYPES.includes(thing.type) || thing.type === ORDER_TYPE;
  const showButton = !isOwner && thing.status !== 'INACTIVE';
  const buttonDisabled = thing.status === 'TAKEN' || submitting || requested;

  const editPath = code
    ? `/collections/${code}/edit-thing/${thing.code}`
    : `/things/${thing.code}/edit`;

  const collectionCode = code || thing.collection_code;
  const backPath = collectionCode ? `/collections/${collectionCode}` : '/';
  const backLabel = thing.collection_headline || (collectionCode ? 'Collection' : 'Home');

  const requestPath = code
    ? `/collections/${code}/things/${thing.code}/request`
    : `/things/${thing.code}/request`;

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
          setThing((prev) => ({ ...prev, status: 'INACTIVE', pending_booking: null }));
          setToast({ type: 'success', message: 'Hold confirmed.' });
        } else {
          setThing((prev) => ({ ...prev, status: 'ACTIVE', pending_booking: null }));
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

  return (
    <div className="page-container">
      <BackLink to={backPath} label={backLabel} />

      <div style={{ display: 'grid', gap: '1rem' }}>
        <img
          src={thing.thumbnail_url || placeholderImg}
          alt={thing.headline}
          style={{ maxWidth: '400px', width: '100%', borderRadius: '4px' }}
        />

        <ThingTags thing={thing} isOwner={isOwner} />

        <h1 className="page-title">{thing.headline}</h1>

        {thing.description && <p>{thing.description}</p>}

        <dl style={{ display: 'grid', gap: '0.5rem' }}>
          <dt><strong>Created</strong></dt>
          <dd>{new Date(thing.created).toLocaleDateString('en-GB')}</dd>
          {thing.fee && (
            <>
              <dt><strong>Price</strong></dt>
              <dd>{thing.fee} EUR</dd>
            </>
          )}
        </dl>

        {thing.pictures_urls && thing.pictures_urls.length > 0 && (
          <div>
            <h2>Photos</h2>
            <div style={{ display: 'flex', gap: '0.5rem', flexWrap: 'wrap' }}>
              {thing.pictures_urls.map((url, i) => (
                <img
                  key={i}
                  src={url}
                  alt={`${thing.headline} photo ${i + 1}`}
                  style={{ maxWidth: '200px', borderRadius: '4px' }}
                />
              ))}
            </div>
          </div>
        )}

        {/* Owner actions */}
        {isOwner && (
          <div style={{ display: 'flex', gap: '0.5rem' }}>
            <Link to={editPath}>
              <Button>Edit</Button>
            </Link>
          </div>
        )}

        {isOwner && thing.pending_booking && (
          <div style={{ display: 'flex', gap: '0.5rem' }}>
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

        {/* Reservation button for invited users */}
        {showButton && (
          <Button
            style={{ width: 'fit-content' }}
            disabled={buttonDisabled}
            onClick={needsPage ? () => navigate(requestPath, { state: { backPath: code ? `/collections/${code}/things/${thing.code}` : `/things/${thing.code}`, backLabel: thing.headline } }) : handleRequest}
          >
            {submitting ? 'Sending...' : requested ? 'Requested' : 'Hold'}
          </Button>
        )}

        {/* FAQs Section */}
        <hr />
        <h2>Questions or comments?</h2>

        {faqs.length === 0 ? (
          <p>No questions yet.</p>
        ) : (
          <div style={{ display: 'grid', gap: '0.25rem' }}>
            {faqs.map((faq) => (
              <div
                key={faq.code}
                style={{ opacity: faq.is_visible === false ? 0.6 : 1 }}
              >
                <Highlight
                  text={faq.question}
                  reference={faq.answer || undefined}
                />
                <div style={{ padding: '0 1rem 1rem' }}>
                  {!faq.answer && (
                    isOwner && (
                      <div style={{ display: 'grid', gap: '0.5rem' }}>
                        <TextArea
                          label="Reply"
                          value={answerTexts[faq.code] || ''}
                          onChange={(e) =>
                            setAnswerTexts((prev) => ({ ...prev, [faq.code]: e.target.value }))
                          }
                        />
                        <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                          <Button
                            style={{ width: 'fit-content' }}
                            disabled={answerSubmitting[faq.code] || !(answerTexts[faq.code] || '').trim()}
                            onClick={() => handleAnswer(faq.code)}
                          >
                            {answerSubmitting[faq.code] ? 'Sending...' : 'Reply'}
                          </Button>
                          <Button
                            variant="secondary"
                            onClick={() => handleToggleVisibility(faq)}
                          >
                            {faq.is_visible === false ? 'Show' : 'Hide'}
                          </Button>
                          {faq.is_visible === false && (
                            <span style={{ fontSize: '0.8rem', color: '#999' }}>
                              (Hidden)
                            </span>
                          )}
                        </div>
                      </div>
                    )
                  )}
                  {faq.answer && isOwner && (
                    <div style={{ display: 'flex', gap: '0.5rem', alignItems: 'center' }}>
                      <Button
                        variant="secondary"
                        onClick={() => handleToggleVisibility(faq)}
                      >
                        {faq.is_visible === false ? 'Show' : 'Hide'}
                      </Button>
                      {faq.is_visible === false && (
                        <span style={{ fontSize: '0.8rem', color: '#999' }}>
                          (Hidden)
                        </span>
                      )}
                    </div>
                  )}
                </div>
              </div>
            ))}
          </div>
        )}


        {!isOwner && (
          <div style={{ display: 'grid', gap: '0.5rem', marginTop: '1rem' }}>
            <TextArea
              label="Question"
              value={faqQuestion}
              onChange={(e) => setFaqQuestion(e.target.value)}
              placeholder="Write your question here..."
            />
            <Button
              style={{ width: 'fit-content' }}
              disabled={faqSubmitting || !faqQuestion.trim()}
              onClick={handleAskQuestion}
            >
              {faqSubmitting ? 'Sending...' : 'Send question'}
            </Button>
          </div>
        )}
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}
