import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

/**
 * Rotating or revoking a private group's share link kills every link and QR already
 * handed out. In a network the server leaves that to the founder (SN1), so the hero
 * only offers the two entries to whoever may edit the collection.
 */
window.scrollTo = vi.fn();

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import CollectionPage from '../pages/CollectionPage';

const GROUP = {
  code: 'COL001',
  headline: 'Network',
  description: '',
  status: 'ACTIVE',
  kind: 'LIBRARY',
  mode: 'NETWORK',
  visibility: 'PRIVATE',
  owner: 'FOUN01',
  owner_name: 'Lala',
  is_curator: true,
  language: '',
  thumbnail_url: '',
  tags: [],
  things: [],
  invites: [],
  co_owners: [{ code: 'ENTA01', name: 'Lele' }],
  points: [],
};

async function openShareMenu(group, userCode) {
  localStorage.setItem('userCode', userCode);
  apiFetch.mockImplementation(() =>
    Promise.resolve({ ok: true, status: 200, json: async () => group })
  );
  render(
    <MemoryRouter initialEntries={['/library/COL001']}>
      <Routes>
        <Route path="/:kind/:code" element={<CollectionPage />} />
      </Routes>
    </MemoryRouter>
  );
  fireEvent.click(await screen.findByRole('button', { name: /share collection/i }));
}

beforeEach(() => {
  apiFetch.mockReset();
  localStorage.clear();
});

describe('taking a private group’s share link back', () => {
  test('a dinamizador of a network is not offered rotate or revoke', async () => {
    await openShareMenu(GROUP, 'ENTA01');

    expect(screen.getByRole('button', { name: /qr code/i })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /rotate link/i })).toBeNull();
    expect(screen.queryByRole('button', { name: /stop sharing/i })).toBeNull();
  });

  test('the founder of a network is offered both', async () => {
    await openShareMenu(GROUP, 'FOUN01');

    expect(screen.getByRole('button', { name: /rotate link/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /stop sharing/i })).toBeInTheDocument();
  });

  test('a co-curator of another mode keeps both', async () => {
    await openShareMenu({ ...GROUP, mode: 'PROPRIETARY' }, 'ENTA01');

    expect(screen.getByRole('button', { name: /rotate link/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /stop sharing/i })).toBeInTheDocument();
  });
});
