import { useCallback } from 'react';
import { useTranslation } from 'react-i18next';

/**
 * Owner content that carries one text per language (O6).
 *
 * An owner of a bilingual group may write a headline, a description or a tag
 * label as inline JSON — `{"es": "Las cosas de mamá", "ca": "Les coses de mama"}` —
 * and every member reads their own. There is no schema behind it: the map lives
 * in the same field it always did.
 *
 * This is the mirror of `core/utils.py::parse_localized` / `resolve_localized`,
 * and it must stay strict in exactly the same way — everything the parse rejects
 * renders **verbatim**, which is what keeps the trick invisible to the owners who
 * never use it (someone writing about JSON in a description must see their words
 * back). Any divergence here shows up as raw braces on a card while the email of
 * the same thing reads fine, so change both sides together.
 */

// The languages OIUEEI speaks — mirrors core/models/language.py and src/i18n.
export const LOCALIZED_LANGS = ['es', 'ca', 'en'];

/** The `{lang: text}` map inside a value, or null when the value is just text. */
export function parseLocalized(value) {
  if (typeof value !== 'string') return null;
  const text = value.trim();
  if (!text.startsWith('{')) return null;
  let parsed;
  try {
    parsed = JSON.parse(text);
  } catch {
    return null;
  }
  if (parsed === null || typeof parsed !== 'object' || Array.isArray(parsed)) return null;
  const entries = Object.entries(parsed);
  if (entries.length === 0) return null;
  for (const [lang, textInLang] of entries) {
    if (!LOCALIZED_LANGS.includes(lang)) return null;
    if (typeof textInLang !== 'string' || !textInLang.trim()) return null;
  }
  return parsed;
}

/**
 * What a reader of `lang` should see for a possibly-localized value.
 *
 * Plain text comes back untouched. A map resolves through `lang` → `es` → the
 * first language the owner wrote, so a reader whose language was skipped still
 * gets words rather than braces. `lang` may be a full i18n tag (`en-GB`).
 */
export function localizedText(value, lang) {
  const localized = parseLocalized(value);
  if (!localized) return value;
  const base = (lang || '').split('-')[0];
  if (localized[base]) return localized[base];
  if (localized.es) return localized.es;
  return Object.values(localized)[0];
}

/**
 * `localizedText` bound to the reader's language — the frontend twin of the
 * email service's `L`. Call it on every owner-written value you render:
 * `const L = useLocalized(); … <h1>{L(thing.headline)}</h1>`.
 */
export function useLocalized() {
  const { i18n } = useTranslation();
  const lang = i18n.resolvedLanguage || i18n.language;
  return useCallback((value) => localizedText(value, lang), [lang]);
}

/**
 * The character counter under a field the owner may localize, and whether it is
 * over the limit.
 *
 * Plain text counts as it always did ("18/64"). A map is counted **per
 * language** ("es 18/64 · ca 17/64"), because that is the rule the server
 * enforces: each language gets the whole limit, and three of them don't buy
 * three times the length.
 */
export function localizedCounter(value, limit) {
  const localized = parseLocalized(value);
  if (!localized) {
    return { text: `${(value || '').length}/${limit}`, over: (value || '').length > limit };
  }
  const entries = Object.entries(localized);
  return {
    text: entries.map(([lang, text]) => `${lang} ${text.length}/${limit}`).join(' · '),
    over: entries.some(([, text]) => text.length > limit),
  };
}
