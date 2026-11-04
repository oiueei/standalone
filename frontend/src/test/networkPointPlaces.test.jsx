import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import ThingInfoRows from '../components/ThingInfoRows';
import ThingPage from '../pages/ThingPage';
import RequestThingPage from '../pages/RequestThingPage';
import { settle } from './settle';

/**
 * "Lent by {point} · {address} · {hours}" says who lends a thing of a network and where
 * it is collected. It belongs where the thing is read and asked for — its page and its
 * request page — and not on the card of the collection, where the filter above the grid
 * already says who lends. The card and the page share `ThingInfoRows`, so the line is
 * the page's to hand it.
 */
const POINT = {
  display_name: 'Cooperativa La Fusteria',
  address: 'Carrer Major 4',
  hours_note: 'martes y jueves',
  contact: '',
};
const THING = {
  code: 'THG001',
  type: 'LEND_THING',
  headline: 'Drill',
  description: '',
  status: 'ACTIVE',
  owner: 'OWNER1',
  owner_name: 'Owner One',
  fee: null,
  thumbnail_url: '',
  gallery_urls: [],
  transfer_count: 0,
  available_today: true,
  next_available: null,
  collection_code: 'COL001',
  collection_headline: 'Network',
  network_point: POINT,
};
const LINE = 'Lent by Cooperativa La Fusteria Carrer Major 4 martes y jueves';

const json = (data) => ({ ok: true, status: 200, json: () => Promise.resolve(data) });

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'USR001');
  vi.clearAllMocks();
  apiFetch.mockImplementation((url) => {
    if (/\/things\/THG001\/(faq|transfers)\//.test(url))
      return Promise.resolve(json({ results: [], transfers: [], total_transfers: 0 }));
    if (/\/things\/THG001\/calendar\//.test(url)) return Promise.resolve(json([]));
    if (/\/things\/THG001\//.test(url)) return Promise.resolve(json(THING));
    return Promise.resolve(json({}));
  });
});

describe('where the pickup point line is', () => {
  test('the info rows of a card carry none: they only have it if a view hands it in', () => {
    render(<ThingInfoRows thing={THING} isDateBased />);

    expect(screen.queryByTestId('network-point-line')).toBeNull();
  });

  test('the thing’s page opens its rows with it', async () => {
    render(
      <MemoryRouter initialEntries={['/collections/COL001/things/THG001']}>
        <Routes>
          <Route path="/collections/:code/things/:thingCode" element={<ThingPage />} />
        </Routes>
      </MemoryRouter>
    );

    const line = await screen.findByTestId('network-point-line');
    expect(line).toHaveTextContent(LINE);
    expect(line).toHaveClass('network-point');
    expect(line.parentElement).toHaveClass('thing-card-info');
    await settle(apiFetch);
  });

  test('the request page has it too', async () => {
    render(
      <MemoryRouter initialEntries={['/collections/COL001/things/THG001/request']}>
        <Routes>
          <Route
            path="/collections/:code/things/:thingCode/request"
            element={<RequestThingPage />}
          />
        </Routes>
      </MemoryRouter>
    );

    await waitFor(() => expect(screen.getByTestId('network-point-line')).toHaveTextContent(LINE));
    await settle(apiFetch);
  });
});
