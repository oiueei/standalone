import { useCallback, useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { apiFetch, extractApiError } from '../services/api';
import { canEditCollection } from '../utils/canEditCollection';
import useCollectionTheeeme from './useCollectionTheeeme';
import useCollectionLanguage from './useCollectionLanguage';
import { useCollectionBase } from './useCollectionBase';

/**
 * What the four collection forms (edit, appearance, notifications, availability)
 * share: reading `GET /collections/{code}/`, wearing the palette and the language the
 * collection has **saved** (never the draft being typed), and the partial `PATCH`
 * with its refusals.
 *
 * `onLoad(data)` is called once with the answer, for the page to fill its fields; the
 * latest one is used, so the page need not memoise it. The load effect depends on the
 * code alone — never on `t` — because `useCollectionLanguage` changes the language as
 * this very answer lands, and a second load would overwrite what was typed meanwhile.
 *
 * Returns `{ loading, loaded, collection, refusal, base, save, submitting, toast,
 * setToast }`. `refusal` is why there is no form to show, and a page renders
 * `CollectionFormRefusal` for it instead of an empty one:
 * - `{ type: 'redirect' }` — the account cannot edit this collection (a member, a
 *   co-curator of a network, a refused read): the page sends them to the collection;
 * - `{ type: 'notFound' }` — there is no such collection;
 * - `{ type: 'error', key }` — any other failure, `key` being the message to paint.
 *
 * `save(body)` sends the `PATCH` and goes to the collection when it succeeds; each
 * failure becomes `toast` (429, the server's own 400 message, anything else, no
 * connection).
 */
export default function useCollectionForm(code, { onLoad } = {}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const base = useCollectionBase(code);
  const [loading, setLoading] = useState(true);
  const [loaded, setLoaded] = useState(false);
  const [collection, setCollection] = useState(null);
  const [refusal, setRefusal] = useState(null);
  const [savedPalette, setSavedPalette] = useState(null);
  const [savedLanguage, setSavedLanguage] = useState('');
  const [savedTexts, setSavedTexts] = useState([]);
  const [submitting, setSubmitting] = useState(false);
  const [toast, setToast] = useState(null);
  useCollectionTheeeme(savedPalette?.colors, savedPalette?.koro);
  useCollectionLanguage(savedLanguage, savedTexts);

  const onLoadRef = useRef(onLoad);
  useEffect(() => {
    onLoadRef.current = onLoad;
  });

  useEffect(() => {
    let alive = true;
    (async () => {
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`);
        if (!alive) return;
        if (res.ok) {
          const data = await res.json();
          if (!alive) return;
          if (!canEditCollection(data, localStorage.getItem('userCode'))) {
            setRefusal({ type: 'redirect' });
            return;
          }
          onLoadRef.current?.(data);
          setCollection(data);
          setSavedPalette({ colors: data.theeeme_colors, koro: data.koro });
          setSavedLanguage(data.language || '');
          setSavedTexts([data.headline, data.description]);
          setLoaded(true);
        } else if (res.status === 403) {
          setRefusal({ type: 'redirect' });
        } else if (res.status === 404) {
          setRefusal({ type: 'notFound' });
        } else {
          setRefusal({ type: 'error', key: 'editCollection.errorLoading' });
        }
      } catch {
        if (alive) setRefusal({ type: 'error', key: 'common.connectionError' });
      } finally {
        if (alive) setLoading(false);
      }
    })();
    return () => {
      alive = false;
    };
  }, [code]);

  const save = useCallback(
    async (body) => {
      setSubmitting(true);
      setToast(null);
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`, {
          method: 'PATCH',
          body: JSON.stringify(body),
        });
        if (res.ok) {
          navigate(base);
        } else if (res.status === 429) {
          setToast({ type: 'error', message: t('common.tooManyAttempts') });
        } else if (res.status === 400) {
          // The server's own message names what it refused (the verbs that would
          // orphan things, a field out of range), so the owner can act on it.
          const message = await extractApiError(res);
          setToast({ type: 'error', message: message || t('editCollection.errorSaving') });
        } else {
          setToast({ type: 'error', message: t('editCollection.errorSaving') });
        }
      } catch {
        setToast({ type: 'error', message: t('common.connectionError') });
      } finally {
        setSubmitting(false);
      }
    },
    [code, base, navigate, t]
  );

  return { loading, loaded, collection, refusal, base, save, submitting, toast, setToast };
}
