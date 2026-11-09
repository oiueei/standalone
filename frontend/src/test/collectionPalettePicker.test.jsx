import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));
vi.mock('../utils/externalForms', () => ({ externalFormUrl: () => null }));
vi.mock('../deployment', async (orig) => ({ ...(await orig()), requestAccessPaths: {} }));

import { apiFetch } from '../services/api';
import CreateCollectionPage from '../pages/CreateCollectionPage';
import EditCollectionPage from '../pages/EditCollectionPage';
import { dropHdsStyles } from './dropHdsStyles';
import { settle } from './settle';
import en from '../i18n/locales/en.json';

/**
 * The curator picks the palette and the Koros wave of the group's pages in "More
 * options" of the create and edit forms, among the twelve rows `GET /theeemes/`
 * lists. The app's own palette is another table: it is never offered, because the
 * list is the only source of what is offered.
 */
const row = (code, name, color_01) => ({
  code,
  name,
  color_01,
  color_02: 'white',
  color_03: 'gold',
  color_04: 'black',
  color_05: 'black',
  color_06: 'white',
});
const THEEEMES = [row('BUU331', 'Bussi', 'bus'), row('JMPA01', 'Metro', 'metro')];
const ok = (data) => ({ ok: true, status: 200, json: () => Promise.resolve(data) });

const COLLECTION = {
  is_curator: true,
  kind: 'LIBRARY',
  headline: 'Tool shed',
  description: '',
  status: 'ACTIVE',
  mode: 'PROPRIETARY',
  visibility: 'PRIVATE',
  allowed_thing_types: ['LEND_THING', 'RENT_THING'],
  digest_frequency: 'WEEKLY',
  language: 'en',
  theeeme: 'JMPA01',
  koro: 'calm',
  owner: 'ABC123',
};

function setApi(collection = COLLECTION) {
  apiFetch.mockImplementation((url) => {
    if (url === '/api/v1/theeemes/') return Promise.resolve(ok(THEEEMES));
    if (/\/collections\/[^/]+\//.test(url)) return Promise.resolve(ok(collection));
    return Promise.resolve(ok({}));
  });
}

beforeEach(() => {
  dropHdsStyles();
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  vi.clearAllMocks();
});

describe('Create — no palette picker', () => {
  test('the palette and the wave are not asked at creation: the server draws one', async () => {
    setApi();
    render(
      <MemoryRouter initialEntries={['/library/new']}>
        <Routes>
          <Route path="/:kind/new" element={<CreateCollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByRole('button', { name: 'Create library' });
    await settle(apiFetch);

    expect(
      screen.queryByRole('group', { name: en.createCollection.theeemeLabel })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('group', { name: en.createCollection.koroLabel })
    ).not.toBeInTheDocument();
    expect(apiFetch.mock.calls.some(([url]) => url === '/api/v1/theeemes/')).toBe(false);
  });
});

describe('Edit — no palette picker', () => {
  test('the palette and the wave are chosen on the Appearance page, not here', async () => {
    setApi();
    render(
      <MemoryRouter initialEntries={['/collections/COL001/edit']}>
        <Routes>
          <Route path="/collections/:code/edit" element={<EditCollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByDisplayValue('Tool shed');
    await settle(apiFetch);

    expect(
      screen.queryByRole('group', { name: en.createCollection.theeemeLabel })
    ).not.toBeInTheDocument();
    expect(
      screen.queryByRole('group', { name: en.createCollection.koroLabel })
    ).not.toBeInTheDocument();
    expect(apiFetch.mock.calls.some(([url]) => url === '/api/v1/theeemes/')).toBe(false);
  });
});
