import { render, screen } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { vi, describe, test, expect } from 'vitest';

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() => Promise.resolve({ ok: true, status: 200, json: async () => [] })),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import ThingLinkbox from '../components/ThingLinkbox';

/**
 * On the owner's card, the list of a thing's bookings says how many of it a request
 * holds ("4 × Arduino kit"), and nothing of the sort for a single one.
 */
const loan = (quantity) => ({
  code: 'THG001',
  type: 'LEND_THING',
  headline: 'Arduino kit',
  description: '',
  status: 'ACTIVE',
  owner: 'OWNER1',
  owner_name: 'Lala',
  can_manage: true,
  units: 6,
  thumbnail_url: '',
  gallery_urls: [],
  transfer_count: 0,
  bookings: [
    {
      code: 'BKG001',
      status: 'ACCEPTED',
      requester_name: 'Lele',
      created: '2026-07-20T10:00:00Z',
      start_date: '2099-10-05',
      end_date: '2099-10-06',
      quantity,
    },
  ],
});

const renderCard = (thing) =>
  render(
    <MemoryRouter>
      <ThingLinkbox thing={thing} userCode="OWNER1" onUpdateThing={() => {}} />
    </MemoryRouter>
  );

describe('the owner’s card — a request for several', () => {
  test('names the thing with how many', () => {
    renderCard(loan(4));

    expect(screen.getByText(/4 × Arduino kit\. Lele\./)).toBeInTheDocument();
  });

  test('says nothing of it for one', () => {
    renderCard(loan(1));

    expect(screen.getByText(/Lele\./)).toBeInTheDocument();
    expect(screen.queryByText(/×/)).toBeNull();
  });
});
