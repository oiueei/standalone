import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import HomePage from './HomePage';

const USER = { code: 'USR001', name: 'Lulu', email: 'lulu1@your-domain.test', koro: 'basic' };
const GROUP = {
  code: 'COL009',
  headline: 'Bibliocoses',
  status: 'ACTIVE',
  things: [],
  invites: [],
};
const MINE = { ...GROUP, code: 'COL001', headline: 'My workshop' };

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });

// What the API answers each of the dashboard's five reads.
function dashboardRoutes({ mine = [], invited = [], invitations = [], user = USER }) {
  return (url) => {
    if (url.startsWith('/api/v1/auth/me/')) return ok(user);
    if (url.startsWith('/api/v1/collections/')) return ok({ results: mine });
    if (url.startsWith('/api/v1/invited-collections/')) return ok(invited);
    if (url.startsWith('/api/v1/my-invitations/')) return ok(invitations);
    return ok([]); // the inbox
  };
}

function mockDashboard(options = {}) {
  apiFetch.mockImplementation(dashboardRoutes(options));
}

// A real connection failure rejects with a TypeError; an HTTP error status does not.
const dropped = () => Promise.reject(new TypeError('Failed to fetch'));
const refused = () => Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });

const renderHome = () =>
  render(
    <MemoryRouter>
      <HomePage />
    </MemoryRouter>
  );

const sectionOrder = () =>
  screen
    .getAllByRole('heading', { level: 2 })
    .map((h) => h.textContent)
    .filter((text) => text === 'My collections' || text === 'Shared with me');

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'USR001');
  vi.clearAllMocks();
});

/**
 * The cross-group page, `/shared`, left the app. Home used to end the list of groups with a quiet line that led to it.
 */
describe('HomePage — no way to a page that no longer exists', () => {
  test('a member of several groups is not offered /shared under them', async () => {
    mockDashboard({
      mine: [],
      invited: [GROUP, { ...GROUP, code: 'COL010', headline: 'Tool bank' }],
    });
    const { container } = renderHome();

    await screen.findByText('Tool bank');
    expect(container.querySelector('a[href="/shared"]')).toBeNull();
    expect(screen.queryByText(/See everything in these groups/i)).toBeNull();
  });
});

/**
 * Most accounts are members: they arrive through somebody else's group and may
 * never start one. Home used to lead with "My collections" for everyone — an
 * empty state and "Create your first collection" above the one thing a member
 * has, which on a phone sat below the fold under the hero's buttons.
 */
describe('HomePage — the greeting', () => {
  test('greets by name when there is one', async () => {
    mockDashboard({ mine: [MINE] });
    renderHome();

    expect(await screen.findByRole('heading', { name: 'Hello, Lulu' })).toBeInTheDocument();
  });

  test('without a name it just says hello, and the address appears nowhere in it', async () => {
    mockDashboard({ mine: [MINE], user: { ...USER, name: '' } });
    renderHome();

    const heading = await screen.findByRole('heading', { name: 'Hello!' });
    expect(heading).toBeInTheDocument();
    expect(screen.queryByText(/lulu1@your-domain\.test/)).toBeNull();
  });
});

describe('HomePage — which section leads', () => {
  test('a member who owns nothing sees their groups first, the invitation to create after', async () => {
    mockDashboard({ mine: [], invited: [GROUP] });
    renderHome();

    await screen.findByText('Bibliocoses');
    expect(sectionOrder()).toEqual(['Shared with me', 'My collections']);
    // Still offered — just not first.
    expect(screen.getByRole('link', { name: 'Create your first collection' })).toBeInTheDocument();
  });

  test('a new account is told what a collection is, including that it can be public', async () => {
    mockDashboard({ mine: [], invited: [] });
    renderHome();

    expect(
      await screen.findByText(
        'A collection is where you share your things with your people: a stall to give away or sell, a library to lend or rent out, or a shed to book. You decide whether only the people you invite can see it, or anyone with the link.'
      )
    ).toBeInTheDocument();
  });

  test('someone who runs a collection keeps it first', async () => {
    mockDashboard({ mine: [MINE], invited: [GROUP] });
    renderHome();

    await screen.findByText('My workshop');
    expect(sectionOrder()).toEqual(['My collections', 'Shared with me']);
  });

  test('a brand-new account with no groups yet is still pointed at creating one first', async () => {
    mockDashboard({ mine: [], invited: [] });
    renderHome();

    await screen.findByText('No one has shared a collection with you yet.');
    expect(sectionOrder()).toEqual(['My collections', 'Shared with me']);
  });
});

/**
 * A co-curator is always on the group's invite list too, so the group they help
 * run came back from both reads and showed twice — under "My collections" and
 * under "Shared with me". It is theirs to run: it belongs to the
 * first section only, and a group they are a plain member of stays in the second.
 */
describe('HomePage — a group you help run shows once', () => {
  test('it is listed under My collections and not again under Shared with me', async () => {
    const coCurated = { ...GROUP, code: 'COL050', headline: 'Team workshop', is_curator: true };
    const memberOf = { ...GROUP, is_curator: false };
    mockDashboard({ mine: [coCurated], invited: [coCurated, memberOf] });
    renderHome();

    await screen.findByText('Bibliocoses');
    expect(screen.getAllByText('Team workshop')).toHaveLength(1);
    const shared = screen.getByRole('heading', { level: 2, name: 'Shared with me' });
    const mineHeading = screen.getByRole('heading', { level: 2, name: 'My collections' });
    const following = (heading, text) =>
      heading.compareDocumentPosition(screen.getByText(text)) & Node.DOCUMENT_POSITION_FOLLOWING;
    // "My collections" leads (the account runs one), so the team's group sits
    // between the two headings and the member's group after "Shared with me".
    expect(following(mineHeading, 'Team workshop')).toBeTruthy();
    expect(following(shared, 'Team workshop')).toBeFalsy();
    expect(following(shared, 'Bibliocoses')).toBeTruthy();
  });

  test('with only a co-curated group there is nothing shared to list', async () => {
    const coCurated = { ...GROUP, code: 'COL050', headline: 'Team workshop', is_curator: true };
    mockDashboard({ mine: [coCurated], invited: [coCurated] });
    renderHome();

    await screen.findByText('No one has shared a collection with you yet.');
    expect(screen.getAllByText('Team workshop')).toHaveLength(1);
  });
});

/**
 * The hero used to repeat the account menu: "My profile", "My requests" and, for
 * some accounts, "Requests to me", each a full-width button, so a phone showed up
 * to four of them stacked before the inbox and the groups. It keeps the one thing
 * only Home offers; the rest is in the account menu, in every hero.
 */
describe('HomePage — the hero holds one button', () => {
  // The accounts the old row judged differently: a plain member, someone who owns
  // a thing (a Community contribution), a curator of a Proprietary collection. Each
  // has a collection of their own here, which is when the hero has the button (an
  // account with none gets the invitation under "My collections" instead).
  const ACCOUNTS = [
    ['a member', { mine: [MINE], invited: [GROUP] }],
    ['someone who owns a thing', { mine: [MINE], user: { ...USER, things: [{ code: 'THG001' }] } }],
    [
      'a curator of a Proprietary collection',
      { mine: [{ ...MINE, mode: 'PROPRIETARY', is_curator: true }] },
    ],
  ];

  test.each(ACCOUNTS)('%s sees only "Create collection" in the hero', async (_who, options) => {
    mockDashboard(options);
    const { container } = renderHome();
    await screen.findByText(/Lulu/);

    const row = container.querySelector('.form-hero .button-row-wide');
    const links = [...row.querySelectorAll('a')];
    expect(links.map((a) => [a.textContent, a.getAttribute('href')])).toEqual([
      ['Create collection', '/new'],
    ]);
    expect(row.querySelectorAll('button')).toHaveLength(0);
    // …and nothing else in the hero points at the account's own pages.
    const hero = container.querySelector('.form-hero');
    for (const href of ['/me', '/my-bookings', '/owner-bookings']) {
      expect(hero.querySelector(`a[href="${href}"]`)).toBeNull();
    }
  });

  test('the account menu still reaches My profile, My requests and Requests to me', async () => {
    // "Requests to me" is for an account that can receive requests, which the
    // server says (`receives_requests`) when the menu opens.
    mockDashboard({ invited: [GROUP], user: { ...USER, receives_requests: true } });
    renderHome();
    await screen.findByText(/Lulu/);

    fireEvent.click(screen.getByRole('button', { name: 'Your account' }));

    const menu = screen.getByRole('navigation', { name: 'Your account' });
    expect(within(menu).getByRole('link', { name: 'My profile' })).toHaveAttribute('href', '/me');
    expect(within(menu).getByRole('link', { name: 'My requests' })).toHaveAttribute(
      'href',
      '/my-bookings'
    );
    expect(await within(menu).findByRole('link', { name: 'Requests to me' })).toHaveAttribute(
      'href',
      '/owner-bookings'
    );
  });
});

/**
 * "Create collection" in one place: a new account saw the hero's
 * button and, under "My collections", "Create your first collection" — two buttons
 * for the same thing. With any collection of their own the button is in the hero
 * and the list below is only the list; with none at all it is the invitation
 * below and the hero has none; while the read is in flight there is none yet, and
 * if it fails the hero's is the one that shows.
 */
describe('HomePage — one create button, in one place', () => {
  const INACTIVE = { ...MINE, code: 'COL002', headline: 'Old workshop', status: 'INACTIVE' };
  const heroButton = (container) =>
    container.querySelector('.form-hero')?.querySelector('a[href="/new"]');
  const createLinks = () => document.querySelectorAll('a[href="/new"]');

  test('with no collection at all the hero has none and the invitation is below', async () => {
    mockDashboard({ mine: [], invited: [] });
    const { container } = renderHome();

    await screen.findByRole('link', { name: 'Create your first collection' });
    expect(heroButton(container)).toBeNull();
    expect(createLinks()).toHaveLength(1);
    // Nothing at all, not "no active ones": that is what only-inactive accounts read.
    expect(screen.getByText("You don't have a collection yet.")).toBeInTheDocument();
    expect(screen.queryByText('You have no active collections yet.')).toBeNull();
    // The explainer names the three kinds.
    expect(
      screen.getByText(
        /a stall to give away or sell, a library to lend or rent out, or a shed to book/
      )
    ).toBeInTheDocument();
  });

  test('with an active collection the button is in the hero and nowhere else', async () => {
    mockDashboard({ mine: [MINE] });
    const { container } = renderHome();

    await screen.findByText('My workshop');
    expect(heroButton(container)).toHaveTextContent('Create collection');
    expect(createLinks()).toHaveLength(1);
    expect(screen.queryByRole('link', { name: 'Create your first collection' })).toBeNull();
    expect(screen.queryByText('You have no active collections yet.')).toBeNull();
  });

  test('with only inactive ones: the hero button, the sentence, the list — and no second button', async () => {
    mockDashboard({ mine: [INACTIVE] });
    const { container } = renderHome();

    await screen.findByText('Old workshop');
    expect(heroButton(container)).toHaveTextContent('Create collection');
    expect(screen.getByText('You have no active collections yet.')).toBeInTheDocument();
    expect(createLinks()).toHaveLength(1);
    expect(screen.queryByRole('link', { name: 'Create your first collection' })).toBeNull();
    expect(screen.queryByText(/A collection is where you share your things/)).toBeNull();
    expect(screen.queryByText("You don't have a collection yet.")).toBeNull();
  });

  test('while the read is in flight there is no button, then the right one', async () => {
    let release;
    const held = new Promise((resolve) => {
      release = resolve;
    });
    const routes = dashboardRoutes({ mine: [MINE] });
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/collections/') ? held : routes(url)
    );
    const { container } = renderHome();

    await screen.findByText(/Lulu/);
    expect(screen.getByText('Loading collections...')).toBeInTheDocument();
    expect(createLinks()).toHaveLength(0);

    release({ ok: true, status: 200, json: () => Promise.resolve({ results: [MINE] }) });
    await screen.findByText('My workshop');
    expect(heroButton(container)).toBeInTheDocument();
  });

  test('if the read fails over a working connection the hero keeps its button', async () => {
    const routes = dashboardRoutes({});
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/collections/') ? refused() : routes(url)
    );
    const { container } = renderHome();

    await screen.findByText(/Lulu/);
    await screen.findByText(/couldn.t load/i);
    expect(heroButton(container)).toBeInTheDocument();
    expect(createLinks()).toHaveLength(1);
  });

  test('if the connection drops on that read the hero keeps its button too', async () => {
    const routes = dashboardRoutes({});
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/collections/') ? dropped() : routes(url)
    );
    const { container } = renderHome();

    await screen.findByText(/Lulu/);
    await waitFor(() => expect(heroButton(container)).toBeInTheDocument());
  });
});

/**
 * The dashboard is five reads, and each can fail in its own way. A dropped
 * connection (a rejected fetch) is not the same as a server that answered with
 * an error, and both must be said, with a way to try again — otherwise the page
 * is an endless spinner or a silent gap.
 */
describe('HomePage — when the connection drops', () => {
  test('a dropped connection is said plainly, and Retry brings the dashboard back', async () => {
    apiFetch.mockImplementation(dropped);
    renderHome();

    expect(await screen.findByText('Connection problem')).toBeInTheDocument();
    expect(screen.getByText(/We can't reach OIUEEI right now/)).toBeInTheDocument();
    expect(screen.queryByText('My workshop')).not.toBeInTheDocument();

    mockDashboard({ mine: [MINE] });
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('My workshop')).toBeInTheDocument();
    // The warning goes with the failure it reported.
    expect(screen.queryByText('Connection problem')).not.toBeInTheDocument();
  });

  test('the browser getting its connection back reloads the dashboard without a click', async () => {
    apiFetch.mockImplementation(dropped);
    renderHome();
    await screen.findByText('Connection problem');

    mockDashboard({ mine: [MINE] });
    fireEvent(window, new Event('online'));

    expect(await screen.findByText('My workshop')).toBeInTheDocument();
    expect(screen.queryByText('Connection problem')).not.toBeInTheDocument();
  });

  test('the inbox losing its connection warns on the dashboard too', async () => {
    const routes = dashboardRoutes({ mine: [MINE] });
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/inbox/') ? dropped() : routes(url)
    );
    renderHome();

    // The rest of the page loaded; the banner sits above it, the page stays.
    expect(await screen.findByText('My workshop')).toBeInTheDocument();
    expect(await screen.findByText('Connection problem')).toBeInTheDocument();
  });
});

describe('HomePage — a section the server refuses', () => {
  test('it says so inline, leaves the other section alone, and Retry brings it back', async () => {
    const routes = dashboardRoutes({ invited: [GROUP] });
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/collections/') ? refused() : routes(url)
    );
    renderHome();

    expect(await screen.findByText("Couldn't load this section")).toBeInTheDocument();
    expect(screen.getByText('Bibliocoses')).toBeInTheDocument();
    // Not the connection banner: the connection worked, the answer was an error.
    expect(screen.queryByText('Connection problem')).not.toBeInTheDocument();

    mockDashboard({ mine: [MINE], invited: [GROUP] });
    fireEvent.click(screen.getByRole('button', { name: 'Retry' }));

    expect(await screen.findByText('My workshop')).toBeInTheDocument();
    expect(screen.queryByText("Couldn't load this section")).not.toBeInTheDocument();
  });
});

describe('HomePage — invitations waiting for an answer', () => {
  const TOOLS = {
    accept_code: 'ACC001',
    reject_code: 'REJ001',
    owner_name: 'Lele',
    collection_headline: 'Tools',
  };
  const BOOKS = {
    accept_code: 'ACC002',
    reject_code: 'REJ002',
    owner_name: 'Lili',
    collection_headline: 'Books',
  };

  test('the card says it is an invitation to join, then names the collection', async () => {
    mockDashboard({ mine: [MINE], invitations: [TOOLS] });
    renderHome();

    // "Lele has invited you to join" + the headline on the next line: one sentence.
    const label = await screen.findByText('Lele has invited you to join');
    expect(label).toBeInTheDocument();
    expect(screen.getByText('Tools')).toBeInTheDocument();
    expect(screen.queryByText(/invited you to view/)).toBeNull();
  });

  test('an owner with no name is “A member”, not an empty subject', async () => {
    mockDashboard({ mine: [MINE], invitations: [{ ...TOOLS, owner_name: '' }] });
    renderHome();

    expect(await screen.findByText('A member has invited you to join')).toBeInTheDocument();
  });

  test('dismissing one removes that one and leaves the other waiting', async () => {
    mockDashboard({ mine: [MINE], invitations: [TOOLS, BOOKS] });
    renderHome();
    await screen.findByText('Tools');
    expect(screen.getByText('Books')).toBeInTheDocument();

    fireEvent.click(screen.getAllByRole('button', { name: 'Dismiss' })[0]);

    await waitFor(() => expect(screen.queryByText('Tools')).not.toBeInTheDocument());
    expect(screen.getByText('Books')).toBeInTheDocument();
    // Still answerable: the remaining card keeps its own accept link.
    expect(screen.getByRole('link', { name: 'Accept invitation' })).toHaveAttribute(
      'href',
      '/verify/ACC002'
    );
  });

  // The answer is two buttons, as everywhere else something is
  // decided. They were two text links side by side. The destinations did not change.
  describe('the answer is two buttons', () => {
    // Home is an app page: it wears the app's own palette (`Braaanding`), whatever
    // the account — the profile carries no colours any more.
    const WITH_THEEEME = USER;
    const card = (headline) => screen.getByText(headline).closest('section');
    const accept = (within_) => within_.getByRole('link', { name: 'Accept invitation' });
    const decline = (within_) => within_.getByRole('link', { name: 'Decline invitation' });
    const background = (link) => link.style.getPropertyValue('--background-color');

    test('accepting is the primary and comes first; declining is the secondary, after it', async () => {
      mockDashboard({ mine: [MINE], invitations: [TOOLS], user: WITH_THEEEME });
      renderHome();
      await screen.findByText('Tools');

      const inCard = within(card('Tools'));
      expect(accept(inCard)).toHaveAttribute('href', '/verify/ACC001');
      expect(decline(inCard)).toHaveAttribute('href', '/verify/REJ001');
      // In that order.
      expect(
        accept(inCard).compareDocumentPosition(decline(inCard)) & Node.DOCUMENT_POSITION_FOLLOWING
      ).toBeTruthy();
      // The app palette's tokens: the primary is filled with the first colour, the secondary is
      // white with that colour as its border.
      expect(background(accept(inCard))).toBe('var(--color-braaanding-01)');
      expect(background(decline(inCard))).toBe('var(--color-white)');
      expect(decline(inCard).style.getPropertyValue('--border-color')).toBe(
        'var(--color-braaanding-01)'
      );
    });

    test('they are buttons that are links, not text links', async () => {
      mockDashboard({ mine: [MINE], invitations: [TOOLS], user: WITH_THEEEME });
      renderHome();
      await screen.findByText('Tools');

      const inCard = within(card('Tools'));
      // The class HDS gives a link that wears a button's style (`useButtonStyles`).
      expect(accept(inCard).className).toMatch(/hds-button/);
      expect(decline(inCard).className).toMatch(/hds-button/);
    });

    test('both sit in one wide row, so on a phone each is the width of the screen', async () => {
      mockDashboard({ mine: [MINE], invitations: [TOOLS], user: WITH_THEEEME });
      renderHome();
      await screen.findByText('Tools');

      const inCard = within(card('Tools'));
      const row = accept(inCard).parentElement;
      expect(row).toHaveClass('button-row-wide');
      expect(decline(inCard).parentElement).toBe(row);
    });

    test('with two invitations each card has its own pair, to its own codes', async () => {
      mockDashboard({ mine: [MINE], invitations: [TOOLS, BOOKS], user: WITH_THEEEME });
      renderHome();
      await screen.findByText('Tools');

      const tools = within(card('Tools'));
      const books = within(card('Books'));
      expect(accept(tools)).toHaveAttribute('href', '/verify/ACC001');
      expect(decline(tools)).toHaveAttribute('href', '/verify/REJ001');
      expect(accept(books)).toHaveAttribute('href', '/verify/ACC002');
      expect(decline(books)).toHaveAttribute('href', '/verify/REJ002');
      expect(screen.getAllByRole('link', { name: 'Accept invitation' })).toHaveLength(2);
      expect(background(accept(books))).toBe('var(--color-braaanding-01)');
      expect(background(decline(books))).toBe('var(--color-white)');
    });
  });
});

describe('HomePage — collections that are switched off', () => {
  const SHED = { ...GROUP, code: 'COL002', headline: 'Old shed', status: 'INACTIVE' };

  test('they are listed apart, after the active ones, under their own heading', async () => {
    mockDashboard({ mine: [MINE, SHED] });
    renderHome();

    await screen.findByText('Old shed');
    expect(screen.getByRole('heading', { level: 2, name: 'Inactive collections' })).toBeVisible();
    const active = screen.getByText('My workshop');
    const inactive = screen.getByText('Old shed');
    expect(
      active.compareDocumentPosition(inactive) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  });

  test('a group with nothing switched off shows no such heading', async () => {
    mockDashboard({ mine: [MINE] });
    renderHome();

    await screen.findByText('My workshop');
    expect(screen.queryByRole('heading', { name: 'Inactive collections' })).not.toBeInTheDocument();
  });
});

/**
 * `/collections/` answers one page at a time; a founder of more groups than that
 * has to see them all, not the first page's.
 */
describe('HomePage — more groups than one page holds', () => {
  const many = Array.from({ length: 25 }, (_, i) => ({
    ...GROUP,
    code: `MYC${String(i).padStart(3, '0')}`,
    headline: `Workshop ${i + 1}`,
  }));
  const pagedRoutes = (secondPage) => {
    const routes = dashboardRoutes({});
    return (url) => {
      if (!url.startsWith('/api/v1/collections/')) return routes(url);
      if (url.includes('page=2')) return secondPage();
      return ok({
        results: many.slice(0, 20),
        next: 'https://app.test/api/v1/collections/?page=2&page_size=100',
      });
    };
  };

  test('it follows the next link and lists every group, asking for the biggest page', async () => {
    apiFetch.mockImplementation(pagedRoutes(() => ok({ results: many.slice(20), next: null })));
    renderHome();

    expect(await screen.findByText('Workshop 25')).toBeInTheDocument();
    expect(screen.getByText('Workshop 1')).toBeInTheDocument();
    const listed = apiFetch.mock.calls
      .map(([url]) => url)
      .filter((u) => u.includes('/collections/?'));
    expect(listed).toEqual([
      '/api/v1/collections/?page_size=100',
      '/api/v1/collections/?page=2&page_size=100',
    ]);
  });

  test('a second page that fails lists the groups already read, under the section error', async () => {
    apiFetch.mockImplementation(pagedRoutes(() => refused()));
    renderHome();

    expect(await screen.findByText("Couldn't load this section")).toBeInTheDocument();
    expect(screen.getByText('Workshop 1')).toBeInTheDocument();
    expect(screen.getByText('Workshop 20')).toBeInTheDocument();
    expect(screen.queryByText('Workshop 21')).not.toBeInTheDocument();
  });
});

/**
 * Someone who arrived by a magic link has no name, and whoever runs their groups sees
 * "A member". Home says so kindly until a name (a nickname will do) is there.
 */
describe('HomePage — the nudge to give a name', () => {
  const nudge = () => screen.queryByText('Tell us a little about yourself');

  test('without a name it asks, with a link to the profile that carries no way back', async () => {
    mockDashboard({ mine: [MINE], user: { ...USER, name: '' } });
    renderHome();

    expect(await screen.findByText('Tell us a little about yourself')).toBeInTheDocument();
    expect(screen.getByText(/It takes 2 minutes and it's all optional\./)).toBeInTheDocument();
    const link = screen.getByRole('link', { name: 'Complete my profile' });
    expect(link).toHaveAttribute('href', '/me/edit');
  });

  test('a name of only spaces is no name', async () => {
    mockDashboard({ mine: [MINE], user: { ...USER, name: '   ' } });
    renderHome();
    expect(await screen.findByText('Tell us a little about yourself')).toBeInTheDocument();
  });

  test('with a name there is nothing to ask, and nothing is left in the browser', async () => {
    mockDashboard({ mine: [MINE] });
    renderHome();

    await screen.findByRole('heading', { name: 'Hello, Lulu' });
    expect(nudge()).toBeNull();
    expect(screen.queryByRole('link', { name: 'Complete my profile' })).toBeNull();
  });

  test('it has no close button and stores nothing', async () => {
    const write = vi.spyOn(localStorage, 'setItem');
    mockDashboard({ mine: [MINE], user: { ...USER, name: '' } });
    renderHome();
    await screen.findByText('Tell us a little about yourself');

    expect(screen.queryByRole('button', { name: /dismiss|close/i })).toBeNull();
    // Home already keeps `userCode`; the nudge adds no key of its own.
    expect(write.mock.calls.filter(([key]) => key !== 'userCode')).toEqual([]);
    write.mockRestore();
  });

  test('it comes after the pending invitations and before My collections', async () => {
    mockDashboard({
      mine: [MINE],
      user: { ...USER, name: '' },
      invitations: [
        {
          accept_code: 'ACC001',
          reject_code: 'REJ001',
          owner_name: 'Lili',
          collection_headline: 'Tool bank',
        },
      ],
    });
    renderHome();
    const invitation = await screen.findByText('Tool bank');
    const notice = await screen.findByText('Tell us a little about yourself');
    const mine = screen.getByRole('heading', { level: 2, name: 'My collections' });

    expect(
      invitation.compareDocumentPosition(notice) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(notice.compareDocumentPosition(mine) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test('the page with the nudge has no axe violations', async () => {
    mockDashboard({ mine: [MINE], user: { ...USER, name: '' } });
    const { container } = renderHome();
    await screen.findByText('Tell us a little about yourself');
    expect(await axe(container)).toHaveNoViolations();
  });
});
