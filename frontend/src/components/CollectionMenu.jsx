import { useRef, useState } from 'react';
import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { IconDocumentGroup, Notification } from 'hds-react';
import useDismissable from '../hooks/useDismissable';
import useReceivesRequests from '../hooks/useReceivesRequests';
import { curatorGuidePath } from '../deployment';
import StatusRegion from './StatusRegion';
import { useCollectionBase } from '../hooks/useCollectionBase';
import { collectionPath } from '../utils/collectionPath';

const PANEL_ID = 'collection-menu-panel';

/**
 * The collection's own options, one click from its page:
 * "Add thing" and "Manage members" used to crowd the hero beside "Edit
 * collection", and the two data downloads lived at the foot of the settings
 * page — so a curator ran the group from three places at once. The hero row
 * holds "Add thing" and "Edit collection" ("Add thing" stays here too);
 * everything else is this menu, the second of the corner's icons (`AccountMenu` ·
 * this · `ShareCollectionMenu`; there used to be a fourth, a contact icon), shown
 * to curators only (owner or co-owner,
 * `is_curator` — the server's own word, the same gate the row uses). Its icon is
 * `IconDocumentGroup`: the menu holds the group's things and
 * files, which a bare ⋯ (what it was drawn as at first) did not say.
 *
 * Its entries, in order: "Add thing", "Add several at once (CSV)", "Manage
 * members", "Invite many at once (CSV)" (the CSV of invitations has a page of its own, not
 * a block of the members page), a divider, then the downloads. "Add thing" is also
 * a button in the hero row (deliberately repeated here).
 *
 * The panel mixes links with the three download buttons, so it is a plain
 * `<div>` — not the account menu's `<nav>` (this is not all navigation)
 * and not `role="menu"` (that role expects arrow keys between actions;
 * these are ordinary Tab-reachable controls — the same reasoning as
 * `AccountMenu`, which spells it out). No `aria-label` either: an
 * unnamed `<div>` is fine, and axe flags the label on a div with no role.
 *
 * The downloads themselves belong to `useCollectionDownloads`, which the
 * page calls once and hands here and to `CollectionDownloadsStatus`; the
 * calendar entry appears only where the group holds date-based things
 * (`hasDateThings`: always in a library or a shed, in a stall only when it holds a loan, a rental or a reservation). The JSON
 * download is **direct, no warning**: the privacy notice
 * it used to carry at the settings page's foot went with it — whoever
 * runs a group should already know what its copy holds, and the place to
 * say so is a curator rights-and-obligations page that does not exist yet.
 *
 * **A member has one too**, in the same place of the corner
 * and with the same trigger, panel and dismissal — `isCurator={false}`. What a
 * member holds is theirs, not the group's: the welcome document (when there is
 * one: a link that opens in a new tab and says so, as "Ideas and bugs" does),
 * "Mute the summaries" / "Get the summaries again" (only when the group sends one,
 * `digest`: a button that makes the POST and leaves its outcome in a status zone,
 * like the downloads), and, under a divider, "Leave the group". The welcome
 * document is the first entry of a curator's menu too: it no longer sits as a
 * loose link in the hero.
 *
 * **"Requests to me" is the first entry of both**, for whoever can
 * receive requests, with a divider under it: it moved here from the account menu on
 * the pages that have this one. The same menu is the corner of a thing's page when it
 * is read through a collection.
 *
 * Props: `code`; `kind` (the collection's kind, which makes its address); `headline` (the resolved name, handed to the leave page, which has
 * nothing else to name the group with); `isCurator` (default true, the menu it
 * always was); `hasDateThings` and `downloads` (a curator's); `welcomeDocUrl`
 * (the API serves it to curators and members only, so its presence is the whole
 * condition); `digest` (a member's: `useDigestPreference`'s answer, passed only
 * when the group sends a summary).
 */
export default function CollectionMenu({
  code,
  kind,
  headline,
  isCurator = true,
  hasDateThings = false,
  downloads,
  welcomeDocUrl = '',
  digest = null,
}) {
  const { t } = useTranslation();
  // The group's own address: by its kind when the page knows it, else the prefix
  // the page itself was reached under.
  const routeBase = useCollectionBase(code);
  const base = kind ? collectionPath(code, kind) : routeBase;
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef(null);
  const buttonRef = useRef(null);
  useDismissable({ open, setOpen, wrapperRef, buttonRef });
  // "Requests to me" is the first entry, for whoever receives requests, on the
  // collection's page and on a thing's: moved from the account
  // menu, with the same question asked the same way when this panel opens.
  const receivesRequests = useReceivesRequests(open);
  const { calendar, stats, collectionExport } = downloads ?? {};

  const label = t('collectionMenu.label');
  // Following any entry closes the panel, as in the account menu. A
  // download also returns focus to the trigger: the pressed button
  // disappears with the panel, and the focus would fall to <body> while
  // the file it asked for is still being fetched.
  const close = () => setOpen(false);
  const runAndClose = (download) => () => {
    setOpen(false);
    buttonRef.current?.focus();
    download();
  };
  const welcomeDocLabel = t('collectionPage.welcomeDoc');
  const digestButton = digest && (
    <button type="button" disabled={digest.busy} onClick={runAndClose(digest.toggle)}>
      {digest.muted ? t('collectionMenu.unmuteDigest') : t('collectionMenu.muteDigest')}
    </button>
  );

  return (
    <span className="collection-menu" ref={wrapperRef}>
      <button
        type="button"
        ref={buttonRef}
        className="collection-menu-trigger"
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? PANEL_ID : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        <IconDocumentGroup aria-hidden="true" />
      </button>
      {open && (
        <div id={PANEL_ID} className="collection-menu-panel">
          {receivesRequests && (
            <>
              <Link to="/owner-bookings" onClick={close}>
                {t('home.requestsToMe')}
              </Link>
              <hr className="collection-menu-divider" />
            </>
          )}
          {/* The group's welcome PDF, first for everyone who is served it. It was a
              loose link in the hero. A new tab, said out loud
              the way "Ideas and bugs" says it: the visible words first, then the
              sentence — not HDS's `openInNewTab`, which prints its label. */}
          {welcomeDocUrl && (
            <a
              href={welcomeDocUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`${welcomeDocLabel}. ${t('common.opensInNewTab')}`}
              onClick={close}
            >
              {welcomeDocLabel}
            </a>
          )}
          {isCurator ? (
            <>
              <Link to={`${base}/add`} onClick={close}>
                {t('collectionPage.addThing')}
              </Link>
              {/* The CSV import used to be a line under an empty group's phrase, then a
                  section of the add page; it is a page of its own now
                  and this entry — curators only — is the way to it. */}
              <Link to={`${base}/import`} onClick={close}>
                {t('collectionPage.addManyCsv')}
              </Link>
              <Link to={`${base}/invites`} onClick={close}>
                {t('collectionPage.manageGuests')}
              </Link>
              {/* Every curator has a page of their own in the group: the entity they answer for. */}
              <Link to={`${base}/organisation`} onClick={close}>
                {t('organisation.menuEntry')}
              </Link>
              {/* The CSV of invitations, like the CSV of things above: it was the last
                  block of the members page, and it is a page of its own.
                  Curators only, as the invitations are. */}
              <Link to={`${base}/invites/import`} onClick={close}>
                {t('bulkInvite.heading')}
              </Link>
              <hr className="collection-menu-divider" />
              {hasDateThings && (
                <button
                  type="button"
                  disabled={calendar.downloading}
                  onClick={runAndClose(calendar.download)}
                >
                  {t('calendarExport.downloadButton')}
                </button>
              )}
              <button
                type="button"
                disabled={stats.downloading}
                onClick={runAndClose(stats.download)}
              >
                {t('stats.downloadStats')}
              </button>
              <button
                type="button"
                disabled={collectionExport.downloading}
                onClick={runAndClose(collectionExport.download)}
              >
                {t('collectionExport.downloadButton')}
              </button>
              {/* The deployment's guide for whoever runs a group, where it has one. */}
              {curatorGuidePath && (
                <Link to={curatorGuidePath} onClick={close}>
                  {t('curatorGuide.link')}
                </Link>
              )}
              {/* The summary goes to the whole team, the founder included, so whoever
                  runs the group has the switch too. */}
              {digest && (
                <>
                  <hr className="collection-menu-divider" />
                  {digestButton}
                </>
              )}
            </>
          ) : (
            <>
              {digest && digestButton}
              {(welcomeDocUrl || digest) && <hr className="collection-menu-divider" />}
              {/* The same link as "My groups" on the own profile, with the same state:
                  the confirmation page has nothing else to name the group with. */}
              <Link to={`${base}/leave`} state={{ headline }} onClick={close}>
                {t('collectionPage.leaveGroup')}
              </Link>
            </>
          )}
        </div>
      )}
    </span>
  );
}

/**
 * The outcome zone for the menu's three downloads, under the hero's
 * "Edit collection" row (where the calendar's used to sit). One message at
 * a time: it renders the state of the download that last started —
 * "Preparing the file…" while it runs, then that download's own result
 * (the calendar's counts; a failure's reason; a stats download that
 * succeeds says nothing, as it always didn't). The `StatusRegion` renders
 * unconditionally so it pre-dates its own content, which is what makes a
 * screen reader announce it.
 */
export function CollectionDownloadsStatus({ downloads }) {
  const { t } = useTranslation();
  const { active, calendar, stats, collectionExport } = downloads;
  const downloading =
    (active === 'calendar' && calendar.downloading) ||
    (active === 'stats' && stats.downloading) ||
    (active === 'collectionExport' && collectionExport.downloading);
  const error =
    !downloading && active === 'calendar'
      ? calendar.error
      : !downloading && active === 'stats' && stats.error
        ? t('stats.downloadStatsError')
        : !downloading && active === 'collectionExport'
          ? collectionExport.error
          : null;
  const info = !downloading && active === 'calendar' ? calendar.info : null;

  return (
    <StatusRegion>
      {downloading && (
        <Notification type="info" size="small" style={{ marginTop: 'var(--spacing-xs)' }}>
          {t('collectionExport.downloading')}
        </Notification>
      )}
      {error && (
        <Notification type="error" size="small" style={{ marginTop: 'var(--spacing-xs)' }}>
          {error}
        </Notification>
      )}
      {info && (
        <Notification type="success" size="small" style={{ marginTop: 'var(--spacing-xs)' }}>
          {info}
        </Notification>
      )}
    </StatusRegion>
  );
}

/**
 * The outcome zone for "Mute the summaries" / "Get the summaries again", a member's
 * or whoever runs the group's: one short message, success or failure, under the
 * hero's row of buttons (the member's, or the team's beside the downloads' zone). Always rendered, so the live region pre-dates
 * its content and a screen reader announces it. `digest` is `useDigestPreference`'s
 * answer; the message is an i18n key translated here.
 */
export function CollectionDigestStatus({ digest }) {
  const { t } = useTranslation();
  const result = digest?.result;
  return (
    <StatusRegion>
      {result && (
        <Notification type={result.type} size="small" style={{ marginTop: 'var(--spacing-xs)' }}>
          {t(result.key)}
        </Notification>
      )}
    </StatusRegion>
  );
}
