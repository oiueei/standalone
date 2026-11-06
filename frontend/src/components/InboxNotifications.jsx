import { useEffect, useState } from 'react';
import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button, Notification } from 'hds-react';
import { apiFetch } from '../services/api';
import InlineConfirm from './InlineConfirm';
import useTheeeme from '../hooks/useTheeeme';
import { curatorGuidePath } from '../deployment';
import { useLocalized } from '../utils/localized';
import { formatBookingWhen, formatDateTime } from '../utils/rental';
import {
  GROUP_THRESHOLD,
  isInformativeNotice,
  isTeamBookingNotice,
  localToday,
  summarizeOwnerBookings,
} from '../utils/inboxGroups';
import { collectionPath, collectionThingPath } from '../utils/collectionPath';
import { withQuantity } from '../utils/quantity';

// The figures on the summary card come from the owner-bookings list, which the API
// pages (100 at most). A group with more history than this many pages says nothing
// rather than a number that undercounts: the card still links to the full list.
const OWNER_BOOKINGS_PAGE_CAP = 10;

const ALERT_TYPES = new Set([
  'COLLECTION_DELETED',
  'COLLECTION_REVOKED',
  'BOOKING_REJECTED',
  'FAQ_HIDDEN',
  'THING_HIDDEN',
  'INVITE_REJECTED',
  'THING_REPORTED',
  'INVITE_PROPOSAL_DECLINED',
]);
const SUCCESS_TYPES = new Set([
  'BOOKING_ACCEPTED',
  'INVITE_PROPOSAL_APPROVED',
  'PROMOTED_CO_OWNER',
]);

// The notices about a request or reservation say when they were registered
// under their body: reading "confirmed" with no idea of when
// that happened asked the member to trust a dateless sentence. The two
// reservation notices additionally speak the booking's own field names
// (start/end date and time), and a dated request or decision does too; a gift
// or sale (no dates in the payload) shows only the registration line.
// BOOKING_DECIDED does not exist until 2026-09-29's team-notice work; it rides
// along here so the rule is one list.
const RESERVATION_TYPES = new Set(['RESERVATION_MADE', 'RESERVATION_CANCELLED']);
const BOOKING_NOTICE_TYPES = new Set([
  ...RESERVATION_TYPES,
  'BOOKING_REQUESTED',
  'BOOKING_ACCEPTED',
  'BOOKING_REJECTED',
  'BOOKING_DECIDED',
]);

// The quiet meta lines under a notice, sized like a helper rather than body
// copy — they qualify the sentence above, they don't continue it.
const META_LINE_STYLE = {
  margin: 'var(--spacing-2-xs) 0 0',
  fontSize: 'var(--fontsize-body-s)',
};

// The owner said yes to a recommendation. Written as INVITE_PROPOSAL_APPROVED;
// older rows are an
// INVITE_PROPOSED carrying `approved: true`, and both must read the same.
const isProposalApproved = (n) =>
  n.type === 'INVITE_PROPOSAL_APPROVED' || (n.type === 'INVITE_PROPOSED' && n.payload?.approved);

const notificationType = (type) => {
  if (ALERT_TYPES.has(type)) return 'alert';
  if (SUCCESS_TYPES.has(type)) return 'success';
  return 'info';
};

/**
 * The inbox: one dismissible Notification per in-app notification.
 *
 * Rendered bare on Home (everything the user has) and scoped on a collection's own
 * page (`collection` — the owner sees a hold request where the thing actually lives,
 * not only on Home). Strings keep the `home.*` namespace they were born in.
 *
 * Past three notices about requests and reservations — the ones that go to whoever
 * *manages* them (`utils/inboxGroups.js`) — they are replaced by a single card with
 * the real figures (requests waiting for an answer, reservations still to come),
 * read from `GET /api/v1/owner-bookings/` only when there is something to fold, and
 * its X dismisses them all at once. Not a count of notices: "you have 5 pending"
 * would be false with four of them already confirmed.
 *
 * Props: `collection` (optional code to filter by), `reloadKey` (bump to re-fetch —
 * Home does it when connectivity returns), `onNetworkError` (a stable callback; Home
 * turns it into its offline banner).
 */
export default function InboxNotifications({ collection, reloadKey = 0, onNetworkError }) {
  const { t, i18n } = useTranslation();
  const { btnStyle } = useTheeeme();
  // Owner content in a payload (headlines) may carry one text per language.
  const L = useLocalized();
  const [notifications, setNotifications] = useState([]);
  // The summary card's figures: `null` while they load, `false` if they could not
  // be read (the card then says no number rather than an invented one).
  const [figures, setFigures] = useState(null);
  const folded = notifications.filter(isTeamBookingNotice).length > GROUP_THRESHOLD;
  // What only informs folds into one card of its own once there are many; the card
  // can be opened to read them one by one.
  const infoCount = notifications.filter(isInformativeNotice).length;
  const infoFolded = infoCount > GROUP_THRESHOLD;
  const [infoOpen, setInfoOpen] = useState(false);
  // The notices the Show / Hide button opens, by id, for `aria-controls`.
  const infoNoticeIds = notifications
    .filter(isInformativeNotice)
    .map((n) => `inbox-notice-${n.code}`)
    .join(' ');

  useEffect(() => {
    const controller = new AbortController();
    const { signal } = controller;
    const fetchInbox = async () => {
      try {
        const url = collection
          ? `/api/v1/inbox/?collection=${encodeURIComponent(collection)}`
          : '/api/v1/inbox/';
        const res = await apiFetch(url, { signal });
        if (res.ok) {
          const data = await res.json();
          // Only ever render a list. This sits on top of Home and of every
          // collection page, so an unexpected body must degrade to "no
          // notifications", never take the whole page down with it.
          if (!signal.aborted && Array.isArray(data)) setNotifications(data);
        }
      } catch (err) {
        if (!signal.aborted) onNetworkError?.(err);
      }
    };
    fetchInbox();
    return () => controller.abort();
  }, [collection, reloadKey, onNetworkError]);

  // Asked for only when there is something to fold. Follows the API's `next` links
  // (an absolute DRF URL, so the origin is stripped, as `OwnerBookingsPage` does).
  useEffect(() => {
    if (!folded) return undefined;
    const controller = new AbortController();
    const { signal } = controller;
    const loadFigures = async () => {
      try {
        const rows = [];
        let path = '/api/v1/owner-bookings/?page_size=100';
        for (let page = 0; path; page += 1) {
          if (page === OWNER_BOOKINGS_PAGE_CAP) throw new Error('too many pages to count');
          const res = await apiFetch(path, { signal });
          if (!res.ok) throw new Error('owner-bookings failed');
          const data = await res.json();
          rows.push(...(data.results || []));
          path = data.next ? data.next.replace(/^https?:\/\/[^/]+/, '') : null;
        }
        if (!signal.aborted) {
          setFigures(summarizeOwnerBookings(rows, { collection, today: localToday() }));
        }
      } catch {
        if (!signal.aborted) setFigures(false);
      }
    };
    loadFigures();
    return () => {
      controller.abort();
      setFigures(null);
    };
  }, [folded, collection, reloadKey]);

  // The summary card's X: every notice it stands for goes in one call, scoped like
  // the list was.
  const dismissGroup = async () => {
    setNotifications((prev) => prev.filter((n) => !isTeamBookingNotice(n)));
    try {
      const scope = collection ? `&collection=${encodeURIComponent(collection)}` : '';
      await apiFetch(`/api/v1/inbox/?group=bookings${scope}`, { method: 'DELETE' });
    } catch (err) {
      onNetworkError?.(err);
    }
  };

  const dismissInfo = async () => {
    setNotifications((prev) => prev.filter((n) => !isInformativeNotice(n)));
    try {
      const scope = collection ? `&collection=${encodeURIComponent(collection)}` : '';
      await apiFetch(`/api/v1/inbox/?group=info${scope}`, { method: 'DELETE' });
    } catch (err) {
      onNetworkError?.(err);
    }
  };

  const dismiss = async (code) => {
    setNotifications((prev) => prev.filter((n) => n.code !== code));
    try {
      await apiFetch(`/api/v1/inbox/${code}/`, { method: 'DELETE' });
    } catch (err) {
      onNetworkError?.(err);
    }
  };

  // Resolve the three headline keys once, then the builders below interpolate plain
  // words like they always did.
  //
  // The name keys get a stand-in for the same reason `ThingLinkbox` has always
  // used one: the backend sends the bare `name`, never `display_name`, because
  // the fallback in `display_name` is the person's email address and the reader
  // here is a co-member who is not entitled to it. A person who never set a
  // name therefore arrives as `''`, and every one of these strings interpolates
  // the name mid-sentence — so without this the body reads " has replied to your
  // question about:". One funnel, so a builder cannot forget.
  //
  // The stand-in is written with a capital where the name opens its sentence
  // ("A member joined…") and in lower case where it falls in the middle of one
  // ("…cancelled the reservation of a member"): `<key>_inline` is the second form,
  // and each builder takes the one its own sentence needs in every language.
  const named = (value) => value || t('common.aMember');
  const namedInline = (value) => value || t('common.aMemberInline');
  const localizedPayload = (payload) => ({
    ...payload,
    collection_headline: L(payload.collection_headline),
    thing_headline: withQuantity(t, L(payload.thing_headline), payload.quantity),
    owner_name: named(payload.owner_name),
    owner_name_inline: namedInline(payload.owner_name),
    questioner_name: named(payload.questioner_name),
    requester_name: named(payload.requester_name),
    requester_name_inline: namedInline(payload.requester_name),
    invitee_name: named(payload.invitee_name),
    // A member who joined by a public link has given only an address: the team
    // (the only readers of these two notices) reads it in the members list, so it
    // names them in the place of a name.
    member_name: payload.member_name || payload.member_email || t('common.aMember'),
    member_name_inline: payload.member_name || payload.member_email || t('common.aMemberInline'),
    removed_by_name: named(payload.removed_by_name),
    proposer_name: named(payload.proposer_name),
    other_name: named(payload.other_name),
    decider_name: named(payload.decider_name),
  });

  const notificationLabel = (n) => {
    const p = localizedPayload(n.payload);
    switch (n.type) {
      case 'COLLECTION_DELETED':
        return t('home.collectionDeletedLabel');
      case 'COLLECTION_REVOKED':
        return t('home.collectionRevokedLabel');
      case 'BOOKING_ACCEPTED':
        return t('home.bookingAcceptedLabel');
      case 'BOOKING_REJECTED':
        return t('home.bookingRejectedLabel');
      case 'BOOKING_REQUESTED':
        return t('home.bookingRequestedLabel');
      // The team-side record of a decision: same labels the requester's own
      // notice uses, so one vocabulary for one event.
      case 'BOOKING_DECIDED':
        return p.accepted ? t('home.bookingAcceptedLabel') : t('home.bookingRejectedLabel');
      case 'FAQ_QUESTION':
        return t('home.faqQuestionLabel');
      case 'FAQ_ANSWERED':
        return t('home.faqAnsweredLabel');
      case 'FAQ_HIDDEN':
        return t('home.faqHiddenLabel');
      case 'THING_HIDDEN':
        return t('home.thingHiddenLabel');
      case 'INVITE_REJECTED':
        return t('home.inviteRejectedLabel');
      case 'THING_REPORTED':
        return t('home.reportedLabel');
      case 'MEMBER_LEFT':
        // A co-curator's removal of someone carries who did it.
        return t(
          'removed_by_name' in n.payload ? 'home.memberRemovedLabel' : 'home.memberLeftLabel'
        );
      case 'MEMBER_JOINED':
        return t('home.memberJoinedLabel');
      case 'INVITE_PROPOSAL_APPROVED':
        return t('home.proposalApprovedLabel');
      case 'INVITE_PROPOSAL_DECLINED':
        return t('home.proposalDeclinedLabel');
      case 'INVITE_PROPOSED':
        return isProposalApproved(n) ? t('home.proposalApprovedLabel') : t('home.proposedLabel');
      case 'RESERVATION_MADE':
        return t('home.reservationMadeLabel');
      case 'RESERVATION_CANCELLED':
        return t('home.reservationCancelledLabel');
      case 'PROMOTED_CO_OWNER':
        return t('home.promotedLabel');
      case 'DEMOTED_CO_OWNER':
        return t('home.demotedLabel');
      default:
        return t('home.broadcastLabel', {
          owner_name: p.owner_name,
          collection_headline: p.collection_headline,
        });
    }
  };

  const notificationBody = (n) => {
    const p = localizedPayload(n.payload);
    switch (n.type) {
      case 'COLLECTION_DELETED':
        return t('home.collectionDeletedBody', {
          collection_headline: p.collection_headline,
          owner_name: p.owner_name_inline,
        });
      case 'COLLECTION_REVOKED':
        // The name opens the sentence in Spanish and Catalan and follows "by" in English.
        return t('home.collectionRevokedBody', {
          collection_headline: p.collection_headline,
          owner_name: p.owner_name,
          owner_name_inline: p.owner_name_inline,
        });
      case 'BOOKING_ACCEPTED':
        return t('home.bookingAcceptedBody', {
          thing_headline: p.thing_headline,
          owner_name: p.owner_name,
        });
      case 'BOOKING_REJECTED':
        return t('home.bookingRejectedBody', {
          thing_headline: p.thing_headline,
          owner_name: p.owner_name,
        });
      case 'BOOKING_REQUESTED':
        return t('home.bookingRequestedBody', {
          thing_headline: p.thing_headline,
          requester_name: p.requester_name,
        });
      case 'FAQ_QUESTION':
        return t('home.faqQuestionBody', {
          thing_headline: p.thing_headline,
          questioner_name: p.questioner_name,
        });
      case 'FAQ_ANSWERED':
        return t('home.faqAnsweredBody', {
          thing_headline: p.thing_headline,
          owner_name: p.owner_name,
        });
      case 'THING_HIDDEN':
        return t('home.thingHiddenBody', {
          thing_headline: p.thing_headline,
          founder_name: named(p.founder_name),
        });
      case 'FAQ_HIDDEN':
        return t('home.faqHiddenBody', {
          thing_headline: p.thing_headline,
          owner_name: p.owner_name,
        });
      case 'INVITE_REJECTED':
        return t('home.inviteRejectedBody', {
          collection_headline: p.collection_headline,
          invitee_name: p.invitee_name,
        });
      case 'THING_REPORTED':
        return t('home.reportedBody', { thing_headline: p.thing_headline });
      case 'MEMBER_JOINED':
        return t('home.memberJoinedBody', {
          collection_headline: p.collection_headline,
          member_name: p.member_name,
        });
      case 'MEMBER_LEFT': {
        // A co-curator's removal of someone is told to the founder with who did
        // it; a member's own leaving carries no `removed_by_name`.
        const left =
          'removed_by_name' in n.payload
            ? t('home.memberRemovedBody', {
                removed_by: p.removed_by_name,
                collection_headline: p.collection_headline,
                member_name: p.member_name_inline,
              })
            : t('home.memberLeftBody', {
                collection_headline: p.collection_headline,
                member_name: p.member_name,
              });
        // A notice written before the count existed has no `things_deleted`: 0.
        const things = p.things_deleted || 0;
        return things > 0 ? `${left} ${t('home.memberLeftThings', { count: things })}` : left;
      }
      case 'INVITE_PROPOSAL_APPROVED':
        return t('home.proposalApprovedBody', {
          collection_headline: p.collection_headline,
          email: p.email,
        });
      case 'INVITE_PROPOSAL_DECLINED':
        return t('home.proposalDeclinedBody', {
          collection_headline: p.collection_headline,
          email: p.email,
        });
      case 'INVITE_PROPOSED':
        return isProposalApproved(n)
          ? t('home.proposalApprovedBody', {
              collection_headline: p.collection_headline,
              email: p.email,
            })
          : t('home.proposedBody', {
              collection_headline: p.collection_headline,
              proposer_name: p.proposer_name,
              email: p.email,
            });
      case 'BOOKING_DECIDED':
        // Whoever reads it either made the call or hears about a teammate's.
        if (p.by_you)
          return t(
            p.accepted
              ? 'home.bookingDecidedAcceptedByYouBody'
              : 'home.bookingDecidedRejectedByYouBody',
            { requester_name: p.requester_name_inline, thing_headline: p.thing_headline }
          );
        return t(
          p.accepted ? 'home.bookingDecidedAcceptedBody' : 'home.bookingDecidedRejectedBody',
          {
            decider_name: p.decider_name,
            requester_name: p.requester_name_inline,
            thing_headline: p.thing_headline,
          }
        );
      case 'RESERVATION_MADE':
        return t('home.reservationMadeBody', {
          requester_name: p.requester_name,
          thing_headline: p.thing_headline,
        });
      case 'RESERVATION_CANCELLED':
        // Whoever cancelled reads their own record in the first person — and
        // learns whose reservation it was when it wasn't theirs. The wording is
        // picked by whether the payload carries `member_name` at all, not by its
        // value: `localizedPayload` fills a missing name with "a member", so `p`
        // can never say (the backend sends '' for an unnamed owner).
        if (p.by_you)
          return t(
            'member_name' in (n.payload || {})
              ? 'home.reservationCancelledByYouOtherBody'
              : 'home.reservationCancelledByYouOwnBody',
            { member_name: p.member_name_inline, thing_headline: p.thing_headline }
          );
        return t('home.reservationCancelledBody', {
          other_name: p.other_name,
          thing_headline: p.thing_headline,
        });
      case 'PROMOTED_CO_OWNER':
        // In a network a dinamizador runs their own things only: the body says so.
        return t(p.network ? 'home.promotedNetworkBody' : 'home.promotedBody', {
          collection_headline: p.collection_headline,
        });
      case 'DEMOTED_CO_OWNER':
        // In a network the things the dinamizador ran went with the role: say so.
        return n.payload.things_deleted > 0
          ? t('home.demotedNetworkBody', {
              count: n.payload.things_deleted,
              collection_headline: p.collection_headline,
            })
          : t('home.demotedBody', { collection_headline: p.collection_headline });
      default:
        return t('home.broadcastBody', { message: p.message });
    }
  };

  // Deep link to the object that originated a notification: the collection for a
  // broadcast, otherwise the thing it is about — a hold request is answered on the
  // thing, so the owner should land there in one click. Returns {to, label} or null.
  const notificationLink = (n) => {
    const p = n.payload || {};
    // A pending recommendation is a question, and the guest list is where the
    // owner answers it — landing them on the collection would leave them hunting
    // for the button. The two resolved states just point at the group.
    if (n.type === 'INVITE_PROPOSED' && !isProposalApproved(n) && p.collection_code) {
      return {
        to: collectionPath(p.collection_code, p.collection_kind, '/invites'),
        label: t('home.viewProposal'),
      };
    }
    // Someone joined or left: the roster is what the team opens next, and only
    // the team gets these notices.
    if ((n.type === 'MEMBER_JOINED' || n.type === 'MEMBER_LEFT') && p.collection_code) {
      return {
        to: collectionPath(p.collection_code, p.collection_kind, '/invites'),
        label: t('home.viewMembers'),
      };
    }
    // A broadcast says whatever its curator wrote, so its link only says where
    // it goes. It was labelled "I can help!" — the call-for-help CTA of the
    // retired WISH_THING flow — under every group message, whatever it said.
    if (
      (n.type === 'BROADCAST' ||
        n.type === 'INVITE_PROPOSAL_APPROVED' ||
        n.type === 'INVITE_PROPOSAL_DECLINED' ||
        n.type === 'INVITE_PROPOSED' ||
        n.type === 'PROMOTED_CO_OWNER' ||
        n.type === 'DEMOTED_CO_OWNER') &&
      p.collection_code
    ) {
      return {
        to: collectionPath(p.collection_code, p.collection_kind),
        label: t('home.viewGroup'),
      };
    }
    if (p.thing_code) {
      const to = p.collection_code
        ? collectionThingPath(p.collection_code, p.collection_kind, p.thing_code)
        : `/things/${p.thing_code}`;
      return { to, label: t('home.viewThing') };
    }
    return null;
  };

  if (notifications.length === 0) return null;

  // The words on the summary card: the figures that are not zero, joined with the
  // language's own conjunction; both at zero says so; unread says nothing at all.
  const summaryBody = (() => {
    if (!figures) return '';
    const parts = [];
    if (figures.pending > 0) parts.push(t('inbox.summary.pending', { count: figures.pending }));
    if (figures.upcoming > 0) parts.push(t('inbox.summary.upcoming', { count: figures.upcoming }));
    if (parts.length === 0) return t('inbox.summary.nothing');
    const items = new Intl.ListFormat(i18n.language, { type: 'conjunction' }).format(parts);
    return t('inbox.summary.body', { items });
  })();

  return (
    <>
      {folded && (
        <Notification
          type="info"
          label={t('inbox.summary.label')}
          dismissible
          closeButtonLabelText={t('home.dismiss')}
          onClose={dismissGroup}
          style={{ marginBottom: 'var(--spacing-s)' }}
        >
          {summaryBody}
          {summaryBody && ' '}
          <Link to="/owner-bookings">{t('inbox.summary.link')}</Link>
        </Notification>
      )}
      {infoFolded && (
        <Notification
          type="info"
          label={t('inbox.info.summary', { count: infoCount })}
          notificationAriaLabel={t('inbox.info.summary', { count: infoCount })}
          style={{ marginBottom: 'var(--spacing-s)' }}
        >
          <Button
            variant="supplementary"
            size="small"
            aria-expanded={infoOpen}
            aria-controls={infoOpen ? infoNoticeIds : undefined}
            onClick={() => setInfoOpen((open) => !open)}
          >
            {infoOpen ? t('inbox.info.hide') : t('inbox.info.show')}
          </Button>{' '}
          <InlineConfirm
            triggerLabel={t('inbox.info.dismissAll')}
            triggerProps={{ variant: 'supplementary', size: 'small' }}
            title={t('inbox.info.dismissConfirmTitle', { count: infoCount })}
            body={t('inbox.info.dismissConfirmBody')}
            confirmLabel={t('inbox.info.dismissAll')}
            onConfirm={dismissInfo}
            confirmProps={{ size: 'small', style: btnStyle }}
          />
        </Notification>
      )}
      {notifications
        .filter((n) => !folded || !isTeamBookingNotice(n))
        .filter((n) => !infoFolded || infoOpen || !isInformativeNotice(n))
        .map((n, position) => {
          // Inside a collection, a link back to that same page leads nowhere.
          const found = notificationLink(n);
          const link =
            found &&
            collection &&
            found.to === collectionPath(collection, n.payload?.collection_kind)
              ? null
              : found;
          // Every request- and reservation-notice says when, under its body:
          // when the event the notice records happened (`created` — for a
          // cancellation that is the cancellation's own stamp, which is the fact
          // being reported) and, when the payload carries dates, when the
          // booking runs — read by the same formatter the booking tables use, so
          // the two never disagree about what '29/09/2026, 10:00–12:00' means. A
          // loan or rental reads pickup — return. Either line with nothing to
          // say (an unparseable stamp, a payload without dates) stays out.
          const registeredAt = BOOKING_NOTICE_TYPES.has(n.type) ? formatDateTime(n.created) : '';
          const scheduledFor = n.payload?.start_date
            ? RESERVATION_TYPES.has(n.type)
              ? formatBookingWhen(n.payload, 'RESERVE_THING')
              : formatBookingWhen(n.payload)
            : '';
          return (
            <Notification
              key={n.code}
              id={`inbox-notice-${n.code}`}
              type={notificationType(n.type)}
              label={notificationLabel(n)}
              // Each notice is a landmark; the number keeps two of one kind apart.
              notificationAriaLabel={`${notificationLabel(n)} ${position + 1}`}
              dismissible
              closeButtonLabelText={t('home.dismiss')}
              onClose={() => dismiss(n.code)}
              style={{ marginBottom: 'var(--spacing-s)' }}
            >
              {notificationBody(n)}
              {link && (
                <>
                  {' '}
                  <Link to={link.to}>{link.label}</Link>
                </>
              )}
              {/* Someone just made co-curator is shown where the deployment explains
                  what running a group means, when it has such a page. */}
              {n.type === 'PROMOTED_CO_OWNER' && curatorGuidePath && (
                <>
                  {' '}
                  <Link to={curatorGuidePath}>{t('curatorGuide.link')}</Link>
                </>
              )}
              {registeredAt && (
                <p style={META_LINE_STYLE}>
                  {t('home.reservationRegisteredAt', { when: registeredAt })}
                </p>
              )}
              {scheduledFor && (
                <p style={META_LINE_STYLE}>
                  {/* A reservation is "reserved for"; a loan or a rental is a request
                      for dates until it is settled, and "reserved" is not the word for
                      it. */}
                  {RESERVATION_TYPES.has(n.type)
                    ? t('home.reservationScheduledFor', { when: scheduledFor })
                    : t('home.requestedDates', { when: scheduledFor })}
                </p>
              )}
            </Notification>
          );
        })}
      <div className="spacer-m" />
    </>
  );
}
