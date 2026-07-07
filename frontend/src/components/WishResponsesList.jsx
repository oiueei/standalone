import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from 'hds-react';
import { WISH_KIND_I18N } from '../constants/things';
import { apiFetch } from '../services/api';
import MarkdownText, { sanitizeUrl } from './MarkdownText';

/**
 * The answers section of a wish (WISH_THING) on ThingPage: the creator sees
 * every answer and can accept one (inline consequence-confirm) or mark the wish
 * resolved (also confirmed); a responder sees only their own. Self-contained:
 * owns the answers list + its fetch (on mount, by thing.code) and the accept /
 * resolve handlers. Only mounted for an authenticated creator/responder, so the
 * fetch never runs for an anonymous visitor.
 *
 * Props: `thing`, `isOwner`, `code` (collection route context for HAVE_THIS
 * listing links), `btnStyle`, `btnSecondaryStyle`, `onToast`, `onResolved`
 * (called after the wish is marked resolved so the parent can flip its status).
 */
export default function WishResponsesList({
  thing,
  isOwner,
  code,
  btnStyle,
  btnSecondaryStyle,
  onToast,
  onResolved,
}) {
  const { t } = useTranslation();
  const [responses, setResponses] = useState([]);
  const [responsesNext, setResponsesNext] = useState(null);
  const [loadingMore, setLoadingMore] = useState(false);
  const [actioning, setActioning] = useState(false);
  const [confirmAcceptCode, setConfirmAcceptCode] = useState(null);
  const [resolveOpen, setResolveOpen] = useState(false);

  useEffect(() => {
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
  }, [thing.code]);

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

  const handleAcceptResponse = async (responseCode) => {
    setActioning(true);
    onToast(null);
    try {
      const res = await apiFetch(`/api/v1/wish-responses/${responseCode}/accept/`, { method: 'POST' });
      if (res.ok) {
        const updated = await res.json();
        setResponses((prev) =>
          prev.map((r) => (r.code === responseCode ? { ...r, status: updated.status } : r))
        );
        onToast({ type: 'success', message: t('wishes.acceptedToast') });
      } else {
        onToast({ type: 'error', message: t('wishes.errorAccepting') });
      }
    } catch {
      onToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setActioning(false);
    }
  };

  const handleResolve = async () => {
    setActioning(true);
    onToast(null);
    try {
      const res = await apiFetch(`/api/v1/things/${thing.code}/resolve/`, { method: 'POST' });
      if (res.ok) {
        onResolved();
        onToast({ type: 'success', message: t('wishes.resolvedToast') });
      } else {
        onToast({ type: 'error', message: t('wishes.errorResolving') });
      }
    } catch {
      onToast({ type: 'error', message: t('common.connectionError') });
    } finally {
      setActioning(false);
    }
  };

  return (
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
                <>
                  <Button
                    disabled={actioning}
                    onClick={() => setConfirmAcceptCode((c) => (c === r.code ? null : r.code))}
                    aria-expanded={confirmAcceptCode === r.code}
                    style={{ ...btnStyle, width: '100%' }}
                  >
                    {t('wishes.accept')}
                  </Button>
                  {confirmAcceptCode === r.code && (
                    <div className="thing-report-confirm">
                      <p><strong>{t('wishes.acceptConfirmTitle')}</strong></p>
                      <p>{t('wishes.acceptConfirmBody')}</p>
                      <div className="button-row">
                        <Button
                          size="small"
                          disabled={actioning}
                          isLoading={actioning}
                          loadingText={t('common.saving')}
                          onClick={() => handleAcceptResponse(r.code)}
                          style={btnStyle}
                        >
                          {t('wishes.acceptConfirm')}
                        </Button>
                        <Button
                          variant="supplementary"
                          size="small"
                          onClick={() => setConfirmAcceptCode(null)}
                        >
                          {t('common.cancel')}
                        </Button>
                      </div>
                    </div>
                  )}
                </>
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
            onClick={() => setResolveOpen((o) => !o)}
            aria-expanded={resolveOpen}
            style={{ ...btnSecondaryStyle, width: '100%' }}
          >
            {t('wishes.resolve')}
          </Button>
          {resolveOpen && (
            <div className="thing-report-confirm">
              <p><strong>{t('wishes.resolveConfirmTitle')}</strong></p>
              <p>{t('wishes.resolveConfirmBody')}</p>
              <div className="button-row">
                <Button
                  size="small"
                  disabled={actioning}
                  isLoading={actioning}
                  loadingText={t('common.saving')}
                  onClick={handleResolve}
                  style={btnStyle}
                >
                  {t('wishes.resolveConfirm')}
                </Button>
                <Button variant="supplementary" size="small" onClick={() => setResolveOpen(false)}>
                  {t('common.cancel')}
                </Button>
              </div>
            </div>
          )}
        </>
      )}
    </>
  );
}
