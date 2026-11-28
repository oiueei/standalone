import { Link as HdsLink } from 'hds-react';
import { useTranslation } from 'react-i18next';
import { externalFormUrl } from '../utils/externalForms';
import { uiLanguage } from '../utils/uiLanguage';

// Alpha feedback channel. This is service-layer policy, not product: without a form
// the door simply isn't offered, the same pattern as `popInPath`/`aboutPath` in
// `src/deployment/` — upstream doesn't point anyone's feedback at the maintainer's own form on
// their behalf. A deployment that wants the feature either hosts forms of its own
// (`deployment/externalForms.feedback`, one address per language, read
// first) or sets the build-time env var `VITE_FEEDBACK_URL`, a single
// address for every language, as it always could.
const FEEDBACK_URL = import.meta.env.VITE_FEEDBACK_URL;

/**
 * "Ideas and bugs", as a button. It was a quiet line — "Something
 * odd? An idea? Tell me →" — that sat under the page's content; a short
 * button replaces it, on Home and wherever a deployment puts it.
 *
 * It renders **only the `<a>`**, no paragraph around it, so it can sit inside a
 * row of buttons (a deployment's own page can put it in one). Built on HDS `Link` with
 * `useButtonStyles`, the same base as `ButtonLink` (read its docstring): the real
 * button CSS on one `<a>`, one tab stop. `style` carries the theeeme tokens, and
 * the caller decides whether this is the primary or the secondary button — Home
 * passes the secondary, alone.
 *
 * It opens in a new tab, and says so — but not through HDS's `openInNewTab`:
 * that prop appends its label **to the visible text** ("Ideas and bugs (Opens in
 * a new tab.)", in Finnish unless `openInNewTabLabel` is given), which is not the
 * short label wanted here. So `target` and `rel` are set here and the
 * announcement is the `aria-label` — the visible words first, then the sentence
 * (`common.opensInNewTab`, in the reader's language), the way HDS itself builds
 * the label of an `external` link. The visible name stays inside the accessible
 * one (WCAG 2.5.3).
 *
 * The address is the deployment's form of the reader's language
 * (`externalForms.feedback`, as written — nothing is added to it) if it has one;
 * otherwise `VITE_FEEDBACK_URL`, as before. Renders nothing without either.
 */
export default function FeedbackLink({ style }) {
  const { t, i18n } = useTranslation();
  const url = externalFormUrl('feedback', uiLanguage(i18n)) || FEEDBACK_URL;
  if (!url) return null;
  const label = t('feedback.button');
  return (
    <HdsLink
      href={url}
      useButtonStyles
      style={style}
      target="_blank"
      rel="noopener noreferrer"
      aria-label={`${label}. ${t('common.opensInNewTab')}`}
    >
      {label}
    </HdsLink>
  );
}
