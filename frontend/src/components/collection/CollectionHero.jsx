import { useRef, useState } from 'react';
import { Link } from 'react-router';
import { useTranslation } from 'react-i18next';
import { Button, Koros, Tag } from 'hds-react';
import { apiFetch } from '../../services/api';
import AccountMenu from '../AccountMenu';
import BackLink from '../BackLink';
import ButtonLink from '../ButtonLink';
import CollectionSettingsMenu from '../CollectionSettingsMenu';
import CollectionMenu, {
  CollectionDigestStatus,
  CollectionDownloadsStatus,
} from '../CollectionMenu';
import MarkdownText, { sanitizeUrl } from '../MarkdownText';
import RecommendGuest from '../RecommendGuest';
import ShareCollectionMenu from '../ShareCollectionMenu';
import useTheeeme from '../../hooks/useTheeeme';
import { useCollectionBase } from '../../hooks/useCollectionBase';
import { useLocalized } from '../../utils/localized';
import { teamParts, teamMemberName } from '../../utils/team';
import { collectionPath } from '../../utils/collectionPath';
import { DATE_TYPES } from '../../constants/things';

// What the member's "Invite someone" button controls (aria-controls) and the
// form it opens sits under.
const RECOMMEND_BOX_ID = 'recommend-box';

/**
 * The collection's hero: its corner of menus, title, text, who runs it, and the
 * buttons each kind of reader is given (a curator's, a member's, a visitor's).
 *
 * It reads the reader off the collection and the session, so the page hands it the
 * collection and little else. `setCollection` is for the one thing the hero does to
 * it, joining a public group from the signed-in visitor's button; `downloads` and
 * `digestPref` are the page's hooks, which the menu and the status zones share.
 */
export default function CollectionHero({
  collection,
  setCollection,
  code,
  headline,
  downloads,
  digestPref,
}) {
  const { t, i18n } = useTranslation();
  const { tc, koro, btnStyle, btnSecondaryStyle } = useTheeeme();
  const L = useLocalized();
  const base = useCollectionBase(code, collection.kind);
  const [joining, setJoining] = useState(false);
  const [joinError, setJoinError] = useState(false);
  const [recommendOpen, setRecommendOpen] = useState(false);
  const recommendButtonRef = useRef(null);

  // Join a PUBLIC group you are only browsing. The signed-in half of
  // login-to-act: an anonymous reader gets `/collections/:code/join`, which
  // takes an email and mails a magic link — no use at all to a session that
  // already exists, so the reader with the most intent had no way in. Re-fetches
  // rather than patching `is_member` locally: joining changes several fields at
  // once (the member roster, the digest switch, what the cards may offer), and
  // the server is the only thing that knows all of them.
  const handleJoin = async () => {
    setJoining(true);
    setJoinError(false);
    try {
      const res = await apiFetch(`/api/v1/collections/${code}/join/`, { method: 'POST' });
      if (res.ok) {
        const fresh = await apiFetch(`/api/v1/collections/${code}/`);
        if (fresh.ok) setCollection(await fresh.json());
        else setJoinError(true);
      } else {
        setJoinError(true);
      }
    } catch {
      setJoinError(true);
    }
    setJoining(false);
  };

  const userCode = localStorage.getItem('userCode');
  // The strict founder check — still what the attribution line and the
  // INACTIVE/delete-adjacent controls key on. Everything else that used to
  // read `isOwner` for an admin power now reads `isCurator` instead, the
  // server-computed field that also admits a co-owner.
  const isOwner = userCode === collection.owner;
  const isCurator = !!collection.is_curator;
  // The team the hero names, alphabetically by the name each is shown under (the
  // founder as one more), whoever has no name counted at the end rather than listed, written as the language on screen writes a list
  // ("A y B", "A, B y C") — one rule (`utils/team.js`) shared with the "Run by"
  // column of "My groups", so the two cannot disagree. The pieces come apart so
  // each name can be a link.
  const teamLine = teamParts(collection, t, i18n.resolvedLanguage || i18n.language);
  const isAuthenticated = !!userCode;
  // The Community/visibility tags in the H1 are purely informational — no
  // click, no delete, so no hover/focus state to design for — so they follow
  // the theeeme's primary-button colours (color_01/color_06) instead of a
  // fixed HDS token pair, matching every other themed surface on the page.
  // They are also the curators' own bookkeeping — how the group is set up, not
  // something a member or a passer-by needs before the title —
  // so both render for `isCurator` only.
  const tagTheme = tc.color_01
    ? {
        '--tag-background': `var(--color-${tc.color_01})`,
        '--tag-color': `var(--color-${tc.color_06})`,
      }
    : undefined;
  // Who may hand the group's link to someone: a curator, and — in a PUBLIC group
  // — any member. A PUBLIC group is shared by its own address,
  // with no token to mint, rotate or revoke, so a member can pass it on without
  // holding anything a curator would need to pull back; it is the cheapest way to
  // bring new people in, and nothing had ever asked a member to. In a PRIVATE one
  // the link is the curators' credential, and the member has "Recommend" instead.
  const canShare = isCurator || (collection.visibility === 'PUBLIC' && !!collection.is_member);
  // A rank-and-file member: signed in, `is_member` (false for a co-owner by design,
  // who is a curator and has the curator's menu). They get a menu of their own in
  // the corner — the welcome document, the summary switch when
  // the group sends one, and "Leave the group".
  // The settings are what "Edit collection" is: in a network only the founder's.
  const showsSettings = isCurator && (collection.mode !== 'NETWORK' || isOwner);
  const isMember = isAuthenticated && !!collection.is_member && !isCurator;
  // Each name of the team opens the page that person has in the group, for everyone
  // who can read the group.
  const entityPath = (userCode) =>
    collectionPath(code, collection.kind, `/organisation/${userCode}`);
  const founderName = teamMemberName(collection, {
    code: collection.owner,
    name: collection.owner_name,
  });
  const isDemo = !!collection.is_onboarding;
  const showInvite = !!collection.allow_member_proposals && !isDemo;
  // A member has a summary only where the group sends the weekly or monthly one; whoever
  // runs the group also gets the daily one about sign-ups, whatever the frequency.
  const sendsDigest = !!collection.digest_frequency && collection.digest_frequency !== 'NONE';
  // A signed-out reader of a PUBLIC group is offered one door in the hero, "Sign in",
  // which leads to the group's join page — whatever the mode and whether it holds
  // things or not. The join page serves whoever types an address alike (a new
  // account is made, an existing one is used, a member is let back in), so a second
  // door to /login would lead to the same place. It used to be a line in the content
  // that only a COMMUNITY or an empty group showed, and a member without a session
  // (the weekly digest's link is an ordinary one) had no way in from here at all.
  const showsSignedOutDoors = !isAuthenticated && collection.visibility === 'PUBLIC';
  // Whether the calendar download has anything to offer: only date-based
  // things (loans, rentals, on-site reservations) ever reach it. A library and
  // a shed hold nothing else; a stall gives or sells, but one that the kind
  // migration took from a collection that also lent keeps those loans, and
  // they do export — so a stall answers by its things. The server's rule for
  // a thing's own page (`_collection_has_date_things`) is this one.
  const hasDateThings =
    collection.kind === 'LIBRARY' ||
    collection.kind === 'SHED' ||
    collection.things.some((thg) => DATE_TYPES.includes(thg.type));

  // When the owner has given the group its own web address, the hero's back
  // link goes there instead of the OIUEEI home — but it still says "Home".
  // `sanitizeUrl` returns "#" for anything that isn't
  // http(s), and we ignore that.
  const homePageUrl = collection.home_page ? sanitizeUrl(collection.home_page) : '';
  const backHref = homePageUrl && homePageUrl !== '#' ? homePageUrl : null;

  return (
    <div
      className="form-hero form-hero--collection"
      style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
    >
      <div className="form-hero-split">
        <div
          className="form-hero-content form-hero-content--settings"
          style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}
        >
          <span className="hero-corners">
            {/* "Requests to me" is the collection menu's first entry where this page
                  has one: the account menu then leaves it out. */}
            {/* Signed out, in a PUBLIC group the hero's "Sign in" is the only
                  door, so the corner's icon is left out rather than offering a
                  second one; with a session `offerSignIn` changes nothing, and on
                  every other page a signed-out reader keeps the icon. */}
            <AccountMenu
              requestsInCollectionMenu={isCurator || isMember}
              offerSignIn={!showsSignedOutDoors}
            />
            {/* The settings pages (appearance…), curators only, between the
                  account menu and the collection's own options. */}
            {showsSettings && <CollectionSettingsMenu code={code} kind={collection.kind} />}
            {/* The group's own options, between the account menu
                  and the share one: a curator's, and a
                  member's, with what is theirs. Nothing for a reader who is
                  neither. */}
            {(isCurator || isMember) && (
              <CollectionMenu
                code={code}
                kind={collection.kind}
                headline={headline}
                isCurator={isCurator}
                hasDateThings={hasDateThings}
                downloads={downloads}
                welcomeDocUrl={collection.welcome_doc_url || ''}
                digest={isCurator || (isMember && sendsDigest) ? digestPref : null}
              />
            )}
            {canShare && (
              <ShareCollectionMenu
                collectionCode={code}
                collectionKind={collection.kind}
                collectionHeadline={headline}
                isPublic={collection.visibility === 'PUBLIC'}
              />
            )}
          </span>
          {/* Says "← Home" whatever it points at: the group's own
                `home_page` when it has one, the app's home otherwise. It used to be
                worded "The group's site" with an external-link icon; the wording
                and the icon went, the destination stayed. */}
          <BackLink to="/" href={backHref} label={t('common.home')} />
          {/* The collection's image is its logo, not a backdrop: an ordinary image
              in the column of one card, as tall as its own proportion makes it
              (App.css puts it above the title under 992px and in the last column
              from there). The <h1> already names the collection. */}
          {collection.thumbnail_url && (
            <img className="hero-logo" src={collection.thumbnail_url} alt="" />
          )}
          <h1 className="form-hero-title">
            {headline}
            {isCurator && collection.mode === 'COMMUNITY' && (
              <>
                {' '}
                <Tag theme={tagTheme}>{t('collectionPage.communityTag')}</Tag>
              </>
            )}
            {isCurator && (
              <>
                {' '}
                <Tag theme={tagTheme}>
                  {collection.visibility === 'PUBLIC'
                    ? t('visibility.publicTag')
                    : t('visibility.privateTag')}
                </Tag>
              </>
            )}
          </h1>
          {collection.description && (
            <MarkdownText text={L(collection.description)} className="form-hero-text" />
          )}
          {/* What a network is, for whoever lands on one: it shows rather than claims
              (DESIGN §6) — who lends, and from where, is on each card. */}
          {collection.mode === 'NETWORK' && (
            <p className="form-hero-text">{t('collectionPage.networkNote')}</p>
          )}
          {/* Attribution. With co-curators, one line names the whole team,
                alphabetical by the name each is shown under (the founder as one
                more), everyone at the same level and shown to everyone
                (2026-09); whoever has no name is counted at the end, not
                linked, and with nobody named there is no line. Without, the
                single founder line, and only to non-owners — the owner knows
                who they are. */}
          {collection.co_owners?.length > 0
            ? teamLine.length > 0 && (
                <p className="form-hero-text">
                  <strong>{t('collectionPage.curatorsLabel')}</strong>{' '}
                  {teamLine.map((part, i) => {
                    if (part.type === 'member') {
                      return (
                        <Link key={i} to={entityPath(part.member.code)} className="owner-link">
                          {part.member.name}
                        </Link>
                      );
                    }
                    // The count of those without a name is plain text, and so is
                    // what the language puts between the pieces ("," and "y").
                    return part.type === 'more' ? part.text : part.value;
                  })}
                </p>
              )
            : !isOwner &&
              founderName && (
                <p className="form-hero-text">
                  <strong>{t('collectionPage.curator')}</strong>{' '}
                  <Link to={entityPath(collection.owner)} className="owner-link">
                    {founderName}
                  </Link>
                </p>
              )}
          {/* The group's welcome PDF is an entry of the collection menu,
                first, for members and curators — the API serves its
                URL to those two only. It was a loose link here. */}
          {/* The hero's one door for a signed-out reader: "Sign in", primary, to the
              group's join page (no ?thing=: there is no thing in it). That page
              takes any address — a new one makes the account, one that exists is
              used, a member is let back in — so it is the way in for a visitor, a
              person with an account and a member whose session expired (the weekly
              digest's link is an ordinary one) alike. In every PUBLIC group,
              COMMUNITY or PROPRIETARY, empty or not; the action button on each
              card (login-to-act) is still there for whoever has one. The account
              icon of the corner is left out on this page (above): this button is
              the only door. */}
          {showsSignedOutDoors && (
            <div className="invite-nudge">
              <div className="button-row-wide">
                <ButtonLink to={`${base}/join`} style={btnStyle}>
                  {t('login.signIn')}
                </ButtonLink>
              </div>
            </div>
          )}
          {/* An invitation for a reader who is already signed in. They
              cannot be sent down the anonymous funnel — it asks for an email and
              answers with a magic link — so they get the action itself. Only on
              a PUBLIC collection: a private one is unreachable without an
              invitation, and this is exactly where the page used to offer
              "Add thing" to someone the API would refuse. */}
          {isAuthenticated &&
            !isCurator &&
            !collection.is_member &&
            collection.visibility === 'PUBLIC' && (
              <div className="invite-nudge">
                <div className="button-row-wide">
                  <Button style={btnStyle} disabled={joining} onClick={handleJoin}>
                    {joining ? t('joinToAct.joining') : t('collectionPage.visitorJoin')}
                  </Button>
                </div>
                {joinError && (
                  <p role="alert" style={{ color: 'var(--color-error)', marginBottom: 0 }}>
                    {t('collectionPage.visitorJoinError')}
                  </p>
                )}
              </div>
            )}
          {isCurator && (
            <>
              {/* "Add thing" first and primary, then "Edit collection":
                    what a curator does most, and what
                    an empty group needs before anything else, is put things in it;
                    editing the group is the second thing. It used to be the other way round
                    ("Edit collection" primary, "Add thing" beside it). Always there,
                    with things or without, and still an
                    entry of the collection menu (deliberately repeated there).
                    "Manage members" and the downloads live only in the menu; the
                    outcome of a download lands right under the row. */}
              <div className="button-row-wide">
                <ButtonLink to={`${base}/add`} style={btnStyle}>
                  {t('collectionPage.addThing')}
                </ButtonLink>
                {/* In a network the settings are the founder's: each dinamizador
                    edits their own point (it has its own page), not the group. */}
                {(collection.mode !== 'NETWORK' || isOwner) && (
                  <ButtonLink to={`${base}/edit`} style={btnSecondaryStyle}>
                    {t('collectionPage.editCollection')}
                  </ButtonLink>
                )}
                {/* The third button of the row (it was a quiet line
                      under the row, "Your collection is taking shape. Now invite your
                      circle →"): secondary, like "Edit collection", so the row keeps its
                      one primary. It was shown only while the group had things and
                      nobody invited, and went with the first guest who accepted — a curator
                      who had invited people found the button gone. Now it is
                      always there for whoever runs the group, owner or co-curator, with
                      things or without and with members or without: inviting is not a
                      step of the beginning. */}
                <ButtonLink to={`${base}/invites`} style={btnSecondaryStyle}>
                  {t('collectionPage.inviteYourPeople')}
                </ButtonLink>
              </div>
              <CollectionDownloadsStatus downloads={downloads} />
              {/* Whoever runs the group has the summary switch in the menu too
                  (`is_member` is false for the team), so its outcome shows here. */}
              <CollectionDigestStatus digest={digestPref} />
            </>
          )}
          {/* Everything in here is a rank-and-file member's control —
              contributing a thing, recommending a guest — so membership
              (excluding a curator, who has the real thing above) is the single
              condition. It used to admit any signed-in reader of a COMMUNITY
              collection, which is how the dead-end button got here. */}
          {isAuthenticated && !isOwner && collection.is_member && (
            <>
              {/* In a demo collection "Invite someone" makes no sense (nobody is
                invited into shared demo data), so the member's way out stands in
                its place: "Leave the group", after "Add thing" where the group
                gives it. A curator and every other collection are untouched. */}
              {/* One row, each button on its own condition:
                "Invite someone" first and primary — it opens the recommend form
                below the row, and stays on screen while the form is open so the
                same button closes it — then "Add thing", secondary. Neither:
                no row. Membership, not just mode, for "Add thing":
                `Collection.can_add_thing` requires an invite, so offering it to
                a signed-in non-member sent them through the whole form — photos
                uploaded to the bucket and all — to collect a 403 at the end.
                They get the join button above instead, which is the thing that
                actually unlocks it. */}
              {(showInvite || collection.mode === 'COMMUNITY' || isDemo) && (
                <div className="button-row-wide">
                  {showInvite && (
                    <Button
                      ref={recommendButtonRef}
                      style={btnStyle}
                      aria-expanded={recommendOpen}
                      aria-controls={recommendOpen ? RECOMMEND_BOX_ID : undefined}
                      onClick={() => setRecommendOpen((open) => !open)}
                    >
                      {t('recommend.openButton')}
                    </Button>
                  )}
                  {collection.mode === 'COMMUNITY' && (
                    <ButtonLink to={`${base}/add`} style={btnSecondaryStyle}>
                      {t('collectionPage.addThing')}
                    </ButtonLink>
                  )}
                  {isDemo && (
                    <ButtonLink to={`${base}/leave`} state={{ headline }} style={btnSecondaryStyle}>
                      {t('collectionPage.leaveGroup')}
                    </ButtonLink>
                  )}
                </div>
              )}
              {showInvite && recommendOpen && (
                <RecommendGuest
                  id={RECOMMEND_BOX_ID}
                  collectionCode={code}
                  ownerName={collection.owner_name}
                  coOwnerCount={collection.co_owners?.length ?? 0}
                  onClose={() => {
                    setRecommendOpen(false);
                    recommendButtonRef.current?.focus();
                  }}
                />
              )}
              {/* The outcome of "Mute the summaries" / "Get the summaries again" from the
                collection menu: a short message in a live region, as the downloads'.
                Members only: the team's own zone is under its row. */}
              <CollectionDigestStatus digest={digestPref} />
              {/* "Leave the group" used to sit here, third in a stack of
                unlabelled text links under the description — and the only
                destructive one of the three. It moved to the own profile's "My
                groups" list: leaving is something you do to your
                own membership, so it belongs with the rest of your account, next
                to the other memberships you might weigh it against. It is also
                the last entry of the member's collection
                menu, under a divider; the route (/collections/:code/leave) is
                unchanged. */}
            </>
          )}
        </div>
      </div>
      <Koros
        className="form-hero-koros"
        type={koro}
        style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
      />
    </div>
  );
}
