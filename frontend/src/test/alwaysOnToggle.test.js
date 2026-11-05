import { describe, test, expect } from 'vitest';
import { css } from './cssRules';

/**
 * The always-on sign-in toggle (`#notify-magic`, checked and disabled) is drawn by HDS
 * in its own light grey. No rule of the stylesheet may repaint it.
 */
describe('the always-on toggle', () => {
  test('is painted by no rule of App.css', () => {
    expect(css).not.toContain('notify-magic');
  });
});
