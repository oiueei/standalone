import { useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Notification, IconSpeechbubbleText, IconSwapUser } from 'hds-react';
import { DATE_TYPES, WISH_TYPE, SHARE_TYPE, SWAP_TYPE } from '../constants/things';
import MarkdownText from './MarkdownText';
import RespondMenu from './RespondMenu';
import useTheeeme from '../hooks/useTheeeme';
import useThingBooking from '../hooks/useThingBooking';
import ThingTags from './ThingTags';
import ThingInfoRows from './ThingInfoRows';
import OwnerBookingsList from './OwnerBookingsList';
import Toast from './Toast';
import ImageCarousel from './ImageCarousel';
import { onImageError } from '../utils/imageFallback';

export default function ThingLinkbox({ thing, userCode, collectionCode, collectionHeadline, collectionOwner, collectionMode, isPaused, canAct = true, hideType = false, loginToAct = false, onUpdateThing }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [toast, setToast] = useState(null);

  const isOwner = thing.owner === userCode;
  const { btnStyle, btnSecondaryStyle } = useTheeeme();
  const isWish = thing.type === WISH_TYPE;
  const isShare = thing.type === SHARE_TYPE;
  const isSwap = thing.type === SWAP_TYPE;
  const isDateBased = DATE_TYPES.includes(thing.type);
  // `needsPage` drives the reserve button's navigation: date-based (pick dates)
  // and swap (pick items) need a follow-up form, everything else POSTs directly.
  // `bookingKeepsStatus` drives whether accepting a hold keeps the thing
  // circulating. Endless GIFT/SELL keep their status but reserve via a direct
  // POST, so the two must stay separate — conflating them sends endless things
  // to an empty request page. (ThingPage computes these identically.)
  const needsPage = isDateBased || isSwap;
  const bookingKeepsStatus = needsPage || thing.is_endless;
  const isCollectionOwner = (collectionOwner || thing.collection_owner) === userCode;
  const canDelete = isCollectionOwner || (isOwner && (!isShare || thing.transfer_count === 0));

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
    isOwner,
    onThingChange: (patch) => onUpdateThing(thing.code, patch),
    setToast,
    initialActivePending: thing.pending_booking,
    initialRequested: thing.type === 'SHARE_THING' && !!thing.my_pending_booking,
    fetchOnEndless: true,
    bookingKeepsStatus,
  });

  // `canAct` is false for an anonymous visitor on a PUBLIC collection: the card
  // is read-only and the page-level JoinToAct prompt drives reserve/ask/respond.
  const showButton = (canAct || loginToAct) && !isOwner && thing.status !== 'INACTIVE';
  // Anonymous visitor (loginToAct): show the action buttons, but route each click
  // to the collection's join page — they log in there and come back able to act.
  const joinPath = `/collections/${collectionCode || thing.collection_code}/join`;
  const goJoin = () => navigate(joinPath, { state: { collectionHeadline: collectionHeadline || thing.collection_headline } });
  const loginButtonDisabled = isPaused || thing.status === 'TAKEN';
  const swapMinimum = thing.collection_swap_minimum_items || 0;
  const swapOwnCount = thing.my_swap_count_in_collection || 0;
  const swapMinimumNotMet = isSwap && swapMinimum > 0 && swapOwnCount < swapMinimum;
  const swapItemsMissing = swapMinimumNotMet ? swapMinimum - swapOwnCount : 0;
  const buttonDisabled = isPaused || thing.status === 'TAKEN' || submitting || requested || swapMinimumNotMet;
  // The current viewer holds the pending booking (locally requested, or returned
  // by the serializer). Only they see "waiting"; everyone else sees a reason the
  // disabled button can't be used — so the cause travels with the control (P1-2).
  const isMine = requested || !!thing.my_pending_booking;
  const buttonLabel = submitting
    ? t('common.sending')
    : isMine
      ? t('thingCard.waitingForConfirmation')
      : thing.status === 'TAKEN'
        ? t('thingCard.notAvailable')
        : isPaused
          ? t('thingCard.paused')
          : swapMinimumNotMet
            ? t('thingCard.needMoreItems', { count: swapItemsMissing })
            : t(`thingCard.action.${thing?.type}`, { defaultValue: t('thingCard.hold') });

  const editPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/edit`
    : `/things/${thing.code}/edit`;

  const deletePath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/delete`
    : `/things/${thing.code}/delete`;

  const deleteBackPath = collectionCode ? `/collections/${collectionCode}` : '/';
  const deleteBackLabel = collectionCode ? (collectionHeadline || t('common.collection')) : t('common.home');

  const thingPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}`
    : `/things/${thing.code}`;

  const requestPath = collectionCode
    ? `/collections/${collectionCode}/things/${thing.code}/request`
    : `/things/${thing.code}/request`;

  return (
    <div className="thing-card">
      {(() => {
        const images = [thing.thumbnail_url, ...(thing.gallery_urls || [])].filter(Boolean);
        if (images.length === 0) return null;
        if (images.length === 1) {
          return (
            <Link to={thingPath}>
              <img src={images[0]} alt={thing.headline} className="thing-card-image" loading="lazy" onError={onImageError} />
            </Link>
          );
        }
        return <ImageCarousel images={images} alt={thing.headline} variant="card" to={thingPath} />;
      })()}
      <div className="thing-card-body">
        {collectionMode === 'COMMUNITY' && (
          <p className="thing-card-meta">
            {thing.owner_name}{thing.created && ` · ${new Date(thing.created).toLocaleDateString(i18n.language, { day: '2-digit', month: '2-digit' })}`}
          </p>
        )}
        <h3 className="thing-card-headline">
          <Link to={thingPath} className="thing-card-link">{thing.headline}</Link>
        </h3>
        {thing.description && (
          <MarkdownText text={thing.description} className="thing-card-description" />
        )}
        <ThingTags thing={thing} isOwner={isOwner} showType={false} />
        <ThingInfoRows thing={thing} isDateBased={isDateBased} hideType={hideType}>
          {isWish && thing.response_count > 0 && (
            <div className="thing-card-info-row">
              <IconSpeechbubbleText size="m" aria-hidden="true" />
              <span>{t('wishes.responseCount', { count: thing.response_count })}</span>
            </div>
          )}
          {thing.transfer_count > 0 && (
            <div className="thing-card-info-row">
              <IconSwapUser size="m" aria-hidden="true" />
              <span>{t(`transfers.${
                thing.type === 'LEND_THING' ? 'lendCount' :
                thing.type === 'RENT_THING' ? 'rentCount' :
                thing.type === 'SHARE_THING' ? 'shareCount' :
                thing.type === 'SWAP_THING' ? 'swapCount' :
                'changesCount'
              }`, { count: thing.transfer_count })}</span>
            </div>
          )}
        </ThingInfoRows>
        <OwnerBookingsList bookings={bookings} activePendingCode={activePendingCode} isOwner={isOwner} />
        <div className="thing-card-buttons">
          {isOwner && thing.status === 'ACTIVE' && (
            <>
              {needsPage && activePendingCode && (
                <>
                  <Button fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('accept', activePendingCode)} style={btnStyle}>
                    {bookingActionVerb === 'accept' ? t('thingCard.confirming') : t('thingCard.confirmHold')}
                  </Button>
                  <Button variant="secondary" fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('reject', activePendingCode)} style={btnSecondaryStyle}>
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
              {!bookings.some((b) => b.status === 'PENDING') && canDelete && (
                <Button variant="secondary" fullWidth style={btnSecondaryStyle} onClick={() => navigate(deletePath, { state: { backPath: deleteBackPath, backLabel: deleteBackLabel } })}>
                  {t('common.delete')}
                </Button>
              )}
            </>
          )}
          {isOwner && thing.status === 'TAKEN' && (
            <>
              <Button fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('accept')} style={btnStyle}>
                {bookingActionVerb === 'accept' ? t('thingCard.confirming') : t('thingCard.confirmHold')}
              </Button>
              <Button variant="secondary" fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('reject')} style={btnSecondaryStyle}>
                {bookingActionVerb === 'reject' ? t('thingCard.cancelling') : t('thingCard.cancelHold')}
              </Button>
              <Link to={editPath} style={{ display: 'contents' }}>
                <Button variant="secondary" fullWidth style={btnSecondaryStyle}>{t('common.edit')}</Button>
              </Link>
            </>
          )}
          {isOwner && thing.status === 'INACTIVE' && (
            <>
              <Button fullWidth disabled={activating} onClick={handleActivate} style={btnStyle}>
                {activating ? t('thingCard.reactivating') : t('thingCard.reactivate')}
              </Button>
              <Link to={editPath} style={{ display: 'contents' }}>
                <Button variant="secondary" fullWidth style={btnSecondaryStyle}>{t('common.edit')}</Button>
              </Link>
              {canDelete && (
                <Button
                  variant="secondary"
                  fullWidth
                  style={btnSecondaryStyle}
                  onClick={() => navigate(deletePath, { state: { backPath: deleteBackPath, backLabel: deleteBackLabel } })}
                >
                  {t('common.delete')}
                </Button>
              )}
            </>
          )}
          {showButton && isWish && (
            loginToAct ? (
              <Button fullWidth style={btnStyle} onClick={goJoin}>{t('wishes.respond')}</Button>
            ) : thing.my_response ? (
              <p className="thing-card-meta">
                {t('wishes.yourAnswer')} · {t('wishes.status.' + thing.my_response.status)}
              </p>
            ) : (
              <RespondMenu
                thingCode={thing.code}
                collectionCode={collectionCode || thing.collection_code}
                backPath={collectionCode ? `/collections/${collectionCode}` : '/'}
                backLabel={collectionCode ? (collectionHeadline || t('common.collection')) : t('common.home')}
              />
            )
          )}
          {showButton && !isWish && (
            <Button
              fullWidth
              disabled={loginToAct ? loginButtonDisabled : buttonDisabled}
              style={btnStyle}
              onClick={loginToAct ? goJoin : (needsPage ? () => navigate(requestPath, { state: { backPath: collectionCode ? `/collections/${collectionCode}` : '/', backLabel: collectionCode ? (collectionHeadline || t('common.collection')) : t('common.home') } }) : handleRequest)}
            >
              {buttonLabel}
            </Button>
          )}
          {showButton && swapMinimumNotMet && !loginToAct && (
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
            <Button
              variant="secondary"
              fullWidth
              style={btnSecondaryStyle}
              onClick={() => navigate(deletePath, { state: { backPath: deleteBackPath, backLabel: deleteBackLabel } })}
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
