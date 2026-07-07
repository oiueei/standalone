import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// PageLayout/RouteFocusReset call scrollTo in jsdom.
window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import ThingPage from '../pages/ThingPage';

const WISH = {
  code: 'WSH001',
  type: 'WISH_THING',
  headline: 'Looking for a tent',
  status: 'ACTIVE',
  owner: 'OWNER1',
  owner_name: 'Owner One',
  thumbnail_url: '',
  gallery_urls: [],
  transfer_count: 0,
  collection_code: 'COL001',
};

const RESPONSE = {
  code: 'RSP001',
  kind: 'KNOW_WHERE',
  status: 'PENDING',
  responder_name: 'Helper',
  message: 'I saw one at the shop',
};

const ok = (data) => ({ ok: true, status: 200, json: () => Promise.resolve(data) });

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'OWNER1'); // owner of the wish → sees owner actions
  localStorage.setItem(
    'theeemeColors',
    JSON.stringify({
      color_01: 'bus',
      color_02: 'fog',
      color_03: 'summer',
      color_04: 'black',
      color_05: 'black',
      color_06: 'white',
    })
  );
  localStorage.setItem('koro', 'basic');
  apiFetch.mockImplementation((url) => {
    if (/\/responses\//.test(url)) return Promise.resolve(ok({ results: [RESPONSE] }));
    if (/\/faq\//.test(url)) return Promise.resolve(ok({ results: [] }));
    if (/\/transfers\//.test(url)) return Promise.resolve(ok({ total_transfers: 0, transfers: [] }));
    if (/\/calendar\//.test(url)) return Promise.resolve(ok([]));
    if (/\/accept\//.test(url)) return Promise.resolve(ok({ status: 'ACCEPTED' }));
    if (/\/resolve\//.test(url)) return Promise.resolve(ok({}));
    return Promise.resolve(ok(WISH));
  });
});

function renderPage() {
  render(
    <MemoryRouter initialEntries={['/things/WSH001']}>
      <Routes>
        <Route path="/things/:thingCode" element={<ThingPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ThingPage wish consequence confirms (DESIGN B1)', () => {
  test('accepting an answer confirms before it commits', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /^accept$/i }));

    // The consequence confirm shows and nothing is committed yet.
    expect(screen.getByText(/other answers stay open/i)).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalledWith(
      '/api/v1/wish-responses/RSP001/accept/',
      expect.anything()
    );

    fireEvent.click(screen.getByRole('button', { name: /accept answer/i }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/wish-responses/RSP001/accept/',
        expect.objectContaining({ method: 'POST' })
      )
    );
  });

  test('resolving a wish confirms before it commits', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: /mark as resolved/i }));

    expect(screen.getByText(/leaves the active board/i)).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalledWith(
      '/api/v1/things/WSH001/resolve/',
      expect.anything()
    );

    fireEvent.click(screen.getByRole('button', { name: /^mark resolved$/i }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/things/WSH001/resolve/',
        expect.objectContaining({ method: 'POST' })
      )
    );
  });
});
