import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';

window.scrollTo = vi.fn();

const navigate = vi.fn();
vi.mock('react-router', async () => ({
  ...(await vi.importActual('react-router')),
  useNavigate: () => navigate,
}));

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
  getCsrfToken: () => 'tok',
}));

vi.mock('../hooks/useCollectionLanguage', () => ({ default: vi.fn() }));

import { apiFetch } from '../services/api';
import CollectionAppearancePage from './CollectionAppearancePage';
import { dropHdsStyles } from '../test/dropHdsStyles';
import { settle } from '../test/settle';

const THEEEMES = [
  { code: 'T1', name: 'Pine', color_01: 'coat-of-arms', color_02: 'white', color_03: 'black-5' },
  { code: 'T2', name: 'Sky', color_01: 'bus', color_02: 'white', color_03: 'black-5' },
];

const COLLECTION = {
  code: 'COL001',
  headline: 'Kitchen Collection',
  description: 'Things from the kitchen',
  kind: 'STALL',
  mode: 'COMMUNITY',
  // What other pages own: the PATCH of this page must leave all of it alone.
  allowed_thing_types: ['GIFT_THING'],
  welcome_doc: 'welcome.pdf',
  language: 'ca',
  theeeme: 'T2',
  koro: 'wave',
  tags: ['Kitchen'],
  home_page: 'https://example.test',
  thumbnail: 'logo.png',
  thumbnail_url: 'https://cdn.test/logo.png',
};

function mockApi({ collection = COLLECTION, save = { ok: true } } = {}) {
  apiFetch.mockImplementation((url, opts) => {
    if (opts?.method === 'PATCH') {
      return Promise.resolve({
        ok: save.ok,
        status: save.status ?? (save.ok ? 200 : 400),
        json: async () => save.body ?? {},
      });
    }
    if (String(url).includes('/theeemes/')) {
      return Promise.resolve({ ok: true, status: 200, json: async () => THEEEMES });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => collection });
  });
}

const patchBody = () => {
  const call = apiFetch.mock.calls.find(([, opts]) => opts?.method === 'PATCH');
  return call ? JSON.parse(call[1].body) : null;
};

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/stall/COL001/settings/appearance']}>
      <Routes>
        <Route path="/stall/:code/settings/appearance" element={<CollectionAppearancePage />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  dropHdsStyles();
  localStorage.clear();
  localStorage.setItem('userCode', 'USR001');
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

describe('CollectionAppearancePage', () => {
  test('shows what the collection has saved', async () => {
    mockApi();
    renderPage();

    expect(await screen.findByRole('heading', { level: 1, name: 'Appearance' })).toBeVisible();
    expect(screen.getByDisplayValue('https://example.test')).toBeInTheDocument();
    expect(screen.getByText('Kitchen')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByRole('button', { name: 'Sky' })).toHaveAttribute('aria-pressed', 'true')
    );
    expect(screen.getByRole('button', { name: 'Pine' })).toHaveAttribute('aria-pressed', 'false');
    // The saved logo is shown as the preview, with its way to remove it.
    expect(screen.getByRole('img', { name: 'Image preview' })).toHaveAttribute(
      'src',
      'https://cdn.test/logo.png'
    );
  });

  test('without a logo it asks for one, naming the formats and the size the upload takes', async () => {
    mockApi({ collection: { ...COLLECTION, thumbnail: '', thumbnail_url: '' } });
    renderPage();

    expect(await screen.findByText('Logo or header image')).toBeInTheDocument();
    expect(
      screen.getByText(
        'Bitmap image files only (JPG, PNG, WebP, GIF, HEIC/HEIF, AVIF, BMP and TIFF), max 10 MB.'
      )
    ).toBeInTheDocument();
  });

  test('lists the palettes the API lists, and nothing else', async () => {
    mockApi();
    renderPage();

    const group = await screen.findByRole('group', { name: 'Theeeme' });
    expect(
      within(group)
        .getAllByRole('button')
        .map((b) => b.getAttribute('aria-label'))
    ).toEqual(['Pine', 'Sky']);
    expect(document.body.textContent).not.toMatch(/braaanding|OIUEEI palette/i);
    // It is the saved palette, so there is nothing to say about a random draw.
    expect(screen.queryByText(/chosen at random/)).toBeNull();
  });

  test('marks the wave the collection has', async () => {
    mockApi();
    renderPage();

    const group = await screen.findByRole('group', { name: 'Koro' });
    expect(within(group).getByRole('button', { name: 'Wave' })).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    expect(within(group).getByRole('button', { name: 'Basic' })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
  });

  test('explains the tags in languages in a notice above the field', async () => {
    mockApi();
    renderPage();

    expect(await screen.findByText(/Write the tags in one language only/)).toBeInTheDocument();
    expect(screen.getByText('{"es": "Juguetes", "ca": "Joguines"}')).toBeInTheDocument();
  });

  test('saves exactly its own fields and nothing the collection keeps elsewhere', async () => {
    mockApi();
    renderPage();
    await screen.findByDisplayValue('https://example.test');
    await settle(apiFetch);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/stall/COL001'));
    const body = patchBody();
    // The page's boundary: every key it may send, and no other. A copy of the edit
    // form's body would add `allowed_thing_types`, `welcome_doc` and `language`.
    expect(Object.keys(body).sort()).toEqual(['home_page', 'koro', 'tags', 'theeeme', 'thumbnail']);
    expect(body).toEqual({
      thumbnail: 'logo.png',
      koro: 'wave',
      tags: ['Kitchen'],
      home_page: 'https://example.test',
      theeeme: 'T2',
    });
  });

  test('sends no palette when the collection has none and none is picked', async () => {
    mockApi({ collection: { ...COLLECTION, theeeme: '' } });
    renderPage();
    await screen.findByDisplayValue('https://example.test');
    await settle(apiFetch);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(Object.keys(patchBody()).sort()).toEqual(['home_page', 'koro', 'tags', 'thumbnail']);
  });

  test('a palette and a wave picked on the page are what is saved', async () => {
    mockApi();
    renderPage();
    await screen.findByDisplayValue('https://example.test');
    fireEvent.click(await screen.findByRole('button', { name: 'Pine' }));
    fireEvent.click(screen.getByRole('button', { name: /Calm/ }));

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(patchBody()).toMatchObject({ theeeme: 'T1', koro: 'calm' });
  });

  test('an edited home page reaches the PATCH, trimmed', async () => {
    mockApi();
    renderPage();
    const web = await screen.findByDisplayValue('https://example.test');
    await settle(apiFetch);

    fireEvent.change(web, { target: { value: '  https://ateneu.example/  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(patchBody().home_page).toBe('https://ateneu.example/');
  });

  test('picking another palette moves the mark', async () => {
    mockApi();
    renderPage();
    const group = await screen.findByRole('group', { name: 'Theeeme' });
    await waitFor(() =>
      expect(within(group).getByRole('button', { name: 'Sky' })).toHaveAttribute(
        'aria-pressed',
        'true'
      )
    );

    fireEvent.click(within(group).getByRole('button', { name: 'Pine' }));

    await waitFor(() =>
      expect(within(group).getByRole('button', { name: 'Pine' })).toHaveAttribute(
        'aria-pressed',
        'true'
      )
    );
    expect(within(group).getByRole('button', { name: 'Sky' })).toHaveAttribute(
      'aria-pressed',
      'false'
    );
  });

  test('a list of palettes that cannot be read leaves the page working, with no picker', async () => {
    apiFetch.mockImplementation((url) =>
      String(url).includes('/theeemes/')
        ? Promise.reject(new Error('offline'))
        : Promise.resolve({ ok: true, status: 200, json: async () => COLLECTION })
    );
    renderPage();
    await screen.findByDisplayValue('https://example.test');
    await settle(apiFetch);

    expect(screen.queryByRole('group', { name: 'Theeeme' })).not.toBeInTheDocument();
    // The wave still is.
    expect(screen.getByRole('group', { name: 'Koro' })).toBeInTheDocument();
  });

  test('cannot be saved before the collection has loaded', async () => {
    mockApi();
    // The collection read fails: the form shows, but a save would send blanks.
    apiFetch.mockImplementation((url) =>
      String(url).includes('/theeemes/')
        ? Promise.resolve({ ok: true, status: 200, json: async () => THEEEMES })
        : Promise.resolve({ ok: false, status: 500, json: async () => ({}) })
    );
    renderPage();

    const save = await screen.findByRole('button', { name: 'Save' });
    expect(save).toBeDisabled();
    fireEvent.click(save);
    expect(patchBody()).toBeNull();
  });

  test('a refusal of the server is shown as its own message', async () => {
    mockApi({
      save: { ok: false, status: 400, body: { home_page: ['Enter a valid URL.'] } },
    });
    renderPage();
    await screen.findByDisplayValue('https://example.test');
    await settle(apiFetch);
    navigate.mockClear();

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText(/Enter a valid URL/)).toBeInTheDocument();
    expect(navigate).not.toHaveBeenCalled();
  });
});
