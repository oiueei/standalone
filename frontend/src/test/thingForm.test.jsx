import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import AddThingPage from '../pages/AddThingPage';
import EditThingPage from '../pages/EditThingPage';

function mockResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

// `collection` feeds AddThingPage's collection fetch (drives type/field gating);
// `thing` feeds EditThingPage's load fetch and PATCH save.
function setApi({ collection = {}, thing = {} } = {}) {
  apiFetch.mockImplementation((url, opts = {}) => {
    const method = opts.method || 'GET';
    if (url === '/api/v1/things/' && method === 'POST') return Promise.resolve(mockResponse({ code: 'NEW001' }));
    if (/\/collections\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(collection));
    if (/\/things\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(thing));
    return Promise.resolve(mockResponse({}));
  });
}

function renderAdd(apiOpts) {
  setApi(apiOpts);
  return render(
    <MemoryRouter initialEntries={['/collections/COL001/add']}>
      <Routes>
        <Route path="/collections/:code/add" element={<AddThingPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

function renderEdit(apiOpts) {
  setApi(apiOpts);
  return render(
    <MemoryRouter initialEntries={['/things/THG001/edit']}>
      <Routes>
        <Route path="/things/:thingCode/edit" element={<EditThingPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  localStorage.setItem('theeemeColors', JSON.stringify({
    color_01: 'bus', color_02: 'suomenlinna-light', color_03: 'copper',
    color_04: 'black', color_05: 'white', color_06: 'white',
  }));
  localStorage.setItem('koro', 'basic');
  vi.clearAllMocks();
  setApi();
});

// ════════════════════════════════════════════════════════════════════════
// AddThingPage — field visibility per type / collection config
// ════════════════════════════════════════════════════════════════════════
describe('AddThingPage — field visibility', () => {
  test('GIFT (default): fee hidden, detail fields + gallery shown', async () => {
    const { container } = renderAdd({ collection: { headline: 'Plain', mode: 'PROPRIETARY' } });

    await waitFor(() => expect(container.querySelector('#add-thing-headline')).toBeTruthy());
    // GIFT is a DETAIL_TYPE but not a FEE_TYPE.
    expect(container.querySelector('#add-thing-fee')).toBeNull();
    expect(screen.getByText('Availability')).toBeInTheDocument();
    expect(screen.getByText('Condition')).toBeInTheDocument();
    expect(container.querySelector('#add-thing-location')).toBeTruthy();
    expect(screen.getByText('More photos')).toBeInTheDocument();
    expect(screen.getByText('Thumbnail')).toBeInTheDocument();
  });

  test('SELL (single-type allowlist): pre-selects type, shows fee + detail fields', async () => {
    const { container } = renderAdd({ collection: { mode: 'PROPRIETARY', allowed_thing_types: ['SELL_THING'] } });

    // The single-element allowlist pre-selects SELL_THING, so the fee surfaces.
    await waitFor(() => expect(container.querySelector('#add-thing-fee')).toBeTruthy());
    expect(screen.getByText('Availability')).toBeInTheDocument();
    expect(container.querySelector('#add-thing-location')).toBeTruthy();
  });

  test('swap collection: shows the type selector (SWAP + wish), defaults to SWAP', async () => {
    const { container } = renderAdd({ collection: { mode: 'COMMUNITY', is_swap: true } });

    await waitFor(() => expect(container.querySelector('#add-thing-headline')).toBeTruthy());
    // Swap-only collections now also accept wishes, so the type Select is shown.
    expect(screen.getByText('Type')).toBeInTheDocument();
    // Default stays SWAP (neither a FEE_TYPE nor a DETAIL_TYPE), so those stay hidden.
    expect(container.querySelector('#add-thing-fee')).toBeNull();
    expect(screen.queryByText('Availability')).toBeNull();
  });

  test('share collection: shows the type selector (SHARE + wish), defaults to SHARE', async () => {
    const { container } = renderAdd({ collection: { mode: 'COMMUNITY', is_share: true } });

    await waitFor(() => expect(container.querySelector('#add-thing-headline')).toBeTruthy());
    // Share-only collections now also accept wishes, so the type Select is shown.
    expect(screen.getByText('Type')).toBeInTheDocument();
    // Default stays SHARE (a DETAIL_TYPE, not a FEE_TYPE): availability shows, fee hidden.
    expect(container.querySelector('#add-thing-fee')).toBeNull();
    expect(screen.getByText('Availability')).toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════
// AddThingPage — submit payload
// ════════════════════════════════════════════════════════════════════════
describe('AddThingPage — submit', () => {
  test('POSTs to /api/v1/things/ with headline, type and collection_code', async () => {
    const { container } = renderAdd({ collection: { mode: 'PROPRIETARY' } });

    await waitFor(() => expect(container.querySelector('#add-thing-headline')).toBeTruthy());
    fireEvent.change(container.querySelector('#add-thing-headline'), { target: { value: 'My Gift' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => {
      const call = apiFetch.mock.calls.find((c) => c[0] === '/api/v1/things/' && c[1]?.method === 'POST');
      expect(call).toBeTruthy();
      const body = JSON.parse(call[1].body);
      expect(body).toMatchObject({
        headline: 'My Gift',
        type: 'GIFT_THING',
        collection_code: 'COL001',
      });
    });
  });
});

// ════════════════════════════════════════════════════════════════════════
// EditThingPage — pre-population + PATCH
// ════════════════════════════════════════════════════════════════════════
describe('EditThingPage', () => {
  test('pre-populates the headline from the loaded thing', async () => {
    renderEdit({ thing: { code: 'THG001', type: 'GIFT_THING', headline: 'Existing Thing', description: '' } });

    expect(await screen.findByDisplayValue('Existing Thing')).toBeInTheDocument();
  });

  test('PATCHes /api/v1/things/{code}/ with the edited fields', async () => {
    const { container } = renderEdit({ thing: { code: 'THG001', type: 'GIFT_THING', headline: 'Existing Thing', description: '' } });

    await screen.findByDisplayValue('Existing Thing');
    fireEvent.change(container.querySelector('#edit-thing-headline'), { target: { value: 'Renamed Thing' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      const call = apiFetch.mock.calls.find((c) => c[0] === '/api/v1/things/THG001/' && c[1]?.method === 'PATCH');
      expect(call).toBeTruthy();
      const body = JSON.parse(call[1].body);
      expect(body).toMatchObject({ headline: 'Renamed Thing', type: 'GIFT_THING' });
    });
  });
});
