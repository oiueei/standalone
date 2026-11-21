import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  ),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import RequestThingPage from '../pages/RequestThingPage';
import declarePalette from './declarePalette';
import { settle } from './settle';

function mockResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

// A RENT_THING whose collection defines rental rules (#7): fixed lengths of one
// and two weeks, pickup/return only on Wednesdays (Python weekday 2).
const RENTAL_THING = {
  code: 'RENT01',
  type: 'RENT_THING',
  headline: 'Cordless drill',
  fee: null,
  collection_code: 'COL001',
  rental_durations: [7, 14],
  rental_weekdays: [2],
  available_today: true,
  next_available: null,
};

function setApi({ thing = RENTAL_THING, calendar = [] } = {}) {
  apiFetch.mockImplementation((url) => {
    if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse(calendar));
    if (/\/things\/[^/]+\/(\?.*)?$/.test(url)) return Promise.resolve(mockResponse(thing));
    if (url === '/api/v1/things/') return Promise.resolve(mockResponse({ results: [] }));
    return Promise.resolve(mockResponse({}));
  });
}

function renderPage() {
  return render(
    <MemoryRouter
      initialEntries={[{ pathname: '/collections/COL001/things/RENT01/request', state: {} }]}
    >
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
  declarePalette({
    color_01: 'bus',
    color_02: 'suomenlinna-light',
    color_03: 'copper',
    color_04: 'black',
    color_05: 'white',
    color_06: 'white',
  });
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
  test("lists the collection's fixed lengths as options", async () => {
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
    // Existing booking occupies Wed 10 → Wed 17. Under strict overlap:
    //  - picking up 06-03 returns on 06-10 = the booking's pickup day → allowed
    //  - picking up 06-10 overlaps the interior → blocked
    //  - picking up 06-17 = the booking's return day → allowed (back-to-back)
    setApi({
      calendar: [{ start_date: '2026-06-10', end_date: '2026-06-17', status: 'ACCEPTED' }],
    });
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

// ── LEND/RENT with free dates (no fixed lengths) ─────────────────────────────
//
// The two pickers of the free form follow the rule of chained handovers the server and
// the card use: a booking [s, e] occupies the pickup on [s, e), its
// return day e is free for the next pickup, and a stretch is out only if it runs over a
// booking. Both pickers used to grey out BOTH ends of every booking, so a card saying
// "available from 06/10" came with a calendar that began on the 7th, and a request from
// the 6th to the 8th — which the server accepts — could not be made.
const FREE_THING = {
  code: 'LEND01',
  type: 'LEND_THING',
  headline: 'Ladder',
  fee: null,
  collection_code: 'COL001',
  rental_durations: [],
  rental_weekdays: [],
  available_today: true,
  next_available: null,
};

// The free form has two calendars: the pickup's button first, the return's second.
async function openFreeCalendar(which) {
  const buttons = screen.getAllByRole('button', { name: 'Choose date' });
  fireEvent.click(buttons[which === 'return' ? 1 : 0]);
  await waitFor(() => expect(document.querySelector('[data-date]')).toBeTruthy());
}
// The form is there once its two calendar buttons are and the calendar has answered.
const freeFormReady = async () => {
  await screen.findAllByRole('button', { name: 'Choose date' });
  await settle(apiFetch);
};
const typeInto = (container, selector, display) => {
  const input = container.querySelector(selector);
  fireEvent.change(input, { target: { value: display } });
  fireEvent.blur(input);
};
const free = (calendar = [], extra = {}) =>
  setApi({ thing: { ...FREE_THING, ...extra }, calendar });

describe('RequestThingPage — free dates: the pickup calendar', () => {
  test('a booking’s return day can be picked up; the days it occupies cannot', async () => {
    free([{ start_date: '2026-06-08', end_date: '2026-06-10', status: 'ACCEPTED' }]);
    renderPage();
    await freeFormReady();

    await openFreeCalendar('pickup');

    expect(dayEnabled('2026-06-07')).toBe(true);
    expect(dayDisabled('2026-06-08')).toBe(true);
    expect(dayDisabled('2026-06-09')).toBe(true);
    expect(dayEnabled('2026-06-10')).toBe(true); // the booking's return day: chained
    expect(dayEnabled('2026-06-11')).toBe(true);
  });

  test('a booking 05→06 — the 06 can be picked up and the 05 cannot', async () => {
    free([{ start_date: '2026-06-05', end_date: '2026-06-06', status: 'ACCEPTED' }]);
    renderPage();
    await freeFormReady();

    await openFreeCalendar('pickup');

    expect(dayDisabled('2026-06-05')).toBe(true);
    expect(dayEnabled('2026-06-06')).toBe(true);
    expect(dayEnabled('2026-06-07')).toBe(true);
  });

  test('a closure day is out', async () => {
    free([], { closed_dates: ['2026-06-12'] });
    renderPage();
    await freeFormReady();

    await openFreeCalendar('pickup');

    expect(dayDisabled('2026-06-12')).toBe(true);
    expect(dayEnabled('2026-06-11')).toBe(true);
    expect(dayEnabled('2026-06-13')).toBe(true);
  });
});

describe('RequestThingPage — free dates: the return calendar', () => {
  test('with a pickup chosen, a return that lands on another booking’s pickup stays open; one that runs over it does not', async () => {
    // A booking 08→10, and a pickup on Saturday the 6th.
    free([{ start_date: '2026-06-08', end_date: '2026-06-10', status: 'ACCEPTED' }]);
    const { container } = renderPage();
    await freeFormReady();
    typeInto(container, '#request-start-date', '06/06/2026');

    await openFreeCalendar('return');

    expect(dayDisabled('2026-06-05')).toBe(true); // before the pickup
    expect(dayEnabled('2026-06-06')).toBe(true); // the pickup day itself: a same-day return
    expect(dayEnabled('2026-06-07')).toBe(true);
    expect(dayEnabled('2026-06-08')).toBe(true); // chained onto the booking's pickup
    expect(dayDisabled('2026-06-09')).toBe(true); // runs over it
    expect(dayDisabled('2026-06-10')).toBe(true);
    expect(dayDisabled('2026-06-11')).toBe(true);
  });

  test('with no pickup chosen yet it follows the pickup’s rule', async () => {
    free([{ start_date: '2026-06-05', end_date: '2026-06-06', status: 'ACCEPTED' }]);
    renderPage();
    await freeFormReady();

    await openFreeCalendar('return');

    expect(dayDisabled('2026-06-05')).toBe(true);
    expect(dayEnabled('2026-06-06')).toBe(true);
    expect(dayEnabled('2026-06-07')).toBe(true);
  });

  test('a closure day is out as a return', async () => {
    free([], { closed_dates: ['2026-06-12'] });
    const { container } = renderPage();
    await freeFormReady();
    typeInto(container, '#request-start-date', '10/06/2026');

    await openFreeCalendar('return');

    expect(dayDisabled('2026-06-12')).toBe(true);
    expect(dayEnabled('2026-06-11')).toBe(true);
    // Across the closure the item is already out, so the day after is open.
    expect(dayEnabled('2026-06-13')).toBe(true);
  });

  test('a pickup after the booking leaves the days before it out and the ones after it open', async () => {
    free([{ start_date: '2026-06-08', end_date: '2026-06-10', status: 'ACCEPTED' }]);
    const { container } = renderPage();
    await freeFormReady();

    typeInto(container, '#request-start-date', '11/06/2026');
    await openFreeCalendar('return');

    expect(dayDisabled('2026-06-09')).toBe(true); // before the pickup
    expect(dayDisabled('2026-06-10')).toBe(true);
    expect(dayEnabled('2026-06-11')).toBe(true);
    expect(dayEnabled('2026-06-12')).toBe(true); // clear of the booking, which is behind
  });
});

// The server demands the collection's weekdays at both ends of a loan
// or rental, with or without fixed lengths, and the free form did not apply them — a
// Wednesday could be picked in a "Saturdays only" collection and was refused on send.
// June 2026: the 6th, 13th and 20th are Saturdays; the 3rd and 10th are Wednesdays.
describe('RequestThingPage — free dates: only the weekdays the collection allows', () => {
  const SATURDAYS = { rental_weekdays: [5] };

  test('the pickup calendar leaves a Wednesday out and a Saturday open', async () => {
    free([], SATURDAYS);
    renderPage();
    await freeFormReady();

    await openFreeCalendar('pickup');

    expect(dayDisabled('2026-06-03')).toBe(true); // Wednesday
    expect(dayDisabled('2026-06-05')).toBe(true); // Friday
    expect(dayDisabled('2026-06-07')).toBe(true); // Sunday
    expect(dayEnabled('2026-06-06')).toBe(true); // Saturday
    expect(dayEnabled('2026-06-13')).toBe(true);
  });

  test('the return calendar does the same before any pickup is chosen', async () => {
    free([], SATURDAYS);
    renderPage();
    await freeFormReady();

    await openFreeCalendar('return');

    expect(dayDisabled('2026-06-03')).toBe(true);
    expect(dayDisabled('2026-06-10')).toBe(true);
    expect(dayEnabled('2026-06-06')).toBe(true);
    expect(dayEnabled('2026-06-13')).toBe(true);
  });

  test('and with a pickup chosen', async () => {
    free([], SATURDAYS);
    const { container } = renderPage();
    await freeFormReady();
    typeInto(container, '#request-start-date', '06/06/2026');

    await openFreeCalendar('return');

    expect(dayDisabled('2026-06-10')).toBe(true); // a Wednesday, after the pickup
    expect(dayDisabled('2026-06-12')).toBe(true);
    expect(dayEnabled('2026-06-13')).toBe(true); // the next Saturday
    expect(dayEnabled('2026-06-20')).toBe(true);
  });

  test('a collection with no weekdays listed leaves every day open', async () => {
    free([], { rental_weekdays: [] });
    renderPage();
    await freeFormReady();

    await openFreeCalendar('pickup');

    expect(dayEnabled('2026-06-03')).toBe(true);
    expect(dayEnabled('2026-06-06')).toBe(true);
    expect(dayEnabled('2026-06-07')).toBe(true);
  });

  test('chained handovers still hold on an allowed weekday: the booking’s return day can be picked up, the days it occupies cannot', async () => {
    free([{ start_date: '2026-06-13', end_date: '2026-06-20', status: 'ACCEPTED' }], SATURDAYS);
    renderPage();
    await freeFormReady();

    await openFreeCalendar('pickup');

    expect(dayEnabled('2026-06-06')).toBe(true);
    expect(dayDisabled('2026-06-13')).toBe(true); // a Saturday, but occupied
    expect(dayEnabled('2026-06-20')).toBe(true); // a Saturday, and the chained handover
  });
});

describe('RequestThingPage — free dates: the request the calendar now allows', () => {
  test('a request 06→08 after a booking 05→06 is sent with those dates', async () => {
    free([{ start_date: '2026-06-05', end_date: '2026-06-06', status: 'ACCEPTED' }]);
    const { container } = renderPage();
    await freeFormReady();
    typeInto(container, '#request-start-date', '06/06/2026');
    typeInto(container, '#request-end-date', '08/06/2026');

    fireEvent.click(screen.getByRole('button', { name: 'Borrow' }));

    await waitFor(() => {
      const post = apiFetch.mock.calls.find(
        ([url, o]) => /\/request\/$/.test(url) && o?.method === 'POST'
      );
      expect(post).toBeTruthy();
      expect(JSON.parse(post[1].body)).toEqual({
        start_date: '2026-06-06',
        end_date: '2026-06-08',
        collection_code: 'COL001',
      });
    });
  });
});
