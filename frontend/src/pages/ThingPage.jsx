import { useCallback, useEffect, useState } from 'react';
import { useParams, useNavigate, Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import CollectionMenu, {
  CollectionDigestStatus,
  CollectionDownloadsStatus,
} from '../components/CollectionMenu';
import LoadingSpinner from '../components/LoadingSpinner';
import InlineConfirm from '../components/InlineConfirm';
import ThingTags from '../components/ThingTags';
import ThingInfoRows from '../components/ThingInfoRows';
import NetworkPointLine from '../components/NetworkPointLine';
import OwnerBookingsList from '../components/OwnerBookingsList';
import ThingReportFooter from '../components/ThingReportFooter';
import ThingFaqSection from '../components/ThingFaqSection';
import DemoNotice from '../components/DemoNotice';
import Toast from '../components/Toast';
import MarkdownText from '../components/MarkdownText';
import ImageCarousel from '../components/ImageCarousel';
import { onImageError } from '../utils/imageFallback';
import { formatDate } from '../utils/rental';
import { useLocalized } from '../utils/localized';
import useTheeeme from '../hooks/useTheeeme';
import useCollectionTheeeme from '../hooks/useCollectionTheeeme';
import useThingActions from '../hooks/useThingActions';
import ButtonLink from '../components/ButtonLink';
import RefusalWayOut from '../components/RefusalWayOut';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import useCollectionDownloads from '../hooks/useCollectionDownloads';
import useDigestPreference from '../hooks/useDigestPreference';
import { useCanonicalCollectionPath } from '../hooks/useCollectionBase';
import { collectionPath, collectionThingPath } from '../utils/collectionPath';
import useDocumentTitle from '../hooks/useDocumentTitle';

export default function ThingPage() {
  const { code, thingCode } = useParams();
  const navigate = useNavigate();
  const { t } = useTranslation();
  const userCode = localStorage.getItem('userCode');
  const isAuthenticated = !!userCode;
  const { btnStyle, btnSecondaryStyle } = useTheeeme();

  const [thing, setThing] = useState(null);
  const [error, setError] = useState('');
  const [toast, setToast] = useState(null);
  // The owner may have written this thing's text once per language.
  const L = useLocalized();
  const headline = L(thing?.headline);
  useCollectionLanguage(thing?.collection_language, [thing?.headline, thing?.description]);
  // The colours of the collection this thing is read through (none when the reader has no
  // collection to read it through: the standalone page then wears the app's palette).
  useCollectionTheeeme(thing?.collection_theeeme_colors, thing?.collection_koro);
  useDocumentTitle(thing ? t('titles.thing', { headline }) : t('titles.thingDefault'));

  // The collection menu of the corner, when this page is read through a collection:
  // the same one the collection's own page has — a curator's
  // (Add thing, CSV, Manage members, downloads) or a member's (document, summary,
  // leave) — plus "Requests to me". Both hooks are called here, unconditionally, and
  // only used when the server sent `collection_menu` (see ThingSerializer).
  const downloads = useCollectionDownloads(code);
  const digestPref = useDigestPreference({
    code,
    muted: !!thing?.collection_menu?.is_digest_muted,
    onChange: useCallback(
      (muted) =>
        setThing((prev) =>
          prev?.collection_menu
            ? { ...prev, collection_menu: { ...prev.collection_menu, is_digest_muted: muted } }
            : prev
        ),
      []
    ),
  });

  // Anonymous visitor on a PUBLIC collection: like ThingLinkbox's login-to-act
  // mode, show the action buttons but route each click to the collection's join
  // page (they log in there and come back able to act) rather than an inline form.
  const collectionCode = code || thing?.collection_code;
  // The kind that makes the collection's address — the one the server resolved the
  // thing to, so only valid for that same code.
  const kind = collectionCode === thing?.collection_code ? thing?.collection_kind : undefined;
  useCanonicalCollectionPath(kind);
  const loginToAct = !isAuthenticated && !!collectionCode;
  const goJoin = () =>
    navigate(`${collectionPath(collectionCode, kind, '/join')}?thing=${thingCode}`, {
      state: { collectionHeadline: L(thing?.collection_headline) },
    });

  // Owner-button-matrix + reservation view-model (shared with ThingLinkbox).
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
    acceptTransfersOwnership,
    hasPendingBookings,
    showButton,
    buttonDisabled,
    loginButtonDisabled,
    buttonLabel,
  } = useThingActions(thing, userCode, {
    canAct: isAuthenticated,
    loginToAct,
    onThingChange: (patch) => setThing((prev) => ({ ...prev, ...patch })),
    setToast,
    activateSuccessMessage: t('thingPage.thingReactivated'),
    collectionCode,
    // Only the collection the server resolved this thing to — never the route's
    // code on its own (see RequestThingPage's `joinableCollection`).
    joinCollectionCode:
      thing?.collection_code && (!code || code === thing.collection_code)
        ? thing.collection_code
        : null,
    joinedGroupName: L(thing?.collection_headline),
  });

  // The owner "Confirm request" label, with its in-flight ("Confirming…") state. Shared
  // by the plain accept Button and the ownership-transfer <InlineConfirm> trigger.
  const acceptLabel =
    bookingActionVerb === 'accept' ? t('thingCard.confirming') : t('thingCard.confirmHold');

  // Transfer state
  const [transfers, setTransfers] = useState(null);

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;

    const fetchThing = async () => {
      try {
        // In a collection's context, read the thing *through* that collection
        // (the same shape as RequestThingPage): `available_today`,
        // `next_available` and `can_manage` come back computed against the
        // collection in the URL, so what the page shows is the collection the
        // reader is browsing, not whichever the server picks.
        const query = code ? `?collection=${encodeURIComponent(code)}` : '';
        const res = await apiFetch(`/api/v1/things/${thingCode}/${query}`, { signal });
        if (res.ok) {
          const data = await res.json();
          if (signal.aborted) return;
          setThing(data);
        } else if (res.status === 403) {
          setError('thingPage.noPermission');
        } else if (res.status === 404) {
          setError('thingPage.notFound');
        } else {
          setError('thingPage.errorLoading');
        }
      } catch {
        if (!signal.aborted) setError('common.connectionError');
      }
    };

    const fetchTransfers = async () => {
      try {
        const res = await apiFetch(`/api/v1/things/${thingCode}/transfers/`, { signal });
        if (res.ok) {
          const data = await res.json();
          if (signal.aborted) return;
          setTransfers(data);
        }
      } catch {
        /* silently fail */
      }
    };

    fetchThing();
    fetchTransfers();
    return () => controller.abort();
    // `code` is a dependency on purpose: without it, moving between two
    // collections that share this thing would keep the first one's answer.
    // `t` is not: `error` holds an i18n key, translated where it is painted, and
    // `useCollectionLanguage` swaps `t` once this very response lands — listing
    // it fetched the thing (and its transfers) a second time.
  }, [userCode, thingCode, code, navigate]);

  if (error) {
    // Not being allowed in is a fact about the reader's access, not a fault: it
    // says so in the title and is announced as a notice rather than as an error.
    const noAccess = error === 'thingPage.noPermission';
    return (
      <PageLayout
        title={noAccess ? t('thingPage.noAccessTitle') : t('common.error')}
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

  if (!thing) {
    return <LoadingSpinner />;
  }

  // canManage, type flags, canDelete, showButton, buttonDisabled and
  // buttonLabel all come from useThingActions (destructured at the top).

  const editPath = code
    ? collectionThingPath(code, kind, thing.code, '/edit')
    : `/things/${thing.code}/edit`;

  const backPath = collectionCode ? collectionPath(collectionCode, kind) : '/';
  const backLabel =
    L(thing.collection_headline) || (collectionCode ? t('common.collection') : t('common.home'));

  const requestPath = code
    ? collectionThingPath(code, kind, thing.code, '/request')
    : `/things/${thing.code}/request`;

  const deletePath = code
    ? collectionThingPath(code, kind, thing.code, '/delete')
    : `/things/${thing.code}/delete`;

  // An empty name in the journey means two different things, and only the
  // viewer's own session tells them apart: for a signed-in reader it is a
  // deleted account (right to erasure), so "Former member" is the truth; for a
  // signed-out one the API withheld every name, and calling people who are
  // still here former members would be a lie the reader has no way to check.
  const holderLabel = (name) =>
    name || t(isAuthenticated ? 'common.formerMember' : 'common.aMember');

  // Whoever runs the thing decides a request from the hero: with
  // one waiting, "Confirm request" (primary) and "Decline request" (secondary) are the
  // first thing under the way back, and Edit / Delete stay in the content where
  // they were. A member's "Reserve" is not here on purpose — they read the whole
  // page before they ask. Two cases, as in the content they came from: a loan or
  // rental with a pending booking (ACTIVE: nothing changes hands for good, so no
  // transfer confirm — `acceptTransfersOwnership` is its inverse), and a taken
  // gift or sale (TAKEN: the transfer confirm opens right under the row).
  // Same handlers, same `disabled`, as ever; and no `fullWidth`: the row makes a
  // phone's buttons the width of the screen and leaves them their own above it.
  const decidesHere =
    canManage &&
    (thing.status === 'TAKEN' || (thing.status === 'ACTIVE' && needsPage && !!activePendingCode));
  const decisionActions = decidesHere ? (
    <>
      {thing.status === 'TAKEN' && acceptTransfersOwnership ? (
        <InlineConfirm
          triggerLabel={acceptLabel}
          triggerProps={{ disabled: !!bookingAction, style: btnStyle }}
          title={t('thingCard.transferConfirmTitle')}
          body={t('thingCard.transferConfirmBody')}
          confirmLabel={t('thingCard.transferConfirm')}
          onConfirm={() => handleBookingAction('accept')}
          confirming={!!bookingAction}
          confirmProps={{ style: btnStyle }}
        />
      ) : (
        <Button
          disabled={!!bookingAction}
          onClick={() => handleBookingAction('accept')}
          style={btnStyle}
        >
          {acceptLabel}
        </Button>
      )}
      <Button
        variant="secondary"
        disabled={!!bookingAction}
        onClick={() => handleBookingAction('reject')}
        style={btnSecondaryStyle}
      >
        {bookingActionVerb === 'reject' ? t('thingCard.cancelling') : t('thingCard.cancelHold')}
      </Button>
    </>
  ) : null;

  // `collection_menu` is there only for a curator or a member of the collection the
  // page is read through, and only on a collection-context URL.
  // The server sends it to nobody else; the page does not take its word for who is signed in.
  const menu = code && isAuthenticated ? thing.collection_menu : null;
  const collectionMenu = menu ? (
    <CollectionMenu
      code={code}
      kind={kind}
      headline={L(thing.collection_headline)}
      isCurator={menu.is_curator}
      isNetwork={thing.collection_mode === 'NETWORK'}
      hasDateThings={menu.has_date_things}
      downloads={downloads}
      welcomeDocUrl={menu.welcome_doc_url || ''}
      digest={
        menu.is_curator || (menu.is_member && menu.digest_frequency !== 'NONE') ? digestPref : null
      }
    />
  ) : undefined;

  return (
    <PageLayout
      backTo={backPath}
      backLabel={backLabel}
      heroActions={decisionActions}
      collectionMenu={collectionMenu}
    >
      {/* The outcome of a download (a curator's) and of the summary switch
          from the corner menu: a live region right under the hero. */}
      {menu && menu.is_curator && <CollectionDownloadsStatus downloads={downloads} />}
      {menu && <CollectionDigestStatus digest={digestPref} />}
      <div className="form-grid">
        {thing.collection_is_onboarding && <DemoNotice />}
        {(() => {
          const images = [thing.thumbnail_url, ...(thing.gallery_urls || [])].filter(Boolean);
          if (images.length === 0) return null;
          if (images.length === 1) {
            return (
              <img
                src={images[0]}
                alt={headline}
                className="detail-image"
                loading="lazy"
                onError={onImageError}
              />
            );
          }
          return <ImageCarousel images={images} alt={headline} />;
        })()}

        <p className="thing-card-meta">
          {formatDate(thing.created)}
          {/* Withheld from a reader with no account when the owner is not the
              person who published the collection (see the card's meta line).
              Only that reader gets the generic stand-in: an empty name for a
              signed-in one means the owner never set one, and they are not
              "a member" in the anonymous sense — they are simply unnamed. */}
          {thing.owner_name
            ? ` — ${thing.owner_name}`
            : !isAuthenticated && ` — ${t('common.aMember')}`}
        </p>

        <h1 className="page-title">{headline}</h1>

        {thing.description && <MarkdownText text={L(thing.description)} />}

        <ThingTags thing={thing} isOwner={canManage} showType={false} />

        <ThingInfoRows
          thing={thing}
          isDateBased={isDateBased}
          // In a network: who lends it, where and when. The card leaves it out: the
          // filter above the grid already says who lends.
          lead={<NetworkPointLine point={thing.network_point} />}
        />

        {/* Owner bookings list */}
        <OwnerBookingsList
          bookings={bookings}
          activePendingCode={activePendingCode}
          isOwner={canManage}
          thingType={thing.type}
        />

        {/* Owner actions. With a request waiting, "Confirm request" and "Decline request"
            are in the hero (see `decisionActions`); Edit and Delete stay here. */}
        {canManage && thing.status === 'ACTIVE' && (
          <div className="button-col">
            <ButtonLink
              to={editPath}
              fullWidth
              style={needsPage && activePendingCode ? btnSecondaryStyle : btnStyle}
            >
              {t('common.edit')}
            </ButtonLink>
            {!hasPendingBookings && canDelete && (
              <Button
                fullWidth
                variant="secondary"
                style={btnSecondaryStyle}
                onClick={() => navigate(deletePath, { state: { backPath, backLabel } })}
              >
                {t('common.delete')}
              </Button>
            )}
          </div>
        )}

        {/* A taken thing's "Confirm request" and "Decline request" are in the hero. */}
        {canManage && thing.status === 'TAKEN' && (
          <div className="button-col">
            <ButtonLink to={editPath} fullWidth style={btnSecondaryStyle}>
              {t('common.edit')}
            </ButtonLink>
          </div>
        )}

        {canManage && thing.status === 'INACTIVE' && (
          <div className="button-row">
            <Button
              style={{ ...btnStyle, width: '100%' }}
              disabled={activating}
              onClick={handleActivate}
            >
              {activating ? t('thingCard.reactivating') : t('thingCard.reactivate')}
            </Button>
            <ButtonLink to={editPath} style={{ ...btnSecondaryStyle, width: '100%' }}>
              {t('common.edit')}
            </ButtonLink>
            {canDelete && (
              <Button
                variant="secondary"
                style={{ ...btnSecondaryStyle, width: '100%' }}
                onClick={() => navigate(deletePath, { state: { backPath, backLabel } })}
              >
                {t('common.delete')}
              </Button>
            )}
          </div>
        )}

        {/* Reservation button for invited users. For an anonymous visitor
            (loginToAct) the click routes to the collection's join page. */}
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
                          backPath: code
                            ? collectionThingPath(code, kind, thing.code)
                            : `/things/${thing.code}`,
                          backLabel: headline,
                        },
                      })
                  : handleRequest
            }
          >
            {buttonLabel}
          </Button>
        )}

        {isCollectionOwner && !canManage && (
          <div className="button-row">
            <Button
              variant="secondary"
              style={{ ...btnSecondaryStyle, width: '100%' }}
              onClick={() => navigate(deletePath, { state: { backPath, backLabel } })}
            >
              {t('common.delete')}
            </Button>
          </div>
        )}

        {/* FAQs Section */}
        <ThingFaqSection
          thingCode={thing.code}
          isOwner={canManage}
          isAuthenticated={isAuthenticated}
          onToast={setToast}
        />

        {/* Journey / Transfer history */}
        {transfers && transfers.total_transfers > 0 && (
          <>
            <div className="spacer-m" />
            <hr />
            <div className="spacer-m" />
            <h2>{t('transfers.heading')}</h2>
            <p>{t('transfers.journeyCount', { count: transfers.unique_homes })}</p>
            {transfers.current_holder_name && (
              <p>
                <strong>
                  {t('transfers.currentlyWith', { name: transfers.current_holder_name })}
                </strong>
              </p>
            )}
            <ul className="thing-card-bookings">
              {transfers.transfers.map((tr) => (
                <li key={tr.code}>
                  {holderLabel(tr.from_user_name)} {t('transfers.to')}{' '}
                  {holderLabel(tr.to_user_name)}
                  {' — '}
                  {t('transfers.lentOn', {
                    date: formatDate(tr.lent_date),
                  })}
                  {/* `auto_closed` means the daily command wrote this date when
                      the booking's end_date passed — nobody said the thing came
                      back. The journey is the product's most human surface, so
                      it says "due back on" rather than claiming a handover we
                      never witnessed. */}
                  {tr.returned_date && (
                    <>
                      {' '}
                      ·{' '}
                      {t(tr.auto_closed ? 'transfers.dueBackOn' : 'transfers.returnedOn', {
                        date: formatDate(tr.returned_date),
                      })}
                    </>
                  )}
                </li>
              ))}
            </ul>
          </>
        )}
        {/* Report footer — logged-in non-owners can flag the listing. */}
        {isAuthenticated && !canManage && (
          <ThingReportFooter thingCode={thing.code} onToast={setToast} />
        )}
      </div>

      <Toast toast={toast} onClose={() => setToast(null)} />
    </PageLayout>
  );
}
