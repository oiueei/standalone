/**
 * The language the page is shown in: the base code of `i18n.language` (`es-ES` → `es`,
 * lower case), or `''` when there is none. It has no fallback of its own; each caller
 * keeps the one it needs.
 *
 * It reads `language` and not `resolvedLanguage` on purpose. i18next fixes `language`
 * together with the language `t()` translates in, whereas `resolvedLanguage` is worked out
 * separately and can stay on the fallback (`en`) while `t()` already translates in the
 * requested language. Anything that reads it then — a link to a form, a language saved
 * with a collection, the language an owner's text is picked in — comes out in another
 * language than the page around it.
 *
 * @param {{ language?: string }} [i18n] the i18next instance
 * @returns {string}
 */
export function uiLanguage(i18n) {
  return String(i18n?.language ?? '')
    .split('-')[0]
    .toLowerCase();
}
