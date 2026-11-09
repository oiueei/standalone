import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useNavigate } from 'react-router';
import { describe, test, expect, vi, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
  getCsrfToken: () => 'tok',
}));

import { apiFetch } from '../services/api';
import en from '../i18n/locales/en.json';
import CollectionAppearancePage from '../pages/CollectionAppearancePage';
import CollectionNotificationsPage from '../pages/CollectionNotificationsPage';
import CollectionAvailabilityPage from '../pages/CollectionAvailabilityPage';
import EditCollectionPage from '../pages/EditCollectionPage';
import { settle } from './settle';

/**
 * The four collection forms read the collection through one hook. Whoever cannot edit it
 * goes to the collection with no message, a refused read does the same (403) or says it
 * is not there (404), and any other failure says so in words: never an empty form.
 */
const json = (status, data = {}) => ({ ok: status < 400, status, json: async () => data });

const COLLECTION = {
  code: 'COL001',
  headline: 'The lending library',
  description: '',
  kind: 'LIBRARY',
  mode: 'PROPRIETARY',
  owner: 'OWN001',
  is_curator: true,
  language: '',
  status: 'ACTIVE',
  visibility: 'PRIVATE',
  allowed_thing_types: ['LEND_THING'],
  digest_frequency: 'WEEKLY',
};

const PAGES = [
  { name: 'Appearance', Page: CollectionAppearancePage, segment: 'appearance' },
  { name: 'Notifications', Page: CollectionNotificationsPage, segment: 'notifications' },
  { name: 'Availability', Page: CollectionAvailabilityPage, segment: 'availability' },
  { name: 'Edit', Page: EditCollectionPage, segment: null },
];

function Collection() {
  const navigate = useNavigate();
  return (
    <div>
      THE COLLECTION
      <button type="button" onClick={() => navigate(-1)}>
        back
      </button>
    </div>
  );
}

function answer(read) {
  apiFetch.mockImplementation((url, opts = {}) => {
    if (opts.method === 'PATCH') return Promise.resolve(json(200));
    if (String(url).includes('/theeemes/')) return Promise.resolve(json(200, []));
    return typeof read === 'function' ? read() : Promise.resolve(read);
  });
}

function open(page) {
  const { segment } = page;
  const PageUnderTest = page.Page;
  const path = segment ? `/library/COL001/settings/${segment}` : '/library/COL001/edit';
  return render(
    <MemoryRouter initialEntries={['/start', path]} initialIndex={1}>
      <Routes>
        <Route path="/start" element={<div>THE START</div>} />
        <Route path="/library/:code" element={<Collection />} />
        <Route path="/library/:code/edit" element={<PageUnderTest />} />
        <Route path="/library/:code/settings/:segment" element={<PageUnderTest />} />
      </Routes>
    </MemoryRouter>
  );
}

const patched = () => apiFetch.mock.calls.some(([, o]) => o?.method === 'PATCH');

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'USR001');
  vi.clearAllMocks();
});

describe.each(PAGES)('$name — who cannot edit', (page) => {
  test('a member (the read is fine, is_curator false) lands on the collection, with no form', async () => {
    answer(json(200, { ...COLLECTION, is_curator: false }));
    open(page);

    expect(await screen.findByText('THE COLLECTION')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
    expect(patched()).toBe(false);
  });

  test('the redirect replaces the entry: back does not return to the setting', async () => {
    answer(json(200, { ...COLLECTION, is_curator: false }));
    open(page);
    await screen.findByText('THE COLLECTION');

    fireEvent.click(screen.getByRole('button', { name: 'back' }));

    expect(await screen.findByText('THE START')).toBeInTheDocument();
  });

  test('in a network a co-curator is sent to the collection too', async () => {
    answer(json(200, { ...COLLECTION, mode: 'NETWORK' }));
    open(page);

    expect(await screen.findByText('THE COLLECTION')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
  });

  test('the founder of a network gets the form', async () => {
    answer(json(200, { ...COLLECTION, mode: 'NETWORK', owner: 'USR001' }));
    open(page);

    expect(await screen.findByRole('button', { name: 'Save' })).toBeInTheDocument();
    expect(screen.queryByText('THE COLLECTION')).toBeNull();
  });

  test('a 403 on the read goes to the collection', async () => {
    answer(json(403));
    open(page);

    expect(await screen.findByText('THE COLLECTION')).toBeInTheDocument();
  });
});

describe.each(PAGES)('$name — a read that fails', (page) => {
  test('a 404 is the not-found page', async () => {
    answer(json(404));
    open(page);

    expect(await screen.findByText(en.notFound.title)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
  });

  test('a 500 says the page could not be loaded, with no form', async () => {
    answer(json(500));
    open(page);

    expect(await screen.findByText(en.editCollection.errorLoading)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
    expect(screen.queryByText('THE COLLECTION')).toBeNull();
  });

  test('no connection says so, with no form', async () => {
    answer(() => Promise.reject(new TypeError('offline')));
    open(page);

    expect(await screen.findByText(en.common.connectionError)).toBeInTheDocument();
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Save' })).toBeNull());
    await settle(apiFetch);
  });
});
