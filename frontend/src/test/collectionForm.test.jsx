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
import { reconcileAllowedTypes } from '../constants/things';
import CreateCollectionPage from '../pages/CreateCollectionPage';
import EditCollectionPage from '../pages/EditCollectionPage';

function mockResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

// `collection` feeds EditCollectionPage's load fetch; Create POSTs, Edit PATCHes.
function setApi({ collection = {} } = {}) {
  apiFetch.mockImplementation((url, opts = {}) => {
    const method = opts.method || 'GET';
    if (url === '/api/v1/collections/' && method === 'POST') return Promise.resolve(mockResponse({ code: 'NEW001' }));
    if (/\/collections\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(collection));
    return Promise.resolve(mockResponse({}));
  });
}

function renderCreate() {
  setApi();
  return render(
    <MemoryRouter initialEntries={['/collections/new']}>
      <Routes>
        <Route path="/collections/new" element={<CreateCollectionPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

function renderEdit(collection) {
  setApi({ collection });
  return render(
    <MemoryRouter initialEntries={['/collections/COL001/edit']}>
      <Routes>
        <Route path="/collections/:code/edit" element={<EditCollectionPage />} />
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
// CreateCollectionPage — mode-gated toggles + submit
// ════════════════════════════════════════════════════════════════════════
describe('CreateCollectionPage', () => {
  test('PROPRIETARY (default): swap/share hidden, types not locked', () => {
    const { container } = renderCreate();

    expect(screen.queryByRole('button', { name: 'Enable item swapping' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Exclusively SHARE things' })).toBeNull();
    expect(screen.queryByRole('button', { name: /Album mode/ })).toBeNull();
    expect(container.querySelector('.multiselect-locked')).toBeNull();
  });

  // P1-5: the mode picker is a radio group with an inline description per option,
  // not a Select hidden behind an info icon.
  test('mode radios render with inline descriptions', () => {
    renderCreate();

    expect(screen.getByRole('radio', { name: 'Proprietary' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: 'Community' })).toBeInTheDocument();
    expect(screen.getByText('Only you can add things to this list.')).toBeInTheDocument();
    expect(screen.getByText('Everyone you invite can add their own things too.')).toBeInTheDocument();
  });

  test('selecting the Community mode radio reveals the COMMUNITY toggles', () => {
    renderCreate();

    expect(screen.queryByRole('button', { name: 'Enable item swapping' })).toBeNull();
    fireEvent.click(screen.getByRole('radio', { name: 'Community' }));
    expect(screen.getByRole('button', { name: 'Enable item swapping' })).toBeInTheDocument();
  });

  // Enabling swap in COMMUNITY locks the allowed-types select to a single
  // auto-filled value, which lets submit pass validation without driving the
  // (jsdom-fiddly) multi-select. We use this to exercise the POST payload.
  test('swap toggle locks the type select and submit POSTs the payload', async () => {
    const { container } = renderCreate();

    fireEvent.click(screen.getByRole('radio', { name: 'Community' }));
    fireEvent.click(screen.getByRole('button', { name: 'Enable item swapping' }));
    expect(container.querySelector('.multiselect-locked')).toBeTruthy();

    fireEvent.change(container.querySelector('#create-collection-headline'), { target: { value: 'My Swap' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => {
      const call = apiFetch.mock.calls.find((c) => c[0] === '/api/v1/collections/' && c[1]?.method === 'POST');
      expect(call).toBeTruthy();
      const body = JSON.parse(call[1].body);
      expect(body).toMatchObject({ headline: 'My Swap', mode: 'COMMUNITY', is_swap: true });
    });
  });
});

// ════════════════════════════════════════════════════════════════════════
// EditCollectionPage — COMMUNITY toggles, mutual exclusivity, lock, pause
// ════════════════════════════════════════════════════════════════════════
describe('EditCollectionPage — COMMUNITY toggles', () => {
  test('COMMUNITY reveals swap + share; require-min hidden when swap off', async () => {
    renderEdit({ headline: 'Comm', mode: 'COMMUNITY', is_swap: false, is_share: false });

    expect(await screen.findByRole('button', { name: 'Enable item swapping' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Exclusively SHARE things' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /Album mode/ })).toBeNull();
    expect(screen.queryByRole('button', { name: /Require 3 items/ })).toBeNull();
  });

  test('swap and share are mutually exclusive', async () => {
    renderEdit({ headline: 'Comm', mode: 'COMMUNITY', is_swap: true, is_share: false });

    const swap = await screen.findByRole('button', { name: 'Enable item swapping' });
    const share = screen.getByRole('button', { name: 'Exclusively SHARE things' });
    expect(swap).toHaveAttribute('aria-pressed', 'true');
    expect(share).toHaveAttribute('aria-pressed', 'false');
    // Require-3-items rides on swap, so it is visible here.
    expect(screen.getByRole('button', { name: /Require 3 items/ })).toBeInTheDocument();

    // Turning share ON clears swap (and the swap-only minimum-items toggle).
    fireEvent.click(share);
    await waitFor(() => expect(share).toHaveAttribute('aria-pressed', 'true'));
    expect(swap).toHaveAttribute('aria-pressed', 'false');
    expect(screen.queryByRole('button', { name: /Require 3 items/ })).toBeNull();
  });

  test('toggling swap on reveals require-min and locks the allowed-types select', async () => {
    const { container } = renderEdit({ headline: 'Comm', mode: 'COMMUNITY', is_swap: false, is_share: false });

    const swap = await screen.findByRole('button', { name: 'Enable item swapping' });
    expect(container.querySelector('.multiselect-locked')).toBeNull();
    expect(screen.queryByRole('button', { name: /Require 3 items/ })).toBeNull();

    fireEvent.click(swap);

    // NOTE: the allowed_thing_types reset to ['SWAP_THING'] is internal state; we
    // lock its visible consequence — the multi-select becomes locked/disabled.
    await waitFor(() => expect(container.querySelector('.multiselect-locked')).toBeTruthy());
    expect(screen.getByRole('button', { name: /Require 3 items/ })).toBeInTheDocument();
  });
});

describe('EditCollectionPage — load + pause + submit', () => {
  test('pre-populates the headline from the loaded collection', async () => {
    renderEdit({ headline: 'Loaded Name', mode: 'PROPRIETARY', allowed_thing_types: ['GIFT_THING'] });

    expect(await screen.findByDisplayValue('Loaded Name')).toBeInTheDocument();
  });

  test('pause section shows the message field + "Pause collection" when not paused', async () => {
    const { container } = renderEdit({ headline: 'Comm', mode: 'PROPRIETARY', allowed_thing_types: ['GIFT_THING'], is_paused: false });

    await screen.findByDisplayValue('Comm');
    expect(container.querySelector('#pause-message')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Pause collection' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Resume collection' })).toBeNull();
  });

  test('pause section shows the message + "Resume collection" when paused', async () => {
    const { container } = renderEdit({
      headline: 'Comm', mode: 'PROPRIETARY', allowed_thing_types: ['GIFT_THING'],
      is_paused: true, pause_message: 'Back in a week',
    });

    await screen.findByDisplayValue('Comm');
    expect(container.querySelector('#pause-message')).toBeNull();
    expect(screen.getByText('Back in a week')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resume collection' })).toBeInTheDocument();
  });

  test('PATCHes /api/v1/collections/{code}/ with the edited fields', async () => {
    const { container } = renderEdit({ headline: 'Old Name', mode: 'PROPRIETARY', allowed_thing_types: ['GIFT_THING'] });

    await screen.findByDisplayValue('Old Name');
    fireEvent.change(container.querySelector('#edit-collection-headline'), { target: { value: 'New Name' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      const call = apiFetch.mock.calls.find(
        (c) => c[0] === '/api/v1/collections/COL001/' && c[1]?.method === 'PATCH' && JSON.parse(c[1].body).headline !== undefined
      );
      expect(call).toBeTruthy();
      const body = JSON.parse(call[1].body);
      expect(body).toMatchObject({ headline: 'New Name', mode: 'PROPRIETARY' });
    });
  });
});

// ════════════════════════════════════════════════════════════════════════
// reconcileAllowedTypes — P1-5: preserve the valid selection across mode/flag
// changes instead of wiping it.
// ════════════════════════════════════════════════════════════════════════
describe('reconcileAllowedTypes', () => {
  test('PROPRIETARY → COMMUNITY keeps the still-valid types', () => {
    expect(reconcileAllowedTypes(
      ['GIFT_THING', 'SELL_THING'],
      { mode: 'COMMUNITY', isSwap: false, isShare: false },
    )).toEqual(['GIFT_THING', 'SELL_THING']);
  });

  test('COMMUNITY → PROPRIETARY drops the COMMUNITY-only types', () => {
    expect(reconcileAllowedTypes(
      ['GIFT_THING', 'SHARE_THING', 'WISH_THING'],
      { mode: 'PROPRIETARY', isSwap: false, isShare: false },
    )).toEqual(['GIFT_THING']);
  });

  test('a locked combination (swap) snaps to its forced single type', () => {
    expect(reconcileAllowedTypes(
      ['GIFT_THING', 'SELL_THING'],
      { mode: 'COMMUNITY', isSwap: true, isShare: false },
    )).toEqual(['SWAP_THING']);
  });
});
