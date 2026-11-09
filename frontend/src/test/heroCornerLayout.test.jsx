import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { readFileSync, readdirSync } from 'node:fs';
import { vi, describe, test, expect, beforeEach } from 'vitest';

/**
 * The icon corner of the hero at 320px (2026-09-29). jsdom does no layout, so the
 * overflow itself cannot be measured here; what can be pinned is the contract the two
 * CSS fixes stand on, in the manner of the `padding-right` rule in
 * `CollectionPage.test.jsx`: that the selector matches the DOM the page really paints
 * (rename a class and the rule silently stops applying, nothing red), and that the
 * declarations the fix relies on are the ones in App.css.
 *
 *  1. The account menu's panel ran off the left of the screen. `.account-menu` was
 *     `position: relative`, which anchored the panel to its own trigger, and for a
 *     curator that trigger is the first of four icons. With no positioned ancestor of
 *     its own the panel anchors to `.hero-corners`, whose right edge is the content
 *     column's.
 *  2. A long "← {collection name}" ran underneath the icons. `.hero-corners` is absolute
 *     and reserves nothing, so the back link is capped by the width the corner can take.
 */

window.scrollTo = vi.fn();

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import PageLayout from '../components/PageLayout';
import CollectionPage from '../pages/CollectionPage';
import CollectionSettingsMenu from '../components/CollectionSettingsMenu';
import { press } from './settle';

// ── App.css, as rules ──────────────────────────────────────────────────
const css = readFileSync('src/App.css', 'utf8').replace(/\/\*[\s\S]*?\*\//g, '');

/** The declaration blocks of every rule in `source` whose selector list names `selector`. */
function rulesIn(source, selector) {
  return [...source.matchAll(/([^{}]+)\{([^{}]*)\}/g)]
    .filter(([, list]) =>
      list
        .split(',')
        .map((s) => s.trim())
        .includes(selector)
    )
    .map(([, , body]) => body);
}

/** The same, over the whole stylesheet — rules inside a media query included. */
const rulesFor = (selector) => rulesIn(css, selector);

/** What sits between the braces of every `@media <query> {…}` block (braces balanced). */
function mediaBlocks(query) {
  const head = `@media ${query} {`;
  const blocks = [];
  for (let from = css.indexOf(head); from !== -1; from = css.indexOf(head, from)) {
    let depth = 1;
    let i = from + head.length;
    while (depth > 0 && i < css.length) {
      if (css[i] === '{') depth += 1;
      else if (css[i] === '}') depth -= 1;
      i += 1;
    }
    blocks.push(css.slice(from + head.length, i - 1));
    from = i;
  }
  return blocks;
}

/** The value a block declares for `property`, or undefined. */
const declared = (body, property) =>
  new RegExp(`(?:^|[;\\s])${property}\\s*:\\s*([^;]+)`).exec(body)?.[1]?.trim();

const declarations = (selector, property) =>
  rulesFor(selector)
    .map((body) => declared(body, property))
    .filter((value) => value !== undefined);

// ── The DOM the rules have to match ────────────────────────────────────
beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  vi.clearAllMocks();
});

const renderHero = () =>
  render(
    <MemoryRouter>
      <PageLayout title="A hero" backTo="/collections/COL001" backLabel="Test Collection" />
    </MemoryRouter>
  );

const CURATED = {
  code: 'COL001',
  headline: 'Test Collection',
  description: '',
  status: 'ACTIVE',
  mode: 'PROPRIETARY',
  visibility: 'PRIVATE',
  owner: 'ABC123',
  owner_name: 'Test User',
  is_curator: true,
  language: '',
  thumbnail_url: '',
  tags: [],
  things: [],
  invites: [],
  co_owners: [],
};

describe('the corner of a reader with no session', () => {
  test('holds one control — the "Sign in" link, with the icon trigger’s own class, so the same 44px', () => {
    localStorage.removeItem('userCode');
    const { container } = renderHero();

    const corners = container.querySelector('.hero-corners');
    expect(corners.children).toHaveLength(1);
    const link = corners.querySelector('.account-menu > a');
    expect(link).toHaveAccessibleName('Sign in');
    // The size is declared on the class both the button and the link wear.
    expect(link).toHaveClass('account-menu-trigger');
    expect(declarations('.account-menu-trigger', 'width')).toEqual(['44px']);
    expect(declarations('.account-menu-trigger', 'height')).toEqual(['44px']);
    // …and it is a link, so it needs no underline of its own.
    expect(declarations('a.account-menu-trigger', 'text-decoration')).toEqual(['none']);
  });
});

describe('the account menu panel anchors to the corner row', () => {
  test('the panel sits in .account-menu, which sits directly in .hero-corners', () => {
    const { container } = renderHero();
    fireEvent.click(screen.getByRole('button', { name: /your account/i }));

    const panel = container.querySelector('.account-menu-panel');
    expect(panel).not.toBeNull();
    // Nothing between them for a positioning rule to hang on to but `.account-menu`
    // itself — which is why what that class declares matters.
    expect(panel.parentElement).toHaveClass('account-menu');
    expect(panel.parentElement.parentElement).toHaveClass('hero-corners');
  });

  test('.account-menu establishes no containing block of its own', () => {
    // Anything below would make the panel anchor to the trigger again. (`position` is
    // the one that was there; the rest are the other ways to become a containing block
    // for an absolutely positioned descendant.)
    const containingBlockMakers = [
      'position',
      'transform',
      'filter',
      'perspective',
      'contain',
      'will-change',
    ];
    for (const property of containingBlockMakers) {
      expect(declarations('.account-menu', property), property).toEqual([]);
    }
  });

  test('.hero-corners is the positioned ancestor, and the panel is pinned to its right edge', () => {
    expect(declarations('.hero-corners', 'position')).toEqual(['absolute']);
    expect(declarations('.account-menu-panel', 'position')).toEqual(['absolute']);
    expect(declarations('.account-menu-panel', 'right')).toEqual(['0']);
    // Whatever the row's width, the panel is never wider than the screen minus gutters.
    expect(declarations('.account-menu-panel', 'max-width')).toEqual([
      'calc(100vw - 2 * var(--spacing-s))',
    ]);
  });
});

describe('the back link keeps out from under the corner icons', () => {
  test('the rule names an element that sits beside the corner row in the hero', () => {
    const { container } = renderHero();

    const backLink = container.querySelector('.form-hero-content .back-link');
    expect(backLink).not.toBeNull();
    expect(backLink.parentElement).toHaveClass('form-hero-content');
    // The thing it has to make room for is its sibling in the same column.
    expect(backLink.parentElement.querySelector(':scope > .hero-corners')).not.toBeNull();
  });

  test('it is capped by the width the corner can take, plus a gap', () => {
    const caps = declarations('.form-hero-content .back-link', 'max-width');
    expect(caps).toEqual(['calc(100% - var(--hero-corners-width) - var(--spacing-xs))']);
  });

  test('that width is the widest corner there is, worked out again from the DOM and the rules', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => CURATED })
    );
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByRole('button', { name: /share collection/i }); // a curator's hero is loaded
    // A curator gets every control a hero can hold: account, settings, collection, share.
    const controls = container.querySelector('.hero-corners').children.length;
    expect(controls).toBe(4);

    // The collection's own hero is the one that carries the settings class, and it
    // reserves exactly the controls it paints.
    expect(container.querySelector('.form-hero-content')).toHaveClass(
      'form-hero-content--settings'
    );
    const widthOf = (selector) => {
      const [declared] = declarations(selector, '--hero-corners-width');
      const [, count, size, gaps] =
        /^calc\((\d+) \* (\d+)px \+ (\d+) \* var\(--spacing-2-xs\)\)$/.exec(declared) ?? [];
      return { count: Number(count), size, gaps: Number(gaps) };
    };
    const own = widthOf('.form-hero-content.form-hero-content--settings');
    // Four controls, each as wide as the CSS says an icon control is, and the gaps
    // between them (one fewer) at the row's own `gap`.
    expect(own.count).toBe(controls);
    expect(own.gaps).toBe(controls - 1);
    for (const selector of [
      '.account-menu-trigger',
      '.collection-settings-menu-trigger',
      '.collection-menu-trigger',
      '.share-menu-trigger',
    ]) {
      expect(declarations(selector, 'width'), selector).toEqual([`${own.size}px`]);
    }

    // Every other hero reserves the three controls a page without a settings menu can
    // hold (account, collection, share): the settings icon is not one of them.
    const rest = widthOf('.form-hero-content');
    expect(rest.count).toBe(controls - 1);
    expect(rest.gaps).toBe(controls - 2);
    expect(rest.size).toBe(own.size);
    expect(declarations('.hero-corners', 'gap')).toEqual(['var(--spacing-2-xs)']);
  });
});

describe('the collection menu panel anchors to the corner row like the account menu', () => {
  test('the corner row reads account · settings · collection · share, left to right', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => CURATED })
    );
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByRole('button', { name: /share collection/i }); // a curator's hero has loaded

    // DOM order is visual order in a flex row: each control is the child that is,
    // or holds, its own marker.
    const markers = [
      '.account-menu',
      '.collection-settings-menu',
      '.collection-menu',
      '.share-menu',
    ];
    const order = [...container.querySelector('.hero-corners').children].map((child) =>
      markers.find((marker) => child.matches(marker) || child.querySelector(marker))
    );
    expect(order).toEqual(markers);
  });

  test('the panel sits in .collection-menu, which sits directly in .hero-corners', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => CURATED })
    );
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await press(await screen.findByRole('button', { name: /collection options/i }));

    const panel = container.querySelector('.collection-menu-panel');
    expect(panel).not.toBeNull();
    expect(panel.parentElement).toHaveClass('collection-menu');
    expect(panel.parentElement.parentElement).toHaveClass('hero-corners');
  });

  test('.collection-menu establishes no containing block of its own', () => {
    // Same rule as .account-menu above: with one of its own, the panel would
    // anchor to its trigger again and run off a narrow screen.
    const containingBlockMakers = [
      'position',
      'transform',
      'filter',
      'perspective',
      'contain',
      'will-change',
    ];
    for (const property of containingBlockMakers) {
      expect(declarations('.collection-menu', property), property).toEqual([]);
    }
  });

  test("the panel is pinned to the row's right edge, never wider than the screen", () => {
    expect(declarations('.collection-menu-panel', 'position')).toEqual(['absolute']);
    expect(declarations('.collection-menu-panel', 'right')).toEqual(['0']);
    expect(declarations('.collection-menu-panel', 'max-width')).toEqual([
      'calc(100vw - 2 * var(--spacing-s))',
    ]);
  });
});

describe('the settings menu panel anchors to the corner row like the others', () => {
  test('.collection-settings-menu establishes no containing block of its own', () => {
    for (const property of [
      'position',
      'transform',
      'filter',
      'perspective',
      'contain',
      'will-change',
    ]) {
      expect(declarations('.collection-settings-menu', property), property).toEqual([]);
    }
  });

  test("the panel is pinned to the row's right edge, never wider than the screen", () => {
    expect(declarations('.collection-settings-menu-panel', 'position')).toEqual(['absolute']);
    expect(declarations('.collection-settings-menu-panel', 'right')).toEqual(['0']);
    expect(declarations('.collection-settings-menu-panel', 'max-width')).toEqual([
      'calc(100vw - 2 * var(--spacing-s))',
    ]);
  });

  test('the panel sits in .collection-settings-menu, directly in .hero-corners', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => CURATED })
    );
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await press(await screen.findByRole('button', { name: 'Settings' }));

    const panel = container.querySelector('.collection-settings-menu-panel');
    expect(panel).not.toBeNull();
    expect(panel.parentElement).toHaveClass('collection-settings-menu');
    expect(panel.parentElement.parentElement).toHaveClass('hero-corners');
  });
});

describe('who gets the settings menu', () => {
  const renderAs = async (collection) => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => collection })
    );
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByRole('button', { name: /collection options/i });
  };

  test('a curator has it', async () => {
    await renderAs(CURATED);
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument();
  });

  test('a co-curator has it too: is_curator is the server’s word for both', async () => {
    await renderAs({ ...CURATED, owner: 'OTHER1', co_owners: [{ code: 'ABC123', name: 'Me' }] });
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument();
  });

  // No `kind`: with one the page redirects to its kind's address, which these routes
  // do not mount, and the hero would vanish mid-test.
  const NETWORK = { ...CURATED, mode: 'NETWORK' };

  test('in a network a dinamizador has no settings: they are the founder’s, and so is "General"', async () => {
    await renderAs({ ...NETWORK, owner: 'OTHER1', co_owners: [{ code: 'ABC123', name: 'Me' }] });

    expect(screen.queryByRole('button', { name: 'Settings' })).toBeNull();
    // They still run the group: the other curator menu is there.
    expect(screen.getByRole('button', { name: /collection options/i })).toBeInTheDocument();
  });

  test('in a network the founder has the settings', async () => {
    await renderAs(NETWORK); // the viewer (ABC123) is the founder

    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument();
  });

  test('outside a network a co-curator keeps the settings', async () => {
    await renderAs({ ...CURATED, owner: 'OTHER1', co_owners: [{ code: 'ABC123', name: 'Me' }] });
    expect(screen.getByRole('button', { name: 'Settings' })).toBeInTheDocument();
  });

  test('a member who does not run the group has no settings', async () => {
    await renderAs({ ...CURATED, owner: 'OTHER1', is_curator: false, is_member: true });
    expect(screen.queryByRole('button', { name: 'Settings' })).toBeNull();
    // …while their own collection menu is still there.
    expect(screen.getByRole('button', { name: /collection options/i })).toBeInTheDocument();
  });

  test('a stall, a library and a shed all offer Appearance', async () => {
    for (const kind of ['STALL', 'LIBRARY', 'SHED']) {
      const { unmount } = render(
        <MemoryRouter>
          <CollectionSettingsMenu code="COL001" kind={kind} />
        </MemoryRouter>
      );
      await press(screen.getByRole('button', { name: 'Settings' }));
      expect(screen.getByRole('link', { name: 'Appearance' })).toHaveAttribute(
        'href',
        `/${kind.toLowerCase()}/COL001/settings/appearance`
      );
      unmount();
    }
  });
});

describe('the share menu panel anchors to the corner row, and fits a 320px screen', () => {
  test('.share-menu establishes no containing block of its own', () => {
    // As .account-menu and .collection-menu: with one of its own, the panel would
    // anchor to its trigger (the last of the row) and could run off a narrow screen.
    for (const property of [
      'position',
      'transform',
      'filter',
      'perspective',
      'contain',
      'will-change',
    ]) {
      expect(declarations('.share-menu', property), property).toEqual([]);
    }
  });

  test("the panel is pinned to the row's right edge, never wider than the screen", () => {
    // At 320px the screen minus the page's two side paddings is 288px: the panel
    // (min-width 12rem, the widest label "Copy invite link" + icon) fits inside it.
    expect(declarations('.share-menu-panel', 'position')).toEqual(['absolute']);
    expect(declarations('.share-menu-panel', 'right')).toEqual(['0']);
    expect(declarations('.share-menu-panel', 'min-width')).toEqual(['12rem']);
    expect(declarations('.share-menu-panel', 'max-width')).toEqual([
      'calc(100vw - 2 * var(--spacing-s))',
    ]);
  });

  test('the panel is a child of .share-menu, which sits directly in .hero-corners', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => CURATED })
    );
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await press(await screen.findByRole('button', { name: /share collection/i }));

    const panel = container.querySelector('.share-menu-panel');
    expect(panel).not.toBeNull();
    expect(panel.parentElement).toHaveClass('share-menu');
    expect(panel.parentElement.parentElement).toHaveClass('hero-corners');
  });
});

/**
 * The hero photo on a wide screen. jsdom does no layout, so what
 * is pinned is the contract of the rule: `.hero-photo-wrap` is a background that
 * ran to the window's edge while the content column, centred from 1248px up, did
 * not; its right edge now comes in by the same centring sum `.hero-corners` uses.
 * It belongs inside `@media (min-width: 768px)` — below that the photo is a static
 * block on the phone, and an `inset` there would move a box that has no edges.
 */
describe('the hero photo ends at the content column on a wide screen', () => {
  const wide = '(min-width: 768px)';
  const photoRightIn = (blocks) =>
    blocks.flatMap((block) =>
      rulesIn(block, '.hero-photo-wrap')
        .map((body) => declared(body, 'right'))
        .filter((value) => value !== undefined)
    );

  test('.hero-photo-wrap declares its right edge inside the ≥768px query, and only there', () => {
    const inWide = photoRightIn(mediaBlocks(wide));

    expect(inWide).toHaveLength(1);
    // The one declaration in the whole stylesheet: a copy outside the query (or in
    // the phone's) would take the phone's stacked photo along with it.
    expect(declarations('.hero-photo-wrap', 'right')).toEqual(inWide);
  });

  test("it is the corner row's own centring sum, without the corner's gutter", () => {
    const [corner] = declarations('.hero-corners', 'right');
    expect(corner).toMatch(/ \+ var\(--page-margin\)\)$/);

    const [photo] = photoRightIn(mediaBlocks(wide));
    expect(photo).toBe(corner.replace(/ \+ var\(--page-margin\)\)$/, ')'));
    // And it is the sum that is 0 up to the column's own width.
    expect(photo).toBe('calc((100% - min(100%, 1248px)) / 2)');
  });

  test("the left edge (30%) is still the base rule's", () => {
    expect(declarations('.hero-photo-wrap', 'inset')).toContain('0 0 0 30%');
  });
});

/**
 * The contact icon is not in any hero (there were too many icons up
 * there): "Contact us" is the site footer's third door. Pinned on the two heroes
 * that paint the corner for everybody — `PageLayout` and a curator's collection,
 * the fullest one — by what is inside `.hero-corners` and by what a hero links at
 * all, and by the source: nothing in `src/` names the old component.
 */
describe('no hero carries the contact icon', () => {
  const contactLinks = (root) => root.querySelectorAll('a[href="/contact"]');

  test('PageLayout’s hero links nowhere to /contact', () => {
    const { container } = renderHero();

    expect(container.querySelector('.hero-corners')).not.toBeNull();
    expect(contactLinks(container.querySelector('.form-hero'))).toHaveLength(0);
  });

  test('a curator’s collection hero, with every corner control, links nowhere to /contact', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => CURATED })
    );
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByRole('button', { name: /share collection/i });

    expect(container.querySelector('.hero-corners').children).toHaveLength(4);
    expect(contactLinks(container.querySelector('.form-hero'))).toHaveLength(0);
  });

  test('nothing in the sources names the component or its rule any more', () => {
    const files = [];
    const walk = (dir) => {
      for (const entry of readdirSync(dir, { withFileTypes: true })) {
        const path = `${dir}/${entry.name}`;
        if (entry.isDirectory()) walk(path);
        else if (/\.(jsx?|css)$/.test(entry.name) && !/\.test\./.test(entry.name)) files.push(path);
      }
    };
    walk('src');

    const offenders = files.filter((file) =>
      /ContactCorner|contact-corner/.test(
        readFileSync(file, 'utf8')
          .replace(/\/\*[\s\S]*?\*\//g, '')
          .replace(/^\s*(\/\/|\*).*$/gm, '')
      )
    );
    expect(offenders).toEqual([]);
  });
});
