import { expect } from 'vitest';

/**
 * What every entry of the four hero menus looks like: one decorative icon, first,
 * and the text in a `<span>` after it. The accessible name stays the text alone,
 * because the icon is `aria-hidden` (testing-library finds the entry by that name).
 * Returns the icon's HDS name (`aria-label`) so a test can say which icon it is.
 */
export function iconOf(entry, text) {
  const icons = entry.querySelectorAll('svg');
  expect(icons).toHaveLength(1);
  const [icon] = icons;
  expect(icon).toHaveAttribute('aria-hidden', 'true');
  expect(entry.firstElementChild).toBe(icon);
  const label = entry.querySelector(':scope > span');
  expect(label).toHaveTextContent(text);
  expect(icon.compareDocumentPosition(label) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  return icon.getAttribute('aria-label');
}
