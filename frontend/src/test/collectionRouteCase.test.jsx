import { render, screen } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

/**
 * A code is six letters and digits, and two sub-routes of a collection are six
 * letters: `delete` and `import`. React Router ignores case unless a route says
 * otherwise, so `/library/ABC123/DELETE` — a person whose code is `DELETE` — opened
 * the page that deletes the collection. Every sub-route of a collection is
 * case-sensitive; only the whole App can say so, since it is the route table that
 * decides.
 */
// A network whose dinamizadores carry codes written by hand, as the demo's do (lowercase).
const thing = (code, owner, ownerName, headline) => ({
  code,
  type: 'LEND_THING',
  owner,
  owner_name: ownerName,
  headline,
  description: '',
  status: 'ACTIVE',
  fee: null,
  availability: '',
  location: '',
  condition: '',
  thumbnail_url: '',
  gallery: [],
  gallery_urls: [],
  available_today: true,
  next_available: null,
  tags: [],
  pending_questions: 0,
  my_pending_booking: null,
  pending_booking: null,
  bookings: [],
  created: '2026-09-01T10:00:00Z',
  network_point: { display_name: ownerName, address: '', hours_note: '', contact: '' },
});
const NETWORK = {
  code: 'NET001',
  headline: 'Demo network',
  description: '',
  status: 'ACTIVE',
  visibility: 'PRIVATE',
  kind: 'LIBRARY',
  mode: 'NETWORK',
  owner: 'FOUN01',
  owner_name: 'Lala',
  is_curator: false,
  is_member: true,
  co_owners: [
    { code: 'L3L3oo', name: 'Lele' },
    { code: 'l0l0oh', name: 'Lolo' },
  ],
  tags: [],
  invites: [],
  is_paused: false,
  allowed_thing_types: ['LEND_THING'],
  things: [thing('THG001', 'L3L3oo', 'Lele', 'Drill'), thing('THG002', 'l0l0oh', 'Lolo', 'Rake')],
};

globalThis.fetch = vi.fn((url) => {
  if (String(url).includes('/api/v1/collections/NET001/')) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(NETWORK) });
  }
  if (String(url).includes('/inbox/')) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
  }
  const collection = String(url).includes('/api/v1/collections/COL001/');
  return Promise.resolve({
    ok: collection,
    status: collection ? 200 : 401,
    json: () =>
      Promise.resolve(
        collection
          ? { code: 'COL001', headline: 'The lending library', kind: 'LIBRARY', things: [] }
          : {}
      ),
  });
});
window.scrollTo = vi.fn();

async function openApp(path) {
  localStorage.setItem('userCode', 'USR001');
  window.history.pushState({}, '', path);
  const { default: App } = await import('../App');
  render(<App />);
}

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  vi.resetModules();
});

afterEach(() => {
  window.history.pushState({}, '', '/');
});

describe('the sub-routes of a collection tell case apart', () => {
  test('the lowercase sub-route is the page that deletes it', async () => {
    await openApp('/library/COL001/delete');

    expect(await screen.findByRole('heading', { level: 1, name: /Delete/ })).toBeVisible();
  });

  test.each(['DELETE', 'IMPORT'])(
    '%s has the shape of a code, so it is the collection, as a code that names nobody',
    async (segment) => {
      await openApp(`/library/COL001/${segment}`);

      expect(
        await screen.findByRole('heading', { level: 1, name: 'The lending library' })
      ).toBeVisible();
      expect(screen.queryByRole('heading', { name: /Delete/ })).toBeNull();
      expect(screen.queryByRole('heading', { name: 'Add several at once (CSV)' })).toBeNull();
    }
  );

  test('Delete and Import are codes too, of nobody: the collection, not a page', async () => {
    await openApp('/library/COL001/Delete');

    expect(
      await screen.findByRole('heading', { level: 1, name: 'The lending library' })
    ).toBeVisible();
    expect(screen.queryByRole('heading', { name: /Delete/ })).toBeNull();
  });

  test.each(['foo', 'JOIN', 'ABC12', 'ABC1234'])(
    '%s is not the shape of a code: the usual "not found"',
    async (segment) => {
      await openApp(`/library/COL001/${segment}`);

      expect(await screen.findByText('Page not found')).toBeInTheDocument();
      expect(screen.queryByRole('heading', { name: /Delete|Join/ })).toBeNull();
      expect(screen.queryByRole('heading', { name: 'The lending library' })).toBeNull();
    }
  );

  test('a code written by hand, with lowercase, filters the network by that dinamizador', async () => {
    await openApp('/library/NET001/L3L3oo');

    expect(await screen.findByRole('heading', { level: 3, name: 'Drill' })).toBeVisible();
    expect(screen.queryByRole('heading', { level: 3, name: 'Rake' })).toBeNull();
    expect(screen.queryByText('Page not found')).toBeNull();
  });

  test('the lowercase import is still the import page', async () => {
    await openApp('/library/COL001/import');

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Add several at once (CSV)' })
    ).toBeVisible();
  });

  test('`organisation` is a page of the collection, not the filter of a dinamizador', async () => {
    await openApp('/library/COL001/organisation');

    expect(await screen.findByRole('heading', { level: 1, name: 'My organisation' })).toBeVisible();
    expect(screen.queryByText('Page not found')).toBeNull();
    expect(screen.queryByRole('heading', { name: 'The lending library' })).toBeNull();
  });

  test('the old `/point` address leads to the organisation page, replacing the history entry', async () => {
    const before = window.history.length;
    await openApp('/library/COL001/point');

    expect(await screen.findByRole('heading', { level: 1, name: 'My organisation' })).toBeVisible();
    expect(window.location.pathname).toBe('/library/COL001/organisation');
    expect(window.history.length).toBe(before + 1);
  });

  test('the page of a curator is public: a reader with no session opens it, at any kind’s prefix', async () => {
    window.history.pushState({}, '', '/library/NET001/organisation/L3L3oo');
    const { default: App } = await import('../App');
    render(<App />);

    expect(await screen.findByRole('heading', { level: 1, name: 'Lele' })).toBeVisible();
    expect(screen.getByText('Pickup point of Demo network')).toBeVisible();
    expect(screen.queryByRole('heading', { name: /Log in|Sign in/i })).toBeNull();
  });
});
