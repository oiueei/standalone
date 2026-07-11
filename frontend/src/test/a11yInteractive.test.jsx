import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

expect.extend(toHaveNoViolations);
window.scrollTo = vi.fn();

// The `region` rule checks whole-page landmark structure (needs a <main>); it is
// orthogonal to whether an opened widget is itself accessible, and once an
// overlay adds a landmark it spuriously flags the rest of the page fragment. We
// keep it enabled for the base-page scan and drop it only for the overlay scans.
const NO_REGION = { rules: { region: { enabled: false } } };

// The plain smoke suite renders every page with an EMPTY collection, so
// ThingLinkbox is never axe-scanned and the owner overlays (broadcast form, QR
// dialog) are never opened. This suite fills that gap: an owner viewing a
// POPULATED, PUBLIC collection, then opening those interactive surfaces.

const MOCK_USER = {
  code: 'ABC123', email: 'me@test.com', name: 'Owner', headline: '', about: '',
  photo: '', photo_url: '', koro: 'basic', notify_activity: true, notify_news: true,
  theeeme_colors: { color_01: 'bus', color_02: 'suomenlinna-medium-light', color_03: 'copper', color_04: 'black', color_05: 'black', color_06: 'white' },
};

const MOCK_THING = {
  code: 'THG001', type: 'GIFT_THING', headline: 'Test Thing', description: 'A test thing',
  status: 'ACTIVE', owner: 'ABC123', owner_name: 'Owner', fee: null, availability: '',
  location: '', condition: '', thumbnail_url: 'https://res.cloudinary.com/demo/image/upload/x.jpg',
  gallery: [], gallery_urls: [], available_today: null, next_available: null,
  tags: ['Vintage'], collection_tags: ['Vintage'], pending_questions: 0,
  my_pending_booking: null, pending_booking: null,
};

const MOCK_COLLECTION = {
  code: 'COL001', headline: 'Test Collection', description: 'A test collection',
  status: 'ACTIVE', mode: 'PROPRIETARY', visibility: 'PUBLIC', owner: 'ABC123',
  owner_name: 'Owner', thumbnail_url: '', tags: ['Vintage'], is_member: false,
  is_paused: false, things: [MOCK_THING], invites: [{ code: 'GUE001', name: 'Guest', email: 'g@test.com' }],
};

function mockResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

vi.mock('../services/api', () => ({
  apiFetch: vi.fn((url) => {
    if (url.includes('/auth/me/')) return Promise.resolve(mockResponse(MOCK_USER));
    if (url.match(/\/things\/[^/]+\/calendar\//)) return Promise.resolve(mockResponse([]));
    if (url.match(/\/collections\/[^/]+\//)) return Promise.resolve(mockResponse(MOCK_COLLECTION));
    return Promise.resolve(mockResponse({}));
  }),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import CollectionPage from '../pages/CollectionPage';

function renderCollection() {
  return render(
    <MemoryRouter initialEntries={['/collections/COL001']}>
      <Routes>
        <Route path="/collections/:code" element={<CollectionPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  localStorage.setItem('theeemeColors', JSON.stringify(MOCK_USER.theeeme_colors));
  localStorage.setItem('koro', 'basic');
  vi.clearAllMocks();
});

describe('CollectionPage (owner, populated) — interactive a11y', () => {
  test('the populated collection with ThingLinkbox cards has no axe violations', async () => {
    const { container } = renderCollection();
    // Wait for the thing card to render (ThingLinkbox — never scanned by smoke).
    await screen.findByText('Test Thing');
    expect(await axe(container)).toHaveNoViolations();
  });

  test('the opened broadcast form has no axe violations', async () => {
    const { container } = renderCollection();
    await screen.findByText('Test Thing');

    fireEvent.click(screen.getByRole('button', { name: 'Send a message to guests' }));
    await waitFor(() => expect(container.querySelector('#broadcast-message')).toBeTruthy());

    expect(await axe(container, NO_REGION)).toHaveNoViolations();
  });

  test('the opened QR share dialog has no axe violations', async () => {
    renderCollection();
    await screen.findByText('Test Thing');

    fireEvent.click(screen.getByRole('combobox', { name: /Share collection/ }));
    fireEvent.click(await screen.findByRole('option', { name: 'QR code' }));

    // The Dialog renders in a portal on document.body.
    await waitFor(() => expect(document.querySelector('.share-qr-code')).toBeTruthy());
    expect(await axe(document.body, NO_REGION)).toHaveNoViolations();
  });
});
