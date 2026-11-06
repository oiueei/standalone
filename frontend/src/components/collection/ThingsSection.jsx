import { useState } from 'react';
import { useNavigate, useParams } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button } from 'hds-react';
import ThingLinkbox from '../ThingLinkbox';
import useTheeeme from '../../hooks/useTheeeme';
import { useLocalized } from '../../utils/localized';
import { compareNames } from '../../utils/team';
import { collectionPath } from '../../utils/collectionPath';

/**
 * Cards mounted before the "Show more" button appears.
 *
 * The collection serialises **every** thing it holds and there is no ceiling on
 * how many that is (`COLLECTION_THINGS_BLOCK` is off by default), so a lending
 * library with 200 items used to mount 200 `ThingLinkbox`es — each with its own
 * theeeme, localisation and booking view-model — on first paint. The photos were
 * already `loading="lazy"`, so what this cuts is the mount cost, which is what
 * a mid-range Android actually feels (DESIGN §7).
 *
 * Deliberately a **render** cap, not server pagination: the tag chips count
 * across the whole collection, and a paginated payload would make those counts
 * lie. 24 fills the widest grid (4 columns) six rows deep.
 */
const CARDS_PER_PAGE = 24;

/**
 * The dinamizadores of a network with at least one visible thing: their code, the name
 * of their pickup point and how many things they show, by name. A thing carries the
 * name its server resolved (`network_point.display_name`).
 */
function lendersOf(collection, visibleThings, t, language) {
  const curators = new Set([collection.owner, ...(collection.co_owners || []).map((c) => c.code)]);
  const byCode = new Map();
  for (const thing of visibleThings) {
    if (!curators.has(thing.owner)) continue;
    const known = byCode.get(thing.owner);
    if (known) known.count += 1;
    else {
      byCode.set(thing.owner, {
        code: thing.owner,
        name: thing.network_point?.display_name || thing.owner_name || t('common.aMember'),
        count: 1,
      });
    }
  }
  return [...byCode.values()].sort(compareNames(language));
}

/**
 * The collection's things: the tag chips, the grid of active cards with its
 * "Show more", and what an empty group or an empty tag says. `onUpdateThing` and
 * `onJoinedGroup` are the page's own (stable) callbacks, handed straight to the
 * memoised cards.
 */
export default function ThingsSection({
  collection,
  code,
  headline,
  canAddThing,
  onUpdateThing,
  onJoinedGroup,
}) {
  const { t, i18n } = useTranslation();
  const language = i18n.resolvedLanguage || i18n.language;
  const { btnSecondaryStyle } = useTheeeme();
  const L = useLocalized();
  const navigate = useNavigate();
  // The dinamizador of a network the page is filtered by lives in the address
  // (`/library/:code/:curatorCode`), so a filtered view can be shared.
  const { curatorCode } = useParams();
  const [activeTag, setActiveTag] = useState(null);
  const [shownCount, setShownCount] = useState(CARDS_PER_PAGE);
  const userCode = localStorage.getItem('userCode');
  const isAuthenticated = !!userCode;
  // A collection locked to one thing type makes the per-card "Type = X" row
  // redundant — hide it (an allowlist of one).
  const singleType = (collection.allowed_thing_types || []).length === 1;

  // Active (non-inactive) things, optionally narrowed to the selected tag chip.
  const visibleThings = collection.things.filter((thg) => thg.status !== 'INACTIVE');
  const collectionTags = collection.tags || [];
  const effectiveTag = activeTag && collectionTags.includes(activeTag) ? activeTag : null;

  // A network's dinamizadores that have something to show, each by the name of their
  // pickup point (the entity's, else their own — resolved by the server on the thing).
  // Only a dinamizador of this network counts, and only with a visible thing.
  const lenders =
    collection.mode === 'NETWORK' ? lendersOf(collection, visibleThings, t, language) : [];
  // An address naming anybody else (not a dinamizador, not a network) is the collection
  // as it is, with no error.
  const effectiveLender = lenders.some((l) => l.code === curatorCode) ? curatorCode : null;
  const base = collectionPath(code, collection.kind);
  const chooseLender = (lenderCode) => {
    setShownCount(CARDS_PER_PAGE);
    // `replace`: a filter is a slice of the page, like a tag, and leaves no history for
    // "Back" to walk through. `keepFocus`: the button pressed keeps the focus and the
    // list stays where it is (see RouteFocusReset in App.jsx). The address is still the
    // filtered one, to share and to open.
    navigate(lenderCode ? `${base}/${lenderCode}` : base, {
      replace: true,
      state: { keepFocus: true },
    });
  };

  const matchingThings = visibleThings.filter(
    (thg) =>
      (!effectiveTag || (thg.tags || []).includes(effectiveTag)) &&
      (!effectiveLender || thg.owner === effectiveLender)
  );
  // Newest first, then capped at what's actually been asked for. Sorting before
  // the slice is what makes "Show more" append older things rather than reshuffle.
  const sortedThings = [...matchingThings].sort(
    (a, b) => new Date(b.created) - new Date(a.created)
  );
  const shownThings = sortedThings.slice(0, shownCount);
  const remainingThings = sortedThings.length - shownThings.length;

  return (
    <>
      {/* Visually hidden, still in the outline. The cards
            below are <h3>s (ThingLinkbox's default) and rely on an <h2> above
            them: take this out and the page jumps from <h1> to <h3>, which axe's
            heading-order flags. It also stays a landmark a screen-reader user can
            jump to, next to "Messages to the group". */}
      <h2 className="sr-only">{t('collectionPage.things')}</h2>
      {/* A recorded DESIGN §1 exception, not an oversight: these are plain
            `<button aria-pressed>`s, not HDS `Tag`. HDS `Tag` (`variant="action"`)
            has no pressed/selected state to bind `aria-pressed` to, and a filter
            chip has to announce which one is active. The `.tag-chip` styling is
            ours; it sits on the same page as real HDS `Tag`s (`ThingTags`, on
            every card below), so the two are free to drift apart visually —
            worth knowing if either one's look changes (found in review,
            2026-09-18). */}
      {visibleThings.length > 0 && collectionTags.length > 0 && (
        <div className="tag-filter-bar">
          <button
            type="button"
            className="tag-chip"
            aria-pressed={!effectiveTag}
            onClick={() => {
              setActiveTag(null);
              setShownCount(CARDS_PER_PAGE);
            }}
          >
            {t('collectionPage.allTags')} ({visibleThings.length})
          </button>
          {collectionTags.map((tag) => {
            const count = visibleThings.filter((thg) => (thg.tags || []).includes(tag)).length;
            return (
              <button
                key={tag}
                type="button"
                className="tag-chip"
                aria-pressed={effectiveTag === tag}
                onClick={() => {
                  setActiveTag(effectiveTag === tag ? null : tag);
                  setShownCount(CARDS_PER_PAGE);
                }}
              >
                {L(tag)} ({count})
              </button>
            );
          })}
        </div>
      )}
      {/* The same chips, by who lends: a second row that combines with the tags. With a
          single dinamizador it would be "All (5)" next to "Fusteria (5)": the same button
          twice, so there is no row until there are two. */}
      {visibleThings.length > 0 && lenders.length > 1 && (
        <div className="tag-filter-bar" role="group" aria-label={t('networkPoint.filterLabel')}>
          <button
            type="button"
            className="tag-chip"
            aria-pressed={!effectiveLender}
            onClick={() => chooseLender(null)}
          >
            {t('collectionPage.allTags')} ({visibleThings.length})
          </button>
          {lenders.map((lender) => (
            <button
              key={lender.code}
              type="button"
              className="tag-chip"
              aria-pressed={effectiveLender === lender.code}
              onClick={() => chooseLender(effectiveLender === lender.code ? null : lender.code)}
            >
              {lender.name} ({lender.count})
            </button>
          ))}
        </div>
      )}
      {visibleThings.length === 0 ? (
        // Whoever can add a thing (a curator, or a member of a COMMUNITY group)
        // already has "Add thing" in the hero, so an empty group says nothing to
        // them: the phrase, "Add one" and the CSV link are gone,
        // the CSV one into the collection menu. Whoever cannot — a member of a
        // PROPRIETARY group, a reader with no session — is told, with no link.
        canAddThing ? null : (
          <p>{t('collectionPage.noThings')}</p>
        )
      ) : shownThings.length === 0 ? (
        <p>{t('collectionPage.noThingsForTag')}</p>
      ) : (
        <>
          <div className="things-grid">
            {shownThings.map((thing) => (
              <ThingLinkbox
                key={thing.code}
                thing={thing}
                userCode={userCode}
                collectionCode={code}
                collectionKind={collection.kind}
                collectionHeadline={headline}
                collectionOwner={collection.owner}
                collectionMode={collection.mode}
                insideGroup={!!collection.is_curator || !!collection.is_member}
                isPaused={collection.is_paused}
                hideType={singleType}
                canAct={isAuthenticated}
                loginToAct={!isAuthenticated}
                onUpdateThing={onUpdateThing}
                onJoinedGroup={onJoinedGroup}
              />
            ))}
          </div>
          {remainingThings > 0 && (
            <>
              <div className="spacer-m" />
              {/* A pager is a loose action button like any other: in a wide row,
                    so on a phone it is the width of the screen. */}
              <div className="button-row-wide">
                <Button
                  variant="secondary"
                  style={btnSecondaryStyle}
                  onClick={() => setShownCount((n) => n + CARDS_PER_PAGE)}
                >
                  {t('collectionPage.showMoreThings', { count: remainingThings })}
                </Button>
              </div>
            </>
          )}
        </>
      )}
    </>
  );
}

/**
 * The things the reader may see that are no longer active: the collection owner's
 * every one, and a member's own in a COMMUNITY group.
 */
export function InactiveThings({ collection, code, headline, onUpdateThing }) {
  const { t } = useTranslation();
  const userCode = localStorage.getItem('userCode');
  const singleType = (collection.allowed_thing_types || []).length === 1;

  return (
    <>
      {/* Gated on the payload, not on `isOwner` (the *collection* owner): the
            backend now sends an INACTIVE thing to two audiences — the
            collection owner (every one) and that thing's own owner (just
            theirs), the same "owner can always view their own things" rule
            `Thing.can_view()` already states. In a COMMUNITY collection a
            member's own gift going INACTIVE after a completed hand-off, or a
            listing they hid themselves, must stay reachable from here — not
            only via the thing's own `/things/{code}` URL — same as it always
            has for the collection owner. */}
      {collection.things.some((thg) => thg.status === 'INACTIVE') && (
        <>
          <div className="spacer-l" />
          <h2>{t('collectionPage.inactiveThings')}</h2>
          <div className="spacer-m" />
          <div className="things-grid">
            {[...collection.things]
              .filter((thg) => thg.status === 'INACTIVE')
              .sort((a, b) => {
                return new Date(b.created) - new Date(a.created);
              })
              .map((thing) => (
                <ThingLinkbox
                  key={thing.code}
                  thing={thing}
                  userCode={userCode}
                  collectionCode={code}
                  collectionKind={collection.kind}
                  collectionHeadline={headline}
                  collectionOwner={collection.owner}
                  collectionMode={collection.mode}
                  insideGroup={!!collection.is_curator || !!collection.is_member}
                  hideType={singleType}
                  onUpdateThing={onUpdateThing}
                />
              ))}
          </div>
        </>
      )}
    </>
  );
}
