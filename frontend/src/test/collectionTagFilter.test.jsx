import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import CollectionPage from '../pages/CollectionPage';

const LOCALIZED_TAG = '{"es": "Crianza", "ca": "Criança"}';

const COLLECTION = {
  code: 'COL001',
  headline: 'Toy library',
  description: 'Shared toys',
  status: 'ACTIVE',
  visibility: 'PRIVATE',
  mode: 'COMMUNITY',
  owner: 'ABC123',
  owner_name: 'Test User',
  thumbnail_url: '',
  tags: [LOCALIZED_TAG, 'Books'],
  things: [
    {
      code: 'THG001',
      headline: 'Cot',
      type: 'GIFT_THING',
      status: 'ACTIVE',
      tags: [LOCALIZED_TAG],
      owner: 'ABC123',
    },
    {
      code: 'THG002',
      headline: 'Picture book',
      type: 'GIFT_THING',
      status: 'ACTIVE',
      tags: ['Books'],
      owner: 'ABC123',
    },
  ],
  invites: [],
  is_paused: false,
  is_swap: false,
  is_share: false,
  allowed_thing_types: [],
};

function setApi() {
  apiFetch.mockImplementation(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(COLLECTION) })
  );
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  vi.clearAllMocks();
  setApi();
});

describe('CollectionPage tag filter chips (S6)', () => {
  test('resolves a localized tag label instead of rendering raw JSON, and still filters by it', async () => {
    render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
        </Routes>
      </MemoryRouter>
    );

    const chip = await screen.findByRole('button', { name: /Crianza \(1\)/ });
    // The resolved label never leaks the raw braces.
    expect(screen.queryByText(/\{"es"/)).not.toBeInTheDocument();

    fireEvent.click(chip);

    await waitFor(() => {
      expect(screen.getByText('Cot')).toBeInTheDocument();
      expect(screen.queryByText('Picture book')).not.toBeInTheDocument();
    });
  });
});
