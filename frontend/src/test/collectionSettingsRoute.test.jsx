import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

/**
 * `/{kind}/:code/settings/appearance` is a route of the app, protected like the other
 * sub-routes of a collection, and is not read as the optional `/:curatorCode?` of the
 * collection's own page. Only the whole App can say the route table has it.
 */
globalThis.fetch = vi.fn((url) => {
  const u = String(url);
  if (u.includes('/theeemes/') || u.includes('/inbox/')) {
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
  }
  const collection = u.includes('/api/v1/collections/COL001/');
  return Promise.resolve({
    ok: collection,
    status: collection ? 200 : 401,
    json: () =>
      Promise.resolve(
        collection
          ? {
              code: 'COL001',
              headline: 'The lending library',
              kind: 'LIBRARY',
              is_curator: true,
              things: [],
            }
          : {}
      ),
  });
});
window.scrollTo = vi.fn();

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  vi.resetModules();
});

afterEach(() => {
  window.history.pushState({}, '', '/');
});

describe('the appearance route', () => {
  test('a signed-in reader gets the page, not the collection filtered by a dinamizador', async () => {
    localStorage.setItem('userCode', 'USR001');
    window.history.pushState({}, '', '/library/COL001/settings/appearance');
    const { default: App } = await import('../App');
    render(<App />);

    expect(await screen.findByRole('heading', { level: 1, name: 'Appearance' })).toBeVisible();
    expect(screen.queryByText('Page not found')).toBeNull();
  });

  test('the notifications page is a route too', async () => {
    localStorage.setItem('userCode', 'USR001');
    window.history.pushState({}, '', '/library/COL001/settings/notifications');
    const { default: App } = await import('../App');
    render(<App />);

    expect(await screen.findByRole('heading', { level: 1, name: 'Notifications' })).toBeVisible();
    expect(screen.queryByText('Page not found')).toBeNull();
  });

  test('the availability page is a route too', async () => {
    localStorage.setItem('userCode', 'USR001');
    window.history.pushState({}, '', '/library/COL001/settings/availability');
    const { default: App } = await import('../App');
    render(<App />);

    expect(await screen.findByRole('heading', { level: 1, name: 'Availability' })).toBeVisible();
    expect(screen.queryByText('Page not found')).toBeNull();
  });

  test('a reader with no session is sent to sign in, and brought back to it', async () => {
    window.history.pushState({}, '', '/library/COL001/settings/appearance');
    const { default: App } = await import('../App');
    render(<App />);

    await waitFor(() => expect(window.location.pathname).toBe('/login'));
    expect(new URLSearchParams(window.location.search).get('next')).toBe(
      '/library/COL001/settings/appearance'
    );
  });
});

describe('the way to the general settings', () => {
  test('a curator opens the pencil, picks General and lands on the edit page', async () => {
    localStorage.setItem('userCode', 'USR001');
    const FULL = {
      code: 'COL001',
      headline: 'The lending library',
      description: '',
      status: 'ACTIVE',
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
      kind: 'LIBRARY',
      owner: 'USR001',
      owner_name: 'Me',
      is_curator: true,
      is_member: false,
      allowed_thing_types: ['LEND_THING'],
      language: '',
      thumbnail_url: '',
      tags: [],
      things: [],
      invites: [],
      pending_invites: [],
      co_owners: [],
      points: [],
    };
    globalThis.fetch = vi.fn((url) => {
      const u = String(url);
      const isCollection = u.includes('/api/v1/collections/COL001/');
      return Promise.resolve({
        ok: true,
        status: 200,
        json: () => Promise.resolve(isCollection ? FULL : []),
      });
    });
    window.history.pushState({}, '', '/library/COL001');
    const { default: App } = await import('../App');
    render(<App />);

    fireEvent.click(await screen.findByRole('button', { name: 'Settings' }));
    const general = screen.getByRole('link', { name: 'General' });
    expect(general).toHaveAttribute('href', '/library/COL001/edit');
    fireEvent.click(general);

    expect(await screen.findByRole('heading', { level: 1, name: 'General' })).toBeVisible();
    expect(window.location.pathname).toBe('/library/COL001/edit');
  });
});
