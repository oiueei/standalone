import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { describe, test, expect, vi, afterEach, beforeEach } from 'vitest';
import i18n from 'i18next';
import en from '../i18n/locales/en.json';
import RequestThingPage from './RequestThingPage';

// utils/rental.js is unit-tested on its own — these tests protect the PAGE's
// wiring: what the pickers produce must be what the POST body carries.

// Dynamic dates keep the test valid on any run day: the next Monday at least
// two days out is always inside the [today, today+90] picker range.
function nextMonday() {
  const d = new Date();
  d.setHours(0, 0, 0, 0);
  d.setDate(d.getDate() + 2);
  while (d.getDay() !== 1) d.setDate(d.getDate() + 1);
  return d;
}
// Local-date ISO — toISOString() is UTC and would slide midnight back a day.
const iso = (d) =>
  `${d.getFullYear()}-${String(d.getMonth() + 1).padStart(2, '0')}-${String(d.getDate()).padStart(2, '0')}`;
const display = (d) =>
  `${String(d.getDate()).padStart(2, '0')}/${String(d.getMonth() + 1).padStart(2, '0')}/${d.getFullYear()}`;
const plusDays = (d, n) => {
  const c = new Date(d);
  c.setDate(c.getDate() + n);
  return c;
};

// The same JSON shapes the DRF serializers emit (subset the page reads).
const RENTAL_THING = {
  code: 'RTHG01',
  headline: 'Drill',
  type: 'RENT_THING',
  fee: '5.00',
  rental_durations: [7],
  rental_weekdays: [0, 1, 2, 3, 4],
  available_today: true,
  next_available: iso(new Date()),
  collection_code: 'RCOL01',
};

function mockRoutes({ thing, ownThings = [], request = { ok: true, status: 201 } }) {
  globalThis.fetch = vi.fn((url, options = {}) => {
    const respond = (status, body) =>
      Promise.resolve({ ok: status < 400, status, json: async () => body });
    if (url.includes('/calendar/')) return respond(200, []);
    if (url.endsWith('/request/'))
      return respond(
        request.status,
        request.body ?? { message: 'Booking request sent', booking_code: 'BK0001' }
      );
    if (url === '/api/v1/things/') return respond(200, { results: ownThings });
    if (options.method === undefined || options.method === 'GET') return respond(200, thing);
    return respond(404, {});
  });
}

function renderPage(collectionCode, thingCode) {
  return render(
    <MemoryRouter initialEntries={[`/collections/${collectionCode}/things/${thingCode}/request`]}>
      <Routes>
        <Route path="/collections/:code/things/:thingCode/request" element={<RequestThingPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('RequestThingPage (what the pickers produce is what the POST carries)', () => {
  beforeEach(() => {
    localStorage.setItem('userCode', 'TEST01');
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  test('a rules-bound rental derives the return date and POSTs it with the collection code', async () => {
    mockRoutes({ thing: RENTAL_THING });
    renderPage('RCOL01', 'RTHG01');
    await screen.findByText('Rental length');

    const pickup = nextMonday();
    // The single fixed length is preselected (#4), so the pickup picker is live.
    // HDS DateInput commits its value on blur, not per keystroke.
    const input = screen.getByLabelText(/Pickup date/);
    fireEvent.change(input, { target: { value: display(pickup) } });
    fireEvent.blur(input);

    // A one-week rental picked up on a Monday returns the NEXT Monday.
    const returnDay = plusDays(pickup, 7);
    expect(screen.getByText(`Return by ${display(returnDay)}`)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Rent' }));

    await screen.findByText("You're all set!");
    const [url, options] = globalThis.fetch.mock.calls.find(([u]) => u.endsWith('/request/'));
    expect(url).toBe('/api/v1/things/RTHG01/request/');
    expect(JSON.parse(options.body)).toEqual({
      start_date: iso(pickup),
      end_date: iso(returnDay),
      collection_code: 'RCOL01',
    });
  });

  test.each([
    ['5.00', true],
    ['0.00', false],
    [null, false],
  ])('the price line for a fee of %j is shown: %s', async (fee, shown) => {
    mockRoutes({ thing: { ...RENTAL_THING, fee } });
    renderPage('RCOL01', 'RTHG01');
    await screen.findByText('Rental length');

    if (shown) expect(screen.getByText('Price:')).toBeInTheDocument();
    else expect(screen.queryByText('Price:')).toBeNull();
  });

  test('a 409 overlap shows the date-overlap message and no success screen', async () => {
    mockRoutes({ thing: RENTAL_THING, request: { status: 409, body: { error: 'overlap' } } });
    renderPage('RCOL01', 'RTHG01');
    await screen.findByText('Rental length');

    const input = screen.getByLabelText(/Pickup date/);
    fireEvent.change(input, { target: { value: display(nextMonday()) } });
    fireEvent.blur(input);
    fireEvent.click(screen.getByRole('button', { name: 'Rent' }));

    expect(await screen.findByText('Date overlaps with another booking.')).toBeInTheDocument();
    expect(screen.queryByText("You're all set!")).not.toBeInTheDocument();
  });
});

describe('RequestThingPage — the availability notice states the status once', () => {
  beforeEach(() => localStorage.setItem('userCode', 'TEST01'));
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  test('available today: the heading is "Availability." and the body is just "Immediate"', async () => {
    mockRoutes({ thing: { ...RENTAL_THING, available_today: true } });
    renderPage('RCOL01', 'RTHG01');
    await screen.findByText('Rental length');

    // The bug: the body was `${availabilityLabel} ${status}`, so with the
    // Notification's own label the word "Availability." printed twice.
    expect(screen.getByText('Immediate')).toBeInTheDocument();
    expect(screen.queryByText(/Availability\.\s*Immediate/)).toBeNull();
  });

  test('not available today: the body is the next-available date, once', async () => {
    const soon = plusDays(new Date(), 5);
    mockRoutes({
      thing: { ...RENTAL_THING, available_today: false, next_available: iso(soon) },
    });
    renderPage('RCOL01', 'RTHG01');
    await screen.findByText('Rental length');

    expect(screen.getByText(display(soon))).toBeInTheDocument();
    expect(screen.queryByText(new RegExp(`Availability\\.\\s*${display(soon)}`))).toBeNull();
  });

  test('nothing on the horizon: the body is the "not available soon" line', async () => {
    mockRoutes({
      thing: { ...RENTAL_THING, available_today: false, next_available: null },
    });
    renderPage('RCOL01', 'RTHG01');
    await screen.findByText('Rental length');

    expect(screen.getByText('Not available soon')).toBeInTheDocument();
  });
});

describe('the date picker chrome speaks the UI language', () => {
  beforeEach(() => {
    localStorage.setItem('userCode', 'TEST01');
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    i18n.removeResourceBundle('en', 'translation');
    i18n.addResourceBundle('en', 'translation', en);
  });

  // HDS's DateInput only localises its calendar to en/fi/sv (the `language`
  // prop); es and ca are not options. What it does expose are these three label
  // props. Overriding the i18n keys and watching the labels follow proves they
  // are wired — a hard-coded string, or leaning on `language` alone, would
  // ignore this.
  test('the open, confirm and close labels come from i18n, not HDS defaults', async () => {
    i18n.addResourceBundle(
      'en',
      'translation',
      { datePicker: { open: 'Abrir calendario', select: 'Confirmar', close: 'Cerrar' } },
      true,
      true
    );
    mockRoutes({ thing: RENTAL_THING });
    const { container } = renderPage('RCOL01', 'RTHG01');
    await screen.findByText('Rental length');

    const openBtn = screen.getByRole('button', { name: 'Abrir calendario' });
    expect(screen.queryByRole('button', { name: 'Choose date' })).not.toBeInTheDocument();

    fireEvent.click(openBtn);
    await waitFor(() => expect(container.querySelector('[data-date]')).toBeTruthy());
    expect(screen.getByRole('button', { name: 'Confirmar' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cerrar' })).toBeInTheDocument();
  });
});

describe('the demo notice on a seed collection', () => {
  beforeEach(() => {
    localStorage.setItem('userCode', 'TEST01');
    // The copy a deployment supplies through `deploymentI18n` — absent upstream.
    i18n.addResourceBundle(
      'en',
      'translation',
      {
        demoNotice: { title: 'This is a demo', body: 'Shared and reset.', realNote: 'Yours stay.' },
      },
      true,
      true
    );
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
    i18n.removeResourceBundle('en', 'translation');
    i18n.addResourceBundle('en', 'translation', en);
  });

  test('shows before and after submit — the confirmation and the "it wasn\'t real" sit together', async () => {
    mockRoutes({ thing: { ...RENTAL_THING, collection_is_onboarding: true } });
    renderPage('RCOL01', 'RTHG01');

    expect(await screen.findByText('This is a demo')).toBeInTheDocument();

    const input = screen.getByLabelText(/Pickup date/);
    fireEvent.change(input, { target: { value: display(nextMonday()) } });
    fireEvent.blur(input);
    fireEvent.click(screen.getByRole('button', { name: 'Rent' }));

    expect(await screen.findByText("You're all set!")).toBeInTheDocument();
    expect(screen.getByText('This is a demo')).toBeInTheDocument();
  });

  test('stays hidden on a normal collection even with the copy present', async () => {
    mockRoutes({ thing: RENTAL_THING });
    renderPage('RCOL01', 'RTHG01');
    await screen.findByText('Rental length');

    expect(screen.queryByText('This is a demo')).not.toBeInTheDocument();
  });
});

describe("the collection's request-page note — every date-based verb, not only RESERVE_THING", () => {
  beforeEach(() => {
    localStorage.setItem('userCode', 'TEST01');
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  test('the hero of a request carries the request modifier, whichever verb it is', async () => {
    mockRoutes({ thing: RENTAL_THING });
    const { container, unmount } = renderPage('RCOL01', 'RTHG01');
    await screen.findByText('Rental length');
    expect(container.querySelector('.form-hero')).toHaveClass('form-hero--request');
    unmount();

    mockRoutes({ thing: { ...RENTAL_THING, type: 'RESERVE_THING', reservation_unit: 'DAY' } });
    const reservation = renderPage('RCOL01', 'RTHG01');
    await screen.findByRole('heading', { level: 1, name: /Reserve/ });
    expect(reservation.container.querySelector('.form-hero')).toHaveClass('form-hero--request');
  });

  test("the page's error hero keeps the large title: only the form is the request's", async () => {
    mockRoutes({ thing: {} });
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 500, json: async () => ({}) })
    );
    const { container } = renderPage('RCOL01', 'RTHG01');
    await screen.findByRole('heading', { level: 1, name: 'Error' });

    expect(container.querySelector('.form-hero')).not.toHaveClass('form-hero--request');
  });

  test('shows on a RENT_THING request page too', async () => {
    mockRoutes({
      thing: { ...RENTAL_THING, collection_request_info: 'Pickup is Tuesdays only.' },
    });
    renderPage('RCOL01', 'RTHG01');
    await screen.findByText('Rental length');

    expect(screen.getByText('Pickup is Tuesdays only.')).toBeInTheDocument();
  });
});
