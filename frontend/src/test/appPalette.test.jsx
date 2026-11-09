import { useLayoutEffect } from 'react';
import { render, renderHook, screen, act } from '@testing-library/react';
import { afterEach, beforeEach, describe, expect, test, vi } from 'vitest';
import fs from 'node:fs';
import useTheeeme, { APP_COLORS, appKoro } from '../hooks/useTheeeme';
import useCollectionTheeeme, { declaredNow } from '../hooks/useCollectionTheeeme';
import { linkColorToken, tokenHex } from '../utils/linkColor';
import { forgetRetiredPreferences, RETIRED_KEYS } from '../utils/retiredStorage';

/**
 * Whose palette `useTheeeme` answers with.
 *
 * Nothing is chosen by the reader or kept in the browser: a page that belongs to a
 * collection declares that collection's palette (`useCollectionTheeeme`, the same
 * spirit as `useCollectionLanguage`) and everything else wears the app's own
 * palette — six CSS variables of its own, `--color-braaanding-01` …
 * `--color-braaanding-06`, whose values the server writes into the page.
 */
const BUSSI = {
  color_01: 'bus',
  color_02: 'suomenlinna-medium-light',
  color_03: 'copper',
  color_04: 'black',
  color_05: 'black',
  color_06: 'white',
};
const JMPA = {
  color_01: 'metro',
  color_02: 'gold',
  color_03: 'tram',
  color_04: 'black',
  color_05: 'white',
  color_06: 'black',
};

function Painted({ label }) {
  const { tc, koro } = useTheeeme();
  return (
    <p data-testid={label}>
      {tc.color_01}|{koro}
    </p>
  );
}

function Declares({ colors, koro, children }) {
  useCollectionTheeeme(colors, koro);
  return children ?? null;
}

const text = (id) => screen.getByTestId(id).textContent;

beforeEach(() => {
  document.head.innerHTML = '';
  document.documentElement.removeAttribute('style');
});
afterEach(() => vi.restoreAllMocks());

describe('the app’s own palette is what nobody has declared otherwise', () => {
  test('with no collection page mounted, the colours are the six braaanding tokens', () => {
    const { result } = renderHook(() => useTheeeme());

    expect(result.current.tc).toEqual({
      color_01: 'braaanding-01',
      color_02: 'braaanding-02',
      color_03: 'braaanding-03',
      color_04: 'braaanding-04',
      color_05: 'braaanding-05',
      color_06: 'braaanding-06',
    });
    expect(result.current.tc).toEqual(APP_COLORS);
  });

  test('the buttons are painted with them', () => {
    const { result } = renderHook(() => useTheeeme());

    expect(result.current.btnStyle['--background-color']).toBe('var(--color-braaanding-01)');
    expect(result.current.btnStyle['--color']).toBe('var(--color-braaanding-06)');
    expect(result.current.btnSecondaryStyle['--border-color']).toBe('var(--color-braaanding-01)');
    expect(result.current.btnSecondaryStyle['--color']).toBe('var(--color-braaanding-04)');
    expect(result.current.tableTheme['--header-background-color']).toBe(
      'var(--color-braaanding-03)'
    );
    expect(result.current.tableTheme['--header-color']).toBe('var(--color-braaanding-05)');
  });

  test('nothing in localStorage changes it: the stored keys are not read', () => {
    localStorage.setItem('theeemeColors', JSON.stringify(BUSSI));
    localStorage.setItem('koro', 'wave');

    const { result } = renderHook(() => useTheeeme());

    expect(result.current.tc).toEqual(APP_COLORS);
    expect(result.current.koro).toBe('basic');
    localStorage.clear();
  });

  test('the koro is the one the server wrote into the page', () => {
    document.head.innerHTML = '<meta name="braaanding-koro" content="vibration">';

    expect(renderHook(() => useTheeeme()).result.current.koro).toBe('vibration');
  });

  test.each([['tsunami'], [''], [null]])('a koro meta of %p becomes basic', (value) => {
    if (value !== null) {
      document.head.innerHTML = `<meta name="braaanding-koro" content="${value}">`;
    }

    expect(appKoro()).toBe('basic');
  });
});

describe('a collection page declares its own', () => {
  test('its colours and koro are what useTheeeme answers while it is mounted', () => {
    render(
      <Declares colors={JMPA} koro="wave">
        <Painted label="in" />
      </Declares>
    );

    expect(text('in')).toBe('metro|wave');
  });

  test('a page with no data yet (nothing to declare) keeps the app’s palette', () => {
    render(
      <Declares colors={null} koro="wave">
        <Painted label="in" />
      </Declares>
    );

    expect(text('in')).toBe('braaanding-01|basic');
  });

  test('the koro defaults to basic when the page declares colours only', () => {
    render(
      <Declares colors={JMPA}>
        <Painted label="in" />
      </Declares>
    );

    expect(text('in')).toBe('metro|basic');
  });

  test('a reader elsewhere in the tree sees it too, and the app’s palette returns on unmount', () => {
    const page = render(
      <>
        <Declares colors={JMPA} koro="wave" />
        <Painted label="elsewhere" />
      </>
    );
    expect(text('elsewhere')).toBe('metro|wave');

    page.rerender(<Painted label="elsewhere" />);

    expect(text('elsewhere')).toBe('braaanding-01|basic');
  });

  test('it is declared in the same commit, before the browser can draw a frame', () => {
    // A layout effect of a sibling that comes after runs in the same commit as the
    // declaration: if the declaration were a passive effect (run after paint) the
    // store would still be empty here, and the app’s palette would flash.
    const atLayoutTime = [];
    function Spy() {
      useLayoutEffect(() => {
        atLayoutTime.push(declaredNow()?.colors.color_01 ?? null);
      });
      return null;
    }

    render(
      <>
        <Declares colors={JMPA} koro="wave" />
        <Spy />
      </>
    );

    expect(atLayoutTime[0]).toBe('metro');
  });

  test('the palette changing (another collection) is followed', () => {
    const view = render(
      <>
        <Declares colors={JMPA} />
        <Painted label="p" />
      </>
    );
    expect(text('p')).toBe('metro|basic');

    view.rerender(
      <>
        <Declares colors={BUSSI} koro="calm" />
        <Painted label="p" />
      </>
    );

    expect(text('p')).toBe('bus|calm');
  });

  test('a page that mounted later keeps its palette when an earlier one goes away', () => {
    const first = render(<Declares colors={JMPA} />);
    render(
      <>
        <Declares colors={BUSSI} />
        <Painted label="p" />
      </>
    );
    expect(text('p')).toBe('bus|basic');

    act(() => first.unmount());

    expect(text('p')).toBe('bus|basic');
  });
});

describe('a collection’s buttons hover with the -dark shade, the app’s with its hero pair', () => {
  test('a collection palette: the HDS token’s dark shade', () => {
    const { result } = renderHook(() => {
      useCollectionTheeeme(BUSSI);
      return useTheeeme();
    });

    expect(result.current.btnStyle['--background-color-hover']).toBe('var(--color-bus-dark)');
    expect(result.current.btnStyle['--color-hover']).toBeUndefined();
  });

  test('the app’s palette has no derived shade, so its hover is color_03 with color_05', () => {
    const { result } = renderHook(() => useTheeeme());

    // `--color-braaanding-01-dark` does not exist: HDS would fall back to its own blue.
    expect(result.current.btnStyle['--background-color-hover']).toBe('var(--color-braaanding-03)');
    expect(result.current.btnStyle['--color-hover']).toBe('var(--color-braaanding-05)');
  });
});

describe('a switch that is on takes the palette’s color_01', () => {
  test('a collection palette: its color_01', () => {
    const { result } = renderHook(() => {
      useCollectionTheeeme(BUSSI);
      return useTheeeme();
    });

    expect(result.current.toggleTheme).toEqual({ '--toggle-button-color': 'var(--color-bus)' });
  });

  test('with nothing declared: the app’s first colour', () => {
    const { result } = renderHook(() => useTheeeme());

    expect(result.current.toggleTheme).toEqual({
      '--toggle-button-color': 'var(--color-braaanding-01)',
    });
  });

  test('a palette with no color_01 gives no theme at all', () => {
    const { result } = renderHook(() => {
      useCollectionTheeeme({ color_02: 'white' });
      return useTheeeme();
    });

    expect(result.current.toggleTheme).toBeUndefined();
  });
});

describe('the content link colour understands the app’s tokens', () => {
  const setApp = (values) => {
    for (const [n, hex] of Object.entries(values)) {
      document.documentElement.style.setProperty(`--color-braaanding-0${n}`, hex);
    }
  };

  test('tokenHex reads a braaanding token from the value the server wrote', () => {
    setApp({ 1: '#191919' });

    expect(tokenHex('braaanding-01')).toBe('#191919');
    expect(tokenHex('braaanding-02')).toBeNull(); // not written: unknown, not a guess
    expect(tokenHex('bus')).toBe('#0000bf');
    expect(tokenHex(undefined)).toBeNull();
  });

  test('color_01 is the link colour when it reads on white and on the page', () => {
    setApp({ 1: '#191919', 2: '#f4e5dd', 4: '#191919' });

    expect(linkColorToken(APP_COLORS)).toBe('braaanding-01');
  });

  test('color_04 is the link colour when color_01 does not read on the page', () => {
    // A pale accent as the primary colour: 1.2:1 on white.
    setApp({ 1: '#ffe977', 2: '#f4e5dd', 4: '#191919' });

    expect(linkColorToken(APP_COLORS)).toBe('braaanding-04');
  });

  test('useTheeeme puts it on the root as --link-color', () => {
    setApp({ 1: '#191919', 2: '#f4e5dd', 4: '#191919' });

    renderHook(() => useTheeeme());

    expect(document.documentElement.style.getPropertyValue('--link-color')).toBe(
      'var(--color-braaanding-01)'
    );
  });

  test('without the served values the link falls back to the text colour, never to nothing', () => {
    expect(linkColorToken(APP_COLORS)).toBe('braaanding-04');
  });
});

describe('what an earlier visit left in the browser is cleared', () => {
  afterEach(() => localStorage.clear());

  test('both retired keys are removed, and nothing else is touched', () => {
    localStorage.setItem('theeemeColors', JSON.stringify(BUSSI));
    localStorage.setItem('koro', 'wave');
    localStorage.setItem('userCode', 'ABC123');
    localStorage.setItem('i18nextLng', 'ca');

    forgetRetiredPreferences();

    expect(RETIRED_KEYS).toEqual(['theeemeColors', 'koro']);
    expect(localStorage.getItem('theeemeColors')).toBeNull();
    expect(localStorage.getItem('koro')).toBeNull();
    expect(localStorage.getItem('userCode')).toBe('ABC123');
    expect(localStorage.getItem('i18nextLng')).toBe('ca');
  });

  test('storage that throws (private mode, blocked data) does not stop the app starting', () => {
    vi.spyOn(Storage.prototype, 'removeItem').mockImplementation(() => {
      throw new Error('blocked');
    });

    expect(() => forgetRetiredPreferences()).not.toThrow();
  });

  test('the app runs it before the first render', () => {
    const main = fs.readFileSync('src/main.jsx', 'utf8');

    expect(main).toContain("from './utils/retiredStorage.js'");
    expect(main.indexOf('forgetRetiredPreferences();')).toBeLessThan(main.indexOf('createRoot('));
  });
});
