import { Link as HdsLink } from 'hds-react';
import { useTranslation } from 'react-i18next';
import ButtonLink from './ButtonLink';
import useCapabilities from '../hooks/useCapabilities';
import useTheeeme from '../hooks/useTheeeme';
import { externalFormUrl } from '../utils/externalForms';
import { requestAccessPaths } from '../deployment';
import { uiLanguage } from '../utils/uiLanguage';

/**
 * "Some of these need approval here" — the one line a narrowed deployment owes
 * the person looking at a shorter list than the product has.
 *
 * **Upstream it never renders.** OIUEEI's own policy withholds nothing, so
 * there is nothing to explain and this returns null on every page it sits on.
 * It lives here rather than in a deployment's own directory precisely so the
 * React is identical in both: a deployment narrows the policy on the server and
 * the explanation appears, with nobody editing a form component.
 *
 * Without it, the form silently offers less than the product does and the user
 * is left to conclude the feature does not exist — which for a deployment with
 * a request URL is not even true.
 *
 * **Where to ask is a primary button, "Request access"**, not a
 * link ending in an arrow: the sentence stays as it was, and under it a
 * `.button-row-wide` (the width of the screen on a phone) holds the button. It is
 * made as `FeedbackLink` is — HDS `Link` with `useButtonStyles`, the theeeme's
 * primary tokens, `target="_blank"` and the announcement of the new tab in the
 * `aria-label`, since HDS's own `openInNewTab` prints its label. Without a request
 * URL there is the sentence and no button, as before. **A deployment may send the request
 * to a page of the app instead** (`deployment/requestAccessPaths`, by withheld value): then
 * the button is a `ButtonLink` to that route — same tab, through the router, no new-tab
 * announcement — for the first withheld value (in the catalogue's order) that has one. These forms already have a
 * primary of their own ("Create" / "Save"); this one is wanted all the same.
 *
 * @param {'collection_modes'|'collection_kinds'|'thing_types'} kind Which capability list to check.
 * @param {Array<{value: string, label: string}>} catalogue Every option the
 *   product has, already labelled — the same list the form would offer if
 *   nothing were withheld.
 */
export default function ApprovalNotice({ kind, catalogue }) {
  const { t, i18n } = useTranslation();
  const capabilities = useCapabilities();
  const { btnStyle } = useTheeeme();

  // Not known yet, or the request failed: say nothing. A wrong "this needs
  // approval" on a deployment that approves everything is worse than silence.
  const allowed = capabilities?.[kind];
  if (!allowed) return null;

  const withheld = catalogue.filter((option) => !allowed.includes(option.value));
  if (withheld.length === 0) return null;

  const list = withheld.map((option) => option.label).join(', ');
  // Where to ask. First, a page of the app: the first withheld value (in the order of
  // the catalogue) that the deployment has a route for — the button goes there, in the
  // same tab, through the router. Failing that, the deployment's own form for it in
  // the reader's language (`externalForms.requestAccess`, as written), or the address
  // the server gives (`capabilities.request_url`), as before. Those two open in a new tab.
  const appPath = withheld.map((option) => requestAccessPaths?.[option.value]).find(Boolean);
  const requestUrl = externalFormUrl('requestAccess', uiLanguage(i18n)) || capabilities.request_url;
  const canAsk = appPath || requestUrl;

  const requestLabel = t('capabilities.requestAccess');

  return (
    <div>
      {/* Two different facts, and the difference is the whole point: somewhere
          to ask means "not yet", nowhere to ask means "not here". Telling
          someone to request access when there is no such page would be worse
          than the disabled control it was meant to explain. */}
      <p className="approval-notice">
        {canAsk
          ? t('capabilities.needsApproval', { list })
          : t('capabilities.unavailable', { list })}
      </p>
      {appPath && (
        <div className="button-row-wide">
          <ButtonLink to={appPath} style={btnStyle}>
            {requestLabel}
          </ButtonLink>
        </div>
      )}
      {!appPath && requestUrl && (
        <div className="button-row-wide">
          <HdsLink
            href={requestUrl}
            useButtonStyles
            style={btnStyle}
            target="_blank"
            rel="noopener noreferrer"
            aria-label={`${requestLabel}. ${t('common.opensInNewTab')}`}
          >
            {requestLabel}
          </HdsLink>
        </div>
      )}
    </div>
  );
}
