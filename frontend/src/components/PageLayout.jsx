import { Koros } from 'hds-react';
import AccountMenu from './AccountMenu';
import BackLink from './BackLink';
import useTheeeme from '../hooks/useTheeeme';

/**
 * The shared page chrome: a theeeme-coloured `form-hero` (optional back link,
 * title, optional description) bridged by a `Koros` wave into a `page-container`
 * for the main content.
 *
 * Centralises the ~18-line wrapper that was copied across the uniform form pages.
 * Pages with a custom hero (owner action buttons, a profile photo, etc.) keep
 * their bespoke markup and do not use this component. The theeeme colours and
 * Koros type come from `useTheeeme`, so the output is identical to the inline
 * version each page had.
 *
 * Props:
 * - `title`: hero `<h1>` text.
 * - `backTo` / `backLabel`: optional back link (rendered only when `backTo` is set).
 * - `description`: optional hero content under the title — a string or a
 *   node (e.g. `<MarkdownText>`). Rendered in a `<div>`, not a `<p>`, since
 *   Markdown can produce block content (lists, headings) a `<p>` can't legally
 *   contain; the class name (`form-hero-text`) is what styling and tests key
 *   on, so this is a same-look, same-selector change for every plain-string
 *   caller.
 * - `heroActions`: optional buttons for the hero, after the title and the
 *   description (the decision about a request sits in the hero
 *   of a thing's page). Rendered in a `.button-row-wide.hero-actions` — on a phone
 *   each one the width of the screen, above it the width of its own text — so
 *   the caller passes the buttons and nothing around them. One primary at most:
 *   any hero has two or three buttons, one of them primary. A
 *   panel the buttons open (an `InlineConfirm`) goes on a line of its own under
 *   the row (`.hero-actions > .thing-report-confirm`). No page but a thing's
 *   uses it yet.
 * - `collectionMenu`: optional node for the corner, after the account menu
 *   (`.hero-corners`: account · collection menu · …). A thing's page, read through
 *   a collection, passes the collection's menu. When it is
 *   there the account menu stops offering "Requests to me", which the collection
 *   menu carries as its first entry.
 * - `offerSignIn` (default `true`): whether a reader with no session gets the
 *   corner's "Sign in" icon (the signed-out `AccountMenu`). `MagicLinkJoinPage` passes
 *   its own `offerSignIn` through, so a door that leaves the
 *   "already have an account?" button out leaves the icon out too. Nothing changes for
 *   a signed-in reader.
 * - `logoUrl`: optional image for a collection's hero (`heroClassName="form-hero--collection"`):
 *   an `<img class="hero-logo" alt="">` between the back link and the title. Decorative,
 *   since the title already names whoever it belongs to.
 * - `heroClassName`: optional extra class for the `.form-hero`, for a page whose hero
 *   needs a rule of its own (the request page's smaller title: `form-hero--request`).
 * - `children`: page-container content.
 */
export default function PageLayout({
  title,
  backTo,
  backLabel,
  description,
  heroActions,
  collectionMenu,
  offerSignIn = true,
  heroClassName,
  logoUrl,
  children,
}) {
  const { tc, koro } = useTheeeme();
  return (
    <div
      className="form-page"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div
        className={heroClassName ? `form-hero ${heroClassName}` : 'form-hero'}
        style={tc.color_03 ? { backgroundColor: `var(--color-${tc.color_03})` } : undefined}
      >
        <div
          className="form-hero-content"
          style={tc.color_05 ? { '--hero-text-color': `var(--color-${tc.color_05})` } : undefined}
        >
          <span className="hero-corners">
            <AccountMenu requestsInCollectionMenu={!!collectionMenu} offerSignIn={offerSignIn} />
            {collectionMenu}
          </span>
          {backTo && <BackLink to={backTo} label={backLabel} />}
          {logoUrl && <img className="hero-logo" src={logoUrl} alt="" />}
          {title && <h1 className="form-hero-title">{title}</h1>}
          {description && <div className="form-hero-text">{description}</div>}
          {heroActions && <div className="button-row-wide hero-actions">{heroActions}</div>}
        </div>
        <Koros
          className="form-hero-koros"
          type={koro}
          style={tc.color_02 ? { fill: `var(--color-${tc.color_02})` } : undefined}
        />
      </div>
      <div className="page-container">{children}</div>
    </div>
  );
}
