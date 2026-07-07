import { useMemo } from 'react';

/**
 * Theeeme-derived inline styles, centralised from the ~21 pages/components that
 * each re-parsed `theeemeColors` from localStorage and rebuilt the same button
 * style objects on every render.
 *
 * The returned objects are byte-identical to the previous inline versions, so the
 * rendered appearance is unchanged. The raw localStorage string is read on every
 * render (cheap) but the parse + style objects are memoised on it, so they only
 * recompute when the theeeme actually changes — which still happens (e.g. right
 * after the first login, when HomePage stores the freshly fetched colours).
 *
 * Returns:
 * - `tc`: the raw theeeme colour map (`color_01`..`color_06`, HDS token names).
 * - `koro`: the user's Koros wave type (default `'basic'`).
 * - `btnStyle`: primary button (theeeme `color_01` background, `color_06` text).
 * - `btnSecondaryStyle`: secondary button (white background, `color_01` border, `color_04` text).
 */
// Fallback palette for a viewer with no stored theeeme yet — e.g. an anonymous
// visitor on a PUBLIC collection, or anyone before their first login. Without it
// `tc` is `{}`, so `--hero-text-color` stays unset and the hero title falls back
// to black-90 — invisible on the dark hero. It's a real, coherent theeeme row
// (the "M&V" palette, code 5BC8W6: black hero + white text + summer/yellow
// accents) rather than a hand-mixed set of tokens, so every surface matches.
const DEFAULT_COLORS = {
  color_01: 'summer',
  color_02: 'black-5',
  color_03: 'black',
  color_04: 'black',
  color_05: 'white',
  color_06: 'black',
};

export default function useTheeeme() {
  const raw = localStorage.getItem('theeemeColors') || '{}';
  const koro = localStorage.getItem('koro') || 'basic';

  return useMemo(() => {
    let parsed;
    try {
      parsed = JSON.parse(raw);
    } catch {
      parsed = null;
    }
    const tc = parsed && Object.keys(parsed).length > 0 ? parsed : DEFAULT_COLORS;
    const btnStyle = tc.color_01
      ? {
          '--background-color': `var(--color-${tc.color_01})`,
          '--background-color-hover': `var(--color-${tc.color_01}-dark)`,
          '--color': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
          '--border-color': `var(--color-${tc.color_01})`,
        }
      : undefined;
    const btnSecondaryStyle = tc.color_01
      ? {
          '--background-color': 'var(--color-white)',
          '--border-color': `var(--color-${tc.color_01})`,
          '--color': tc.color_04 ? `var(--color-${tc.color_04})` : undefined,
          '--background-color-hover': `var(--color-${tc.color_01})`,
          '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
        }
      : undefined;
    return { tc, koro, btnStyle, btnSecondaryStyle };
  }, [raw, koro]);
}
