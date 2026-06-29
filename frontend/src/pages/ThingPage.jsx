import { useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import {
  Button,
  Fieldset,
  Highlight,
  Notification,
  TextArea,
} from 'hds-react';
import { DATE_TYPES, WISH_TYPE, SHARE_TYPE, SWAP_TYPE, WISH_KIND_I18N } from '../constants/things';
import { apiFetch, extractApiError } from '../services/api';

const isDateType = (type) => DATE_TYPES.includes(type);
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import RespondMenu from '../components/RespondMenu';
import ThingTags from '../components/ThingTags';
import ThingInfoRows from '../components/ThingInfoRows';
import OwnerBookingsList from '../components/OwnerBookingsList';
import Toast from '../components/Toast';
import MarkdownText, { sanitizeUrl } from '../components/MarkdownText';
import ImageCarousel from '../components/ImageCarousel';
import { onImageError } from '../utils/imageFallback';
import JoinToAct from '../components/JoinToAct';
import useTheeeme from '../hooks/useTheeeme';
import useThingBooking from '../hooks/useThingBooking';

export default function ThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const { t, i18n } = useTranslation();
  const userCode = localStorage.getItem('userCode');
  const isAuthenticated = !!userCode;
  const { tc, btnStyle, btnSecondaryStyle } = useTheeeme();

  const [thing, setThing] = useState(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  useEffect(() => { document.title = thing ? t('titles.thing', { headline: thing.headline }) : t('titles.thingDefault'); }, [thing, t]);

  // Document links point at the auth-gated download endpoint (which 302-redirects
  // to a short-lived signed Cloudinary URL). A plain anchor can't refresh an
  // expired access token, so warm it via apiFetch first, then navigate.
  const handleDownloadDocument = async (e, url) => {
    e.preventDefault();
    try {
      const res = await apiFetch('/api/v1/auth/me/');
      if (!res.ok) throw new Error('refresh_failed');
      window.location.href = url;
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    }
  };

  // Reservation engine (shared with ThingLinkbox)
  const {
    submitting,
    requested,
    bookingAction,
    bookingActionVerb,
    activating,
    bookings,
    activePendingCode,
    handleRequest,
    handleActivate,
    handleBookingAction,
  } = useThingBooking(thing, {
    isOwner: thing?.owner === userCode,
    onThingChange: (patch) => setThing((prev) => ({ ...prev, ...patch })),
    setToast,
    // Keep the thing circulating on accept/reject for date-based, swap, and
    // endless flows — must match ThingLinkbox's `bookingKeepsStatus`.
    bookingKeepsStatus: isDateType(thing?.type) || thing?.type === SWAP_TYPE || !!thing?.is_endless,
    activateSuccessMessage: t('thingPage.thingReactivated'),
  });

  // FAQ state
  const [faqs, setFaqs] = useState([]);
  const [faqsNext, setFaqsNext] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [faqQuestion, setFaqQuestion] = useState('');
  const [faqSubmitting, setFaqSubmitting] = useState(false);
  const [answerTexts, setAnswerTexts] = useState({});
  const [answerSubmitting, setAnswerSubmitting] = useState({});

  // Transfer state
  const [transfers, setTransfers] = useState(null);

  // Wish state
  const [responses, setResponses] = useState([]);
  const [responsesNext, setResponsesNext] = useState(null);
  const [actioning, setActioning] = useState(false);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchThing = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/`, { signal });
        if (res.ok) {
          const data = await res.json();
          if (signal.aborted) return;
          setThing(data);
        } else if (res.status === 403) {
          setError(t('thingPage.noPermission'));
        } else if (res.status === 404) {
          setError(t('thingPage.notFound'));
        } else {
          setError(t('thingPage.errorLoading'));
        }
      } catch {
        if (!signal.aborted) setError(t('common.connectionError'));
      }
    };

    const fetchFaqs = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/faq/`, { signal });
        if (res.ok) {
          const data = await res.json();
          if (signal.aborted) return;
          setFaqs(data.results || data);
          setFaqsNext(data.next || null);
        }
      } catch { /* silently fail */ }
    };

    const fetchTransfers = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/transfers/`, { signal });
        if (res.ok) {
          const data = await res.json();
          if (signal.aborted) return;
          setTransfers(data);
        }
      } catch { /* silently fail */ }
    };

    fetchThing();
    fetchFaqs();
    fetchTransfers();
    return () => controller.abort();
  }, [userCode, thingCode, navigate, t]);

  useEffect(() => {
    // Wish responses are member-only (creator-all / responder-own), so skip the
    // fetch entirely for an anonymous visitor — it would 401 and bounce them to login.
    // Key on code/type (not the whole `thing`) so a booking accept/reject/resolve
    // patch doesn't refire it, and abort in flight to avoid a post-unmount set.
    if (!thing?.code || thing.type !== WISH_TYPE || !userCode) return undefined;
    const controller = new AbortController();
    apiFetch(`/api/v1/things/${thing.code}/responses/`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (controller.signal.aborted || !data) return;
        setResponses(data.results || data);
        setResponsesNext(data.next || null);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [thing?.code, thing?.type, userCode]);

  const loadMoreFaqs = async () => {
    if (!faqsNext || loadingMore) return;
    setLoadingMore(true);
    try {
      const res = await apiFetch(faqsNext.replace(/^https?:\/\/[^/]+/, ''));
      if (res.ok) {
        const data = await res.json();
        setFaqs((prev) => [...prev, ...(data.results || [])]);
        setFaqsNext(data.next || null);
      }
    } finally {
      setLoadingMore(false);
    }
  };

  const loadMoreResponses = async () => {
    if (!responsesNext || loadingMore) return;
    setLoadingMore(true);
    try {
      const res = await apiFetch(responsesNext.replace(/^https?:\/\/[^/]+/, ''));
      if (res.ok) {
        const data = await res.json();
        setResponses((prev) => [...prev, ...(data.results || [])]);
        setResponsesNext(data.next || null);
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

  if (!thing) {
    return <LoadingSpinner />;
  }

  const isOwner = thing.owner === userCode;
  const isCollectionOwner = thing.collection_owner === userCode;
  const isWish = thing.type === WISH_TYPE;
  const isShare = thing.type === SHARE_TYPE;
  const isSwap = thing.type === SWAP_TYPE;
  const isDateBased = isDateType(thing.type);
  const needsPage = isDateBased || isSwap;
  const hasPendingBookings = bookings.some((b) => b.status === 'PENDING');
  const canDelete = isCollectionOwner || (isOwner && (!isShare || thing.transfer_count === 0));
  // Anonymous visitors get a read-only page plus the JoinToAct prompt; only
  // authenticated members see the reserve / respond / ask controls.
  const showButton = isAuthenticated && !isOwner && thing.status !== 'INACTIVE';
  const swapMinimum = thing.collection_swap_minimum_items || 0;
  const swapOwnCount = thing.my_swap_count_in_collection || 0;
  const swapMinimumNotMet = isSwap && swapMinimum > 0 && swapOwnCount < swapMinimum;
  const swapItemsMissing = swapMinimumNotMet ? swapMinimum - swapOwnCount : 0;
  const buttonDisabled = thing.status === 'TAKEN' || submitting || requested || (isShare && !!thing.my_pending_booking) || swapMinimumNotMet;
  // Only the viewer who holds the pending booking sees "waiting"; everyone else
  // sees why the disabled button can't be used, so the cause travels with it.
  const isMine = requested || !!thing.my_pending_booking;
  const buttonLabel = submitting
    ? t('common.sending')
    : isMine
      ? t('thingCard.waitingForConfirmation')
      : thing.status === 'TAKEN'
        ? t('thingCard.notAvailable')
        : swapMinimumNotMet
          ? t('thingCard.needMoreItems', { count: swapItemsMissing })
          : t(`thingCard.action.${thing?.type}`, { defaultValue: t('thingCard.hold') });

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

  const handleAcceptResponse = async (responseCode) => {
    setActioning(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/wish-responses/${responseCode}/accept/`, { method: 'POST' });
      if (res.ok) {
        const updated = await res.json();
        setResponses((prev) => prev.map((r) => (r.code === responseCode ? { ...r, status: updated.status } : r)));
        setToast({ type: 'success', message: t('wishes.acceptedToast') });
      } else {
        setToast({ type: 'error', message: t('wishes.errorAccepting') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setActioning(false);
    }
  };

  const handleResolve = async () => {
    setActioning(true);
    setToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/resolve/`, { method: 'POST' });
      if (res.ok) {
        setThing((prev) => ({ ...prev, status: 'INACTIVE' }));
        setToast({ type: 'success', message: t('wishes.resolvedToast') });
      } else {
        setToast({ type: 'error', message: t('wishes.errorResolving') });
      }
    } catch {
      setToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setActioning(false);
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
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('thingPage.errorSendingQuestion') });
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
      } else if (res.status === 429) {
        setToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        const detail = await extractApiError(res);
        setToast({ type: 'error', message: detail || t('thingPage.errorSendingAnswer') });
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

  return (
    <PageLayout backTo={backPath} backLabel={backLabel}>

      <div className="form-grid">
        {(() => {
          const images = [thing.thumbnail_url, ...(thing.gallery_urls || [])].filter(Boolean);
          if (images.length === 0) return null;
          if (images.length === 1) {
            return <img src={images[0]} alt={thing.headline} className="detail-image" loading="lazy" onError={onImageError} />;
          }
          return <ImageCarousel images={images} alt={thing.headline} />;
        })()}

        <p className="thing-card-meta">
          {new Date(thing.created).toLocaleDateString(i18n.language)}
          {thing.owner_name && ` — ${thing.owner_name}`}
        </p>

        <h1 className="page-title">{thing.headline}</h1>

        {thing.description && <MarkdownText text={thing.description} />}

        {thing.document_urls && thing.document_urls.length > 0 && (
          <div className="document-downloads">
            <h2>{t('documents.heading')}</h2>
            <ul className="document-list">
              {thing.document_urls.map((doc, i) => (
                <li key={i} className="document-list-item">
                  <a
                    href={doc.url}
                    rel="noopener noreferrer"
                    onClick={(e) => handleDownloadDocument(e, doc.url)}
                  >
                    {doc.filename}
                  </a>
                </li>
              ))}
            </ul>
          </div>
        )}

        <ThingTags thing={thing} isOwner={isOwner} showType={false} />

        <ThingInfoRows thing={thing} isDateBased={isDateBased} />

        {/* Owner bookings list */}
        <OwnerBookingsList bookings={bookings} activePendingCode={activePendingCode} isOwner={isOwner} />

        {/* Owner actions */}
        {isOwner && thing.status === 'ACTIVE' && (
          <div className="button-col">
            {needsPage && activePendingCode && (
              <>
                <Button fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('accept')} style={btnStyle}>
                  {bookingActionVerb === 'accept' ? t('thingCard.confirming') : t('thingCard.confirmHold')}
                </Button>
                <Button fullWidth variant="secondary" disabled={!!bookingAction} onClick={() => handleBookingAction('reject')} style={btnSecondaryStyle}>
                  {bookingActionVerb === 'reject' ? t('thingCard.cancelling') : t('thingCard.cancelHold')}
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
            {!hasPendingBookings && canDelete && (
              <Button fullWidth variant="secondary" style={btnSecondaryStyle} onClick={() => navigate(deletePath, { state: { backPath, backLabel } })}>{t('common.delete')}</Button>
            )}
          </div>
        )}

        {isOwner && thing.status === 'TAKEN' && (
          <div className="button-col">
            <Button fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('accept')} style={btnStyle}>
              {bookingActionVerb === 'accept' ? t('thingCard.confirming') : t('thingCard.confirmHold')}
            </Button>
            <Button fullWidth variant="secondary" disabled={!!bookingAction} onClick={() => handleBookingAction('reject')} style={btnSecondaryStyle}>
              {bookingActionVerb === 'reject' ? t('thingCard.cancelling') : t('thingCard.cancelHold')}
            </Button>
            <Link to={editPath} style={{ display: 'contents' }}>
              <Button fullWidth variant="secondary" style={btnSecondaryStyle}>{t('common.edit')}</Button>
            </Link>
          </div>
        )}

        {isOwner && thing.status === 'INACTIVE' && (
          <div className="button-row">
            <Button style={{ ...btnStyle, width: '100%' }} disabled={activating} onClick={handleActivate}>
              {activating ? t('thingCard.reactivating') : t('thingCard.reactivate')}
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

        {/* Answer ("Contestar") menu for wishes */}
        {showButton && isWish && (
          thing.my_response ? (
            <p className="thing-card-meta">
              {t('wishes.yourAnswer')} · {t('wishes.status.' + thing.my_response.status)}
            </p>
          ) : (
            <RespondMenu
              thingCode={thing.code}
              collectionCode={collectionCode}
              backPath={code ? `/collections/${code}/things/${thing.code}` : `/things/${thing.code}`}
              backLabel={thing.headline}
            />
          )
        )}

        {/* Reservation button for non-wish invited users */}
        {showButton && !isWish && (
          <Button
            fullWidth
            disabled={buttonDisabled}
            style={btnStyle}
            onClick={needsPage ? () => navigate(requestPath, { state: { backPath: code ? `/collections/${code}/things/${thing.code}` : `/things/${thing.code}`, backLabel: thing.headline } }) : handleRequest}
          >
            {buttonLabel}
          </Button>
        )}
        {showButton && swapMinimumNotMet && (
          <Notification
            type="info"
            label={t('swap.minimumNotMetLabel')}
            size="small"
            style={{ marginTop: 'var(--spacing-2-xs)' }}
          >
            {t('swap.minimumNotMetBody', { count: swapItemsMissing })}
          </Notification>
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

        {!isAuthenticated && thing.status !== 'INACTIVE' && collectionCode && (
          <JoinToAct collectionCode={collectionCode} collectionHeadline={thing.collection_headline} />
        )}

        {/* Responses section for wishes (creator sees all; responder sees own) */}
        {isWish && (isOwner || thing.my_response) && (
          <>
            <div className="spacer-m" />
            <hr />
            <div className="spacer-m" />
            <h2>{t('wishes.responsesHeading')}</h2>
            {responses.length === 0 ? (
              <p>{t('wishes.noResponses')}</p>
            ) : (
              <div className="faq-grid">
                {responses.map((r) => (
                  <div key={r.code}>
                    <p className="thing-card-meta">
                      <strong>{r.responder_name}</strong>
                      {' · '}{t('wishes.kind.' + WISH_KIND_I18N[r.kind])}
                      {' · '}
                      <span style={{ color: r.status === 'ACCEPTED' ? 'var(--color-success)' : 'var(--color-alert-dark)' }}>
                        {t('wishes.status.' + r.status)}
                      </span>
                    </p>
                    {r.kind === 'HAVE_THIS' && r.thing && (
                      <p>
                        <Link to={code ? `/collections/${code}/things/${r.thing}` : `/things/${r.thing}`}>
                          {r.thing_headline}
                        </Link>
                        {r.thing_type && <> ({t('types.' + r.thing_type)})</>}
                      </p>
                    )}
                    {r.message && <MarkdownText text={r.message} />}
                    {r.url && (
                      <p><a href={sanitizeUrl(r.url)} target="_blank" rel="noopener noreferrer">{r.url}</a></p>
                    )}
                    {r.fee && <p>{r.fee} €</p>}
                    {isOwner && r.status === 'PENDING' && (
                      <Button
                        disabled={actioning}
                        onClick={() => handleAcceptResponse(r.code)}
                        style={{ ...btnStyle, width: '100%' }}
                      >
                        {t('wishes.accept')}
                      </Button>
                    )}
                  </div>
                ))}
              </div>
            )}
            {responsesNext && (
              <>
                <div className="spacer-s" />
                <Button variant="secondary" onClick={loadMoreResponses} disabled={loadingMore} style={btnSecondaryStyle}>
                  {t('common.loadMore')}
                </Button>
              </>
            )}
            {isOwner && thing.status === 'ACTIVE' && (
              <>
                <div className="spacer-m" />
                <Button
                  variant="secondary"
                  disabled={actioning}
                  onClick={handleResolve}
                  style={{ ...btnSecondaryStyle, width: '100%' }}
                >
                  {t('wishes.resolve')}
                </Button>
              </>
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
                  theme={tc.color_03 ? { '--accent-line-color': `var(--color-${tc.color_03})` } : undefined}
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
        {faqsNext && (
          <>
            <div className="spacer-s" />
            <Button variant="secondary" onClick={loadMoreFaqs} disabled={loadingMore} style={btnSecondaryStyle}>
              {t('common.loadMore')}
            </Button>
          </>
        )}


        <div className="spacer-m" />
        {isAuthenticated && !isOwner && (
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
                      {t(isSwap ? 'transfers.swappedOn' : 'transfers.lentOn', { date: new Date(tr.lent_date).toLocaleDateString(i18n.language) })}
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
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
