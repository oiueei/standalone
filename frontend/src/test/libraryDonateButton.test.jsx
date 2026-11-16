import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import CollectionPage from '../pages/CollectionPage';

/**
 * "Donate things" in the hero of a library that accepts donations: a secondary button,
 * **last in the row of each reader**, for everyone who reads the library except its team.
 */
const LIBRARY = {
  code: 'COL001',
  headline: 'Tool library',
  description: '',
  status: 'ACTIVE',
  visibility: 'PUBLIC',
  mode: 'PROPRIETARY',
  kind: 'LIBRARY',
  owner: 'OWNER1',
  owner_name: 'Lala',
  is_curator: false,
  is_member: false,
  co_owners: [],
  thumbnail_url: '',
  tags: [],
  things: [],
  invites: [],
  is_paused: false,
  allowed_thing_types: ['LEND_THING', 'RENT_THING'],
  digest_frequency: 'NONE',
  allow_member_proposals: false,
  accepts_donations: true,
  donations_info: 'Bring books on Tuesdays.',
};

function renderCollection(over = {}, { signedIn = true } = {}) {
  localStorage.clear();
  if (signedIn) localStorage.setItem('userCode', 'ABC123');
  const collection = { ...LIBRARY, ...over };
  apiFetch.mockImplementation((url) =>
    Promise.resolve({
      ok: true,
      status: 200,
      json: async () => (url.startsWith('/api/v1/inbox/') ? [] : collection),
    })
  );
  return render(
    <MemoryRouter initialEntries={['/library/COL001']}>
      <Routes>
        {['library', 'stall', 'shed'].map((prefix) => (
          <Route key={prefix} path={`/${prefix}/:code`} element={<CollectionPage />} />
        ))}
      </Routes>
    </MemoryRouter>
  );
}

// Every control of the hero's rows, in document order (links and buttons alike).
const rows = (container) => [...container.querySelectorAll('.form-hero .button-row-wide > *')];
const labels = (container) => rows(container).map((el) => el.textContent);
const donate = (container) => rows(container).find((el) => el.textContent === 'Donate things');
const isPrimary = (el) => el.style.getPropertyValue('--background-color') !== 'var(--color-white)';

beforeEach(() => vi.clearAllMocks());

describe('who is offered "Donate things"', () => {
  test('a reader with no session, after "Sign in"', async () => {
    const { container } = renderCollection({}, { signedIn: false });
    await screen.findByRole('heading', { level: 1, name: /Tool library/ });

    expect(labels(container)).toEqual(['Sign in', 'Donate things']);
    expect(donate(container)).toHaveAttribute('href', '/library/COL001/donate');
    expect(donate(container)).toBeInstanceOf(HTMLAnchorElement);
  });

  test('a signed-in reader who is not a member, after "Join this group"', async () => {
    const { container } = renderCollection();
    await screen.findByRole('heading', { level: 1, name: /Tool library/ });

    expect(labels(container)).toEqual(['Join this group', 'Donate things']);
  });

  test('a member of a library with nothing else to offer has a row of the button alone', async () => {
    const { container } = renderCollection({ is_member: true });
    await screen.findByRole('heading', { level: 1, name: /Tool library/ });

    expect(labels(container)).toEqual(['Donate things']);
  });

  test('a member who may recommend people: after "Invite someone"', async () => {
    const { container } = renderCollection({ is_member: true, allow_member_proposals: true });
    await screen.findByRole('heading', { level: 1, name: /Tool library/ });

    expect(labels(container)).toEqual(['Invite someone', 'Donate things']);
  });

  test('a member of a demo library: after "Leave the group"', async () => {
    const { container } = renderCollection({ is_member: true, is_onboarding: true });
    await screen.findByRole('heading', { level: 1, name: /Tool library/ });

    expect(labels(container)).toEqual(['Leave the group', 'Donate things']);
  });

  test('it is secondary, and never the row’s only primary taken from the primary', async () => {
    const { container } = renderCollection({ is_member: true, allow_member_proposals: true });
    await screen.findByRole('heading', { level: 1, name: /Tool library/ });

    expect(rows(container).map(isPrimary)).toEqual([true, false]);
  });
});

describe('who is not', () => {
  test.each([
    ['the founder', { owner: 'ABC123', is_curator: true }],
    ['a co-curator', { is_curator: true, co_owners: [{ code: 'ABC123', name: 'Me' }] }],
    [
      'a curator the payload also lists as a member',
      { is_curator: true, is_member: true, co_owners: [{ code: 'ABC123', name: 'Me' }] },
    ],
    [
      'a dinamizador of a network',
      { mode: 'NETWORK', is_curator: true, co_owners: [{ code: 'ABC123', name: 'Me' }] },
    ],
  ])('%s', async (_who, over) => {
    const { container } = renderCollection(over);
    await screen.findByRole('heading', { level: 1, name: /Tool library/ });

    expect(screen.queryByRole('link', { name: 'Donate things' })).toBeNull();
    expect(labels(container)).not.toContain('Donate things');
  });

  test('anyone, when the library does not accept donations', async () => {
    const { container } = renderCollection({ accepts_donations: false, is_member: true });
    await screen.findByRole('heading', { level: 1, name: /Tool library/ });

    expect(labels(container)).not.toContain('Donate things');
    expect(rows(container)).toHaveLength(0);
  });

  test('a stall that still carries the flag from old data', async () => {
    const { container } = renderCollection({
      kind: 'STALL',
      allowed_thing_types: ['GIFT_THING', 'SELL_THING'],
      is_member: true,
    });
    await screen.findByRole('heading', { level: 1, name: /Tool library/ });

    expect(labels(container)).not.toContain('Donate things');
  });
});
