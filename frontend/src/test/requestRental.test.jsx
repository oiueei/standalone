import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import RequestThingPage from '../pages/RequestThingPage';

function mockResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

// A RENT_THING whose collection defines rental rules (#7): fixed lengths of one
// and two weeks, pickup/return only on Wednesdays (Python weekday 2).
const RENTAL_THING = {
  code: 'RENT01', type: 'RENT_THING', headline: 'Cordless drill', fee: null,
  collection_code: 'COL001', rental_durations: [7, 14], rental_weekdays: [2],
  available_today: true, next_available: null,
};

function setApi({ thing = RENTAL_THING, calendar = [] } = {}) {
  apiFetch.mockImplementation((url) => {
    if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse(calendar));
    if (/\/things\/[^/]+\/$/.test(url)) return Promise.resolve(mockResponse(thing));
    if (url === '/api/v1/things/') return Promise.resolve(mockResponse({ results: [] }));
    return Promise.resolve(mockResponse({}));
  });
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/collections/COL001/things/RENT01/request', state: {} }]}>
      <Routes>
        <Route path="/collections/:code/things/:thingCode/request" element={<RequestThingPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

// Open the duration Select and click the option with the given label.
async function chooseDuration(label) {
  fireEvent.click(screen.getByRole('combobox', { name: /Rental length/ }));
  fireEvent.click(await screen.findByRole('option', { name: label }));
}

// Open the pickup calendar (enabled only once a duration is chosen).
async function openCalendar() {
  fireEvent.click(screen.getByRole('button', { name: 'Choose date' }));
  await waitFor(() => expect(document.querySelector('[data-date]')).toBeTruthy());
}

// Type a pickup date into the DateInput (DD/MM/YYYY — the display format). HDS
// commits the field's value to its onChange prop on blur/Enter (not on every
// keystroke), so change + blur.
function typePickup(container, display) {
  const input = container.querySelector('#request-pickup-date');
  fireEvent.change(input, { target: { value: display } });
  fireEvent.blur(input);
}

// HDS renders selectable days as <button data-date>, disabled days as
// <span aria-disabled="true" data-date>.
const dayCell = (iso) => document.querySelector(`[data-date="${iso}"]`);
const dayEnabled = (iso) => dayCell(iso)?.tagName === 'BUTTON';
const dayDisabled = (iso) => dayCell(iso)?.getAttribute('aria-disabled') === 'true';

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  localStorage.setItem('theeemeColors', JSON.stringify({
    color_01: 'bus', color_02: 'suomenlinna-light', color_03: 'copper',
    color_04: 'black', color_05: 'white', color_06: 'white',
  }));
  localStorage.setItem('koro', 'basic');
  vi.clearAllMocks();
  // Freeze "today" on Monday 2026-06-01 so the picker opens on June 2026 and the
  // Wednesdays (03/10/17/24) are all visible without month navigation. Fake only
  // Date so the HDS popovers' timers still run.
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 5, 1, 12, 0, 0));
  setApi();
});

afterEach(() => {
  vi.useRealTimers();
});

describe('RequestThingPage — rental duration Select', () => {
  test('lists the collection\'s fixed lengths as options', async () => {
    renderPage();
    await screen.findByRole('combobox', { name: /Rental length/ });

    fireEvent.click(screen.getByRole('combobox', { name: /Rental length/ }));
    const options = await screen.findAllByRole('option');
    expect(options.map((o) => o.textContent)).toEqual(['1 week', '2 weeks']);
  });

  test('the pickup date picker is disabled until a length is chosen', async () => {
    const { container } = renderPage();
    await screen.findByRole('combobox', { name: /Rental length/ });

    expect(container.querySelector('#request-pickup-date')).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Choose date' })).toBeDisabled();

    await chooseDuration('1 week');

    await waitFor(() => expect(container.querySelector('#request-pickup-date')).not.toBeDisabled());
    expect(screen.getByRole('button', { name: 'Choose date' })).not.toBeDisabled();
  });
});

describe('RequestThingPage — derived return date', () => {
  test('a one-week pickup returns the NEXT Wednesday (same weekday)', async () => {
    const { container } = renderPage();
    await screen.findByRole('combobox', { name: /Rental length/ });

    await chooseDuration('1 week');
    typePickup(container, '03/06/2026'); // Wednesday

    expect(await screen.findByText('Return by 10/06/2026')).toBeInTheDocument();
  });

  test('a two-week pickup returns two Wednesdays later', async () => {
    const { container } = renderPage();
    await screen.findByRole('combobox', { name: /Rental length/ });

    await chooseDuration('2 weeks');
    typePickup(container, '03/06/2026'); // Wednesday

    expect(await screen.findByText('Return by 17/06/2026')).toBeInTheDocument();
  });

  test('a single fixed length is preselected — no choice needed (#4)', async () => {
    setApi({ thing: { ...RENTAL_THING, rental_durations: [7] } });
    const { container } = renderPage();
    await screen.findByRole('combobox', { name: /Rental length/ });

    // The pickup picker unlocks without touching the Select…
    await waitFor(() => expect(container.querySelector('#request-pickup-date')).not.toBeDisabled());

    // …and the derived return date appears straight after picking a pickup day.
    typePickup(container, '03/06/2026'); // Wednesday
    expect(await screen.findByText('Return by 10/06/2026')).toBeInTheDocument();
  });
});

describe('RequestThingPage — pickup calendar disabling', () => {
  test('only the allowed weekday (Wednesday) is selectable', async () => {
    renderPage();
    await screen.findByRole('combobox', { name: /Rental length/ });

    await chooseDuration('1 week');
    await openCalendar();

    expect(dayEnabled('2026-06-03')).toBe(true); // Wednesday
    expect(dayDisabled('2026-06-04')).toBe(true); // Thursday — weekday rule
    expect(dayDisabled('2026-06-05')).toBe(true); // Friday
    expect(dayEnabled('2026-06-10')).toBe(true); // Wednesday
  });

  test('a conflicting week is blocked, but back-to-back Wednesdays stay open', async () => {
    // Existing booking occupies Wed 10 → Wed 17. Under strict overlap (O1):
    //  - picking up 06-03 returns on 06-10 = the booking's pickup day → allowed
    //  - picking up 06-10 overlaps the interior → blocked
    //  - picking up 06-17 = the booking's return day → allowed (back-to-back)
    setApi({ calendar: [{ start_date: '2026-06-10', end_date: '2026-06-17', status: 'ACCEPTED' }] });
    renderPage();
    await screen.findByRole('combobox', { name: /Rental length/ });

    await chooseDuration('1 week');
    await openCalendar();

    expect(dayEnabled('2026-06-03')).toBe(true); // return 06-10 = existing pickup
    expect(dayDisabled('2026-06-10')).toBe(true); // interior conflict
    expect(dayEnabled('2026-06-17')).toBe(true); // pickup on existing return day
    expect(dayEnabled('2026-06-24')).toBe(true); // clear of the booking
  });
});
