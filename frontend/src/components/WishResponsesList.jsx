import { useEffect, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { Link } from 'react-router-dom';
import { Button } from 'hds-react';
import { WISH_KIND_I18N } from '../constants/things';
import { apiFetch } from '../services/api';
import InlineConfirm from './InlineConfirm';
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
                <InlineConfirm
                  open={confirmAcceptCode === r.code}
                  onTriggerClick={() => setConfirmAcceptCode((c) => (c === r.code ? null : r.code))}
                  onClose={() => setConfirmAcceptCode(null)}
                  triggerLabel={t('wishes.accept')}
                  triggerProps={{ disabled: actioning, style: { ...btnStyle, width: '100%' } }}
                  title={t('wishes.acceptConfirmTitle')}
                  body={t('wishes.acceptConfirmBody')}
                  confirmLabel={t('wishes.acceptConfirm')}
                  onConfirm={() => handleAcceptResponse(r.code)}
                  confirming={actioning}
                  confirmProps={{ size: 'small', loadingText: t('common.saving'), style: btnStyle }}
                />
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
          <InlineConfirm
            open={resolveOpen}
            onTriggerClick={() => setResolveOpen((o) => !o)}
            onClose={() => setResolveOpen(false)}
            triggerLabel={t('wishes.resolve')}
            triggerProps={{ variant: 'secondary', disabled: actioning, style: { ...btnSecondaryStyle, width: '100%' } }}
            title={t('wishes.resolveConfirmTitle')}
            body={t('wishes.resolveConfirmBody')}
            confirmLabel={t('wishes.resolveConfirm')}
            onConfirm={handleResolve}
            confirming={actioning}
            confirmProps={{ size: 'small', loadingText: t('common.saving'), style: btnStyle }}
          />
        </>
      )}
    </>
  );
}
