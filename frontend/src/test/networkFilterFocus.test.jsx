import { render, screen, fireEvent, act, waitFor } from '@testing-library/react';
import { settle } from './settle';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

/**
 * Pressing a dinamizador in a network's filter changes the address, and the app moves
 * the focus to the page and scrolls to the top on every new address. For the filter that
 * would take the reader off the button they pressed (a keyboard, a screen reader) and
 * throw the list to the top on a phone. The filter asks to keep the place
 * (`state.keepFocus`); a real change of page still moves the focus to `<main>`.
 * It also replaces the history entry, so "Back" leaves the collection instead of walking
 * through filters, as the tags (which leave no history) do.
 */
const thing = (code, owner, name, headline) => ({
  code,
  type: 'LEND_THING',
  owner,
  owner_name: name,
  headline,
  description: '',
  status: 'ACTIVE',
  tags: [],
  gallery_urls: [],
  bookings: [],
  created: '2026-09-01T10:00:00Z',
  network_point: { display_name: name, address: '', hours_note: '', contact: '' },
});

const NETWORK = {
  code: 'COL001',
  headline: 'Neighbourhood network',
  kind: 'LIBRARY',
  mode: 'NETWORK',
  status: 'ACTIVE',
  visibility: 'PRIVATE',
  owner: 'FOUN01',
  owner_name: 'Lala',
  is_member: true,
  co_owners: [{ code: 'ENTA01', name: 'Lele' }],
  tags: [],
  invites: [],
  allowed_thing_types: ['LEND_THING', 'RENT_THING'],
  things: [thing('THG001', 'ENTA01', 'Lele', 'Drill'), thing('THG002', 'FOUN01', 'Lala', 'Saw')],
};

globalThis.fetch = vi.fn((url) => {
  const body = String(url).includes('/api/v1/collections/COL001/')
    ? NETWORK
    : String(url).includes('/inbox/')
      ? []
      : {};
  return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
});
window.scrollTo = vi.fn();

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'MEMB01');
  vi.clearAllMocks();
  vi.resetModules();
  window.history.pushState({}, '', '/library/COL001');
});
// The page asks for more than the collection (the inbox, for one) and a test can end on a
// synchronous assertion before those answers land: outside `act`, which setup.js fails.
afterEach(async () => {
  await settle(globalThis.fetch);
});
afterEach(() => window.history.pushState({}, '', '/'));

async function openApp() {
  const { default: App } = await import('../App');
  render(<App />);
  await screen.findByText('Drill');
  // The inbox is asked for once the collection is painted; its answer is waited for here,
  // inside the test, and not left to land right after this returns.
  await settle(globalThis.fetch);
}

describe('the network’s filter keeps the reader where they are', () => {
  test('the pressed button keeps the focus and the page does not scroll', async () => {
    await openApp();
    const group = screen.getByRole('group', { name: 'Who lends' });
    const button = Array.from(group.querySelectorAll('button')).find((b) =>
      b.textContent.startsWith('Lele')
    );
    button.focus();
    window.scrollTo.mockClear();

    fireEvent.click(button);

    expect(window.location.pathname).toBe('/library/COL001/ENTA01');
    expect(document.activeElement).toBe(button);
    expect(window.scrollTo).not.toHaveBeenCalled();
  });

  test('the filter replaces the history entry: Back leaves the collection, not the filters', async () => {
    await openApp();
    const before = window.history.length;
    const group = screen.getByRole('group', { name: 'Who lends' });

    fireEvent.click(
      Array.from(group.querySelectorAll('button')).find((b) => b.textContent.startsWith('Lele'))
    );

    expect(window.history.length).toBe(before);
  });

  test('coming back to a filtered address from another page brings the focus to the main content', async () => {
    await openApp();
    const group = screen.getByRole('group', { name: 'Who lends' });
    fireEvent.click(
      Array.from(group.querySelectorAll('button')).find((b) => b.textContent.startsWith('Lele'))
    );
    // A real move within the app, from the footer: a new history entry after the filter.
    fireEvent.click(screen.getByRole('link', { name: /Privacy & legal/ }));
    // The move has landed once the app has taken the focus to the page (the address
    // changes first; the page itself loads lazily).
    await waitFor(() => expect(document.activeElement).toBe(document.getElementById('main')));
    expect(window.location.pathname).toBe('/legal');
    document.getElementById('main').blur();
    window.scrollTo.mockClear();

    await act(async () => {
      window.history.back();
      await new Promise((resolve) => setTimeout(resolve, 50));
    });

    await waitFor(() => expect(window.location.pathname).toBe('/library/COL001/ENTA01'));
    await waitFor(() => expect(document.activeElement).toBe(document.getElementById('main')));
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' });
    // Going back mounts the collection again, and with it the inbox's request.
    await settle(globalThis.fetch);
  });

  test('going to another page still brings the focus to the main content', async () => {
    await openApp();

    await act(async () => {
      window.history.pushState({}, '', '/legal');
      window.dispatchEvent(new PopStateEvent('popstate'));
    });

    await waitFor(() => expect(document.activeElement).toBe(document.getElementById('main')));
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' });
  });
});
