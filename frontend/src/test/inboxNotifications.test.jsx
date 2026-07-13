import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import CollectionPage from '../pages/CollectionPage';
import HomePage from '../pages/HomePage';

const REQUEST_NOTIFICATION = {
  code: 'NOT001',
  type: 'BOOKING_REQUESTED',
  payload: {
    thing_headline: 'The drill',
    requester_name: 'Lele',
    booking_code: 'BKG001',
    thing_code: 'THG001',
    collection_code: 'COL001',
  },
  created: '2026-07-13T10:00:00Z',
};

// A notification from another collection: Home shows it, COL001's page must not.
const ELSEWHERE_NOTIFICATION = {
  code: 'NOT002',
  type: 'FAQ_QUESTION',
  payload: {
    thing_headline: 'A ladder',
    questioner_name: 'Lili',
    thing_code: 'THG009',
    collection_code: 'COL009',
  },
  created: '2026-07-13T09:00:00Z',
};

const COLLECTION = {
  code: 'COL001',
  headline: 'Toy library',
  description: 'Shared toys',
  status: 'ACTIVE',
  visibility: 'PRIVATE',
  mode: 'PROPRIETARY',
  owner: 'ABC123',
  owner_name: 'Test User',
  thumbnail_url: '',
  tags: [],
  things: [],
  invites: [],
  is_paused: false,
  is_swap: false,
  is_share: false,
  allowed_thing_types: [],
};

const USER = { code: 'ABC123', name: 'Test User', email: 'me@test.com', koro: 'basic' };

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });

/** Route by URL like the real API does — the inbox filter is the point of the test. */
function setApi() {
  apiFetch.mockImplementation((url) => {
    if (url.startsWith('/api/v1/inbox/?collection=')) return ok([REQUEST_NOTIFICATION]);
    if (url.startsWith('/api/v1/inbox/')) return ok([REQUEST_NOTIFICATION, ELSEWHERE_NOTIFICATION]);
    if (url.startsWith('/api/v1/auth/me/')) return ok(USER);
    if (url.startsWith('/api/v1/collections/COL001/')) return ok(COLLECTION);
    if (url.startsWith('/api/v1/collections/')) return ok({ results: [] });
    return ok([]);
  });
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  vi.clearAllMocks();
  setApi();
});

const renderCollection = () =>
  render(
    <MemoryRouter initialEntries={['/collections/COL001']}>
      <Routes>
        <Route path="/collections/:code" element={<CollectionPage />} />
      </Routes>
    </MemoryRouter>
  );

describe('InboxNotifications (O1)', () => {
  test('the owner sees the collection\'s own notifications on its page', async () => {
    renderCollection();

    expect(await screen.findByText(/The drill/)).toBeInTheDocument();
    // Scoped: it asked the API for this collection only.
    expect(apiFetch).toHaveBeenCalledWith(
      '/api/v1/inbox/?collection=COL001',
      expect.anything()
    );
    // And the request deep-links the thing, so the owner can go and answer it.
    expect(screen.getByRole('link', { name: /view/i })).toHaveAttribute(
      'href',
      '/collections/COL001/things/THG001'
    );
  });

  test('a guest gets no inbox on the collection page', async () => {
    localStorage.setItem('userCode', 'GUEST1');
    renderCollection();

    await screen.findByText('Toy library');
    expect(screen.queryByText(/The drill/)).not.toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/inbox/'),
      expect.anything()
    );
  });

  test('Home still shows every notification, whatever collection it came from', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/The drill/)).toBeInTheDocument();
      expect(screen.getByText(/A ladder/)).toBeInTheDocument();
    });
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/inbox/', expect.anything());
  });
});
