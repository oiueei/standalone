import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import ThingLinkbox from '../components/ThingLinkbox';
import ThingPage from '../pages/ThingPage';

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });

const THING = {
  code: 'THG001',
  headline: 'A cordless drill',
  description: '',
  type: 'GIFT_THING',
  status: 'ACTIVE',
  owner: 'MEM001',
  owner_name: 'Lele',
  created: '2026-07-01T10:00:00Z',
  thumbnail_url: '',
  gallery_urls: [],
  tags: [],
  collection_code: 'COL001',
};

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  apiFetch.mockImplementation((url) => {
    if (url.includes('/transfers/')) return ok({ total_transfers: 0, transfers: [] });
    if (url.includes('/faq/')) return ok({ results: [] });
    if (url.includes('/calendar/')) return ok([]);
    if (url.includes('/things/')) return ok({ ...THING, owner_name: '' });
    return ok({});
  });
});

const renderCard = (ownerName, { insideGroup = true } = {}) =>
  render(
    <MemoryRouter>
      <ThingLinkbox
        thing={{ ...THING, owner_name: ownerName }}
        collectionCode="COL001"
        collectionMode="COMMUNITY"
        insideGroup={insideGroup}
      />
    </MemoryRouter>
  );

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/things/THG001']}>
      <Routes>
        <Route path="/things/:thingCode" element={<ThingPage />} />
      </Routes>
    </MemoryRouter>
  );

/**
 * A COMMUNITY grid exists to show that a thing was contributed by a *member*,
 * not by the curator — that attribution is half the reason the mode exists.
 * But the API withholds the member's name from a reader with no account (a
 * group's membership is not for the open web), so the card has to keep the
 * fact while losing the person. Empty must not render an empty link.
 */
describe('Community attribution when the name is withheld', () => {
  test('a signed-out reader is told there is a member, not which one', () => {
    renderCard('');

    expect(screen.getByText(/A member/)).toBeInTheDocument();
    // No link: the profile behind it is IsAuthenticated, so for this reader it
    // was only ever a door onto a 403.
    expect(screen.queryByRole('link', { name: /A member/ })).not.toBeInTheDocument();
  });

  test('a name that was served links to the member, for someone inside the group', () => {
    renderCard('Lele');

    expect(screen.getByRole('link', { name: 'Lele' })).toBeInTheDocument();
    expect(screen.queryByText(/A member/)).not.toBeInTheDocument();
  });

  test('the detail page names the stand-in only for a signed-out reader', async () => {
    renderPage();

    expect(await screen.findByText(/A member/)).toBeInTheDocument();
  });

  test('a signed-in reader with an unnamed owner is not called "a member"', async () => {
    localStorage.setItem('userCode', 'SOMEBODY');
    renderPage();

    expect(await screen.findByText('A cordless drill')).toBeInTheDocument();
    // Their name is simply unset — inventing "A member" would state something
    // about them that the withholding rule never said.
    expect(screen.queryByText(/A member/)).not.toBeInTheDocument();
  });
});
