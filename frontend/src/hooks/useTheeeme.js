import { useEffect, useMemo } from 'react';
import { linkColorToken } from '../utils/linkColor';
import { useDeclaredCollectionTheeeme } from './useCollectionTheeeme';

/**
 * Theeeme-derived inline styles, centralised from the ~21 pages/components that
 * each rebuilt the same button style objects on every render.
 *
 * **Whose palette it is.** A page that belongs to a collection declares that
 * collection's palette with `useCollectionTheeeme` and this hook answers with it;
 * everywhere else — Home, the account pages, the front door, the legal text, the 404
 * — it answers with **the app's own palette** (`Braaanding`, edited in the Django
 * admin). Nothing is stored in the browser and nothing is chosen by the reader.
 *
 * The app's palette is not HDS token names but six CSS variables of its own,
 * `--color-braaanding-01` … `--color-braaanding-06` (the server writes their values
 * into the page; `styles/oiueei-theme.css` holds the fallback), so its "token names"
 * below are `braaanding-01` … `braaanding-06` and every `var(--color-<token>)` in
 * the app resolves them with no change.
 *
 * Returns:
 * - `tc`: the raw colour map (`color_01`..`color_06`, token names).
 * - `koro`: the Koros wave type (a collection's, or the app's served one).
 * - `btnStyle`: primary button (`color_01` background, `color_06` text).
 * - `btnSecondaryStyle`: secondary button (white background, `color_01` border, `color_04` text).
 *
 * Both button styles pin the `*-focus` tokens to the resting colours, so keyboard
 * focus never recolours the button — the two-tone ring in `App.css` marks it.
 *
 * - `tableTheme`: the `theme` of an HDS `Table` (header fill `color_03`, header text `color_05`).
 * - `toggleTheme`: the `theme` of an HDS `ToggleButton` (`--toggle-button-color` is `color_01`);
 *   `undefined` without one. `test/themedToggles.test.js` sweeps for every toggle that omits it.
 * - `uploadStyle`: the `--upload-*` CSS vars for the ImageUpload/GalleryUpload wrapper.
 */

/** The prefix of the app's own palette tokens (`braaanding-01` … `braaanding-06`). */
export const APP_TOKEN_PREFIX = 'braaanding-';

export const APP_COLORS = {
  color_01: 'braaanding-01',
  color_02: 'braaanding-02',
  color_03: 'braaanding-03',
  color_04: 'braaanding-04',
  color_05: 'braaanding-05',
  color_06: 'braaanding-06',
};

const KOROS = ['basic', 'beat', 'calm', 'pulse', 'vibration', 'wave'];

/**
 * The app's Koros wave, served in the page's `<head>` as
 * `<meta name="braaanding-koro">` (a script reads it with no request; see
 * `core/services/app_palette.py`). `basic` where the page was never filled in (the
 * Vite dev server) or the value is not one of the six.
 */
export function appKoro() {
  const value = document.querySelector('meta[name="braaanding-koro"]')?.getAttribute('content');
  return KOROS.includes(value) ? value : 'basic';
}

export default function useTheeeme() {
  const declared = useDeclaredCollectionTheeeme();
  const tc = declared?.colors ?? APP_COLORS;
  const koro = declared?.koro ?? appKoro();
  // Stringified for a stable memo dependency (a collection's colours arrive as a
  // fresh object every time its page fetches).
  const colorsKey = JSON.stringify(tc);

  const result = useMemo(() => {
    const colors = JSON.parse(colorsKey);
    const isApp = colors.color_01?.startsWith(APP_TOKEN_PREFIX);
    // The `*-focus` tokens repeat the resting colours on purpose. HDS repaints a
    // button when it takes focus — the `primary` variant declares
    // `--background-color-focus: var(--color-bus)` and `secondary` declares it
    // `transparent` — and those declarations WIN over the `--background-color`
    // passed here, because HDS's fallback chain
    // (`var(--background-color-focus, var(--computed-background-color, …))`)
    // only reaches our value when nobody declares the focus one. On a
    // suomenlinna theeeme that turned a pink button blue with black text
    // (1.75:1, WCAG 1.4.3 asks 4.5:1) exactly when the keyboard arrived at it.
    // So the focus state must recolour nothing: what marks focus is the
    // two-tone ring in App.css, not a change of fill.
    const tc = colors;
    const primaryColor = tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)';
    const secondaryColor = tc.color_04 ? `var(--color-${tc.color_04})` : undefined;
    // Outer band of that ring. HDS draws the button's own outline with a
    // higher-specificity rule, so its colour has to arrive as a token; the
    // inner white band and the gap between them come from App.css, which HDS
    // does not contest.
    const focusOutline = 'var(--color-black)';
    const btnStyle = tc.color_01
      ? {
          '--background-color': `var(--color-${tc.color_01})`,
          // A collection's palette is HDS tokens, whose `-dark` shade is the hover. The app's
          // own colours are free hexadecimal and have no derived shade, so its hover is the
          // hero's pair (`color_03` with `color_05`), the one the emails' buttons use too.
          '--background-color-hover': isApp
            ? `var(--color-${tc.color_03})`
            : `var(--color-${tc.color_01}-dark)`,
          ...(isApp ? { '--color-hover': `var(--color-${tc.color_05})` } : {}),
          '--color': primaryColor,
          '--border-color': `var(--color-${tc.color_01})`,
          '--background-color-focus': `var(--color-${tc.color_01})`,
          '--border-color-focus': `var(--color-${tc.color_01})`,
          '--color-focus': primaryColor,
          '--outline-color-focus': focusOutline,
        }
      : undefined;
    const btnSecondaryStyle = tc.color_01
      ? {
          '--background-color': 'var(--color-white)',
          '--border-color': `var(--color-${tc.color_01})`,
          '--color': secondaryColor,
          '--background-color-hover': `var(--color-${tc.color_01})`,
          '--color-hover': tc.color_06 ? `var(--color-${tc.color_06})` : 'var(--color-white)',
          '--background-color-focus': 'var(--color-white)',
          '--border-color-focus': `var(--color-${tc.color_01})`,
          '--color-focus': secondaryColor,
          '--outline-color-focus': focusOutline,
        }
      : undefined;
    const uploadStyle = tc.color_01
      ? {
          '--upload-border': `var(--color-${tc.color_01})`,
          '--upload-color': tc.color_04
            ? `var(--color-${tc.color_04})`
            : `var(--color-${tc.color_01})`,
          '--upload-bg-hover': `var(--color-${tc.color_01})`,
          '--upload-color-hover': tc.color_06
            ? `var(--color-${tc.color_06})`
            : 'var(--color-white)',
        }
      : {};
    // The header of an HDS Table: the hero's colour behind it and the hero's text
    // on it (HDS paints that text white or near-black by its own theme, whatever
    // the fill; `.table-wrap th` in App.css reads `--header-color`).
    const tableTheme = tc.color_03
      ? {
          '--header-background-color': `var(--color-${tc.color_03})`,
          ...(tc.color_05 ? { '--header-color': `var(--color-${tc.color_05})` } : {}),
        }
      : undefined;
    // The colour of an HDS `ToggleButton` when it is on.
    const toggleTheme = tc.color_01
      ? { '--toggle-button-color': `var(--color-${tc.color_01})` }
      : undefined;
    // The colour of the text links in the page's content (`App.css` reads it).
    const linkToken = linkColorToken(tc);
    return {
      tc,
      koro,
      btnStyle,
      btnSecondaryStyle,
      uploadStyle,
      tableTheme,
      toggleTheme,
      linkToken,
    };
  }, [colorsKey, koro]);

  // On the root, so every page gets the link colour without passing it down.
  const { linkToken } = result;
  useEffect(() => {
    const root = document.documentElement.style;
    if (linkToken) root.setProperty('--link-color', `var(--color-${linkToken})`);
    else root.removeProperty('--link-color');
  }, [linkToken]);

  const { linkToken: _linkToken, ...styles } = result;
  return styles;
}
