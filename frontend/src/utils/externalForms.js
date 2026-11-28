import { externalForms } from '../deployment';

/**
 * The address of a form hosted elsewhere that a deployment puts in the place of one of
 * the app's own ways of writing to the team: `'contact'` (the
 * footer's "Contact us"), `'feedback'` ("Ideas and bugs") or `'requestAccess'`
 * ("Request access"), as `deployment/externalForms` gives it — `{ es, ca, en }` for
 * each. Core knows nothing about who hosts them.
 *
 * It is the address of the reader's language **exactly as it is written there**: no
 * `lang`, no user and no page is added to it (nothing of the reader goes to
 * somebody else's form). A language without an address falls back to `es`, the language
 * the forms are always written in, and with none at all, or with no `externalForms`
 * (upstream), it is `null`, which each place reads as "keep the way it was".
 *
 * `language` is the one on screen (`uiLanguage(i18n)`); a
 * regional tag (`ca-ES`) counts as its language.
 *
 * @param {'contact'|'feedback'|'requestAccess'} kind
 * @param {string} [language]
 * @returns {?string}
 */
export function externalFormUrl(kind, language) {
  const urls = externalForms?.[kind];
  if (!urls) return null;
  const code = String(language ?? '')
    .split('-')[0]
    .toLowerCase();
  return urls[code] || urls.es || null;
}
