import { useState, memo } from 'react';
import { Link, useNavigate } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button, Notification, IconSpeechbubbleText, IconSwapUser } from 'hds-react';
import MarkdownText from './MarkdownText';
import InlineConfirm from './InlineConfirm';
import useTheeeme from '../hooks/useTheeeme';
import useThingActions from '../hooks/useThingActions';
import ThingTags from './ThingTags';
import ThingInfoRows from './ThingInfoRows';
import OwnerBookingsList from './OwnerBookingsList';
import Toast from './Toast';
import ImageCarousel from './ImageCarousel';
import { onImageError } from '../utils/imageFallback';
import { useLocalized } from '../utils/localized';
import { formatDate } from '../utils/rental';
import ButtonLink from './ButtonLink';
import { collectionPath, collectionThingPath } from '../utils/collectionPath';

// Memoised: CollectionPage keeps broadcast/tag-filter state at its root, so a
// keystroke in the broadcast box re-renders the page. With stable props (the
// parent passes a useCallback'd onUpdateThing) memo skips re-rendering every card.
function ThingLinkbox({
  thing,
  userCode,
  collectionCode,
  collectionKind,
  collectionHeadline,
  collectionOwner,
  collectionMode,
  insideGroup = false,
  isPaused,
  canAct = true,
  hideType = false,
  loginToAct = false,
  onUpdateThing,
  onJoinedGroup,
}) {
  const { t } = useTranslation();
  const navigate = useNavigate();
  const [toast, setToast] = useState(null);
  // The owner may have written the headline / description once per language.
  const L = useLocalized();
  const headline = L(thing.headline);

  const { btnStyle, btnSecondaryStyle } = useTheeeme();

  // Owner-button-matrix + reservation view-model (shared with ThingPage). The
  // card's own seeds (pending from the serializer, endless calendar)
  // and `loginToAct` mode are passed as options; see useThingActions.
  const {
    bookingAction,
    bookingActionVerb,
    activating,
    bookings,
    activePendingCode,
    handleRequest,
    handleActivate,
    handleBookingAction,
    canManage,
    isCollectionOwner,
    isDateBased,
    needsPage,
    canDelete,
    showButton,
    buttonDisabled,
    loginButtonDisabled,
    buttonLabel,
  } = useThingActions(thing, userCode, {
    isPaused,
    canAct,
    loginToAct,
    collectionOwner,
    onThingChange: (patch) => onUpdateThing(thing.code, patch),
    setToast,
    initialActivePending: thing.pending_booking,
    fetchOnEndless: true,
    collectionCode: collectionCode || thing.collection_code,
    // The group the page lists this card from: the card's payload carries no
    // `collection_code` of its own, and the thing is in it by construction.
    joinCollectionCode: collectionCode || null,
    joinedGroupName: collectionHeadline,
    onJoined: onJoinedGroup,
  });

  // Anonymous visitor (loginToAct): show the action buttons, but route each click
  // to the collection's join page — they log in there and come back able to act.
  // `?thing=` rides along so the magic link lands them back on *this* thing, not
  // the collection index; it survives a refresh of the join page, unlike
  // navigation state.
  const kind = collectionKind || thing.collection_kind;
  const joinPath = `${collectionPath(collectionCode || thing.collection_code, kind, '/join')}?thing=${thing.code}`;
  const goJoin = () =>
    navigate(joinPath, {
      state: { collectionHeadline: collectionHeadline || L(thing.collection_headline) },
    });
  // The owner "Confirm request" label, with its in-flight ("Confirming…") state. Shared
  // by the plain accept Button and the ownership-transfer <InlineConfirm> trigger.
  const acceptLabel =
    bookingActionVerb === 'accept' ? t('thingCard.confirming') : t('thingCard.confirmHold');

  const editPath = collectionCode
    ? collectionThingPath(collectionCode, kind, thing.code, '/edit')
    : `/things/${thing.code}/edit`;

  const deletePath = collectionCode
    ? collectionThingPath(collectionCode, kind, thing.code, '/delete')
    : `/things/${thing.code}/delete`;

  const deleteBackPath = collectionCode ? collectionPath(collectionCode, kind) : '/';
  const deleteBackLabel = collectionCode
    ? collectionHeadline || t('common.collection')
    : t('common.home');

  const thingPath = collectionCode
    ? collectionThingPath(collectionCode, kind, thing.code)
    : `/things/${thing.code}`;

  const requestPath = collectionCode
    ? collectionThingPath(collectionCode, kind, thing.code, '/request')
    : `/things/${thing.code}/request`;

  return (
    // `data-thing-code` is how the collection page finds this card: it scrolls to
    // the one just uploaded, and marks it.
    <div className="thing-card" data-thing-code={thing.code}>
      {(() => {
        const images = [thing.thumbnail_url, ...(thing.gallery_urls || [])].filter(Boolean);
        if (images.length === 0) return null;
        if (images.length === 1) {
          return (
            // Same destination and same name as the headline link below, so it
            // is a second tab stop that goes nowhere new — and a second entry
            // under the same words in a screen reader's list of links, twice per
            // card. The headline is the real link; this one keeps working for a
            // pointer and steps out of the way of everything else. The `alt`
            // empties with it: the name is announced once, by the link that
            // stayed.
            <Link to={thingPath} tabIndex={-1} aria-hidden="true">
              <img
                src={images[0]}
                alt=""
                className="thing-card-image"
                loading="lazy"
                onError={onImageError}
              />
            </Link>
          );
        }
        return <ImageCarousel images={images} alt={headline} variant="card" to={thingPath} />;
      })()}
      <div className="thing-card-body">
        {collectionMode === 'COMMUNITY' && (
          <p className="thing-card-meta">
            {/* The contributing member. A reader with no account is told there
                *is* one — which is what the COMMUNITY grid exists to show —
                but not who: the API withholds the name from them
                (`ThingComputedFieldsMixin.get_owner_name`). The link is for
                someone inside the group only (`insideGroup`): the profile behind
                it opens for the group's own people and nobody else, so for any
                other reader it was only ever a door onto a 403. */}
            {insideGroup && thing.owner_name && thing.owner ? (
              <Link to={`/${thing.owner}`} className="thing-card-owner-link">
                {thing.owner_name}
              </Link>
            ) : (
              thing.owner_name || t('common.aMember')
            )}
            {thing.created && ` · ${formatDate(thing.created)}`}
          </p>
        )}
        {/* Always an h3: the card's headline is a heading in the *page's* outline,
            and the only page that renders cards, CollectionPage, puts its grids
            under an <h2> section heading ("Things", "Inactive things"). A page
            that put them straight under its <h1> would skip a level — the
            `headingLevel` prop that answered that went with /shared (2026-10-03). */}
        <h3 className="thing-card-headline">
          <Link to={thingPath} className="thing-card-link">
            {headline}
          </Link>
        </h3>
        {thing.description && (
          <MarkdownText
            text={L(thing.description)}
            className="thing-card-description"
            variant="card"
          />
        )}
        <ThingTags thing={thing} isOwner={canManage} showType={false} />
        <ThingInfoRows thing={thing} isDateBased={isDateBased} hideType={hideType}>
          {thing.transfer_count > 0 && (
            <div className="thing-card-info-row">
              <IconSwapUser size="m" aria-hidden="true" />
              <span>
                {t(
                  `transfers.${
                    thing.type === 'LEND_THING'
                      ? 'lendCount'
                      : thing.type === 'RENT_THING'
                        ? 'rentCount'
                        : 'changesCount'
                  }`,
                  { count: thing.transfer_count }
                )}
              </span>
            </div>
          )}
        </ThingInfoRows>
        <OwnerBookingsList
          bookings={bookings}
          activePendingCode={activePendingCode}
          isOwner={canManage}
          thingType={thing.type}
          thingHeadline={thing.headline}
        />
        <div className="thing-card-buttons">
          {canManage && thing.status === 'ACTIVE' && (
            <>
              {needsPage && activePendingCode && (
                <>
                  <Button
                    fullWidth
                    disabled={!!bookingAction}
                    onClick={() => handleBookingAction('accept', activePendingCode)}
                    style={btnStyle}
                  >
                    {acceptLabel}
                  </Button>
                  <Button
                    variant="secondary"
                    fullWidth
                    disabled={!!bookingAction}
                    onClick={() => handleBookingAction('reject', activePendingCode)}
                    style={btnSecondaryStyle}
                  >
                    {bookingActionVerb === 'reject'
                      ? t('thingCard.cancelling')
                      : t('thingCard.cancelHold')}
                  </Button>
                </>
              )}
              <ButtonLink
                to={editPath}
                fullWidth
                style={needsPage && activePendingCode ? btnSecondaryStyle : btnStyle}
              >
                {t('common.edit')}
              </ButtonLink>
              {!bookings.some((b) => b.status === 'PENDING') && canDelete && (
                <Button
                  variant="secondary"
                  fullWidth
                  style={btnSecondaryStyle}
                  onClick={() =>
                    navigate(deletePath, {
                      state: { backPath: deleteBackPath, backLabel: deleteBackLabel },
                    })
                  }
                >
                  {t('common.delete')}
                </Button>
              )}
            </>
          )}
          {canManage && thing.status === 'TAKEN' && (
            <>
              <Button
                fullWidth
                disabled={!!bookingAction}
                onClick={() => handleBookingAction('accept')}
                style={btnStyle}
              >
                {acceptLabel}
              </Button>
              <Button
                variant="secondary"
                fullWidth
                disabled={!!bookingAction}
                onClick={() => handleBookingAction('reject')}
                style={btnSecondaryStyle}
              >
                {bookingActionVerb === 'reject'
                  ? t('thingCard.cancelling')
                  : t('thingCard.cancelHold')}
              </Button>
              <ButtonLink to={editPath} fullWidth style={btnSecondaryStyle}>
                {t('common.edit')}
              </ButtonLink>
            </>
          )}
          {canManage && thing.status === 'INACTIVE' && (
            <>
              <Button fullWidth disabled={activating} onClick={handleActivate} style={btnStyle}>
                {activating ? t('thingCard.reactivating') : t('thingCard.reactivate')}
              </Button>
              <ButtonLink to={editPath} fullWidth style={btnSecondaryStyle}>
                {t('common.edit')}
              </ButtonLink>
              {canDelete && (
                <Button
                  variant="secondary"
                  fullWidth
                  style={btnSecondaryStyle}
                  onClick={() =>
                    navigate(deletePath, {
                      state: { backPath: deleteBackPath, backLabel: deleteBackLabel },
                    })
                  }
                >
                  {t('common.delete')}
                </Button>
              )}
            </>
          )}
          {showButton && (
            <Button
              fullWidth
              disabled={loginToAct ? loginButtonDisabled : buttonDisabled}
              style={btnStyle}
              onClick={
                loginToAct
                  ? goJoin
                  : needsPage
                    ? () =>
                        navigate(requestPath, {
                          state: {
                            backPath: collectionCode ? collectionPath(collectionCode, kind) : '/',
                            backLabel: collectionCode
                              ? collectionHeadline || t('common.collection')
                              : t('common.home'),
                          },
                        })
                    : handleRequest
              }
            >
              {buttonLabel}
            </Button>
          )}
          {isCollectionOwner && !canManage && (
            <Button
              variant="secondary"
              fullWidth
              style={btnSecondaryStyle}
              onClick={() =>
                navigate(deletePath, {
                  state: { backPath: deleteBackPath, backLabel: deleteBackLabel },
                })
              }
            >
              {t('common.delete')}
            </Button>
          )}
        </div>
      </div>
      <Toast toast={toast} onClose={() => setToast(null)} />
    </div>
  );
}

export default memo(ThingLinkbox);
