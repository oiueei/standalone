import { useRef, useState } from 'react';
import { Link, NavLink, useLocation } from 'react-router';
import { useTranslation } from 'react-i18next';
import { IconHome, IconSignout, IconUser } from 'hds-react';
import { IconMyRequests, IconRequestsToMe } from './icons/OiueeiIcons';
import useDismissable from '../hooks/useDismissable';
import useReceivesRequests from '../hooks/useReceivesRequests';
import { isDoorPath, loginPathFor } from '../utils/nextPath';

const PANEL_ID = 'account-menu-panel';

/**
 * The account's own pages, one click away from every hero: "My profile", "My requests", "Requests to me" and "Log
 * out", under "Home", used to live only on `/` and `/me` — hard to reach from
 * inside a collection, and **unreachable at all** from one whose owner set a
 * `home_page`, since that hero's own "Home" link leaves OIUEEI for the group's
 * own site.
 *
 * "Edit profile" and "Create collection" are not here: the first
 * is reached from "My profile", the second from Home. And "Requests to me" is
 * shown only to someone who can receive requests — owns a thing, or runs a
 * PROPRIETARY collection — which only the server knows, so the menu asks
 * `GET /auth/me/` (`receives_requests`) when it opens (`useReceivesRequests`,
 * shared with the collection menu). Nothing is kept in the browser for it (a new
 * storage key is one more line in the `/legal`), and while the answer is not there,
 * or if it cannot be had, the link is left out.
 *
 * **On a page that has a collection menu, "Requests to me" is that menu's first
 * entry, not this one's**: `requestsInCollectionMenu` says so,
 * and the menu then neither shows the link nor asks the server. That is a
 * collection's page and a thing's read through a collection, for whoever has the
 * collection menu there; everywhere else (Home, `/me`…) the link stays here — and
 * so it does for a reader who has no collection menu on such a page, so the link is
 * never in neither.
 *
 * **The link to the page on screen says so**: each is a `NavLink` with `end`, which
 * sets `aria-current="page"` on an exact match (`/me` is current on `/me`, not on
 * `/me/edit`).
 *
 * A plain navigation disclosure — a button that shows/hides a `<nav>` of
 * `Link`s — not an HDS `Select` dressed as a menu: every
 * option here is a **route**, not an action, and a `Select` announces itself
 * as a combobox to a screen reader (an accessibility risk). No `role="menu"` either — that role expects arrow-key
 * navigation between actions; this is `Tab`-navigable links, so the native
 * semantics already say what it is.
 *
 * Rendered first in the shared `.hero-corners` flex row (and, on `CollectionPage`,
 * followed by `CollectionMenu` and `ShareCollectionMenu`) — see `PageLayout` and
 * the manual-hero pages for where. The contact icon that used to close the row
 * went to the site footer on 2026-10-04 ("Contact us"): too many icons up here.
 * **Session-gated, not page-gated**: it reads `userCode` itself, so it needs no
 * prop from any of its many call sites.
 *
 * **Signed out, the same icon in the same place is a link to sign in**: not a panel but a plain `<Link>` to `/login` that comes back to the
 * page the reader is on (`loginPathFor(location)`), named "Sign in". It was nothing
 * at all, so a visitor with no session had no corner. Not on `/login` (it would
 * lead to itself), `/logout` or `/verify/…` and its aliases, where it still paints
 * nothing — `isDoorPath`, the same list a login never returns to. On a public
 * collection it used to sit beside the hero's own "Sign in" button; `CollectionPage`
 * now passes `offerSignIn={false}` there, since
 * the hero's button is the way in.
 * **`offerSignIn={false}` paints nothing signed out either**: a
 * door that does not want to send people to `/login` — a deployment's own
 * open door (`popInPath`), which drops "Already have an account?" on purpose — says so through
 * `MagicLinkJoinPage`'s `offerSignIn`, which `PageLayout` hands down. It changes
 * nothing for a signed-in reader, and where nobody passes it (`/share`, `/join`, the
 * 404…) the icon stays.
 */
export default function AccountMenu({ requestsInCollectionMenu = false, offerSignIn = true }) {
  const { t } = useTranslation();
  const [open, setOpen] = useState(false);
  const wrapperRef = useRef(null);
  const buttonRef = useRef(null);
  const location = useLocation();
  // Asked each time the panel opens (`useReceivesRequests`) — and not at all where
  // the collection menu beside this one carries the link instead.
  const receivesRequests = useReceivesRequests(open && !requestsInCollectionMenu);

  // The panel's dismissal contract — Escape refocuses the trigger, a click
  // outside closes without moving focus — lives in `useDismissable`, shared
  // with the collection menu that sits beside this one in the hero's corner.
  useDismissable({ open, setOpen, wrapperRef, buttonRef });

  // Read directly, like every other per-viewer check in this app (ThingLinkbox,
  // CollectionPage, …) — no context, no prop, so every hero can render this
  // unconditionally and let it decide for itself.
  const userCode = localStorage.getItem('userCode');
  if (!userCode) {
    if (!offerSignIn || isDoorPath(location.pathname)) return null;
    return (
      <span className="account-menu">
        <Link
          to={loginPathFor(location)}
          className="account-menu-trigger"
          aria-label={t('login.signIn')}
        >
          <IconUser aria-hidden="true" />
        </Link>
      </span>
    );
  }

  const label = t('accountMenu.label');
  // Following any link closes the panel: one to the page already on screen
  // (Home from `/`, My profile from `/me`) keeps this component mounted, and
  // the panel would otherwise stay open over the page it just "went" to.
  const close = () => setOpen(false);

  return (
    // Focus leaving the whole menu (Tab past the last link, or back past the
    // trigger) closes the panel, as `InfoPopover` does. A `null` `relatedTarget`
    // is not "left": Safari does not focus a button or link on click, so the
    // trigger would blur into nothing just before a click on a link lands.
    // Clicks elsewhere close it through `useDismissable`.
    // eslint-disable-next-line jsx-a11y/no-static-element-interactions
    <span
      className="account-menu"
      ref={wrapperRef}
      onBlur={(e) => {
        if (e.relatedTarget && !e.currentTarget.contains(e.relatedTarget)) close();
      }}
    >
      <button
        type="button"
        ref={buttonRef}
        className="account-menu-trigger"
        aria-label={label}
        aria-expanded={open}
        aria-controls={open ? PANEL_ID : undefined}
        onClick={() => setOpen((v) => !v)}
      >
        <IconUser aria-hidden="true" />
      </button>
      {open && (
        <nav id={PANEL_ID} className="account-menu-panel" aria-label={label}>
          <NavLink to="/" end onClick={close}>
            <IconHome aria-hidden="true" />
            <span>{t('common.home')}</span>
          </NavLink>
          <NavLink to="/me" end onClick={close}>
            <IconUser aria-hidden="true" />
            <span>{t('home.myProfile')}</span>
          </NavLink>
          <NavLink to="/my-bookings" end onClick={close}>
            <IconMyRequests aria-hidden="true" />
            <span>{t('home.myRequests')}</span>
          </NavLink>
          {receivesRequests && !requestsInCollectionMenu && (
            <NavLink to="/owner-bookings" end onClick={close}>
              <IconRequestsToMe aria-hidden="true" />
              <span>{t('home.requestsToMe')}</span>
            </NavLink>
          )}
          <hr className="account-menu-divider" />
          <Link to="/logout" onClick={close}>
            <IconSignout aria-hidden="true" />
            <span>{t('userPage.logout')}</span>
          </Link>
        </nav>
      )}
    </span>
  );
}
