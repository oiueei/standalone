import { readFileSync } from 'node:fs';
import { render, screen, waitFor, fireEvent, within, act } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import en from '../i18n/locales/en.json';
import { settle, switchLanguage } from '../test/settle';

expect.extend(toHaveNoViolations);

// The busier hero (headline + tags + owner buttons + share menu) is what the hero photo
// composition is added on top of — HeroPhoto itself is unit-tested
// separately (HeroPhoto.test.jsx); this checks the combination doesn't
// introduce an axe violation the way the shared smoke.test.jsx fixture
// (thumbnail_url: '') never exercises.
const COLLECTION_WITH_PHOTO = {
  code: 'COL001',
  headline: 'Kitchen Collection',
  description: 'Things from the kitchen',
  status: 'ACTIVE',
  visibility: 'PRIVATE',
  mode: 'PROPRIETARY',
  owner: 'ABC123',
  owner_name: 'Test User',
  is_curator: true,
  thumbnail_url: 'https://bucket.your-domain.test/oiueei/collections/cover.jpg',
  tags: [],
  things: [],
  invites: [],
  is_paused: false,
  allowed_thing_types: [],
};

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(COLLECTION_WITH_PHOTO) })
  ),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import CollectionPage from './CollectionPage';
import declarePalette from '../test/declarePalette';

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  // Each test asserts on the exact calls it caused; without this the previous
  // test's POSTs are still in the log and `find(...)` picks the wrong one.
  vi.clearAllMocks();
});

describe('CollectionPage with a collection thumbnail', () => {
  test('renders the logo hero with no accessibility violations', async () => {
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(container.querySelector('img.hero-logo')).toBeTruthy();
    });
    expect(container.querySelector('img.hero-logo')).toHaveAttribute(
      'src',
      COLLECTION_WITH_PHOTO.thumbnail_url
    );

    await settle(apiFetch);
    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });

  /**
   * The "Things" heading is visually hidden but still in the outline.
   * Every card below is an <h3> (ThingLinkbox's default) that counts
   * on an <h2> above it, so deleting the heading — rather than hiding it — turns
   * the page into <h1> → <h3>, which axe's heading-order flags. Both halves are
   * pinned: that it is hidden, and that the outline it protects is intact.
   */
  describe('CollectionPage things heading', () => {
    const WITH_A_THING = {
      ...COLLECTION_WITH_PHOTO,
      thumbnail_url: '',
      things: [
        {
          code: 'THG001',
          headline: 'Blender',
          type: 'GIFT_THING',
          status: 'ACTIVE',
          owner: 'ABC123',
          owner_name: 'Test User',
          created: '2026-07-01T10:00:00Z',
          tags: [],
          gallery_urls: [],
        },
      ],
    };

    const renderPage = async () => {
      apiFetch.mockImplementation((url) =>
        url.startsWith('/api/v1/inbox/')
          ? Promise.resolve({ ok: true, status: 200, json: async () => [] })
          : Promise.resolve({ ok: true, status: 200, json: async () => WITH_A_THING })
      );
      const utils = render(
        <MemoryRouter initialEntries={['/collections/COL001']}>
          <Routes>
            <Route path="/collections/:code" element={<CollectionPage />} />
          </Routes>
        </MemoryRouter>
      );
      await screen.findByRole('heading', { level: 3, name: 'Blender' });
      return utils;
    };

    test('is a level-2 heading that is visually hidden', async () => {
      await renderPage();

      const heading = screen.getByRole('heading', { level: 2, name: 'Things' });
      expect(heading).toHaveClass('sr-only');
    });

    test('keeps the outline whole: h1, the hidden h2, then the cards at h3', async () => {
      const { container } = await renderPage();

      const levels = [...container.querySelectorAll('h1, h2, h3')].map((h) => h.tagName);
      expect(levels).toEqual(['H1', 'H2', 'H3']);
      await settle(apiFetch);
      expect(await axe(container)).toHaveNoViolations();
    });
  });

  /**
   * The image is the collection's logo, not a backdrop: an ordinary `<img>` before
   * the title, with no alt (the `<h1>` names the collection), and none of the
   * photo composition. jsdom does no layout; the widths and the place it takes are
   * pinned against the stylesheet in `test/collectionLogo.test.jsx`.
   */
  describe('the logo', () => {
    const renderPage = async (collection) => {
      apiFetch.mockImplementation(() =>
        Promise.resolve({ ok: true, status: 200, json: async () => collection })
      );
      const utils = render(
        <MemoryRouter initialEntries={['/collections/COL001']}>
          <Routes>
            <Route path="/collections/:code" element={<CollectionPage />} />
          </Routes>
        </MemoryRouter>
      );
      await screen.findByText('Things from the kitchen');
      return utils;
    };

    test('is a plain image of the thumbnail, before the title, with no alt', async () => {
      const { container } = await renderPage(COLLECTION_WITH_PHOTO);

      const logo = container.querySelector('img.hero-logo');
      expect(logo).toHaveAttribute('src', COLLECTION_WITH_PHOTO.thumbnail_url);
      expect(logo).toHaveAttribute('alt', '');
      const title = container.querySelector('h1.form-hero-title');
      expect(logo.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    test('the photo composition is gone from a collection', async () => {
      const { container } = await renderPage(COLLECTION_WITH_PHOTO);

      expect(container.querySelector('.form-hero--photo')).toBeNull();
      expect(container.querySelector('.hero-photo-wrap')).toBeNull();
      expect(container.querySelector('.hero-photo-diag')).toBeNull();
      expect(container.querySelector('.form-hero')).toHaveClass('form-hero--collection');
    });

    test('without a thumbnail there is no image in the hero', async () => {
      const { container } = await renderPage({ ...COLLECTION_WITH_PHOTO, thumbnail_url: '' });

      expect(container.querySelector('.hero-logo')).toBeNull();
      expect(container.querySelector('.form-hero img')).toBeNull();
    });

    test('the padding that keeps text off a photo background is still only behind 768px', () => {
      // `.form-hero--photo` is now the profile's and the join page's; the rule stays
      // for them and must not reach a phone.
      const css = readFileSync('src/App.css', 'utf8');
      const selector = '.form-hero--photo .markdown-text.form-hero-text';
      expect(css.split(selector).length - 1).toBe(1);
      const gated = new RegExp(
        String.raw`@media \(min-width: 768px\)\s*\{\s*` +
          selector.replaceAll('.', String.raw`\.`) +
          String.raw`\s*\{[^}]*padding-right:`
      );
      expect(css).toMatch(gated);
    });
  });
});

describe('CollectionPage hero corners', () => {
  /**
   * The icon-only controls that can share the hero's top-right corner: the
   * account menu (any signed-in visitor), the collection menu (curators
   * only, 2026-10-03) and the share menu. They sit together in one
   * `.hero-corners` flex row instead of each computing its own absolute
   * offset — this pins that a curator gets all three and a plain member gets
   * the ones that apply to them, not a gap where the share menu used to
   * reserve its slot. The contact icon that was a fourth went to the site
   * footer on 2026-10-04: no hero links `/contact` from its corner.
   */
  const contactInCorner = () => document.querySelector('.hero-corners a[href="/contact"]');

  function renderCollection(collection) {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => collection })
    );
    return render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
  }

  test('a curator gets the account menu, the collection menu and the share menu — and no contact link', async () => {
    renderCollection(COLLECTION_WITH_PHOTO); // is_curator: true
    await screen.findByText('Things from the kitchen');

    expect(screen.getByRole('button', { name: /your account/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /collection options/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Share collection' })).toBeInTheDocument(); // ShareCollectionMenu
    expect(contactInCorner()).toBeNull();
    expect(screen.queryByRole('link', { name: /contact us/i })).toBeNull();
  });

  const MEMBER_VIEW = {
    ...COLLECTION_WITH_PHOTO,
    owner: 'OTHER1',
    is_curator: false,
    is_member: true,
  };

  test('a member of a PRIVATE group gets the account menu, never the share menu', async () => {
    // There the link is the curators' credential; the member has "Recommend".
    renderCollection({ ...MEMBER_VIEW, visibility: 'PRIVATE' });
    await screen.findByText('Things from the kitchen');

    expect(screen.getByRole('button', { name: /your account/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Share collection' })).not.toBeInTheDocument();
    expect(contactInCorner()).toBeNull();
  });

  // A PUBLIC group is shared by its own address, so a member can
  // bring people in without holding anything a curator would have to pull back.
  test('a member of a PUBLIC group gets the share menu too — both controls, in the corner', async () => {
    renderCollection({ ...MEMBER_VIEW, visibility: 'PUBLIC' });
    await screen.findByText('Things from the kitchen');

    expect(screen.getByRole('button', { name: /your account/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Share collection' })).toBeInTheDocument(); // ShareCollectionMenu
    expect(contactInCorner()).toBeNull();
  });

  test("a member's share menu has no Rotate or Stop sharing, and shares without calling share-link", async () => {
    const writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, 'clipboard', { configurable: true, value: { writeText } });
    renderCollection({ ...MEMBER_VIEW, visibility: 'PUBLIC' });
    await screen.findByText('Things from the kitchen');

    fireEvent.click(screen.getByRole('button', { name: 'Share collection' }));
    expect(screen.queryByRole('button', { name: /rotate link/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /stop sharing/i })).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Copy invite link' }));
    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/collections/COL001`)
    );
    expect(apiFetch.mock.calls.some(([url]) => String(url).includes('/share-link/'))).toBe(false);
  });

  test('a signed-out reader of a PUBLIC group gets no share menu', async () => {
    localStorage.clear();
    renderCollection({ ...MEMBER_VIEW, visibility: 'PUBLIC', is_member: false });
    await screen.findByText('Things from the kitchen');

    expect(screen.queryByRole('button', { name: 'Share collection' })).not.toBeInTheDocument();
    expect(contactInCorner()).toBeNull();
  });

  test('a signed-in reader who is not in a PUBLIC group gets no share menu either', async () => {
    renderCollection({ ...MEMBER_VIEW, visibility: 'PUBLIC', is_member: false });
    await screen.findByText('Things from the kitchen');

    expect(screen.queryByRole('button', { name: 'Share collection' })).not.toBeInTheDocument();
  });
});

describe('CollectionPage signed-out reader', () => {
  /**
   * The hero's "This group shares its things on OIUEEI. Join to take part →"
   * line was removed, a line in the content stood in for it for a while, and the
   * hero now has one door: `[Sign in]`, primary, to the group's join page, which
   * also keeps the account icon out of the corner of this page.
   * The tests of every shape of group are further down (`the one door of a
   * signed-out reader`); this one is the hero of a plain public group.
   *
   * Asserted through the links' targets and the raw i18n key — the old line's
   * strings went with it, so a resurrected `t('collectionPage.anonIntro')`
   * renders its own key and an English-text query would pass for the wrong reason.
   */
  const PUBLIC_VIEW = {
    ...COLLECTION_WITH_PHOTO,
    thumbnail_url: '',
    visibility: 'PUBLIC',
    owner: 'OTHER1',
    is_curator: false,
    is_member: false,
  };

  test('is offered one "Sign in" door to the join page in the hero, and no standing line', async () => {
    localStorage.clear();
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => PUBLIC_VIEW })
    );
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(container.querySelector('.form-hero-title')).toHaveTextContent('Kitchen Collection');
    });
    const doors = [...container.querySelectorAll('.form-hero .button-row-wide a')];
    expect(doors.map((a) => a.textContent)).toEqual(['Sign in']);
    expect(doors.map((a) => a.getAttribute('href'))).toEqual(['/collections/COL001/join']);
    // The primary: the theeeme's fill, not the white of a secondary.
    expect(doors[0].style.getPropertyValue('--background-color')).not.toBe('var(--color-white)');
    expect(container.textContent).not.toMatch(/collectionPage\.anonIntro/);
  });
});

describe('CollectionPage inactive-things grid', () => {
  // The inactive grid used to build its own inline `onUpdateThing` instead of
  // sharing the page's useCallback'd one. Both did the same work, so the bug it
  // could hide is silent: hand the wrong callback (or none) to these cards and
  // reactivating a hidden thing still POSTs and still succeeds, but the card
  // never leaves the "Inactive things" section — the owner clicks Reactivate
  // again, and again. This pins that the card's update actually reaches the
  // page's state.
  const HIDDEN_THING = {
    code: 'THG001',
    headline: 'Old blender',
    type: 'GIFT_THING',
    status: 'INACTIVE',
    owner: 'ABC123',
    owner_name: 'Test User',
    created: '2026-07-01T10:00:00Z',
    tags: [],
    gallery_urls: [],
  };
  const COLLECTION_WITH_HIDDEN = {
    ...COLLECTION_WITH_PHOTO,
    thumbnail_url: '',
    things: [HIDDEN_THING],
  };

  test('reactivating a hidden thing moves it out of the hidden section', async () => {
    const { apiFetch } = await import('../services/api');
    apiFetch.mockImplementation((url) => {
      if (url.includes('/activate/')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(COLLECTION_WITH_HIDDEN),
      });
    });

    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    // It starts under "Hidden things", carrying the owner-only Inactive tag.
    await screen.findByRole('heading', { name: 'Inactive things' });
    expect(screen.getByText('Old blender')).toBeInTheDocument();
    expect(screen.getByText('Inactive')).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Reactivate' }));

    // The section disappears with its last member — proof the card's patch
    // landed in the page's `things` state, not in a detached copy.
    await waitFor(() => {
      expect(screen.queryByRole('heading', { name: 'Inactive things' })).toBeNull();
    });
    expect(screen.queryByText('Inactive')).toBeNull();
    expect(screen.getByText('Old blender')).toBeInTheDocument();
  });
});

describe('CollectionPage member hero', () => {
  const MEMBER_VIEW = {
    ...COLLECTION_WITH_PHOTO,
    thumbnail_url: '',
    owner: 'OTHER1',
    is_member: true,
    // A plain member of somebody else's group, not a curator — override
    // rather than inherit COLLECTION_WITH_PHOTO's true.
    is_curator: false,
    digest_frequency: 'WEEKLY',
    is_digest_muted: false,
    allow_member_proposals: true,
  };

  function mockPage(collection) {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => collection })
    );
    return apiFetch;
  }

  function renderCollection() {
    return render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
  }

  /**
   * The per-group "You get a summary of what's new here — turn it off" line
   * left the hero: a sentence about email, in the one place a
   * member comes to look at things. Muting a group is still one click from the
   * footer of every digest (`DigestMutePage`), and the endpoint behind the old
   * switch is untouched, so this is only about what the page offers. A member has
   * the switch again, as an entry of the collection menu
   * (`collectionMenu.test.jsx`): the hero still has none, and nothing is sent
   * until it is pressed.
   *
   * Asserted three ways, because each alone can be fooled: the class the block
   * carried, the raw i18n key (the strings were deleted with the block, so a
   * resurrected `t('collectionPage.digestSubscribed')` renders its own key —
   * an English-text assertion would pass for the wrong reason), and the one
   * thing the switch could do, which is send a POST.
   */
  test.each([
    ['a member of a group that sends a digest', MEMBER_VIEW],
    ['a member who had muted it', { ...MEMBER_VIEW, is_digest_muted: true }],
    [
      'a co-curator, who is still an ordinary invitee for the digest',
      { ...MEMBER_VIEW, is_member: false, is_curator: true },
    ],
  ])('%s is offered no digest switch', async (_who, view) => {
    const fetchMock = mockPage(view);
    const { container } = renderCollection();
    await screen.findByText('Things from the kitchen');

    expect(container.querySelector('.digest-pref')).toBeNull();
    expect(container.textContent).not.toMatch(/collectionPage\.digest/);
    expect(screen.queryByRole('button', { name: /turn it off|turn them back on/i })).toBeNull();
    expect(fetchMock.mock.calls.some(([, o]) => o?.method === 'POST')).toBe(false);
  });

  /**
   * Leaving moved out of this hero to the own
   * profile's "My groups" list. Its new home is well covered (`myGroups.test`);
   * the place it left was not, so a resurrected link would put the one
   * destructive control back where it was third in a stack of unlabelled text
   * links under the description — and nothing would go red.
   *
   * Asserted against the *route*, not a label: the point is that no control
   * here leads to the leave confirm, whatever it ends up being called.
   */
  test('a member is given no way out of the group from the collection hero', async () => {
    mockPage(MEMBER_VIEW);
    const { container } = renderCollection();
    // A member-only hero control that stayed — so this is a page where the
    // leave link *would* render, not one where the member section is missing.
    await screen.findByRole('button', { name: 'Invite someone' });

    expect(container.querySelector('a[href="/collections/COL001/leave"]')).toBeNull();
    expect(screen.queryByRole('link', { name: /leave the group/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /leave the group/i })).toBeNull();
  });
});

/**
 * A member's two hero controls, in one row: "Invite someone"
 * first, primary, and "Add thing" after it, secondary — each on its own
 * condition, no row when neither applies. "Invite someone" opens the recommend
 * form *below* the row and stays on screen while it is open, so the same button
 * closes it. The form itself still says "Recommend" and that whoever runs the
 * group decides (`recommendGuest.test.jsx`): the button outside promises less
 * than the word on it, and the form is what keeps the promise honest.
 */
describe('CollectionPage — the member row: "Invite someone" and "Add thing"', () => {
  const MEMBER = {
    ...COLLECTION_WITH_PHOTO,
    thumbnail_url: '',
    owner: 'OTHER1',
    is_member: true,
    is_curator: false,
    mode: 'PROPRIETARY',
    allow_member_proposals: true,
  };

  function renderAs(collection) {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => collection })
    );
    return render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
  }

  const invite = () => screen.getByRole('button', { name: 'Invite someone' });
  const rowOf = (el) => [...el.closest('.button-row-wide').querySelectorAll('a, button')];

  test('the button opens the form below the row, stays there, and closes it again', async () => {
    renderAs(MEMBER);
    await screen.findByRole('button', { name: 'Invite someone' });
    expect(invite()).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByLabelText(/Their email/i)).toBeNull();

    fireEvent.click(invite());

    // Still on the page — the form did not replace it — and now says what it controls.
    expect(invite()).toHaveAttribute('aria-expanded', 'true');
    const form = document.getElementById(invite().getAttribute('aria-controls'));
    expect(form).toContainElement(screen.getByLabelText(/Their email/i));
    // Below the row, not inside it.
    expect(invite().closest('.button-row-wide')).not.toContainElement(form);

    fireEvent.click(invite());

    expect(invite()).toHaveAttribute('aria-expanded', 'false');
    expect(invite()).not.toHaveAttribute('aria-controls');
    expect(screen.queryByLabelText(/Their email/i)).toBeNull();
  });

  test('"Close" inside the form closes it and leaves the focus on the button', async () => {
    renderAs(MEMBER);
    await screen.findByRole('button', { name: 'Invite someone' });
    fireEvent.click(invite());

    fireEvent.click(screen.getByRole('button', { name: 'Close' }));

    expect(screen.queryByLabelText(/Their email/i)).toBeNull();
    expect(invite()).toHaveFocus();
  });

  test('a COMMUNITY group with recommendations: "Invite someone" before "Add thing", in one row', async () => {
    renderAs({ ...MEMBER, mode: 'COMMUNITY' });
    await screen.findByRole('button', { name: 'Invite someone' });

    const row = rowOf(invite());
    expect(row.map((el) => el.textContent.trim())).toEqual(['Invite someone', 'Add thing']);
    expect(row[1]).toHaveAttribute('href', '/collections/COL001/add');
  });

  test('a PROPRIETARY group with recommendations: only "Invite someone"', async () => {
    renderAs(MEMBER);
    await screen.findByRole('button', { name: 'Invite someone' });

    expect(rowOf(invite()).map((el) => el.textContent.trim())).toEqual(['Invite someone']);
    expect(screen.queryByRole('link', { name: 'Add thing' })).toBeNull();
  });

  test('a COMMUNITY group without recommendations: only "Add thing"', async () => {
    renderAs({ ...MEMBER, mode: 'COMMUNITY', allow_member_proposals: false });
    const add = await screen.findByRole('link', { name: 'Add thing' });

    expect(rowOf(add).map((el) => el.textContent.trim())).toEqual(['Add thing']);
    expect(screen.queryByRole('button', { name: 'Invite someone' })).toBeNull();
  });

  test('a PROPRIETARY group without recommendations: no row at all', async () => {
    const { container } = renderAs({ ...MEMBER, allow_member_proposals: false });
    await screen.findByText('Things from the kitchen');

    expect(container.querySelector('.button-row-wide')).toBeNull();
  });

  // A demo collection is shared data nobody is invited into: the member's way out
  // stands where "Invite someone" would be.
  describe('in a demo collection', () => {
    const DEMO = { ...MEMBER, is_onboarding: true };

    const LeaveProbe = () => {
      const location = useLocation();
      return <p>left with {location.state?.headline}</p>;
    };

    test('"Leave the group" replaces "Invite someone" and leads to the leave page', async () => {
      apiFetch.mockImplementation(() =>
        Promise.resolve({ ok: true, status: 200, json: async () => DEMO })
      );
      render(
        <MemoryRouter initialEntries={['/collections/COL001']}>
          <Routes>
            <Route path="/collections/:code" element={<CollectionPage />} />
            <Route path="/collections/:code/leave" element={<LeaveProbe />} />
          </Routes>
        </MemoryRouter>
      );
      const leave = await screen.findByRole('link', { name: 'Leave the group' });

      expect(leave).toHaveAttribute('href', '/collections/COL001/leave');
      expect(screen.queryByRole('button', { name: 'Invite someone' })).toBeNull();
      expect(screen.queryByLabelText(/Their email/i)).toBeNull();
      expect(rowOf(leave).map((el) => el.textContent.trim())).toEqual(['Leave the group']);

      fireEvent.click(leave);
      expect(await screen.findByText('left with Kitchen Collection')).toBeInTheDocument();
    });

    test('in a COMMUNITY demo it comes after "Add thing"', async () => {
      renderAs({ ...DEMO, mode: 'COMMUNITY' });
      const leave = await screen.findByRole('link', { name: 'Leave the group' });

      expect(rowOf(leave).map((el) => el.textContent.trim())).toEqual([
        'Add thing',
        'Leave the group',
      ]);
    });

    test('it shows even when the group takes no recommendations', async () => {
      renderAs({ ...DEMO, allow_member_proposals: false });

      expect(await screen.findByRole('link', { name: 'Leave the group' })).toBeInTheDocument();
    });

    test('a curator of a demo is untouched: no "Leave the group" in the hero', async () => {
      renderAs({ ...DEMO, owner: 'ABC123', is_member: false, is_curator: true });
      await screen.findByText('Things from the kitchen');

      expect(screen.queryByRole('link', { name: 'Leave the group' })).toBeNull();
    });

    test('a collection that is not a demo keeps "Invite someone" and has no "Leave the group"', async () => {
      renderAs({ ...MEMBER, is_onboarding: false });
      await screen.findByRole('button', { name: 'Invite someone' });

      expect(screen.queryByRole('link', { name: 'Leave the group' })).toBeNull();
    });
  });

  test('a member of a group run by a team reads the curators in the form, not the founder', async () => {
    renderAs({ ...MEMBER, co_owners: [{ code: 'CO0001', name: 'Co Curator' }] });
    await screen.findByRole('button', { name: 'Invite someone' });
    fireEvent.click(invite());

    expect(screen.getByText(/The curators decide/)).toBeInTheDocument();
    expect(screen.queryByText(/Test User decides/)).toBeNull();
  });

  test('a member of a group with no co-curators reads the founder by name', async () => {
    renderAs(MEMBER);
    await screen.findByRole('button', { name: 'Invite someone' });
    fireEvent.click(invite());

    expect(screen.getByText(/Test User decides/)).toBeInTheDocument();
    expect(screen.queryByText(/The curators decide/)).toBeNull();
  });

  test('whoever runs the group has no member row: no "Invite someone", and one "Add thing" — the curator row’s', async () => {
    renderAs({
      ...MEMBER,
      mode: 'COMMUNITY',
      is_curator: true,
      is_member: false,
    });
    await screen.findByRole('link', { name: 'Edit collection' });

    expect(screen.queryByRole('button', { name: 'Invite someone' })).toBeNull();
    // The menu is closed, so the only "Add thing" is the hero's — in the row of
    // "Edit collection", not in a member's row.
    const [add] = screen.getAllByRole('link', { name: 'Add thing' });
    expect(screen.getAllByRole('link', { name: 'Add thing' })).toHaveLength(1);
    expect(
      within(add.closest('.button-row-wide')).getByRole('link', { name: 'Edit collection' })
    ).toBeInTheDocument();
  });
});

/**
 * The Community / Public / Private tags after the title say how a group is set
 * up — bookkeeping for whoever runs it, not something a member or a passer-by
 * needs before they have read the name. Community used to show
 * to everyone; Public/Private was already curator-only. Now both are.
 */
describe('CollectionPage hero tags belong to the curators', () => {
  const COMMUNITY_PUBLIC = {
    ...COLLECTION_WITH_PHOTO,
    thumbnail_url: '',
    mode: 'COMMUNITY',
    visibility: 'PUBLIC',
    digest_frequency: 'NONE',
  };

  function renderAs(collection, { signedIn = true } = {}) {
    if (!signedIn) localStorage.removeItem('userCode');
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
    return screen.findByRole('heading', { level: 1, name: /Kitchen Collection/ });
  }

  test('a curator sees both the mode and the visibility tag', async () => {
    const title = await renderAs({ ...COMMUNITY_PUBLIC, is_curator: true });

    expect(within(title).getByText('Community')).toBeInTheDocument();
    expect(within(title).getByText('Public')).toBeInTheDocument();
  });

  test('a curator of a private, proprietary group sees just Private', async () => {
    const title = await renderAs({
      ...COMMUNITY_PUBLIC,
      is_curator: true,
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
    });

    expect(within(title).getByText('Private')).toBeInTheDocument();
    expect(within(title).queryByText('Community')).toBeNull();
  });

  test('a member of the same group sees the title and nothing after it', async () => {
    const title = await renderAs({
      ...COMMUNITY_PUBLIC,
      owner: 'OTHER1',
      is_curator: false,
      is_member: true,
    });

    expect(title).toHaveTextContent(/^Kitchen Collection$/);
    expect(within(title).queryByText('Community')).toBeNull();
    expect(within(title).queryByText('Public')).toBeNull();
  });

  test('an anonymous reader of a public group sees the title and nothing after it', async () => {
    const title = await renderAs(
      { ...COMMUNITY_PUBLIC, owner: 'OTHER1', is_curator: false, is_member: false },
      { signedIn: false }
    );

    expect(title).toHaveTextContent(/^Kitchen Collection$/);
    expect(within(title).queryByText('Community')).toBeNull();
    expect(within(title).queryByText('Public')).toBeNull();
  });
});

describe('CollectionPage — the hero does not say the kind', () => {
  const LIBRARY = {
    ...COLLECTION_WITH_PHOTO,
    thumbnail_url: '',
    kind: 'LIBRARY',
    mode: 'PROPRIETARY',
    visibility: 'PUBLIC',
    digest_frequency: 'NONE',
    owner: 'OTHER1',
    is_curator: false,
    is_member: false,
  };

  async function renderAs(collection, { signedIn = true } = {}) {
    if (!signedIn) localStorage.removeItem('userCode');
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => collection })
    );
    const view = render(
      <MemoryRouter initialEntries={['/library/COL001']}>
        <Routes>
          <Route path="/library/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    const title = await screen.findByRole('heading', { level: 1, name: /Kitchen Collection/ });
    await settle(apiFetch);
    return { title, view };
  }

  test.each([
    ['an anonymous reader', { is_member: false }, { signedIn: false }],
    ['a member', { is_member: true }, {}],
    ['a curator', { is_curator: true, owner: 'ABC123' }, {}],
  ])('%s reads the name and the description, not the kind', async (_who, over, opts) => {
    await renderAs({ ...LIBRARY, ...over }, opts);

    expect(screen.queryByText(en.kinds.LIBRARY.long)).toBeNull();
  });

  test('the title is still the collection’s name and nothing else', async () => {
    const { title } = await renderAs({ ...LIBRARY, is_member: true });

    expect(title).toHaveTextContent(/^Kitchen Collection$/);
    expect(within(title).queryByText(en.kinds.LIBRARY.long)).toBeNull();
  });

  test('has no accessibility violations', async () => {
    const { view } = await renderAs({ ...LIBRARY, is_member: true });

    expect(await axe(view.container)).toHaveNoViolations();
  });
});

describe('CollectionPage — an hourly shed nobody can book yet', () => {
  const SHED = {
    ...COLLECTION_WITH_PHOTO,
    thumbnail_url: '',
    kind: 'SHED',
    reservation_unit: 'HOUR',
    opening_hours: {},
    allowed_thing_types: ['RESERVE_THING'],
    digest_frequency: 'NONE',
  };
  const NOTICE = en.collectionPage.noOpeningHoursBody;

  async function renderAs(collection, { signedIn = true } = {}) {
    if (!signedIn) localStorage.removeItem('userCode');
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: async () => collection })
    );
    render(
      <MemoryRouter initialEntries={['/shed/COL001']}>
        <Routes>
          <Route path="/shed/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByRole('heading', { level: 1, name: /Kitchen Collection/ });
    await settle(apiFetch);
  }

  test('the curator is told, and is given the way to Availability, where the hours are', async () => {
    await renderAs(SHED);

    expect(screen.getByText(en.collectionPage.noOpeningHoursLabel)).toBeInTheDocument();
    expect(screen.getByText(NOTICE)).toBeInTheDocument();
    expect(NOTICE).not.toMatch(/More options|Edit collection/);
    const links = screen.getAllByRole('link', { name: en.collectionSettings.availability });
    expect(links).toHaveLength(1);
    expect(links[0]).toHaveAttribute('href', '/shed/COL001/settings/availability');
  });

  test('a week of empty days is the same as none', async () => {
    await renderAs({ ...SHED, opening_hours: { 0: [], 3: [] } });

    expect(screen.getByText(NOTICE)).toBeInTheDocument();
  });

  test.each([
    ['a member', { is_curator: false, is_member: true, owner: 'OTHER1' }, {}],
    [
      'an anonymous reader',
      { is_curator: false, owner: 'OTHER1', visibility: 'PUBLIC' },
      { signedIn: false },
    ],
  ])('%s is not told: it is not theirs to fix', async (_who, over, opts) => {
    await renderAs({ ...SHED, ...over }, opts);

    expect(screen.queryByText(NOTICE)).toBeNull();
  });

  test('a shed booked by the day has no opening hours to miss', async () => {
    await renderAs({ ...SHED, reservation_unit: 'DAY' });

    expect(screen.queryByText(NOTICE)).toBeNull();
  });

  test('with a range on some day there is nothing to say', async () => {
    await renderAs({ ...SHED, opening_hours: { 2: [['10:00', '14:00']] } });

    expect(screen.queryByText(NOTICE)).toBeNull();
  });

  test('a library, whatever its unit says, is never told it', async () => {
    await renderAs({ ...SHED, kind: 'LIBRARY' });

    expect(screen.queryByText(NOTICE)).toBeNull();
  });
});

const PUBLIC_COMMUNITY = {
  ...COLLECTION_WITH_PHOTO,
  visibility: 'PUBLIC',
  mode: 'COMMUNITY',
  is_member: false,
  // Unlike COLLECTION_WITH_PHOTO's own tests, the viewer here (VISITOR1) is
  // never the owner — is_curator must say so explicitly rather than inherit
  // the spread owner's true value.
  is_curator: false,
  digest_frequency: 'NONE',
  allow_member_proposals: false,
};

/**
 * The signed-in half of login-to-act.
 *
 * A PUBLIC collection is readable with no account, and an anonymous reader who
 * wants to act is sent to `/collections/:code/join` — which takes an email and
 * answers with a magic link. A reader who is *already signed in* fell straight
 * through that funnel: no join page could help them, and no endpoint existed to
 * ask. Meanwhile the page offered them "Add thing" whenever the collection was
 * COMMUNITY, an action `can_add_thing` refuses without an invite — so the reader
 * with the most intent filled the form, uploaded the photos, and got a 403.
 */
describe('A signed-in visitor on a public group', () => {
  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

  beforeEach(() => {
    localStorage.setItem('userCode', 'VISITOR1');
  });

  test('is offered a way in, and not an action the API would refuse', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(PUBLIC_COMMUNITY) })
    );

    renderPage();

    expect(await screen.findByRole('button', { name: 'Join this group' })).toBeInTheDocument();
    expect(screen.queryByText('Add thing')).not.toBeInTheDocument();
  });

  test('the join button sits in a wide row, so on a phone it is the width of the screen', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(PUBLIC_COMMUNITY) })
    );

    renderPage();

    const join = await screen.findByRole('button', { name: 'Join this group' });
    expect(join.parentElement).toHaveClass('button-row-wide');
  });

  test('joining unlocks the member controls', async () => {
    apiFetch.mockImplementation((url, options) => {
      if (options?.method === 'POST') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
      }
      // The refetch after a successful join sees the membership it created.
      const joined = apiFetch.mock.calls.some((c) => c[1]?.method === 'POST');
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ ...PUBLIC_COMMUNITY, is_member: joined }),
      });
    });

    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Join this group' }));

    expect(await screen.findByText('Add thing')).toBeInTheDocument();
    expect(
      apiFetch.mock.calls.some(
        ([url, options]) => url === '/api/v1/collections/COL001/join/' && options?.method === 'POST'
      )
    ).toBe(true);
  });

  test('asking for a thing from a card joins the group, and the hero stops offering to', async () => {
    const withAGift = {
      ...PUBLIC_COMMUNITY,
      things: [{ code: 'THG001', headline: 'Lamp', type: 'GIFT_THING', status: 'ACTIVE' }],
    };
    let asked = 0;
    apiFetch.mockImplementation((url, options) => {
      const json = (data, status = 200) =>
        Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(data) });
      if (/\/things\/THG001\/request\/$/.test(url) && options?.method === 'POST') {
        asked += 1;
        return asked === 1 ? json({ error: 'x', code: 'not_a_member' }, 403) : json({}, 201);
      }
      if (/\/join\/$/.test(url)) return json({});
      // The reload after the join sees the membership it created.
      return json({ ...withAGift, is_member: asked > 0 });
    });

    renderPage();
    expect(await screen.findByRole('button', { name: 'Join this group' })).toBeInTheDocument();

    fireEvent.click(await screen.findByRole('button', { name: 'Claim' }));

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Join this group' })).not.toBeInTheDocument()
    );
    expect(screen.getByText('Add thing')).toBeInTheDocument();
  });

  test('a member is not asked to join again', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ ...PUBLIC_COMMUNITY, is_member: true }),
      })
    );

    renderPage();

    expect(await screen.findByText('Add thing')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Join this group' })).not.toBeInTheDocument();
  });

  // The same dead end, one screen lower: an EMPTY community group's "no things
  // yet" line kept offering "Add one" and the CSV import to every reader of a
  // COMMUNITY collection, member or not — the hero button above was fixed and
  // this one wasn't, because nothing here had ever rendered an empty group.
  test('an empty group does not invite a non-member to fill it', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(PUBLIC_COMMUNITY) })
    );

    renderPage();

    expect(await screen.findByText(/No things in this collection yet/)).toBeInTheDocument();
    expect(document.querySelector('a[href$="/add"]')).toBeNull();
    expect(screen.queryByRole('link', { name: /Add several at once/ })).not.toBeInTheDocument();
  });

  // A signed-out reader of a PUBLIC group has a button to press on every card, and
  // also one door in the hero: "Sign in" (primary, to the group's join page, no
  // ?thing= — there is no thing in it), because that page serves a new address, an
  // account that exists and a member alike. In every public group, COMMUNITY or
  // PROPRIETARY, empty or not. No link to /login anywhere on the page: neither the
  // hero nor the corner offers a second door.
  // Asserted by target as well as by words, and by the raw i18n key: the old
  // strings left the locales, so a resurrected `t('collectionPage.anonJoin…')`
  // renders its own key, which an English-text query would never catch.
  describe('the one door of a signed-out reader', () => {
    const anThing = (n) => ({
      code: `THG${String(n).padStart(3, '0')}`,
      headline: `Thing ${n}`,
      type: 'GIFT_THING',
      status: 'ACTIVE',
      owner: 'OTHER1',
      owner_name: 'Someone',
      created: '2026-07-01T10:00:00Z',
      tags: [],
      gallery_urls: [],
    });
    const show = (collection, { signedIn = false } = {}) => {
      localStorage.clear();
      if (signedIn) localStorage.setItem('userCode', 'VISITOR1');
      apiFetch.mockImplementation(() =>
        Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(collection) })
      );
      return renderPage();
    };
    const joinLinks = () => [...document.querySelectorAll('a[href$="/join"]')];
    const heroDoors = () => [...document.querySelectorAll('.form-hero .button-row-wide a')];
    // The primary button is the theeeme's fill; the secondary is white.
    const isPrimary = (link) =>
      link.style.getPropertyValue('--background-color') !== 'var(--color-white)';

    const loginLinks = () => [...document.querySelectorAll('a[href^="/login"]')];

    const expectTheOneDoor = () => {
      const doors = heroDoors();
      expect(doors.map((a) => a.textContent)).toEqual([en.login.signIn]);
      expect(doors.map((a) => a.getAttribute('href'))).toEqual(['/collections/COL001/join']);
      expect(doors.map(isPrimary)).toEqual([true]);
      // Nobody is sent to /login from here, and the old second button is gone.
      expect(loginLinks()).toHaveLength(0);
      expect(screen.queryByRole('link', { name: en.collectionPage.visitorJoin })).toBeNull();
    };

    test.each([
      ['an empty COMMUNITY group', PUBLIC_COMMUNITY, /No things in this collection yet/],
      [
        'an empty PROPRIETARY group that sends a digest',
        { ...PUBLIC_COMMUNITY, mode: 'PROPRIETARY', digest_frequency: 'WEEKLY' },
        /No things in this collection yet/,
      ],
      [
        'an empty PROPRIETARY group that sends none',
        { ...PUBLIC_COMMUNITY, mode: 'PROPRIETARY', digest_frequency: 'NONE' },
        /No things in this collection yet/,
      ],
      ['a COMMUNITY group with things', { ...PUBLIC_COMMUNITY, things: [anThing(1)] }, /Thing 1/],
      [
        'a PROPRIETARY group with things — the case that had no door but each card’s button',
        { ...PUBLIC_COMMUNITY, mode: 'PROPRIETARY', things: [anThing(1)] },
        /Thing 1/,
      ],
    ])('%s: one door, in the hero, primary, to the join page', async (_what, group, ready) => {
      show(group);

      await screen.findByText(ready);

      expectTheOneDoor();
      // The only link to the join page is the hero's: no second line in the content.
      expect(joinLinks()).toHaveLength(1);
      expect(document.body.textContent).not.toMatch(/anonJoin/);
    });

    test('a COMMUNITY group with a second page of things has no line under the grid either', async () => {
      // 25 cards: one past the page size, so the "Show 1 more" button is there too.
      const things = Array.from({ length: 25 }, (_, i) => anThing(i + 1));
      show({ ...PUBLIC_COMMUNITY, things });

      await screen.findByRole('button', { name: /Show 1 more/ });

      expectTheOneDoor();
      expect(joinLinks()).toHaveLength(1);
      expect(document.body.textContent).not.toMatch(/anonJoin/);
    });

    // The hero offers "Sign in" as its first button, so the
    // account icon of the corner — the link to the same place — is left out of
    // this page. A thing's page, the /legal page and the rest keep it (see
    // `test/signedOutCorner.test.jsx`).
    test('the corner has no account icon: the hero’s button is the only way to sign in', async () => {
      show(PUBLIC_COMMUNITY);

      await screen.findByText(/No things in this collection yet/);

      expect(screen.getAllByRole('link', { name: en.login.signIn })).toHaveLength(1);
      expect(heroDoors()[0]).toHaveTextContent(en.login.signIn);
      expect(loginLinks()).toHaveLength(0);
      expect(document.querySelector('.hero-corners .account-menu')).toBeNull();
      expect(document.querySelector('.hero-corners a[href^="/login"]')).toBeNull();
    });

    test('a PRIVATE group is not reachable signed out, so it offers nothing either', async () => {
      // Whatever the API sent for it, the doors are for the PUBLIC ones.
      show({ ...PUBLIC_COMMUNITY, visibility: 'PRIVATE' });

      await screen.findByText(/No things in this collection yet/);
      expect(heroDoors()).toHaveLength(0);
      expect(joinLinks()).toHaveLength(0);
    });

    test('a signed-in reader has the "Join this group" button instead, and no pair of links', async () => {
      show(PUBLIC_COMMUNITY, { signedIn: true });

      expect(await screen.findByRole('button', { name: 'Join this group' })).toBeInTheDocument();
      expect(joinLinks()).toHaveLength(0);
      expect(screen.queryByRole('link', { name: en.login.signIn })).not.toBeInTheDocument();
      // …and the corner is the account menu it always was.
      expect(document.querySelector('.hero-corners')).toContainElement(
        screen.getByRole('button', { name: /your account/i })
      );
    });

    test.each([
      ['a member', { is_member: true }],
      ['a curator', { is_curator: true, owner: 'VISITOR1' }],
    ])('%s of the group is offered neither door', async (_who, over) => {
      show({ ...PUBLIC_COMMUNITY, things: [anThing(1)], ...over }, { signedIn: true });

      await screen.findByText(/Thing 1/);
      expect(joinLinks()).toHaveLength(0);
      expect(screen.queryByRole('link', { name: en.login.signIn })).not.toBeInTheDocument();
      expect(screen.queryByRole('button', { name: 'Join this group' })).not.toBeInTheDocument();
    });
  });

  // Whoever can add a thing has "Add thing" in their row, so an
  // empty group no longer says a word to them: not the phrase, not "Add one" (gone)
  // and not the CSV link (it moved into the curators' menu).
  test('a member of an empty COMMUNITY group sees no "no things" block: their "Add thing" is the invitation', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ ...PUBLIC_COMMUNITY, is_member: true }),
      })
    );

    renderPage();

    expect(await screen.findByRole('link', { name: 'Add thing' })).toHaveAttribute(
      'href',
      '/collections/COL001/add'
    );
    expect(screen.queryByText(/No things in this collection yet/)).toBeNull();
    expect(document.querySelector('a[href$="#bulk-add"]')).toBeNull();
  });

  test('a member of an empty PROPRIETARY group is still told, and offered nothing to click', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve({ ...PUBLIC_COMMUNITY, mode: 'PROPRIETARY', is_member: true }),
      })
    );

    renderPage();

    const phrase = await screen.findByText(/No things in this collection yet/);
    expect(phrase.querySelector('a')).toBeNull();
    expect(document.querySelector('a[href$="/add"], a[href$="#bulk-add"]')).toBeNull();
    expect(screen.queryByRole('link', { name: 'Add thing' })).toBeNull();
  });
});

/**
 * The broadcast emails every member of the group, and an email cannot be
 * unsent. Its only test until now was an axe scan of the opened form
 * (a11yInteractive) — nothing had ever pressed the button, so nothing said when
 * it fires, when it must not, or what it reports afterwards.
 */
describe('sending a message to the whole group', () => {
  const OWNED_WITH_GUESTS = {
    code: 'COL001',
    headline: 'Kitchen Collection',
    description: 'Things from the kitchen',
    status: 'ACTIVE',
    visibility: 'PRIVATE',
    mode: 'PROPRIETARY',
    owner: 'ABC123',
    owner_name: 'Test User',
    is_curator: true,
    thumbnail_url: '',
    tags: [],
    things: [],
    invites: [{ code: 'GUE001', name: 'Guest', email: 'lulu@your-domain.test' }],
    is_paused: false,
    allowed_thing_types: [],
    digest_frequency: 'NONE',
    allow_member_proposals: false,
  };

  const ok = (body) =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });

  /** The collection loads; the POST answers however this test needs it to. */
  function mockPost(post) {
    apiFetch.mockImplementation((url, options) =>
      options?.method === 'POST' ? post() : ok(OWNED_WITH_GUESTS)
    );
  }

  const broadcastPosts = () =>
    apiFetch.mock.calls.filter(
      ([url, opts]) => opts?.method === 'POST' && url.endsWith('/broadcast/')
    );

  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

  async function openComposer() {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Send a message to members' }));
    return screen.getByLabelText(/Message/);
  }

  test('the button that opens it sits in a wide row, so on a phone it is the width of the screen', async () => {
    mockPost(() => ok({}));
    renderPage();

    const open = await screen.findByRole('button', { name: 'Send a message to members' });
    expect(open.parentElement).toHaveClass('button-row-wide');
  });

  test('opening it and writing sends nothing, and names the cost first', async () => {
    mockPost(() => ok({}));

    const message = await openComposer();
    fireEvent.change(message, { target: { value: 'The library is closed on Monday' } });

    expect(broadcastPosts()).toHaveLength(0);
    // DESIGN §6: the broadcast carries the owner's own address as Reply-To, and
    // that is said on the way in — before the send, not in the confirmation.
    expect(screen.getByText(/see your email address/i)).toBeInTheDocument();
  });

  test('an empty message — or one made of spaces — cannot be sent', async () => {
    // Not a validation nicety: a blank group email costs every member's
    // attention and the owner's standing to ask for it again.
    mockPost(() => ok({}));

    const message = await openComposer();
    expect(screen.getByRole('button', { name: 'Send broadcast' })).toBeDisabled();

    fireEvent.change(message, { target: { value: '   ' } });
    expect(screen.getByRole('button', { name: 'Send broadcast' })).toBeDisabled();

    fireEvent.change(message, { target: { value: 'Real words' } });
    expect(screen.getByRole('button', { name: 'Send broadcast' })).not.toBeDisabled();
  });

  test('the confirmation reports the server’s own count, not the roster on screen', async () => {
    // The page knows of one invitee; the server says it reached twelve. Only the
    // server counts who was actually emailed, so a confirmation built from the
    // invite list would be a number the owner cannot act on.
    mockPost(() => ok({ message: 'Broadcast sent', recipients: 12 }));

    const message = await openComposer();
    fireEvent.change(message, { target: { value: 'The library is closed on Monday' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send broadcast' }));

    expect(await screen.findByText('Broadcast sent to 12 members.')).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith(
      '/api/v1/collections/COL001/broadcast/',
      expect.objectContaining({
        method: 'POST',
        body: JSON.stringify({ message: 'The library is closed on Monday' }),
      })
    );
    // Emptied, so the next click cannot repeat the send that just went out.
    expect(screen.getByLabelText(/Message/)).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Send broadcast' })).toBeDisabled();
  });

  test('a send that fails keeps the words the owner wrote', async () => {
    // Losing the text would be the second cost of one failure: they typed it
    // once, the network dropped it, and retyping is what makes people give up.
    mockPost(() => Promise.reject(new Error('network down')));

    const message = await openComposer();
    fireEvent.change(message, { target: { value: 'The library is closed on Monday' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send broadcast' }));

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
    expect(screen.getByLabelText(/Message/)).toHaveValue('The library is closed on Monday');
    expect(screen.queryByText(/Broadcast sent/)).toBeNull();
  });

  test('an impatient second press cannot send it twice', async () => {
    // The window between the click and the answer, on the one control here
    // whose double-fire mails everybody a second copy.
    let deliver;
    mockPost(
      () =>
        new Promise((resolve) => {
          deliver = () =>
            resolve({ ok: true, status: 200, json: () => Promise.resolve({ recipients: 1 }) });
        })
    );

    const message = await openComposer();
    fireEvent.change(message, { target: { value: 'The library is closed on Monday' } });
    fireEvent.click(screen.getByRole('button', { name: 'Send broadcast' }));

    const busy = await screen.findByRole('button', { name: 'Sending...' });
    expect(busy).toBeDisabled();
    fireEvent.click(busy);
    expect(broadcastPosts()).toHaveLength(1);

    deliver();
    expect(await screen.findByText('Broadcast sent to 1 members.')).toBeInTheDocument();
  });
});

describe('a broadcast the server turns down', () => {
  /* Separate from the cases above because this one changed the page rather than
     covering it. The daily cap (5/day, `key="user"`) is the only refusal an
     owner meets in practice, and it does not arrive in the shape this handler
     was reading: `@ratelimit(block=True)` raises, and `api_exception_handler`
     answers `{detail: …}` with a 429. The page read `data.error` alone, so the
     owner got "Error" — while the message sat unsent and nothing said that
     tomorrow would work. */
  const OWNED_WITH_GUESTS = {
    code: 'COL001',
    headline: 'Kitchen Collection',
    description: 'Things from the kitchen',
    status: 'ACTIVE',
    visibility: 'PRIVATE',
    mode: 'PROPRIETARY',
    owner: 'ABC123',
    owner_name: 'Test User',
    is_curator: true,
    thumbnail_url: '',
    tags: [],
    things: [],
    invites: [{ code: 'GUE001', name: 'Guest', email: 'lulu@your-domain.test' }],
    is_paused: false,
    allowed_thing_types: [],
    digest_frequency: 'NONE',
    allow_member_proposals: false,
  };

  async function sendUnder(response) {
    apiFetch.mockImplementation((url, options) =>
      options?.method === 'POST'
        ? Promise.resolve(response)
        : Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(OWNED_WITH_GUESTS) })
    );
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    fireEvent.click(await screen.findByRole('button', { name: 'Send a message to members' }));
    fireEvent.change(screen.getByLabelText(/Message/), {
      target: { value: 'The library is closed on Monday' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send broadcast' }));
  }

  test('names the daily cap instead of saying "Error"', async () => {
    await sendUnder({
      ok: false,
      status: 429,
      json: () =>
        Promise.resolve({ detail: 'Too many requests. Please slow down and try again later.' }),
    });

    expect(
      await screen.findByText('Too many requests. Please slow down and try again later.')
    ).toBeInTheDocument();
    // The words are still there to send tomorrow.
    expect(screen.getByLabelText(/Message/)).toHaveValue('The library is closed on Monday');
  });

  test('still names the view’s own refusals', async () => {
    // `{error}` is what this endpoint answers when it refuses on its own terms,
    // and reordering must not cost that.
    await sendUnder({
      ok: false,
      status: 400,
      json: () => Promise.resolve({ error: 'No invitees to broadcast to' }),
    });

    expect(await screen.findByText('No invitees to broadcast to')).toBeInTheDocument();
  });
});

/**
 * Four ways this page can fail to open, and the reader does something different
 * with each: a 403 is "your access changed, go and check", a 404 is "this URL
 * is wrong", a 500 is "not your fault, try later", and a dead connection is
 * "you are offline". Only the 404 had ever been rendered by the suite, so three
 * of the four could have collapsed into any other and nothing would have said
 * so — least of all to the member who was quietly removed from a group and
 * would read "not found" as a typo.
 */
describe('the ways a collection fails to load', () => {
  const renderAfter = (response) => {
    apiFetch.mockImplementation(() => Promise.resolve(response));
    return render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
  };

  const refused = (status) => ({ ok: false, status, json: () => Promise.resolve({}) });

  test('access you no longer have says so, and where to look', async () => {
    renderAfter(refused(403));

    expect(await screen.findByText(/your access may have changed/i)).toBeInTheDocument();
  });

  test('access you no longer have is a notice titled for the reader, not an "Error"', async () => {
    renderAfter(refused(403));

    expect(
      await screen.findByRole('heading', { level: 1, name: "You can't see this group" })
    ).toBeInTheDocument();
    expect(screen.getByText('Notice')).toBeInTheDocument();
    expect(screen.queryByText('Error')).not.toBeInTheDocument();
    // The tab keeps saying what page it is.
    expect(document.title).toBe('Collection — OIUEEI');
  });

  test.each([[404], [500]])('a %i is still an "Error"', async (status) => {
    renderAfter(refused(status));

    expect(await screen.findByRole('heading', { level: 1, name: 'Error' })).toBeInTheDocument();
    expect(screen.getByText('Error', { selector: 'h2, h3, div, span' })).toBeInTheDocument();
    expect(screen.queryByText("You can't see this group")).not.toBeInTheDocument();
  });

  describe('a refusal leaves a way out', () => {
    const THEEEME = {
      color_01: 'bus',
      color_02: 'white',
      color_03: 'bus-light',
      color_04: 'black',
      color_06: 'white',
    };
    const wayOut = (container) => container.querySelector('.button-row-wide a');

    test('with a session it is a secondary button to Home', async () => {
      declarePalette(THEEEME);
      const { container } = renderAfter(refused(403));
      await screen.findByText(/your access may have changed/i);

      const link = wayOut(container);
      expect(link).toHaveTextContent('Home');
      expect(link).toHaveAttribute('href', '/');
      expect(link.className).toMatch(/hds-button/);
      // Secondary: the white fill with the theeeme's border, not the primary's fill.
      expect(link.style.getPropertyValue('--background-color')).toBe('var(--color-white)');
      expect(link.style.getPropertyValue('--border-color')).toBe('var(--color-bus)');
      expect(screen.queryByRole('link', { name: 'Sign in' })).toBeNull();
    });

    test('without one it is a primary Sign in that brings them back to this collection', async () => {
      localStorage.removeItem('userCode');
      declarePalette(THEEEME);
      const { container } = renderAfter(refused(403));
      await screen.findByText(/your access may have changed/i);

      const link = wayOut(container);
      expect(link).toHaveTextContent('Sign in');
      expect(link).toHaveAttribute('href', '/login?next=%2Fcollections%2FCOL001');
      expect(link.style.getPropertyValue('--background-color')).toBe('var(--color-bus)');
    });

    test.each([[404], [500]])(
      'a %i has no such row: the access is not what is wrong',
      async (status) => {
        const { container } = renderAfter(refused(status));
        await screen.findByRole('heading', { level: 1 });
        await screen.findAllByRole('link');

        expect(wayOut(container)).toBeNull();
      }
    );
  });

  test('a collection that is not there says only that', async () => {
    renderAfter(refused(404));

    expect(await screen.findByText('Collection not found.')).toBeInTheDocument();
  });

  test('a server fault is not dressed up as a permission problem', async () => {
    renderAfter(refused(500));

    expect(await screen.findByText('Error loading collection.')).toBeInTheDocument();
    expect(screen.queryByText(/your access may have changed/i)).toBeNull();
  });

  test('being offline says so rather than blaming the collection', async () => {
    apiFetch.mockImplementation(() => Promise.reject(new Error('network down')));
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
  });
});

describe('a join that does not take', () => {
  /* The happy path is covered above. These are the three ways it can fail, and
     they matter because the page deliberately re-fetches instead of flipping
     `is_member` locally: a visitor who is told nothing, or shown the member
     controls anyway, would go on to act on a group they never joined and meet a
     403 from an API that is right. */
  beforeEach(() => {
    localStorage.setItem('userCode', 'VISITOR1');
  });

  const renderPublic = () =>
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

  const page = () =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(PUBLIC_COMMUNITY) });

  async function pressJoin() {
    renderPublic();
    const join = await screen.findByRole('button', { name: 'Join this group' });
    // The press starts a request whose answer sets state: keep it inside `act`.
    await act(async () => {
      fireEvent.click(join);
    });
  }

  test('a refused join says so and leaves the door where it was', async () => {
    apiFetch.mockImplementation((url, options) =>
      options?.method === 'POST'
        ? Promise.resolve({ ok: false, status: 403, json: () => Promise.resolve({}) })
        : page()
    );

    await pressJoin();

    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn't add you to the group/i);
    expect(screen.getByRole('button', { name: 'Join this group' })).toBeInTheDocument();
  });

  test('a join whose re-fetch fails is not reported as a success', async () => {
    // The subtle one: the server did add them, but the page cannot prove what
    // that changed. Claiming membership on a payload it never received is how a
    // page ends up showing controls the API will refuse.
    let getCalls = 0;
    apiFetch.mockImplementation((url, options) => {
      if (options?.method === 'POST') {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) });
      }
      getCalls += 1;
      return getCalls === 1
        ? page()
        : Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
    });

    await pressJoin();

    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn't add you to the group/i);
  });

  test('a connection lost mid-join says so too', async () => {
    apiFetch.mockImplementation((url, options) =>
      options?.method === 'POST' ? Promise.reject(new Error('network down')) : page()
    );

    await pressJoin();

    expect(await screen.findByRole('alert')).toHaveTextContent(/couldn't add you to the group/i);
  });
});

// ════════════════════════════════════════════════════════════════════════
// A COMMUNITY member's own notifications and own INACTIVE thing — both used
// to be gated on `isOwner` (the *collection* owner), which only happened to
// be right in PROPRIETARY mode, where that person and the thing's owner are
// the same. In COMMUNITY mode a member owns what they contributed, and
// stayed stranded: their own hold request never reached them here, and a
// completed/hidden thing of theirs was reachable nowhere on this page.
// ════════════════════════════════════════════════════════════════════════
describe("CollectionPage — a COMMUNITY member's own things and notifications", () => {
  const MY_INACTIVE_THING = {
    code: 'THG002',
    headline: 'My contributed gift',
    type: 'GIFT_THING',
    status: 'INACTIVE',
    owner: 'ABC123', // the signed-in viewer (localStorage userCode), not the collection owner
    owner_name: 'Me',
    created: '2026-07-01T10:00:00Z',
    tags: [],
    gallery_urls: [],
  };
  const MEMBER_COMMUNITY = {
    ...COLLECTION_WITH_PHOTO,
    thumbnail_url: '',
    mode: 'COMMUNITY',
    owner: 'OTHER1',
    owner_name: 'The Curator',
    is_member: true,
    // The viewer here is a plain member of somebody else's group, not a
    // curator — override rather than inherit COLLECTION_WITH_PHOTO's true.
    is_curator: false,
    things: [MY_INACTIVE_THING],
  };

  test('a member sees the "Inactive things" section for their own INACTIVE contribution', async () => {
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => [] });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => MEMBER_COMMUNITY });
    });

    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByRole('heading', { name: 'Inactive things' });
    expect(screen.getByText('My contributed gift')).toBeInTheDocument();
    // The per-card owner-button-matrix (isOwner keyed on the *thing*'s owner)
    // was already right — it is the section wrapping it that used to be hidden.
    expect(screen.getByRole('link', { name: 'Edit' })).toBeInTheDocument();
  });

  test('a co-member who does not own the thing still does not see the section', async () => {
    // Not a general "INACTIVE things are visible in COMMUNITY" change — only an
    // exception for the thing's own owner. The backend enforces this; here we
    // just confirm the frontend gate doesn't invent visibility of its own by
    // rendering a section the payload never carries a member's own thing in.
    const collectionWithSomeoneElsesInactiveThing = {
      ...MEMBER_COMMUNITY,
      things: [], // the backend already excluded it for this viewer
    };
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) {
        return Promise.resolve({ ok: true, status: 200, json: async () => [] });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => collectionWithSomeoneElsesInactiveThing,
      });
    });

    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Kitchen Collection');
    expect(screen.queryByRole('heading', { name: 'Inactive things' })).toBeNull();
  });

  test('a member (not the collection owner) sees a hold request on their own thing here', async () => {
    const notification = {
      code: 'NOT001',
      type: 'BOOKING_REQUESTED',
      payload: {
        thing_headline: 'My contributed gift',
        requester_name: 'Someone Else',
        booking_code: 'BOK001',
        thing_code: 'THG002',
        collection_code: 'COL001',
      },
      created: '2026-09-04T10:00:00Z',
    };
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) {
        // Proof this is the collection-scoped call, not the unscoped Home one.
        expect(url).toBe('/api/v1/inbox/?collection=COL001');
        return Promise.resolve({ ok: true, status: 200, json: async () => [notification] });
      }
      return Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ ...MEMBER_COMMUNITY, things: [] }),
      });
    });

    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByText('New request')).toBeInTheDocument();
    expect(screen.getByText('Someone Else requested My contributed gift.')).toBeInTheDocument();
  });

  test('a signed-out visitor on a PUBLIC collection triggers no inbox call at all', async () => {
    localStorage.clear(); // no userCode: neither isOwner nor is_member can be true
    apiFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ ...MEMBER_COMMUNITY, is_member: false, visibility: 'PUBLIC' }),
      })
    );

    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('Kitchen Collection');
    expect(apiFetch.mock.calls.some(([u]) => u.startsWith('/api/v1/inbox/'))).toBe(false);
  });
});

describe('CollectionPage — a network', () => {
  const NETWORK = {
    code: 'COL001',
    headline: 'Kitchen Collection',
    description: '',
    status: 'ACTIVE',
    visibility: 'PRIVATE',
    kind: 'LIBRARY',
    mode: 'NETWORK',
    owner: 'FOUN01',
    owner_name: 'The Founder',
    is_curator: true,
    is_member: false,
    co_owners: [{ code: 'ABC123', name: 'Me' }],
    thumbnail_url: '',
    tags: [],
    things: [],
    invites: [{ code: 'ABC123', name: 'Me' }],
    is_paused: false,
    allowed_thing_types: ['LEND_THING', 'RENT_THING'],
    digest_frequency: 'WEEKLY',
    is_digest_muted: false,
    allow_member_proposals: false,
  };

  async function renderAs(collection, userCode) {
    localStorage.setItem('userCode', userCode);
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/inbox/')
        ? Promise.resolve({ ok: true, status: 200, json: async () => [] })
        : Promise.resolve({ ok: true, status: 200, json: async () => collection })
    );
    render(
      <MemoryRouter initialEntries={['/library/COL001']}>
        <Routes>
          <Route path="/library/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByRole('heading', { level: 1, name: /Kitchen Collection/ });
    await settle(apiFetch);
  }

  test('says what a network is, to whoever lands on one', async () => {
    await renderAs(NETWORK, 'ABC123');

    expect(screen.getByText(en.collectionPage.networkNote)).toBeInTheDocument();
  });

  test('a library that is not a network says nothing of the sort', async () => {
    await renderAs({ ...NETWORK, mode: 'PROPRIETARY' }, 'ABC123');

    expect(screen.queryByText(en.collectionPage.networkNote)).toBeNull();
  });

  test('a dinamizador is not offered the settings of the group, the founder is', async () => {
    await renderAs(NETWORK, 'ABC123');
    expect(screen.queryByRole('link', { name: 'Edit collection' })).toBeNull();
    expect(screen.getAllByRole('link', { name: 'Add thing' }).length).toBeGreaterThan(0);
  });

  test('the founder is offered them', async () => {
    await renderAs({ ...NETWORK, is_curator: true }, 'FOUN01');

    expect(screen.getByRole('link', { name: 'Edit collection' })).toBeInTheDocument();
  });
});

describe('CollectionPage as a co-owner', () => {
  // A co-owner is not the founder (`owner`), but the server says `is_curator:
  // true` — that field, not the client-side owner comparison, is what now
  // unlocks every admin control on this page.
  const CO_OWNED = {
    code: 'COL001',
    headline: 'Kitchen Collection',
    description: 'Things from the kitchen',
    status: 'ACTIVE',
    visibility: 'PRIVATE',
    mode: 'COMMUNITY',
    owner: 'OTHER1',
    owner_name: 'The Founder',
    is_curator: true,
    is_member: false,
    co_owners: [{ code: 'ABC123', name: 'Me' }],
    thumbnail_url: '',
    tags: [],
    things: [],
    invites: [{ code: 'ABC123', name: 'Me' }],
    is_paused: false,
    allowed_thing_types: [],
    digest_frequency: 'WEEKLY',
    is_digest_muted: false,
    allow_member_proposals: false,
  };

  test('sees the same admin controls the founder would, not the "join" nudge', async () => {
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/inbox/')
        ? Promise.resolve({ ok: true, status: 200, json: async () => [] })
        : Promise.resolve({ ok: true, status: 200, json: async () => CO_OWNED })
    );

    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    expect(await screen.findByRole('link', { name: 'Edit collection' })).toBeInTheDocument();
    // "Manage members" lives in the collection menu now (2026-10-03): open it.
    fireEvent.click(screen.getByRole('button', { name: 'Collection options' }));
    expect(await screen.findByRole('link', { name: 'Manage members' })).toBeInTheDocument();
    // "Add thing" is in the menu and in the hero row (2026-10-04): one each.
    expect(screen.getAllByRole('link', { name: 'Add thing' })).toHaveLength(2);
    expect(screen.queryByRole('button', { name: 'Join this group' })).not.toBeInTheDocument();
  });

  // The hero row holds "Add thing" and "Edit collection": the
  // first primary, the second secondary — and "Invite your people", always, a third
  // secondary one (`test/inviteYourPeople.test.jsx` pins when it is there). It once
  // held "Edit collection" alone — the rest of the curator's controls are in the
  // collection menu, one click further — and then "Edit collection" primary with
  // "Add thing" after it: the thing a curator does most is put things in, so that is
  // the button the eye lands on.
  test('the curator hero row holds "Add thing" and then "Edit collection", the first primary, and "Invite your people"', async () => {
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/inbox/')
        ? Promise.resolve({ ok: true, status: 200, json: async () => [] })
        : Promise.resolve({ ok: true, status: 200, json: async () => CO_OWNED })
    );

    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByRole('link', { name: 'Edit collection' });
    const row = container.querySelector('.button-row-wide');
    expect(row).not.toBeNull();
    const inRow = [...row.querySelectorAll('a, button')];
    expect(inRow.map((el) => el.textContent)).toEqual([
      'Add thing',
      'Edit collection',
      'Invite your people',
    ]);
    expect(inRow[0]).toHaveAttribute('href', '/collections/COL001/add');
    expect(inRow[1]).toHaveAttribute('href', '/collections/COL001/edit');
    expect(inRow[2]).toHaveAttribute('href', '/collections/COL001/invites');
    // The secondary tokens are a white background; the primary's are the theeeme's.
    expect(inRow[0].style.getPropertyValue('--background-color')).not.toBe('var(--color-white)');
    expect(inRow[1].style.getPropertyValue('--background-color')).toBe('var(--color-white)');
    expect(inRow[2].style.getPropertyValue('--background-color')).toBe('var(--color-white)');
  });

  // The button is there with things or without: an empty group
  // had it only in the menu, and a group with things only there too.
  const KETTLE = {
    code: 'THG001',
    headline: 'Kettle',
    type: 'GIFT_THING',
    status: 'ACTIVE',
    owner: 'OTHER1',
    owner_name: 'The Founder',
    created: '2026-07-01T10:00:00Z',
    tags: [],
    gallery_urls: [],
  };

  const renderCurating = (collection) => {
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/inbox/')
        ? Promise.resolve({ ok: true, status: 200, json: async () => [] })
        : Promise.resolve({ ok: true, status: 200, json: async () => collection })
    );
    return render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
  };

  test('an empty group says nothing to whoever runs it — "Add thing" is in the hero', async () => {
    renderCurating(CO_OWNED);

    expect(await screen.findByRole('link', { name: 'Add thing' })).toHaveAttribute(
      'href',
      '/collections/COL001/add'
    );
    expect(screen.queryByText(/No things in this collection yet/)).toBeNull();
    expect(document.querySelector('a[href$="#bulk-add"]')).toBeNull();
  });

  test('with things, whoever runs the group still has "Add thing" in the hero', async () => {
    renderCurating({ ...CO_OWNED, things: [KETTLE] });

    await screen.findByText('Kettle');
    expect(screen.getByRole('link', { name: 'Add thing' })).toHaveAttribute(
      'href',
      '/collections/COL001/add'
    );
  });

  test('the hero names the whole team on one "Run by:" line, alphabetical', async () => {
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/inbox/')
        ? Promise.resolve({ ok: true, status: 200, json: async () => [] })
        : Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({
              ...CO_OWNED,
              co_owners: [
                { code: 'ABC123', name: 'Me' },
                { code: 'XYZ999', name: 'Nil' },
              ],
            }),
          })
    );

    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    const line = (await screen.findByText(/Run by:/)).closest('p');
    // alphabetical, the founder as one more, all linked — written as English writes a
    // list of three: commas, and the conjunction before the last
    expect(line).toHaveTextContent('Run by: Me, Nil, and The Founder');
    expect(within(line).getByRole('link', { name: 'The Founder' })).toHaveAttribute(
      'href',
      '/collections/COL001/organisation/OTHER1'
    );
    expect(within(line).getByRole('link', { name: 'Nil' })).toHaveAttribute(
      'href',
      '/collections/COL001/organisation/XYZ999'
    );
    // The team and the founder share one label now, so "no separate founder
    // line" is: the label is on the page once.
    expect(screen.getAllByText('Run by:')).toHaveLength(1);
  });

  test('with no co-curators the hero shows the single "Run by:" line (non-owner viewer)', async () => {
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/inbox/')
        ? Promise.resolve({ ok: true, status: 200, json: async () => [] })
        : Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ ...CO_OWNED, co_owners: [], is_curator: false, is_member: true }),
          })
    );

    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    const line = (await screen.findByText(/Run by:/)).closest('p');
    // Exact: the label is the same one with a team, so only the names tell the
    // two lines apart and nobody else may follow the founder here.
    expect(line).toHaveTextContent(/^Run by: The Founder$/);
    expect(screen.getAllByText('Run by:')).toHaveLength(1);
  });

  // The hero's team line as a signed-in non-founder sees it, in the collection's
  // own language: the profile has none saved, which is what lets the collection's
  // reach the page's chrome.
  const renderTeamHero = (language, overrides) => {
    const respond = (body) => Promise.resolve({ ok: true, status: 200, json: async () => body });
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) return respond([]);
      if (url.endsWith('/auth/me/')) return respond({ code: 'ABC123', language: '' });
      return respond({ ...CO_OWNED, language, ...overrides });
    });
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
  };

  // Each name in the team line is the name of that person's page in the group (the
  // entity's name, else their account's) and opens that page — for everyone who can read
  // the group, inside it or not, with a session or without. The general profile stays
  // closed to those outside; nobody reaches it from here.
  describe('the team line names each person by their page in the group and links to it', () => {
    const links = (line) =>
      within(line)
        .queryAllByRole('link')
        .map((a) => [a.textContent, a.getAttribute('href')]);
    const page = (userCode) => `/collections/COL001/organisation/${userCode}`;
    const TEAM = [
      { code: 'ABC123', name: 'Me' },
      { code: 'XYZ999', name: 'Nil' },
    ];
    // [who is looking, session, the fields the server sends them]
    const viewers = {
      curator: [true, { is_curator: true, is_member: false }],
      member: [true, { is_curator: false, is_member: true }],
      'signed-in non-member': [true, { is_curator: false, is_member: false }],
      'signed-out reader': [false, { is_curator: false, is_member: false }],
    };

    test.each(Object.keys(viewers))('a %s gets a link per name, to its page', async (who) => {
      const [signedIn, fields] = viewers[who];
      if (!signedIn) localStorage.removeItem('userCode');
      renderTeamHero('en', { ...fields, co_owners: TEAM });

      const line = (await screen.findByText('Run by:')).closest('p');
      expect(line).toHaveTextContent('Run by: Me, Nil, and The Founder');
      expect(links(line)).toEqual([
        ['Me', page('ABC123')],
        ['Nil', page('XYZ999')],
        ['The Founder', page('OTHER1')],
      ]);
    });

    test('the name of a person is their entity’s, and one with no page keeps their account’s', async () => {
      renderTeamHero('en', {
        co_owners: TEAM,
        points: [
          { user: 'OTHER1', display_name: 'Associació del Passatge' },
          { user: 'XYZ999', display_name: 'Nil' },
        ],
      });

      const line = (await screen.findByText('Run by:')).closest('p');
      expect(line).toHaveTextContent('Run by: Associació del Passatge, Me, and Nil');
      expect(links(line)).toEqual([
        ['Associació del Passatge', page('OTHER1')],
        ['Me', page('ABC123')],
        ['Nil', page('XYZ999')],
      ]);
    });

    test('a page whose name is empty counts the person among those without one', async () => {
      renderTeamHero('en', {
        co_owners: TEAM,
        points: [{ user: 'XYZ999', display_name: '' }],
      });

      const line = (await screen.findByText('Run by:')).closest('p');
      expect(line).toHaveTextContent('Run by: Me, The Founder, and 1 more person');
      expect(links(line).map(([name]) => name)).toEqual(['Me', 'The Founder']);
    });

    test.each(Object.keys(viewers))(
      'with a single founder, a %s gets a link to their page too',
      async (who) => {
        const [signedIn, fields] = viewers[who];
        if (!signedIn) localStorage.removeItem('userCode');
        renderTeamHero('en', { ...fields, co_owners: [] });

        const line = (await screen.findByText('Run by:')).closest('p');
        expect(line).toHaveTextContent(/^Run by: The Founder$/);
        expect(links(line)).toEqual([['The Founder', page('OTHER1')]]);
      }
    );

    test('a single founder is named by their entity', async () => {
      renderTeamHero('en', {
        co_owners: [],
        points: [{ user: 'OTHER1', display_name: 'Cooperativa Brúixola' }],
      });

      const line = (await screen.findByText('Run by:')).closest('p');
      expect(links(line)).toEqual([['Cooperativa Brúixola', page('OTHER1')]]);
    });
  });

  // The API sends a co-curator's bare `name` — never the email in its place —
  // so one who set none arrives as ''. Joined with commas that left "Oriol, ," on
  // the page; whoever has no name is counted after the names instead.
  describe('a co-curator with no name is counted at the end, not listed', () => {
    const nameless = (code) => ({ code, name: '' });
    const linked = (line) =>
      within(line)
        .getAllByRole('link')
        .map((a) => a.textContent);

    test('two without a name leave "and 2 more people" and no gaps', async () => {
      renderTeamHero('en', { co_owners: [nameless('XYZ001'), nameless('XYZ002')] });

      const line = (await screen.findByText('Run by:')).closest('p');
      expect(line).toHaveTextContent(/^Run by: The Founder and 2 more people$/);
      // Only who has a name is linked: a profile with no name has nothing to show.
      expect(linked(line)).toEqual(['The Founder']);
    });

    test('one without a name is "1 more person"', async () => {
      renderTeamHero('en', { co_owners: [nameless('XYZ001')] });

      const line = (await screen.findByText('Run by:')).closest('p');
      expect(line).toHaveTextContent(/^Run by: The Founder and 1 more person$/);
    });

    test('named and unnamed together: the names, then the count as the last of the list', async () => {
      renderTeamHero('en', { co_owners: [{ code: 'XYZ999', name: 'Nil' }, nameless('XYZ001')] });

      const line = (await screen.findByText('Run by:')).closest('p');
      expect(line).toHaveTextContent(/^Run by: Nil, The Founder, and 1 more person$/);
      expect(linked(line)).toEqual(['Nil', 'The Founder']);
    });

    test('two named and two without a name: "A, B, and 2 more people"', async () => {
      renderTeamHero('en', {
        co_owners: [{ code: 'XYZ999', name: 'Nil' }, nameless('XYZ001'), nameless('XYZ002')],
      });

      const line = (await screen.findByText('Run by:')).closest('p');
      expect(line).toHaveTextContent(/^Run by: Nil, The Founder, and 2 more people$/);
      expect(linked(line)).toEqual(['Nil', 'The Founder']);
    });

    test('a founder with no name is one of the people counted', async () => {
      renderTeamHero('en', { owner_name: '', co_owners: [{ code: 'XYZ999', name: 'Nil' }] });

      const line = (await screen.findByText('Run by:')).closest('p');
      expect(line).toHaveTextContent(/^Run by: Nil and 1 more person$/);
    });

    test('with nobody named there is no line at all', async () => {
      renderTeamHero('en', { owner_name: '', co_owners: [nameless('XYZ001'), nameless('XYZ002')] });

      await screen.findByText('Kitchen Collection');
      expect(screen.queryByText('Run by:')).not.toBeInTheDocument();
    });
  });

  // The label is one noun, "Dinamización:" — like a credit line, no gender, no
  // number — for a team of one and a team of three, so it is
  // the same word in both lines. Nothing but these pins the Spanish and Catalan
  // wording of the hero.
  //
  // The names are joined with that language's own "and": "A y B",
  // "A, B y C" in Spanish, "A i B", "A, B i C" in Catalan; the count of those without
  // a name is the last element of the list, so its text carries no conjunction.
  describe.each([
    ['es', 'Dinamización:', 'y', '2 personas más'],
    ['ca', 'Dinamització:', 'i', '2 persones més'],
  ])('in a %s group', (language, label, and, twoMore) => {
    afterEach(async () => {
      // `useCollectionLanguage` moves the whole UI to the collection's language;
      // put it back so the next test starts in English.
      const { default: i18n } = await import('../i18n');
      await switchLanguage(i18n, 'en');
      localStorage.removeItem('i18nextLng');
    });

    const renderHero = (overrides) =>
      renderTeamHero(language, { owner_name: 'El Fundador', ...overrides });

    test(`the founder and two co-curators come on one "${label}" line`, async () => {
      renderHero({
        co_owners: [
          { code: 'ABC123', name: 'Yo' },
          { code: 'XYZ999', name: 'Nil' },
        ],
      });

      const line = (await screen.findByText(label)).closest('p');
      expect(line).toHaveTextContent(`${label} El Fundador, Nil ${and} Yo`);
      expect(screen.getAllByText(label)).toHaveLength(1);
    });

    test(`two names are joined by "${and}", with no comma`, async () => {
      renderHero({ co_owners: [{ code: 'XYZ999', name: 'Nil' }] });

      const line = (await screen.findByText(label)).closest('p');
      expect(line).toHaveTextContent(new RegExp(`^${label} El Fundador ${and} Nil$`));
      // The names are still links to the profiles; the conjunction is not.
      expect(
        within(line)
          .getAllByRole('link')
          .map((a) => a.textContent)
      ).toEqual(['El Fundador', 'Nil']);
    });

    test(`with no co-curators the founder alone follows "${label}" (non-owner viewer)`, async () => {
      renderHero({ co_owners: [], is_curator: false, is_member: true });

      const line = (await screen.findByText(label)).closest('p');
      expect(line).toHaveTextContent(new RegExp(`^${label} El Fundador$`));
      expect(screen.getAllByText(label)).toHaveLength(1);
    });

    test(`co-curators with no name are counted after the names: "${and} ${twoMore}"`, async () => {
      renderHero({
        co_owners: [
          { code: 'XYZ001', name: '' },
          { code: 'XYZ002', name: '' },
        ],
      });

      const line = (await screen.findByText(label)).closest('p');
      // One conjunction, not two: "y y 2 personas más" is the text of the count
      // keeping its own "y" under the list's.
      expect(line).toHaveTextContent(new RegExp(`^${label} El Fundador ${and} ${twoMore}$`));
    });

    test('two named and two without a name: the names, then the count, one conjunction', async () => {
      renderHero({
        co_owners: [
          { code: 'XYZ999', name: 'Nil' },
          { code: 'XYZ001', name: '' },
          { code: 'XYZ002', name: '' },
        ],
      });

      const line = (await screen.findByText(label)).closest('p');
      expect(line).toHaveTextContent(new RegExp(`^${label} El Fundador, Nil ${and} ${twoMore}$`));
    });
  });
});

/**
 * The hero's back link always SAYS "← Home", whatever it points
 * at: the group's own `Collection.home_page` when the owner has set one, the
 * app's home otherwise. It used to say "The group's site" and carry an
 * external-link icon; the wording and the icon are gone, the destination stayed.
 *
 * The label is asserted through the raw i18n key as well as the visible name —
 * the string that named the destination was deleted, so a resurrected
 * `t('collectionPage.backToSite')` would render its own key, which a name query
 * for "site" would never match. And the link carries exactly one icon (the
 * arrow): a second one is the external-link icon coming back.
 */
describe('CollectionPage back link says Home wherever it goes', () => {
  const renderPage = () =>
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

  const mockCollection = (extra) =>
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/inbox/')
        ? Promise.resolve({ ok: true, status: 200, json: async () => [] })
        : Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ ...COLLECTION_WITH_PHOTO, thumbnail_url: '', ...extra }),
          })
    );

  test.each([
    ['no home_page', {}, '/', false],
    [
      'an https home_page',
      { home_page: 'https://ateneu.example/' },
      'https://ateneu.example/',
      true,
    ],
    // The backend URLField would let ftp:// through; `sanitizeUrl` here does not.
    ['a non-http home_page', { home_page: 'ftp://ateneu.example/' }, '/', false],
  ])(
    'with %s, the link says Home and goes where it should',
    async (_case, extra, href, external) => {
      mockCollection(extra);
      const { container } = renderPage();

      const back = await screen.findByRole('link', { name: /Home/ });
      expect(back).toHaveAttribute('href', href);
      expect(back).toHaveClass('back-link');
      // Only the external variant is a plain anchor that leaves the app.
      if (external) expect(back).toHaveAttribute('rel', 'noopener noreferrer');
      else expect(back).not.toHaveAttribute('rel');
      expect(back.querySelectorAll('svg')).toHaveLength(1);
      expect(container.textContent).not.toMatch(/collectionPage\.backToSite/);
    }
  );
});

/**
 * A collection's own language used to override the owner's own translations
 * for every reader without a saved preference — every anonymous visitor
 * among them — because owner text resolves by the reader's current language
 * and the override changed it. Pinned end to end on the headline a stranger
 * sees first (the hook's own rule is in useCollectionLanguage.test.jsx).
 */
describe('CollectionPage — the owner wrote in the visitor’s language', () => {
  const renderAnon = (collection) => {
    localStorage.clear();
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(collection) })
    );
    return render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
  };

  afterEach(async () => {
    const { default: i18n } = await import('../i18n');
    await switchLanguage(i18n, 'en');
    localStorage.removeItem('i18nextLng');
  });

  test('a visitor reads the translation the owner wrote for them', async () => {
    renderAnon({
      ...PUBLIC_COMMUNITY,
      language: 'ca',
      headline: '{"ca": "Eines del barri", "en": "Neighbourhood tools"}',
    });

    expect(
      await screen.findByRole('heading', { level: 1, name: /Neighbourhood tools/ })
    ).toBeInTheDocument();
    await settle(apiFetch);
    expect(screen.queryByText(/Eines del barri/)).not.toBeInTheDocument();
  });

  test('with no translation for them, the collection’s language still applies', async () => {
    // The same page with the override free to act — what makes the test above
    // a claim about the veto and not about a harness that never switches.
    renderAnon({
      ...PUBLIC_COMMUNITY,
      language: 'ca',
      headline: '{"ca": "Eines del barri", "es": "Herramientas del barrio"}',
    });

    expect(
      await screen.findByRole('heading', { level: 1, name: /Eines del barri/ })
    ).toBeInTheDocument();
  });
});

/**
 * A group's welcome PDF reached a member once, in the email sent when they
 * joined, and nowhere else: a member who had deleted it could not find it
 * again. The API serves `welcome_doc_url` to curators and members only, so the page shows whatever it is given.
 */
describe('CollectionPage — the welcome document', () => {
  const renderWith = (collection) => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(collection) })
    );
    return render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
  };

  test('a member can open it from the group page, in a new tab', async () => {
    renderWith({
      ...PUBLIC_COMMUNITY,
      is_member: true,
      welcome_doc_url: 'https://bucket.your-domain.test/oiueei/documents/welcome.pdf',
    });

    // In the collection menu: it was a loose link in the hero.
    fireEvent.click(await screen.findByRole('button', { name: 'Collection options' }));
    const link = await screen.findByRole('link', { name: /welcome document \(PDF\)/ });
    expect(link).toHaveAttribute(
      'href',
      'https://bucket.your-domain.test/oiueei/documents/welcome.pdf'
    );
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
  });

  test('no document, or none served to this reader, means no link', async () => {
    renderWith({ ...PUBLIC_COMMUNITY, is_member: true, welcome_doc_url: '' });

    fireEvent.click(await screen.findByRole('button', { name: 'Collection options' }));
    // Opening the menu asks whether this reader receives requests; let it answer.
    await settle(apiFetch);
    expect(screen.queryByRole('link', { name: /welcome document/ })).not.toBeInTheDocument();
  });

  test('the hero holds no link to it, whoever reads: it is the menu’s first entry', async () => {
    const { container } = renderWith({
      ...PUBLIC_COMMUNITY,
      is_member: true,
      welcome_doc_url: 'https://bucket.your-domain.test/oiueei/documents/welcome.pdf',
    });

    await screen.findByRole('button', { name: 'Collection options' });
    expect(container.querySelector('.form-hero a[href$="welcome.pdf"]')).toBeNull();
    expect(screen.queryByRole('link', { name: /welcome document/ })).not.toBeInTheDocument();
  });
});
