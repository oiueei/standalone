import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Button, Highlight, TextArea } from 'hds-react';
import { apiFetch, extractApiError } from '../services/api';

/**
 * The FAQ section of ThingPage: the question list (owner sees hidden ones and
 * gets answer / hide-show controls), a "Load more" pager, and — for a logged-in
 * non-owner — the ask-a-question form. Self-contained: owns its FAQ list, form
 * state and the fetch (on mount, by thingCode), reporting feedback via onToast.
 *
 * Props: `thingCode`, `isOwner`, `isAuthenticated`, `btnStyle`,
 * `btnSecondaryStyle`, `tc` (theeeme colours for the Highlight accent), `onToast`.
 */
export default function ThingFaqSection({
  thingCode,
  isOwner,
  isAuthenticated,
  btnStyle,
  btnSecondaryStyle,
  tc,
  onToast,
}) {
  const { t } = useTranslation();
  const [faqs, setFaqs] = useState([]);
  const [faqsNext, setFaqsNext] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [faqQuestion, setFaqQuestion] = useState('');
  const [faqSubmitting, setFaqSubmitting] = useState(false);
  const [answerTexts, setAnswerTexts] = useState({});
  const [answerSubmitting, setAnswerSubmitting] = useState({});

  useEffect(() => {
    const controller = new AbortController();
    apiFetch(`/api/v1/things/${thingCode}/faq/`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        if (controller.signal.aborted || !data) return;
        setFaqs(data.results || data);
        setFaqsNext(data.next || null);
      })
      .catch(() => {});
    return () => controller.abort();
  }, [thingCode]);

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

  const handleAskQuestion = async () => {
    if (!faqQuestion.trim()) return;
    setFaqSubmitting(true);
    onToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${thingCode}/faq/`, {
        method: 'POST',
        body: JSON.stringify({ question: faqQuestion.trim() }),
      });
      if (res.ok) {
        const newFaq = await res.json();
        setFaqs((prev) => [...prev, newFaq]);
        setFaqQuestion('');
        onToast({ type: 'success', message: t('thingPage.questionSent') });
      } else if (res.status === 429) {
        onToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        const detail = await extractApiError(res);
        onToast({ type: 'error', message: detail || t('thingPage.errorSendingQuestion') });
      }
    } catch {
      onToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setFaqSubmitting(false);
    }
  };

  const handleAnswer = async (faqCode) => {
    const answer = (answerTexts[faqCode] || '').trim();
    if (!answer) return;
    setAnswerSubmitting((prev) => ({ ...prev, [faqCode]: true }));
    onToast(null);
    try {
      const res = await apiFetch(`/api/v1/faq/${faqCode}/answer/`, {
        method: 'POST',
        body: JSON.stringify({ answer }),
      });
      if (res.ok) {
        const updated = await res.json();
        setFaqs((prev) => prev.map((f) => (f.code === faqCode ? { ...f, ...updated } : f)));
        setAnswerTexts((prev) => ({ ...prev, [faqCode]: '' }));
        onToast({ type: 'success', message: t('thingPage.answerSent') });
      } else if (res.status === 429) {
        onToast({ type: 'error', message: t('common.tooManyAttempts') });
      } else {
        const detail = await extractApiError(res);
        onToast({ type: 'error', message: detail || t('thingPage.errorSendingAnswer') });
      }
    } catch {
      onToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setAnswerSubmitting((prev) => ({ ...prev, [faqCode]: false }));
    }
  };

  const handleToggleVisibility = async (faq) => {
    const action = faq.is_visible ? 'hide' : 'show';
    onToast(null);
    try {
      const res = await apiFetch(`/api/v1/faq/${faq.code}/${action}/`, { method: 'POST' });
      if (res.ok) {
        setFaqs((prev) =>
          prev.map((f) => (f.code === faq.code ? { ...f, is_visible: !faq.is_visible } : f))
        );
      } else {
        onToast({
          type: 'error',
          message:
            action === 'hide'
              ? t('thingPage.errorHidingQuestion')
              : t('thingPage.errorShowingQuestion'),
        });
      }
    } catch {
      onToast({ type: 'error', message: t('common.connectionError') });
    }
  };

  return (
    <>
      <div className="spacer-m" />
      <hr />
      <div className="spacer-m" />
      <h2>{t('thingPage.faqHeading')}</h2>

      {faqs.length === 0 ? (
        <p>{t('thingPage.noQuestions')}</p>
      ) : (
        <div className="faq-grid">
          {faqs.map((faq) => (
            <div key={faq.code} style={{ opacity: faq.is_visible === false ? 0.6 : 1 }}>
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
                        <span className="faq-meta">{t('thingPage.hidden')}</span>
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
                    <span className="faq-meta">{t('thingPage.hidden')}</span>
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
    </>
  );
}
