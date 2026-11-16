import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { axe, toHaveNoViolations } from 'jest-axe';
import { describe, test, expect, beforeEach, vi } from 'vitest';

vi.mock('../services/api', () => ({ apiFetch: vi.fn() }));

import { apiFetch } from '../services/api';
import AccountMenu from './AccountMenu';
import { press, settle } from '../test/settle';
import { iconOf } from '../test/menuEntryIcon';

expect.extend(toHaveNoViolations);

/**
 * The routes one click away from every hero (2026-09-28) — see the
 * component's own docstring for why this is a plain disclosure, not
 * an HDS Select dressed as a menu. Every scenario here mirrors a line
 * from that plan: the trigger's accessible name, aria-expanded toggling,
 * the link set and its order, Escape returning focus, a click outside
 * closing it, no session meaning no render, and an axe pass with the panel
 * open.
 *
 * Since 2026-10-02 the menu is Home, My profile, My requests, "Requests to me" —
 * only for an account that can receive requests, which the server says — and Log
 * out. "Edit profile" is reached from My profile and "Create collection" from Home.
 */

const ALWAYS = [
  { name: /home/i, href: '/' },
  { name: /my profile/i, href: '/me' },
  { name: /my requests/i, href: '/my-bookings' },
];
const REQUESTS_TO_ME = { name: /requests to me/i, href: '/owner-bookings' };
const LOG_OUT = { name: /log out/i, href: '/logout' };

// What GET /auth/me/ answers, as far as the menu reads it.
const meSays = (receivesRequests) =>
  apiFetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ code: 'ABC123', receives_requests: receivesRequests }),
  });

function renderMenu() {
  return render(
    <MemoryRouter>
      <AccountMenu />
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  vi.clearAllMocks();
  meSays(false);
});

describe('AccountMenu — where the reader is', () => {
  const openAt = async (path) => {
    render(
      <MemoryRouter initialEntries={[path]}>
        <AccountMenu />
      </MemoryRouter>
    );
    await press(screen.getByRole('button', { name: /your account/i }));
  };

  test('the link to the page on screen is the current one, and only that one', async () => {
    await openAt('/me');

    expect(screen.getByRole('link', { name: /my profile/i })).toHaveAttribute(
      'aria-current',
      'page'
    );
    for (const name of [/home/i, /my requests/i, /log out/i]) {
      expect(screen.getByRole('link', { name })).not.toHaveAttribute('aria-current');
    }
  });

  test('a page below a link is not that link’s page', async () => {
    await openAt('/me/edit');

    expect(screen.getByRole('link', { name: /my profile/i })).not.toHaveAttribute('aria-current');
  });

  test('Home is current on the root only', async () => {
    await openAt('/');

    expect(screen.getByRole('link', { name: /home/i })).toHaveAttribute('aria-current', 'page');
  });
});

describe('AccountMenu — when focus leaves', () => {
  test('tabbing out of the menu closes the panel', async () => {
    render(
      <MemoryRouter>
        <AccountMenu />
        <button type="button">Outside</button>
      </MemoryRouter>
    );
    await press(screen.getByRole('button', { name: /your account/i }));
    const last = screen.getByRole('link', { name: /log out/i });
    last.focus();

    fireEvent.blur(last, { relatedTarget: screen.getByRole('button', { name: 'Outside' }) });

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  test('moving between the menu’s own controls keeps it open', async () => {
    renderMenu();
    await press(screen.getByRole('button', { name: /your account/i }));
    const first = screen.getByRole('link', { name: /home/i });

    fireEvent.blur(first, { relatedTarget: screen.getByRole('link', { name: /my profile/i }) });

    expect(screen.getAllByRole('link').length).toBeGreaterThan(0);
  });

  test('a blur into nothing (a click that focuses nothing) does not close it', async () => {
    renderMenu();
    await press(screen.getByRole('button', { name: /your account/i }));

    fireEvent.blur(screen.getByRole('button', { name: /your account/i }), { relatedTarget: null });

    expect(screen.getAllByRole('link').length).toBeGreaterThan(0);
  });
});

describe('AccountMenu — signed in', () => {
  test('following a link closes the panel, even to the page already on screen', () => {
    // MemoryRouter at '/': the Home link does not unmount the menu, so only
    // the menu itself can close its panel.
    renderMenu();
    fireEvent.click(screen.getByRole('button', { name: /your account/i }));

    fireEvent.click(screen.getByRole('link', { name: /home/i }));

    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /your account/i })).toHaveAttribute(
      'aria-expanded',
      'false'
    );
  });

  test('the trigger has an accessible name and starts collapsed', () => {
    renderMenu();

    const trigger = screen.getByRole('button', { name: /your account/i });
    expect(trigger).toHaveAttribute('aria-expanded', 'false');
  });

  const expectLinks = (expectedLinks) => {
    const links = screen.getAllByRole('link');
    expect(links).toHaveLength(expectedLinks.length);
    expectedLinks.forEach((expected, i) => {
      expect(links[i]).toHaveAccessibleName(expected.name);
      expect(links[i]).toHaveAttribute('href', expected.href);
    });
  };

  test('a click opens it: aria-expanded flips and the account’s links are there, in order', async () => {
    renderMenu();

    fireEvent.click(screen.getByRole('button', { name: /your account/i }));

    expect(screen.getByRole('button', { name: /your account/i })).toHaveAttribute(
      'aria-expanded',
      'true'
    );
    // An account that cannot receive requests: four links, and no Edit profile or
    // Create collection (the first is under My profile, the second on Home).
    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    expectLinks([...ALWAYS, LOG_OUT]);
    expect(screen.queryByRole('link', { name: /edit profile/i })).toBeNull();
    expect(screen.queryByRole('link', { name: /create collection/i })).toBeNull();
  });

  test('an account that can receive requests also gets "Requests to me", after My requests', async () => {
    meSays(true);
    renderMenu();

    fireEvent.click(screen.getByRole('button', { name: /your account/i }));

    await screen.findByRole('link', { name: /requests to me/i });
    expectLinks([...ALWAYS, REQUESTS_TO_ME, LOG_OUT]);
  });

  test('it asks the server when it opens, not before, and again each time', async () => {
    renderMenu();
    expect(apiFetch).not.toHaveBeenCalled();
    const trigger = screen.getByRole('button', { name: /your account/i });

    fireEvent.click(trigger);
    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(1));
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/auth/me/', expect.anything());
    fireEvent.click(trigger);
    fireEvent.click(trigger);

    await waitFor(() => expect(apiFetch).toHaveBeenCalledTimes(2));
  });

  test('if the answer cannot be had the link is left out rather than guessed', async () => {
    apiFetch.mockRejectedValue(new TypeError('Failed to fetch'));
    renderMenu();

    fireEvent.click(screen.getByRole('button', { name: /your account/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    expectLinks([...ALWAYS, LOG_OUT]);
  });

  test('an error status is no answer either', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 500, json: () => Promise.resolve({}) });
    renderMenu();

    fireEvent.click(screen.getByRole('button', { name: /your account/i }));

    await waitFor(() => expect(apiFetch).toHaveBeenCalled());
    expectLinks([...ALWAYS, LOG_OUT]);
  });

  test('it writes nothing to the browser: the /legal names every key the app stores', async () => {
    meSays(true);
    const wroteLocal = vi.spyOn(localStorage, 'setItem');
    const wroteSession = vi.spyOn(Storage.prototype, 'setItem');
    renderMenu();

    fireEvent.click(screen.getByRole('button', { name: /your account/i }));

    await screen.findByRole('link', { name: /requests to me/i });
    expect(wroteLocal).not.toHaveBeenCalled();
    expect(wroteSession).not.toHaveBeenCalled();
    wroteLocal.mockRestore();
    wroteSession.mockRestore();
  });

  test('a second click closes it again', () => {
    renderMenu();
    const trigger = screen.getByRole('button', { name: /your account/i });

    fireEvent.click(trigger);
    fireEvent.click(trigger);

    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
  });

  test('Escape closes it and returns focus to the trigger', () => {
    renderMenu();
    const trigger = screen.getByRole('button', { name: /your account/i });
    fireEvent.click(trigger);
    expect(screen.getAllByRole('link').length).toBeGreaterThan(0);

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(trigger).toHaveAttribute('aria-expanded', 'false');
    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(trigger).toHaveFocus();
  });

  test('a click outside the menu closes it, without moving focus anywhere in particular', () => {
    render(
      <MemoryRouter>
        <button type="button">Outside</button>
        <AccountMenu />
      </MemoryRouter>
    );
    fireEvent.click(screen.getByRole('button', { name: /your account/i }));
    expect(screen.getAllByRole('link').length).toBeGreaterThan(0);

    fireEvent.pointerDown(screen.getByRole('button', { name: 'Outside' }));

    expect(screen.queryByRole('link')).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /your account/i })).toHaveAttribute(
      'aria-expanded',
      'false'
    );
  });

  test('a click inside the open panel is not mistaken for a click outside', async () => {
    renderMenu();
    await press(screen.getByRole('button', { name: /your account/i }));

    fireEvent.pointerDown(screen.getByRole('link', { name: /my profile/i }));

    // Still open: the panel itself is "inside", so this must not have closed it.
    expect(screen.getAllByRole('link').length).toBeGreaterThan(0);
  });

  test('the open panel has no axe violations', async () => {
    const { container } = renderMenu();
    await press(screen.getByRole('button', { name: /your account/i }));

    const results = await axe(container);
    expect(results).toHaveNoViolations();
  });
});

/**
 * "Requests to me" moved to the collection menu on the pages that have one.
 * `requestsInCollectionMenu` tells the account menu not to offer it
 * there — and not to ask the server about it either. Without the prop (Home, `/me`
 * and every page with no collection menu) nothing changed.
 */
describe('AccountMenu — where the collection menu carries "Requests to me"', () => {
  const renderWithCollectionMenu = () =>
    render(
      <MemoryRouter>
        <AccountMenu requestsInCollectionMenu />
      </MemoryRouter>
    );

  test('it leaves the link out even for an account that receives requests', async () => {
    meSays(true);
    renderWithCollectionMenu();

    await press(screen.getByRole('button', { name: /your account/i }));

    expect(screen.getByRole('link', { name: /my requests/i })).toBeInTheDocument();
    // Let any answer the menu asked for arrive, inside act.
    await settle(apiFetch);
    expect(screen.queryByRole('link', { name: REQUESTS_TO_ME.name })).not.toBeInTheDocument();
  });

  test('it does not ask the server whether the account receives requests', async () => {
    meSays(true);
    renderWithCollectionMenu();

    await press(screen.getByRole('button', { name: /your account/i }));
    await settle(apiFetch);

    expect(apiFetch).not.toHaveBeenCalled();
  });

  test('the rest of the menu is as it was, in order', () => {
    meSays(false);
    renderWithCollectionMenu();

    fireEvent.click(screen.getByRole('button', { name: /your account/i }));

    const names = within(screen.getByRole('navigation'))
      .getAllByRole('link')
      .map((l) => l.textContent);
    expect(names).toEqual(['Home', 'My profile', 'My requests', 'Log out']);
  });

  test('without the prop an account that receives requests still has it, after My requests', async () => {
    meSays(true);
    renderMenu();

    fireEvent.click(screen.getByRole('button', { name: /your account/i }));

    expect(await screen.findByRole('link', { name: REQUESTS_TO_ME.name })).toHaveAttribute(
      'href',
      '/owner-bookings'
    );
  });
});

/**
 * Signed out, the same icon in the same place is a link to sign in:
 * a plain `<Link>` to `/login` that comes back to the page the reader
 * is on, named "Sign in" — not a panel. It was nothing at all. It is not painted on
 * the doors a login never returns to: `/login` itself, `/logout`, `/verify/…`.
 */
describe('AccountMenu — signed out', () => {
  const renderAt = (path) => {
    localStorage.removeItem('userCode');
    return render(
      <MemoryRouter initialEntries={[path]}>
        <AccountMenu />
      </MemoryRouter>
    );
  };

  test('on a public collection it is a "Sign in" link back to that collection, in the trigger’s place', () => {
    const { container } = renderAt('/collections/COL001');

    const link = screen.getByRole('link', { name: 'Sign in' });
    expect(link).toHaveAttribute('href', '/login?next=%2Fcollections%2FCOL001');
    // The trigger's own class — size, colour and place come from it — inside the
    // same wrapper, and an icon the screen reader does not read twice.
    expect(link).toHaveClass('account-menu-trigger');
    expect(container.querySelector('.account-menu')).toContainElement(link);
    expect(link.querySelector('svg')).toHaveAttribute('aria-hidden', 'true');
    // Not the signed-in menu: no button, no panel.
    expect(screen.queryByRole('button', { name: /your account/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('navigation')).not.toBeInTheDocument();
  });

  test('on /legal the way back is /legal itself', () => {
    renderAt('/legal');

    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute(
      'href',
      '/login?next=%2Flegal'
    );
  });

  test('the query string comes along: it is part of the page they were on', () => {
    renderAt('/collections/COL001/things/THG001?x=1');

    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute(
      'href',
      '/login?next=%2Fcollections%2FCOL001%2Fthings%2FTHG001%3Fx%3D1'
    );
  });

  test('where there is nothing to come back to it is a plain /login', () => {
    renderAt('/');

    expect(screen.getByRole('link', { name: 'Sign in' })).toHaveAttribute('href', '/login');
  });

  test.each([
    '/login',
    '/login?next=%2Fcollections%2FCOL001',
    '/logout',
    '/verify/abc123',
    '/rsvp/abc123',
    '/magic-link/abc123',
    '/LOGIN',
    '/%76erify/abc123',
  ])('on %s it paints nothing at all', (path) => {
    const { container } = renderAt(path);

    expect(container).toBeEmptyDOMElement();
  });

  test('with offerSignIn={false} it paints nothing at all, on any page', () => {
    // A door that does not want to send people to /login — the
    // deployment's own open door — says so, and PageLayout hands it down.
    localStorage.removeItem('userCode');
    const { container } = render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <AccountMenu offerSignIn={false} />
      </MemoryRouter>
    );

    expect(container).toBeEmptyDOMElement();
  });

  test('without the prop, or with true, the icon is there — the default is to offer it', () => {
    renderAt('/collections/COL001');
    expect(screen.getByRole('link', { name: 'Sign in' })).toBeInTheDocument();
  });

  test('offerSignIn={false} changes nothing for a reader with a session', () => {
    render(
      <MemoryRouter>
        <AccountMenu offerSignIn={false} />
      </MemoryRouter>
    );

    expect(screen.getByRole('button', { name: /your account/i })).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
  });

  test('it asks the server nothing: the only request the signed-in menu makes is when it opens', () => {
    renderAt('/collections/COL001');

    expect(apiFetch).not.toHaveBeenCalled();
  });

  test('signed in, the link is not there and the menu is the one it always was', () => {
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <AccountMenu />
      </MemoryRouter>
    );

    expect(screen.queryByRole('link', { name: 'Sign in' })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /your account/i })).toBeInTheDocument();
  });

  test('has no axe violations', async () => {
    const { container } = renderAt('/collections/COL001');

    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('AccountMenu — an icon before every entry', () => {
  test('each entry opens with its own decorative icon and keeps its name', async () => {
    meSays(true);
    renderMenu();
    await press(screen.getByRole('button', { name: /your account/i }));
    await settle();

    const icons = {
      Home: 'home',
      'My profile': 'user',
      'My requests': 'my-requests',
      'Requests to me': 'requests-to-me',
      'Log out': 'signout',
    };
    for (const [name, icon] of Object.entries(icons)) {
      expect(iconOf(screen.getByRole('link', { name }), name)).toBe(icon);
    }
  });
});
