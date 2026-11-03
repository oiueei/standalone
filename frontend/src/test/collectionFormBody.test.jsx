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
 * The whole body Create POSTs and Edit PATCHes, field by field, with every field of
 * the "More options" block changed from the screen (or loaded, for what Edit loads).
 * The expected bodies are written by hand from what was typed and loaded — not copied
 * from what the pages send — so a field that stops reaching the server, or reaches it
 * under another name, fails here. They exist for the day the block both pages share
 * moves into one component: the two requests must not change by a byte.
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

/** Everything the block holds, edited from the screen. `p` is the id prefix. */
async function fillAdvanced(container, p) {
  fireEvent.click(screen.getByRole('button', { name: 'More options' }));
  const tagInput = await screen.findByPlaceholderText(en.createCollection.tagsPlaceholder);
  fireEvent.change(tagInput, { target: { value: 'Kitchen' } });
  fireEvent.click(screen.getByRole('button', { name: 'Add' }));
  fireEvent.click(screen.getByRole('button', { name: 'Monday' }));
  fireEvent.click(screen.getByRole('button', { name: 'Wednesday' }));
  type(container, `#${p}-deposit-policy`, 'Back when it comes home');
  type(container, `#${p}-closed-dates`, '25/12/2099, 01/01/2100');
  type(container, `#${p}-request-info`, 'Ask in the evening');
  type(container, `#${p}-email-note`, 'The key is in the box');
  type(container, `#${p}-home-page`, 'https://group.example/');
  await pickOption(/Digest emails/, en.editCollection.digestMonthly);
  // The palette and the wave of the group's pages.
  fireEvent.click(await screen.findByRole('button', { name: 'Metro' }));
  fireEvent.click(screen.getByRole('button', { name: 'Wave' }));
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

describe('Create — the body of a library with every optional field filled in', () => {
  test('is exactly what was typed', async () => {
    setApi();
    const { container } = render(
      <MemoryRouter initialEntries={['/library/new']}>
        <Routes>
          <Route path="/:kind/new" element={<CreateCollectionPage />} />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() =>
      expect(container.querySelector('#create-collection-headline')).toBeInTheDocument()
    );
    await settle(apiFetch);
    type(container, '#create-collection-headline', 'Tool shed');
    type(container, '#create-collection-description', 'Tools for the street');
    await fillAdvanced(container, 'create-collection');

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(postBody()).toBeTruthy());
    expect(postBody()).toEqual({
      kind: 'LIBRARY',
      headline: 'Tool shed',
      description: 'Tools for the street',
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
      allow_member_proposals: false,
      allowed_thing_types: ['LEND_THING', 'RENT_THING'],
      home_page: 'https://group.example/',
      email_note: 'The key is in the box',
      tags: ['Kitchen'],
      thumbnail: '',
      language: 'en',
      digest_frequency: 'MONTHLY',
      theeeme: 'JMPA01',
      koro: 'wave',
      welcome_doc: '',
      closed_dates: '25/12/2099, 01/01/2100',
      request_info: 'Ask in the evening',
      rental_weekdays: [0, 2],
      rental_durations: [],
      deposit_policy: 'Back when it comes home',
    });
  });

  test('a stall has none of the library’s fields in its body', async () => {
    setApi();
    const { container } = render(
      <MemoryRouter initialEntries={['/stall/new']}>
        <Routes>
          <Route path="/:kind/new" element={<CreateCollectionPage />} />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </MemoryRouter>
    );
    await waitFor(() =>
      expect(container.querySelector('#create-collection-headline')).toBeInTheDocument()
    );
    await settle(apiFetch);
    type(container, '#create-collection-headline', 'Free stall');
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    type(container, '#create-collection-email-note', 'Come by');

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(postBody()).toBeTruthy());
    expect(postBody()).toEqual({
      kind: 'STALL',
      headline: 'Free stall',
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
      allow_member_proposals: false,
      allowed_thing_types: ['GIFT_THING', 'SELL_THING'],
      home_page: '',
      email_note: 'Come by',
      tags: [],
      thumbnail: '',
      language: 'en',
      digest_frequency: 'MONTHLY',
      // No palette picked: none is sent and the server draws one. The koro is the basic wave.
      koro: 'basic',
      welcome_doc: '',
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
  test('saved untouched, it sends back what it loaded', async () => {
    await renderEdit(LIBRARY);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toEqual({
      headline: 'Tool shed',
      description: 'Tools',
      status: 'ACTIVE',
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
      allow_member_proposals: true,
      digest_frequency: 'WEEKLY',
      allowed_thing_types: ['LEND_THING', 'RENT_THING'],
      home_page: 'https://old.example/',
      email_note: 'Old email note',
      tags: ['Old tag'],
      thumbnail: 'oiueei/collections/thumb',
      language: 'en',
      theeeme: 'BUU331',
      koro: 'calm',
      welcome_doc: 'oiueei/documents/doc',
      closed_dates: '25/12/2099',
      request_info: 'Old request note',
      rental_weekdays: [1],
      rental_durations: [7],
      deposit_policy: 'Old policy',
    });
  });

  test('every field of the optional block, edited, reaches the PATCH', async () => {
    const { container } = await renderEdit(LIBRARY);
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    const tagInput = await screen.findByPlaceholderText(en.createCollection.tagsPlaceholder);
    fireEvent.change(tagInput, { target: { value: 'Kitchen' } });
    fireEvent.click(screen.getByRole('button', { name: 'Add' }));
    fireEvent.click(screen.getByRole('button', { name: 'Monday' }));
    type(container, '#edit-collection-deposit-policy', 'New policy');
    type(container, '#edit-collection-closed-dates', '01/01/2100');
    type(container, '#edit-collection-request-info', 'New request note');
    type(container, '#edit-collection-email-note', 'New email note');
    type(container, '#edit-collection-home-page', 'https://new.example/');
    await pickOption(/Digest emails/, en.editCollection.digestNone);
    await pickOption(/Language of the group messages/, 'Español');
    fireEvent.click(await screen.findByRole('button', { name: 'Metro' }));
    fireEvent.click(screen.getByRole('button', { name: 'Wave' }));

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toEqual({
      headline: 'Tool shed',
      description: 'Tools',
      status: 'ACTIVE',
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
      allow_member_proposals: true,
      digest_frequency: 'NONE',
      allowed_thing_types: ['LEND_THING', 'RENT_THING'],
      home_page: 'https://new.example/',
      email_note: 'New email note',
      tags: ['Old tag', 'Kitchen'],
      thumbnail: 'oiueei/collections/thumb',
      language: 'es',
      theeeme: 'JMPA01',
      koro: 'wave',
      welcome_doc: 'oiueei/documents/doc',
      closed_dates: '01/01/2100',
      request_info: 'New request note',
      rental_weekdays: [0, 1],
      rental_durations: [7],
      deposit_policy: 'New policy',
    });
  });

  test('the loaded photo and welcome document are shown, and the email-note test is there', async () => {
    await renderEdit(LIBRARY);
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));

    expect(await screen.findByRole('link', { name: /view/i })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: /send me a test email/i })).toBeInTheDocument();
  });
});

describe('Edit — the body of a shed booked by the day', () => {
  test('keeps the reservation fields and sends no rental ones as rules', async () => {
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
      allow_member_proposals: true,
      digest_frequency: 'WEEKLY',
      allowed_thing_types: ['RESERVE_THING'],
      home_page: 'https://old.example/',
      email_note: 'Old email note',
      tags: ['Old tag'],
      thumbnail: 'oiueei/collections/thumb',
      language: 'en',
      theeeme: 'BUU331',
      koro: 'calm',
      welcome_doc: 'oiueei/documents/doc',
      closed_dates: '25/12/2099',
      request_info: 'Old request note',
      rental_weekdays: [1],
      rental_durations: [],
      deposit_policy: '',
      reservation_horizon_days: 30,
      reservation_max_active_per_member: 4,
      reservation_asks_phone: false,
      reservation_unit: 'DAY',
      reservation_max_days: 3,
    });
  });
});
