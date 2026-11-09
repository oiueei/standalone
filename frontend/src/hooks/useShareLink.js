import { useCallback, useRef, useState } from 'react';
import { useTranslation } from 'react-i18next';
import { apiFetch } from '../services/api';
import { collectionPath } from '../utils/collectionPath';

/**
 * The link a collection is joined by, and copying it: what `ShareCollectionMenu` and
 * the invitations page both need.
 *
 * - **A PUBLIC collection** is shared by its own address, with no token and no request.
 * - **A PRIVATE one** is shared by `/share/{token}`, minted on demand the first time
 *   (`POST share-link/`: a group never shared by link has no token in the database). In
 *   a network any dinamizador may ask for it; only its founder rotates or revokes it.
 *
 * The resolved link is kept for the life of the component, so asking twice is one
 * request. `setUrl` replaces what is kept (`null` forgets it) for the caller that
 * rotates or revokes. `toast` is the outcome of `copy()` in the shape `Toast` takes
 * (`{type, message}`, or `null`); the caller paints it and clears it with `setToast`.
 *
 * `ensureShareUrl` rejects when the request fails; `copy` catches that and says
 * `shareMenu.linkError`, and says `shareMenu.copyError` when the clipboard refuses.
 */
export default function useShareLink({ code, kind, isPublic }) {
  const { t } = useTranslation();
  const urlRef = useRef(null);
  const [toast, setToast] = useState(null);

  const setUrl = useCallback((url) => {
    urlRef.current = url;
  }, []);

  const ensureShareUrl = useCallback(async () => {
    if (urlRef.current) return urlRef.current;
    if (isPublic) {
      urlRef.current = `${window.location.origin}${collectionPath(code, kind)}`;
      return urlRef.current;
    }
    const res = await apiFetch(`/api/v1/collections/${code}/share-link/`, { method: 'POST' });
    if (!res.ok) throw new Error('share-link request failed');
    const data = await res.json();
    urlRef.current = data.share_url;
    return data.share_url;
  }, [code, kind, isPublic]);

  // Copies `url` when the caller already holds it, else the collection's link.
  const copy = useCallback(
    async (url) => {
      let link = url;
      if (!link) {
        try {
          link = await ensureShareUrl();
        } catch {
          setToast({ type: 'error', message: t('shareMenu.linkError') });
          return;
        }
      }
      try {
        await navigator.clipboard.writeText(link);
        setToast({ type: 'success', message: t('shareMenu.copied') });
      } catch {
        setToast({ type: 'error', message: t('shareMenu.copyError') });
      }
    },
    [ensureShareUrl, t]
  );

  return { ensureShareUrl, copy, setUrl, toast, setToast };
}
