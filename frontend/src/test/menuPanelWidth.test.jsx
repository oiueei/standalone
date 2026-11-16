import { describe, test, expect } from 'vitest';
import { declarations } from './cssRules';

/**
 * The four hero menus' panels hang from `.hero-corners`, which is narrow, so a
 * panel left to shrink-wrap its row broke "Download the whole collection (JSON)" in
 * two. Each is as wide as its longest entry (`max-content`), with no minimum, and
 * keeps the cap that lets an entry break on a 320px screen. jsdom does no layout:
 * this pins what the stylesheet declares.
 */
const PANELS = [
  '.account-menu-panel',
  '.collection-menu-panel',
  '.collection-settings-menu-panel',
  '.share-menu-panel',
];

describe.each(PANELS)('%s', (selector) => {
  test('is as wide as its longest entry', () => {
    expect(declarations(selector, 'width')).toEqual(['max-content']);
  });

  test('has no minimum width of its own', () => {
    expect(declarations(selector, 'min-width')).toEqual([]);
  });

  test('keeps the cap that fits a 320px screen, and does not forbid wrapping', () => {
    expect(declarations(selector, 'max-width')).toEqual(['calc(100vw - 2 * var(--spacing-s))']);
    expect(declarations(selector, 'white-space')).toEqual([]);
  });
});
