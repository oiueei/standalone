import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  ),
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
 * The whole body Create POSTs (the short form) and Edit PATCHes, field by field, with every
 * field the page owns changed from the screen (or loaded, for what Edit loads). The expected bodies are written by hand from what was typed and loaded — not
 * copied from what the pages send — so a field that stops reaching the server, or reaches
 * it under another name, fails here.
 */

const ok = (data) => ({ ok: true, status: 200, json: () => Promise.resolve(data) });

// The twelve palettes the selector lists (two of them are enough here).
const THEEEMES = [
  {
    code: 'BUU331',
    name: 'Bussi',
    color_01: 'bus',
    color_02: 'suomenlinna-medium-light',
    color_03: 'copper',
    color_04: 'black',
    color_05: 'black',
    color_06: 'white',
  },
  {
    code: 'JMPA01',
    name: 'Metro',
    color_01: 'metro',
    color_02: 'suomenlinna-medium-light',
    color_03: 'gold',
    color_04: 'black',
    color_05: 'black',
    color_06: 'black',
  },
];

function setApi(collection = {}) {
  apiFetch.mockImplementation((url, opts = {}) => {
    const method = opts.method || 'GET';
    if (url === '/api/v1/theeemes/') return Promise.resolve(ok(THEEEMES));
    if (url === '/api/v1/collections/' && method === 'POST')
      return Promise.resolve(ok({ code: 'NEW001', kind: 'LIBRARY' }));
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

const type = (container, selector, value) =>
  fireEvent.change(container.querySelector(selector), { target: { value } });

async function pickOption(comboName, optionName) {
  fireEvent.click(screen.getByRole('combobox', { name: comboName }));
  fireEvent.click(await screen.findByRole('option', { name: optionName }));
}

const patchBody = () => {
  const call = apiFetch.mock.calls.find(([, o]) => o?.method === 'PATCH');
  return call && JSON.parse(call[1].body);
};
const postBody = () => {
  const call = apiFetch.mock.calls.find(
    ([u, o]) => u === '/api/v1/collections/' && o?.method === 'POST'
  );
  return call && JSON.parse(call[1].body);
};

describe('Create — the body of the short form', () => {
  async function renderCreate(prefix) {
    setApi();
    const view = render(
      <MemoryRouter initialEntries={[`/${prefix}/new`]}>
        <Routes>
          <Route path="/:kind/new" element={<CreateCollectionPage />} />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() =>
      expect(view.container.querySelector('#create-collection-headline')).toBeInTheDocument()
    );
    await settle(apiFetch);
    return view;
  }

  test('a library is exactly what was typed and chosen, and nothing of the settings pages', async () => {
    const { container } = await renderCreate('library');
    type(container, '#create-collection-headline', 'Tool shed');
    type(container, '#create-collection-description', 'Tools for the street');
    fireEvent.click(screen.getByRole('radio', { name: /^Community:/ }));
    fireEvent.click(container.querySelector('#create-collection-members-price'));
    fireEvent.click(container.querySelector('#create-collection-visibility'));

    fireEvent.click(screen.getByRole('button', { name: 'Create library' }));

    await waitFor(() => expect(postBody()).toBeTruthy());
    expect(postBody()).toEqual({
      kind: 'LIBRARY',
      headline: 'Tool shed',
      description: 'Tools for the street',
      mode: 'COMMUNITY',
      visibility: 'PUBLIC',
      allowed_thing_types: ['LEND_THING'],
      language: 'en',
    });
  });

  test('a stall left as it opens sends the private proprietary default', async () => {
    const { container } = await renderCreate('stall');
    type(container, '#create-collection-headline', 'Free stall');

    fireEvent.click(screen.getByRole('button', { name: 'Create stall' }));

    await waitFor(() => expect(postBody()).toBeTruthy());
    expect(postBody()).toEqual({
      kind: 'STALL',
      headline: 'Free stall',
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
      allowed_thing_types: ['GIFT_THING', 'SELL_THING'],
      language: 'en',
    });
  });
});

const LIBRARY = {
  kind: 'LIBRARY',
  headline: 'Tool shed',
  description: 'Tools',
  status: 'ACTIVE',
  mode: 'PROPRIETARY',
  visibility: 'PRIVATE',
  allow_member_proposals: true,
  allowed_thing_types: ['LEND_THING', 'RENT_THING'],
  digest_frequency: 'WEEKLY',
  rental_durations: [7],
  rental_weekdays: [1],
  deposit_policy: 'Old policy',
  closed_dates: ['2099-12-25'],
  home_page: 'https://old.example/',
  request_info: 'Old request note',
  email_note: 'Old email note',
  tags: ['Old tag'],
  thumbnail: 'oiueei/collections/thumb',
  thumbnail_url: 'http://x/thumb.png',
  welcome_doc: 'oiueei/documents/doc',
  welcome_doc_url: 'http://x/doc.pdf',
  // English, the language the test reads in: a collection in another language would
  // switch the page's own words under the queries.
  language: 'en',
  theeeme: 'BUU331',
  koro: 'calm',
  owner: 'ABC123',
};

async function renderEdit(collection) {
  setApi(collection);
  const view = render(
    <MemoryRouter initialEntries={['/collections/COL001/edit']}>
      <Routes>
        <Route path="/collections/:code/edit" element={<EditCollectionPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
  await settle(apiFetch);
  await screen.findByDisplayValue(collection.headline);
  return view;
}

describe('Edit — the body of a library', () => {
  test('saved untouched, it sends back the six fields of the page as loaded', async () => {
    await renderEdit(LIBRARY);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toEqual({
      headline: 'Tool shed',
      description: 'Tools',
      status: 'ACTIVE',
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
      allowed_thing_types: ['LEND_THING', 'RENT_THING'],
    });
  });

  test('what the page owns, edited, reaches the PATCH', async () => {
    const { container } = await renderEdit(LIBRARY);
    type(container, '#edit-collection-headline', '  Tool library  ');
    type(container, '#edit-collection-description', '  Tools for the street  ');
    await pickOption(/^Status/, en.editCollection.statusInactive);
    fireEvent.click(screen.getByRole('radio', { name: /^Community:/ }));
    fireEvent.click(container.querySelector('#edit-collection-members-price'));
    fireEvent.click(container.querySelector('#edit-collection-visibility'));

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toEqual({
      headline: 'Tool library',
      description: 'Tools for the street',
      status: 'INACTIVE',
      mode: 'COMMUNITY',
      visibility: 'PUBLIC',
      allowed_thing_types: ['LEND_THING'],
    });
  });

  test('none of the fields that have a settings page of their own is on the page', async () => {
    const { container } = await renderEdit(LIBRARY);

    expect(screen.queryByRole('button', { name: 'More options' })).toBeNull();
    for (const field of [
      'thumbnail',
      'welcome-doc',
      'digest',
      'language',
      'home-page',
      'email-note',
      'request-info',
      'closed-dates',
      'deposit-policy',
      'allow-proposals',
    ]) {
      expect(container.querySelector(`[id="edit-collection-${field}"]`), field).toBeNull();
    }
    expect(screen.queryByRole('button', { name: /send me a test email/i })).toBeNull();
  });
});

describe('Edit — the body of a shed booked by the day', () => {
  test('keeps its one verb and sends no reservation rule', async () => {
    await renderEdit({
      ...LIBRARY,
      kind: 'SHED',
      allowed_thing_types: ['RESERVE_THING'],
      reservation_unit: 'DAY',
      reservation_max_days: 3,
      reservation_horizon_days: 30,
      reservation_max_active_per_member: 4,
      rental_durations: [],
      deposit_policy: '',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toEqual({
      headline: 'Tool shed',
      description: 'Tools',
      status: 'ACTIVE',
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
      allowed_thing_types: ['RESERVE_THING'],
    });
  });
});
