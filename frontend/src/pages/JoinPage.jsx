import { useEffect, useState } from 'react';
import { useParams, useLocation, useSearchParams } from 'react-router';
import { useTranslation } from 'react-i18next';
import JoinToAct from '../components/JoinToAct';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import LoadingSpinner from '../components/LoadingSpinner';
import PageLayout from '../components/PageLayout';
import { apiFetch } from '../services/api';
import { useLocalized } from '../utils/localized';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import { useCollectionBase, useCanonicalCollectionPath } from '../hooks/useCollectionBase';
import useDocumentTitle from '../hooks/useDocumentTitle';

/**
 * Login-to-act landing page for a PUBLIC collection. An anonymous visitor who
 * clicks an action button (reserve / order / respond …) on a public collection
 * lands here: they enter their email, the backend emails a magic link, and
 * pressing it joins them to that collection and drops them back on it — now a
 * member who can act. Standard `form-hero` + `Koros` layout, with the
 * collection's image as its logo (an `<img class="hero-logo">` in a
 * `form-hero--collection` hero, as on its own page) when it has one.
 */
export default function JoinPage() {
  const { code } = useParams();
  const location = useLocation();
  const [searchParams] = useSearchParams();
  // The thing the visitor was trying to act on, if they came from a card/detail
  // "Reserve" click. Passed through to `/auth/join/` so the magic link
  // lands them back on it, not the collection index. A `/join` URL opened cold
  // simply has no `?thing=` and behaves as before.
  const thingCode = searchParams.get('thing') || undefined;
  const { t } = useTranslation();
  const L = useLocalized();
  // The name is seeded from the navigation state when there is one — that
  // renders it with no flicker — but it can't be the only source. Only
  // `ThingLinkbox` passes it; a refresh, `ThingPage`'s reserve button and
  // a /join URL somebody shared all arrive with nothing, and the
  // page then asked a stranger to hand over their email to join "Collection".
  // This is the first screen of the viral funnel, so it fetches the collection
  // itself. Public and ACTIVE by definition (login-to-act only exists there), so
  // an anonymous GET resolves; a private or missing one simply 403/404s and we
  // keep the generic copy rather than inventing a name.
  const [collectionLanguage, setCollectionLanguage] = useState('');
  // What a member can do there — the door's first line names exactly that. The
  // API gives both to an anonymous reader of a PUBLIC collection.
  const [mode, setMode] = useState('');
  const [kind, setKind] = useState('');
  const base = useCollectionBase(code, kind);
  useCanonicalCollectionPath(kind);
  const [allowedThingTypes, setAllowedThingTypes] = useState([]);
  // The collection's image, shown as its logo so the door looks like the page it leads to.
  const [thumbnailUrl, setThumbnailUrl] = useState('');
  // The raw headline, per-language map and all: the hook reads it, and it is resolved
  // here, at render, in whatever language the page is in by then. It used to be
  // resolved once, when the response landed, and kept as words — so when
  // `useCollectionLanguage` then switched the page to the group's language, the name
  // stayed in the one before. Until it arrives, the name the card handed over.
  const [ownerHeadline, setOwnerHeadline] = useState('');
  useCollectionLanguage(collectionLanguage, [ownerHeadline]);
  // This is the door of that group, so it wears the group's colours — and does not
  // paint its hero until the collection has answered, or the app's palette would show
  // for an instant first. A collection that cannot be read (private, gone) settles
  // with no palette and the page keeps the app's.
  const [palette, setPalette] = useState(null);
  const [settled, setSettled] = useState(!code);
  useCollectionTheeeme(palette?.colors, palette?.koro);
  const headline = ownerHeadline ? L(ownerHeadline) : location.state?.collectionHeadline || '';

  // "Join {collection}", the words `/share/:token` already says:
  // the page says which group the stranger is about to join, in the title and the
  // tab, once the name is known. Until then — a collection that cannot be read
  // keeps the generic copy rather than an invented name — the title of always.
  const heading = headline ? t('share.pageTitleNamed', { name: headline }) : t('joinToAct.heading');
  useDocumentTitle(
    headline ? t('titles.shareNamed', { name: headline }) : `${t('joinToAct.heading')} — OIUEEI`
  );

  useEffect(() => {
    if (!code) return undefined;
    const controller = new AbortController();
    apiFetch(`/api/v1/collections/${code}/`, { signal: controller.signal })
      .then((res) => (res.ok ? res.json() : Promise.reject()))
      .then((data) => {
        setCollectionLanguage(data?.language || '');
        setMode(data?.mode || '');
        setKind(data?.kind || '');
        setAllowedThingTypes(data?.allowed_thing_types || []);
        setThumbnailUrl(data?.thumbnail_url || '');
        setOwnerHeadline(data?.headline || '');
        setPalette({ colors: data?.theeeme_colors, koro: data?.koro });
      })
      .catch(() => {})
      .finally(() => {
        if (!controller.signal.aborted) setSettled(true);
      });
    return () => controller.abort();
  }, [code]);

  if (!settled) return <LoadingSpinner />;

  return (
    <PageLayout
      title={heading}
      backTo={base}
      backLabel={headline || t('common.collection')}
      logoUrl={thumbnailUrl}
      heroClassName="form-hero--collection"
      // No "Sign in" icon without a session: the email below serves a new address, an
      // account that exists and a member alike, so it is the page's only action. With a
      // session the menu is as ever.
      offerSignIn={false}
    >
      <JoinToAct
        collectionCode={code}
        collectionHeadline={headline}
        thingCode={thingCode}
        mode={mode}
        allowedThingTypes={allowedThingTypes}
      />
    </PageLayout>
  );
}
