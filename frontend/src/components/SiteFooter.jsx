import { Link, useLocation } from 'react-router';
import { IconArrowUp } from 'hds-react';
import { useTranslation } from 'react-i18next';
import useTheeeme from '../hooks/useTheeeme';
import { aboutPath } from '../deployment';
import { externalFormUrl } from '../utils/externalForms';
import { uiLanguage } from '../utils/uiLanguage';

/**
 * The colophon under every page: "Made with ♥︎ in Zona Franca,
 * Barcelona…" after the doors below. From 768px it is **one line** — "What
 * OIUEEI is · Privacy & legal · Contact us · Made with ♥︎ in …" — and under 768px
 * the two lines it always was, the doors over the text. Global (mounted once in App), painted with the viewer's theeeme
 * `color_02` — the same token every `.form-page` uses as its background — so
 * there is no colour seam under the page. It sits at the bottom of the visible
 * screen on a short page and after the content on a long one (`#root` is a column as tall as the viewport, `<main>` takes what
 * is left). `useLocation()` re-renders it
 * on navigation, which re-reads the theeeme after a login/profile change (the
 * pages get this for free by remounting; a permanent component must ask).
 * The heart is U+2665 + U+FE0E (text presentation) so it inherits the text
 * colour instead of turning into a red emoji.
 *
 * **The links.** `/legal` is the page the
 * privacy claims tell you to go and check, and a deployment's "what is this?"
 * page answers the question a stranger asks first — yet every link to either
 * sat behind a login (Home's empty state) or on a page only a joiner sees
 * (LoginPage, a deployment's own doors). Someone reading a public collection,
 * which is the top of the whole funnel, could reach neither. They stay plain
 * text links: this is still a colophon, not the HDS `Footer` site-map OIUEEI
 * has no content for (DESIGN §3).
 *
 * **"Contact us" is the third door**: it was a speech-bubble icon
 * in the corner of every hero ("too many icons up there"); it is `/contact` here,
 * on every page, in the reader's language — **or, where a deployment hosts a form of
 * its own for it (`deployment/externalForms.contact`), a plain
 * link to that form** in the reader's language, in a new tab and announced as one.
 * `/contact` and its page stay in the app either way (upstream uses them; elsewhere
 * they are reached only by typing the address). `/login` keeps its own "trouble signing
 * in?" line, which is a different link, in the content.
 *
 * **Aligned to the content column, not centred**: the footer's own
 * background is the full width of the page, and `.site-footer-inner` inside it has
 * the column of the page (1248px, the same side padding as `.page-container`) with
 * `text-align: left`, so the first letter falls on the vertical of the headings and
 * the text above it. The first link loses its left padding for that.
 *
 * **A line before the doors, only upstream and only with no session.**
 * `footer.tagline` — what OIUEEI is for, in one sentence — links to `/login` for
 * someone who is not signed in, the one place that leads on from a public
 * collection's page. It shows only when **all three** hold:
 * - there is no session (read the way `AccountMenu` reads it, `localStorage.userCode`;
 *   `useLocation()` re-renders the footer when a login navigates, so it asks nothing);
 * - `aboutPath` is null: a deployment with its own page about OIUEEI already says
 *   it in this footer (the "What OIUEEI is" link), and its own pages may not want a
 *   link to `/login` at all;
 * - the page is not `/login`, where it would link to itself.
 * The hero is untouched.
 *
 * The about link is conditional because upstream there is no such page —
 * `/welcome` left with the demo, and what OIUEEI is gets told in the README.
 * A deployment that has one supplies it through `frontend/src/deployment/`.
 *
 * **The one line.** The `<nav>` keeps only the links (it is a landmark) and the
 * text stays outside it; between them is a separator `·`, `aria-hidden` like the
 * one between the links and spaced the same, that App.css shows only from 768px.
 * Below that it is `display: none`, because on two lines it would hang at the end
 * of the first one. Upstream, with no about link, the line is "Privacy & legal ·
 * Contact us · Made with ♥︎ in …".
 *
 * **"Back to top" under 992px.** After the colophon, a plain anchor to `#main` (the target
 * of the skip link, which starts at the hero) with an `aria-hidden` arrow: an anchor carries
 * the focus up without JavaScript, which a `<button>` with `scrollTo` would not. App.css
 * hides it from 992px and smooths the scroll only for `prefers-reduced-motion: no-preference`.
 */
export default function SiteFooter() {
  const { pathname } = useLocation();
  const { t, i18n } = useTranslation();
  const { tc } = useTheeeme();
  // Where "Contact us" goes: a form a deployment hosts elsewhere, in the reader's
  // language and in a new tab, or the app's own `/contact`.
  const contactUrl = externalFormUrl('contact', uiLanguage(i18n));
  const showTagline = !localStorage.getItem('userCode') && !aboutPath && pathname !== '/login';
  return (
    <footer
      className="site-footer"
      style={tc.color_02 ? { backgroundColor: `var(--color-${tc.color_02})` } : undefined}
    >
      <div className="site-footer-inner">
        {showTagline && (
          <p className="site-footer-tagline">
            <Link to="/login">{t('footer.tagline')}</Link>
          </p>
        )}
        <nav className="site-footer-links" aria-label={t('footer.navLabel')}>
          {/* Only where this deployment has a page saying what it is. Upstream
              there is none, and a footer link to a route that 404s is worse than
              one link fewer. /legal always exists — it is the page the privacy
              claims tell you to go and check — and so does /contact. */}
          {aboutPath && (
            <>
              <Link to={aboutPath}>{t('footer.about')}</Link>
              <span aria-hidden="true"> · </span>
            </>
          )}
          <Link to="/legal">{t('footer.legal')}</Link>
          <span aria-hidden="true"> · </span>
          {contactUrl ? (
            // Opens in a new tab and says so, the way "Ideas and bugs" does: the
            // visible words first, then the sentence (HDS's own prop would print it).
            <a
              href={contactUrl}
              target="_blank"
              rel="noopener noreferrer"
              aria-label={`${t('footer.contact')}. ${t('common.opensInNewTab')}`}
            >
              {t('footer.contact')}
            </a>
          ) : (
            <Link to="/contact">{t('footer.contact')}</Link>
          )}
        </nav>
        <span className="site-footer-sep" aria-hidden="true">
          {' · '}
        </span>
        {t('footer.madeIn')}
        <a href="#main" className="site-footer-top">
          {t('footer.backToTop')}
          <IconArrowUp aria-hidden="true" />
        </a>
      </div>
    </footer>
  );
}
