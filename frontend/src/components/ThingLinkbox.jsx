import { useState, memo } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import { Button, Notification, IconSpeechbubbleText, IconSwapUser } from 'hds-react';
import { SHARE_TYPE } from '../constants/things';
import MarkdownText from './MarkdownText';
import InlineConfirm from './InlineConfirm';
import RespondMenu from './RespondMenu';
import useTheeeme from '../hooks/useTheeeme';
import useThingActions from '../hooks/useThingActions';
import ThingTags from './ThingTags';
import ThingInfoRows from './ThingInfoRows';
import OwnerBookingsList from './OwnerBookingsList';
import Toast from './Toast';
import ImageCarousel from './ImageCarousel';
import { onImageError } from '../utils/imageFallback';
import { useLocalized } from '../utils/localized';

// Memoised: CollectionPage keeps broadcast/tag-filter state at its root, so a
// keystroke in the broadcast box re-renders the page. With stable props (the
// parent passes a useCallback'd onUpdateThing) memo skips re-rendering every card.
function ThingLinkbox({ thing, userCode, collectionCode, collectionHeadline, collectionOwner, collectionMode, isPaused, canAct = true, hideType = false, loginToAct = false, onUpdateThing }) {
  const { t, i18n } = useTranslation();
  const navigate = useNavigate();
  const [toast, setToast] = useState(null);
  // The owner may have written the headline / description once per language.
  const L = useLocalized();
  const headline = L(thing.headline);

  const { btnStyle, btnSecondaryStyle } = useTheeeme();

  // Owner-button-matrix + reservation view-model (shared with ThingPage). The
  // card's own seeds (pending from the serializer, SHARE fold, endless calendar)
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
    isOwner,
    isCollectionOwner,
    isWish,
    isDateBased,
    needsPage,
    canDelete,
    acceptTransfersOwnership,
    showButton,
    swapMinimumNotMet,
    swapItemsMissing,
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
    initialRequested: thing.type === SHARE_TYPE && !!thing.my_pending_booking,
    fetchOnEndless: true,
    collectionCode: collectionCode || thing.collection_code,
  });

  // Anonymous visitor (loginToAct): show the action buttons, but route each click
  // to the collection's join page — they log in there and come back able to act.
  const joinPath = `/collections/${collectionCode || thing.collection_code}/join`;
  const goJoin = () => navigate(joinPath, { state: { collectionHeadline: collectionHeadline || L(thing.collection_headline) } });
  // The owner "Confirm hold" label, with its in-flight ("Confirming…") state. Shared
  // by the plain accept Button and the ownership-transfer <InlineConfirm> trigger.
  const acceptLabel = bookingActionVerb === 'accept' ? t('thingCard.confirming') : t('thingCard.confirmHold');

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
              <img src={images[0]} alt={headline} className="thing-card-image" loading="lazy" onError={onImageError} />
            </Link>
          );
        }
        return <ImageCarousel images={images} alt={headline} variant="card" to={thingPath} />;
      })()}
      <div className="thing-card-body">
        {collectionMode === 'COMMUNITY' && (
          <p className="thing-card-meta">
            {thing.owner ? (
              <Link to={`/${thing.owner}`} className="thing-card-owner-link">{thing.owner_name}</Link>
            ) : (
              thing.owner_name
            )}
            {thing.created && ` · ${new Date(thing.created).toLocaleDateString(i18n.language, { day: '2-digit', month: '2-digit' })}`}
          </p>
        )}
        <h3 className="thing-card-headline">
          <Link to={thingPath} className="thing-card-link">{headline}</Link>
        </h3>
        {thing.description && (
          <MarkdownText text={L(thing.description)} className="thing-card-description" />
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
                  {acceptTransfersOwnership ? (
                    <InlineConfirm
                      triggerLabel={acceptLabel}
                      triggerProps={{ fullWidth: true, disabled: !!bookingAction, style: btnStyle }}
                      title={t('thingCard.transferConfirmTitle')}
                      body={t('thingCard.transferConfirmBody')}
                      confirmLabel={t('thingCard.transferConfirm')}
                      onConfirm={() => handleBookingAction('accept', activePendingCode)}
                      confirming={!!bookingAction}
                      confirmProps={{ style: btnStyle }}
                    />
                  ) : (
                    <Button fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('accept', activePendingCode)} style={btnStyle}>
                      {acceptLabel}
                    </Button>
                  )}
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
              {acceptTransfersOwnership ? (
                <InlineConfirm
                  triggerLabel={acceptLabel}
                  triggerProps={{ fullWidth: true, disabled: !!bookingAction, style: btnStyle }}
                  title={t('thingCard.transferConfirmTitle')}
                  body={t('thingCard.transferConfirmBody')}
                  confirmLabel={t('thingCard.transferConfirm')}
                  onConfirm={() => handleBookingAction('accept')}
                  confirming={!!bookingAction}
                  confirmProps={{ style: btnStyle }}
                />
              ) : (
                <Button fullWidth disabled={!!bookingAction} onClick={() => handleBookingAction('accept')} style={btnStyle}>
                  {acceptLabel}
                </Button>
              )}
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

export default memo(ThingLinkbox);
