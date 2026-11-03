/**
 * The target of a `tel:` link for a phone number as someone typed it: only digits
 * and `+` stay. "(93) 123-45.67" dials as "931234567"; the text next to the link
 * keeps what was typed.
 */
export function phoneHref(value) {
  return String(value ?? '').replace(/[^0-9+]/g, '');
}
