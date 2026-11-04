import { useEffect, useRef, useState, useCallback } from 'react';
import { useParams, useNavigate, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import LoadingSpinner from '../components/LoadingSpinner';
import InboxNotifications from '../components/InboxNotifications';
import DemoNotice from '../components/DemoNotice';
import ButtonLink from '../components/ButtonLink';
import RefusalWayOut from '../components/RefusalWayOut';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import { useLocalized } from '../utils/localized';
import useCollectionDownloads from '../hooks/useCollectionDownloads';
import useDigestPreference from '../hooks/useDigestPreference';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import useMediaQuery from '../hooks/useMediaQuery';
import Toast from '../components/Toast';
import { useCanonicalCollectionPath } from '../hooks/useCollectionBase';
import useDocumentTitle from '../hooks/useDocumentTitle';
import { collectionPath } from '../utils/collectionPath';
import { hasOpeningHours } from '../utils/rental';
import CollectionHero from '../components/collection/CollectionHero';
import BroadcastBox from '../components/collection/BroadcastBox';
import ThingsSection, { InactiveThings } from '../components/collection/ThingsSection';

// How long the card of a thing just uploaded stays marked.
const JUST_ADDED_MS = 2000;

export default function CollectionPage() {
  const { code } = useParams();
  const navigate = useNavigate();
  const location = useLocation();
  const { t } = useTranslation();
  const { tc, btnStyle } = useTheeeme();
  const [collection, setCollection] = useState(null);
  // The move off a wrong address: a link made before kinds, or at the wrong
  // kind's prefix, is corrected here.
  useCanonicalCollectionPath(collection?.kind);
  const [error, setError] = useState('');
  // The owner may have written the collection's text once per language; every
  // child (cards, share menu, back labels) gets the resolved words from here.
  const L = useLocalized();
  const headline = L(collection?.headline);
  useCollectionLanguage(collection?.language, [collection?.headline, collection?.description]);
  // The group's pages wear the group's colours: the palette its curators chose, which
  // anyone who can read the collection is served.
  useCollectionTheeeme(collection?.theeeme_colors, collection?.koro);
  // Called unconditionally (it is a hook): non-curators simply never see the
  // menu that offers it. One call owns the calendar, stats and JSON
  // downloads, and the page hands it to the menu and to the status zone.
  const downloads = useCollectionDownloads(code);
  // A member's own switch for this group's summary email, in the
  // collection menu. Called unconditionally too; the page learns the answer, so the
  // menu's wording is the server's word.
  const digestPref = useDigestPreference({
    code,
    muted: !!collection?.is_digest_muted,
    onChange: useCallback(
      (muted) => setCollection((prev) => (prev ? { ...prev, is_digest_muted: muted } : prev)),
      []
    ),
  });

  // Arriving from "Add thing" with the new thing's code. On a
  // desktop the new card is the first of the grid and in plain sight; on a phone
  // the hero fills the screen and nothing of the upload shows, which reads as if
  // nothing happened. So, below 768px only: a green notice, the page brought down
  // to the card if it is not already in view, the focus on its link and the card
  // marked for a moment. On a desktop nothing — but the state is cleared either
  // way, so a reload or the back button never repeats it.
  const isPhone = useMediaQuery('(max-width: 767px)');
  const reducedMotion = useMediaQuery('(prefers-reduced-motion: reduce)');
  const addedThing = location.state?.addedThing;
  // The notice is read off the state this page was *opened* with: the effect below
  // clears the state, and a notice that lives on it would go with it.
  const [arrivedWith] = useState(addedThing ?? null);
  const [uploadedClosed, setUploadedClosed] = useState(false);
  // Once per code, whatever re-runs the effect (StrictMode, a language change).
  const handledAddedThing = useRef(null);
  const justAddedTimer = useRef(null);
  useEffect(() => () => clearTimeout(justAddedTimer.current), []);
  useEffect(() => {
    // Wait for the cards: they are painted in the commit that stored the collection.
    if (!addedThing || !collection || handledAddedThing.current === addedThing) return;
    handledAddedThing.current = addedThing;
    navigate(location.pathname, { replace: true, state: null });
    if (!isPhone) return;
    // Not in the list — a tag filter, past the first page — is the notice alone.
    const card = document.querySelector(`[data-thing-code="${CSS.escape(addedThing)}"]`);
    if (!card) return;
    const { top, bottom } = card.getBoundingClientRect();
    if (top < 0 || bottom > window.innerHeight) {
      card.scrollIntoView?.({ block: 'center', behavior: reducedMotion ? 'auto' : 'smooth' });
    }
    // The link, for a keyboard and a screen reader; the scroll above is already
    // asked for, so the focus must not scroll again.
    card.querySelector('a.thing-card-link')?.focus({ preventScroll: true });
    // The mark goes straight on the element, like the scroll and the focus: this
    // effect is already speaking to the DOM, and a card is a memoised component
    // that would re-render for a flag it only needs for two seconds.
    if (tc.color_01) card.style.setProperty('--just-added-color', `var(--color-${tc.color_01})`);
    card.classList.add('thing-card--just-added');
    clearTimeout(justAddedTimer.current);
    justAddedTimer.current = setTimeout(
      () => card.classList.remove('thing-card--just-added'),
      JUST_ADDED_MS
    );
  }, [addedThing, collection, isPhone, reducedMotion, tc.color_01, location.pathname, navigate]);
  useDocumentTitle(
    collection ? t('titles.collection', { headline }) : t('titles.collectionDefault')
  );

  // Stable across renders (functional setState, no deps) so memoised ThingLinkbox
  // cards don't re-render when unrelated page state (broadcast box, tag filter)
  // changes. Shared by the active and inactive thing lists.
  const handleUpdateThing = useCallback((thingCode, updates) => {
    setCollection((prev) => ({
      ...prev,
      things: prev.things.map((thg) => (thg.code === thingCode ? { ...thg, ...updates } : thg)),
    }));
  }, []);

  // The server's copy of the collection, as the reader is now: joined from a
  // card, they are a member and the hero and the menu must say so.
  // Stable for the same reason as `handleUpdateThing`: every active card gets it, and
  // a new function on each render would undo their `memo` — up to 24 cards painted
  // again for each key typed in the broadcast box.
  const reloadCollection = useCallback(async () => {
    try {
      const fresh = await apiFetch(`/api/v1/collections/${code}/`);
      if (fresh.ok) setCollection(await fresh.json());
    } catch {
      // The request itself already went through; the page catches up on reload.
    }
  }, [code]);

  useEffect(() => {
    // Guard against a fast A→B navigation: without aborting, collection A's
    // response can land after B's and render the wrong collection. Aborting on
    // cleanup (code change / unmount) drops the stale fetch. Mirrors ThingPage.
    const controller = new AbortController();
    const { signal } = controller;
    const fetchCollection = async () => {
      try {
        const res = await apiFetch(`/api/v1/collections/${code}/`, { signal });
        if (signal.aborted) return;
        if (res.ok) {
          const data = await res.json();
          if (signal.aborted) return;
          setCollection(data);
        } else if (res.status === 403) {
          setError('collectionPage.noPermission');
        } else if (res.status === 404) {
          setError('collectionPage.notFound');
        } else {
          setError('collectionPage.errorLoading');
        }
      } catch {
        if (!signal.aborted) setError('common.connectionError');
      }
    };
    fetchCollection();
    return () => controller.abort();
    // `error` holds the i18n *key*, translated where it is painted, so this effect
    // never reads `t`: `useCollectionLanguage` changes the language once the first
    // response lands, `t` gets a new identity, and listing it here fetched the
    // whole collection a second time. Nor `navigate`: it is not read here, and its
    // identity changes with every address, so listing it loaded the collection again
    // each time a network's filter moved the address.
  }, [code]);

  if (error) {
    // Not being allowed in is a fact about the reader's access, not a fault: it
    // says so in the title and is announced as a notice rather than as an error.
    const noAccess = error === 'collectionPage.noPermission';
    return (
      <PageLayout
        title={noAccess ? t('collectionPage.noAccessTitle') : t('common.error')}
        backTo="/"
        backLabel={t('common.home')}
      >
        <Notification
          label={noAccess ? t('common.notice') : t('common.error')}
          type={noAccess ? 'info' : 'error'}
        >
          {t(error)}
        </Notification>
        {noAccess && <RefusalWayOut />}
      </PageLayout>
    );
  }

  if (!collection) {
    return <LoadingSpinner />;
  }

  const isCurator = !!collection.is_curator;
  // Who may put a thing here: a curator, or a member of a COMMUNITY group —
  // the same rule `Collection.can_add_thing` enforces. Mode alone is not enough:
  // a reader who is not a member (signed in or not) would be sent through the
  // whole form, photos uploaded and all, to collect a 403 at the end.
  const canAddThing = isCurator || (collection.mode === 'COMMUNITY' && !!collection.is_member);

  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <CollectionHero
        collection={collection}
        setCollection={setCollection}
        code={code}
        headline={headline}
        downloads={downloads}
        digestPref={digestPref}
      />
      <div className="page-container">
        {collection.is_onboarding && <DemoNotice />}
        {/* Each viewer's own notifications for this collection — a hold request or a
          FAQ question is answered on the thing, so it should reach whoever owns
          that thing where it actually lives, not only on Home. The endpoint always
          scopes to `request.user`, so a member sees only their own (e.g. a
          COMMUNITY contribution's own booking requests) — never a co-member's or
          the owner's. Gated on membership rather than `isOwner` alone: in
          PROPRIETARY mode that was the same person, but a COMMUNITY member who
          owns a thing here is not the collection owner and was missing this
          entirely, stranded on Home. A co-owner needs it too — `isCurator`
          covers them alongside `is_member`. */}
        {(isCurator || collection.is_member) && <InboxNotifications collection={code} />}
        {isCurator && collection.status === 'INACTIVE' && (
          <Notification
            label={t('common.notice')}
            type="info"
            style={{ marginBottom: 'var(--spacing-m)' }}
          >
            {t('collectionPage.inactiveNotice')}
          </Notification>
        )}
        {/* A shed booked by the hour that has no opening hours is closed every day,
            and whoever tries to reserve sees a calendar of grey: its curators are
            told where to fix it. Nobody else can. */}
        {isCurator &&
          collection.kind === 'SHED' &&
          collection.reservation_unit === 'HOUR' &&
          !hasOpeningHours(collection.opening_hours) && (
            <Notification
              label={t('collectionPage.noOpeningHoursLabel')}
              type="alert"
              style={{ marginBottom: 'var(--spacing-m)' }}
            >
              <p>{t('collectionPage.noOpeningHoursBody')}</p>
              <ButtonLink
                to={`${collectionPath(code, collection.kind)}/settings/availability`}
                style={btnStyle}
              >
                {t('collectionSettings.availability')}
              </ButtonLink>
            </Notification>
          )}
        {collection.is_paused && (
          <Notification
            label={t('pause.bannerLabel')}
            type="alert"
            style={{ marginBottom: 'var(--spacing-m)' }}
          >
            {collection.pause_message}
          </Notification>
        )}

        <ThingsSection
          collection={collection}
          code={code}
          headline={headline}
          canAddThing={canAddThing}
          onUpdateThing={handleUpdateThing}
          onJoinedGroup={reloadCollection}
        />
        {isCurator && collection.invites.length > 0 && <BroadcastBox code={code} />}

        <InactiveThings
          collection={collection}
          code={code}
          headline={headline}
          onUpdateThing={handleUpdateThing}
        />
        {/* A key, not text: Toast translates where it paints, and this opens just as
            `useCollectionLanguage` is changing the language. */}
        <Toast
          toast={
            isPhone && arrivedWith && !uploadedClosed
              ? { type: 'success', messageKey: 'addThing.uploaded' }
              : null
          }
          onClose={() => setUploadedClosed(true)}
        />
      </div>
    </div>
  );
}
