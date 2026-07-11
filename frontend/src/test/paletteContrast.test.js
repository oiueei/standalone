import { readFileSync } from 'node:fs';
import { describe, test, expect } from 'vitest';

// jsdom can't run axe's colour-contrast rule (it needs real layout/paint), so we
// verify the curated theeeme palette here instead: for every theeeme, the text
// roles that sit on a coloured background must meet WCAG 2.1 AA (>= 4.5:1 for
// normal text).
//
// The 12 palettes mirror the backend seed (core/migrations/0036, as amended by
// 0081 color_02 -> -medium-light and 0112 Vaakuna color_05 -> black). Keep this
// list in lockstep with that seed.
const THEEEMES = [
  { name: 'Bussi', color_01: 'bus', color_02: 'suomenlinna-medium-light', color_03: 'copper', color_04: 'black', color_05: 'black', color_06: 'white' },
  { name: 'Engel', color_01: 'engel', color_02: 'bus-medium-light', color_03: 'copper', color_04: 'black', color_05: 'black', color_06: 'black' },
  { name: 'Hopea', color_01: 'gold', color_02: 'bus-medium-light', color_03: 'silver', color_04: 'black', color_05: 'black', color_06: 'black' },
  { name: 'Kesä', color_01: 'summer', color_02: 'engel-medium-light', color_03: 'tram', color_04: 'black', color_05: 'white', color_06: 'black' },
  { name: 'Kupari', color_01: 'copper', color_02: 'fog-medium-light', color_03: 'suomenlinna', color_04: 'black', color_05: 'black', color_06: 'black' },
  { name: 'Kulta', color_01: 'gold', color_02: 'fog-medium-light', color_03: 'metro', color_04: 'black', color_05: 'black', color_06: 'black' },
  { name: 'Metro', color_01: 'metro', color_02: 'suomenlinna-medium-light', color_03: 'gold', color_04: 'black', color_05: 'black', color_06: 'black' },
  { name: 'Sumu', color_01: 'fog', color_02: 'engel-medium-light', color_03: 'metro', color_04: 'black', color_05: 'black', color_06: 'black' },
  { name: 'Spåra', color_01: 'tram', color_02: 'engel-medium-light', color_03: 'summer', color_04: 'black', color_05: 'black', color_06: 'white' },
  { name: 'Suomenlinna', color_01: 'suomenlinna', color_02: 'bus-medium-light', color_03: 'bus', color_04: 'black', color_05: 'white', color_06: 'black' },
  { name: 'Vaakuna', color_01: 'summer', color_02: 'fog-medium-light', color_03: 'suomenlinna', color_04: 'black', color_05: 'black', color_06: 'black' },
  { name: 'M&V', color_01: 'summer', color_02: 'black-5', color_03: 'black', color_04: 'black', color_05: 'white', color_06: 'black' },
];

// The role pairings that render text on a coloured surface (frontend/CLAUDE.md
// "Theeeme Color Roles"): body text, primary-button label, koros/hero text.
const PAIRINGS = [
  { role: 'body text (color_04 on color_02)', fg: 'color_04', bg: 'color_02' },
  { role: 'primary button (color_06 on color_01)', fg: 'color_06', bg: 'color_01' },
  { role: 'koros/hero text (color_05 on color_03)', fg: 'color_05', bg: 'color_03' },
];

const AA_NORMAL = 4.5;

// Resolve HDS colour tokens to hex from the design-tokens package — the single
// source of truth for the values behind names like "bus" or "fog-medium-light".
function loadTokenHexMap() {
  const css = readFileSync('node_modules/hds-design-tokens/lib/color/all.css', 'utf8');
  const map = { black: '#000000', white: '#ffffff' };
  for (const m of css.matchAll(/--color-([a-z0-9-]+):\s*(#[0-9a-fA-F]{3,8})/g)) {
    map[m[1]] = m[2];
  }
  return map;
}

function relativeLuminance(hex) {
  const h = hex.replace('#', '');
  const chan = (i) => {
    const c = parseInt(h.slice(i, i + 2), 16) / 255;
    return c <= 0.03928 ? c / 12.92 : ((c + 0.055) / 1.055) ** 2.4;
  };
  return 0.2126 * chan(0) + 0.7152 * chan(2) + 0.0722 * chan(4);
}

function contrastRatio(a, b) {
  const la = relativeLuminance(a);
  const lb = relativeLuminance(b);
  return (Math.max(la, lb) + 0.05) / (Math.min(la, lb) + 0.05);
}

describe('theeeme palette WCAG AA contrast', () => {
  const tokens = loadTokenHexMap();

  test('all curated theeeme role tokens resolve to a hex value', () => {
    for (const theeeme of THEEEMES) {
      for (const key of ['color_01', 'color_02', 'color_03', 'color_04', 'color_05', 'color_06']) {
        expect(tokens[theeeme[key]], `${theeeme.name} ${key}=${theeeme[key]}`).toMatch(/^#[0-9a-fA-F]{6}$/);
      }
    }
  });

  test.each(THEEEMES)('$name meets AA for every text-on-colour role', (theeeme) => {
    for (const { role, fg, bg } of PAIRINGS) {
      const ratio = contrastRatio(tokens[theeeme[fg]], tokens[theeeme[bg]]);
      expect(ratio, `${theeeme.name} — ${role}: ${ratio.toFixed(2)}:1`).toBeGreaterThanOrEqual(AA_NORMAL);
    }
  });
});
