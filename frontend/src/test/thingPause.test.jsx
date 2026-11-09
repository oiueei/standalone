import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import { axe, toHaveNoViolations } from 'jest-axe';
import en from '../i18n/locales/en.json';
import es from '../i18n/locales/es.json';
import ca from '../i18n/locales/ca.json';

expect.extend(toHaveNoViolations);
window.scrollTo = vi.fn();

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  ),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import AddThingPage from '../pages/AddThingPage';
import EditThingPage from '../pages/EditThingPage';
import RequestThingPage from '../pages/RequestThingPage';
import ThingInfoRows from '../components/ThingInfoRows';
import { settle } from './settle';
import declarePalette from './declarePalette';

/**
 * Pausing a thing with a calendar between two days: a switch and two days on the edit
 * page only, a warning (never a cancellation) about the bookings in those days, a row on
 * the thing, and the refusal of a request that overlaps it said in the reader's language.
 */
const mockResponse = (data, ok = true, status = ok ? 200 : 400) => ({
  ok,
  status,
  json: () => Promise.resolve(data),
  clone() {
    return mockResponse(data, ok, status);
  },
});

const LOAN = {
  code: 'THG001',
  type: 'LEND_THING',
  collection_kind: 'LIBRARY',
  collection_allowed_thing_types: ['LEND_THING', 'RENT_THING'],
  headline: 'Drill',
  description: '',
};

function setApi({ thing = {}, collection = {}, patch } = {}) {
  apiFetch.mockImplementation((url, opts = {}) => {
    const method = opts.method || 'GET';
    if (method === 'PATCH') return Promise.resolve(patch ?? mockResponse({}));
    if (url === '/api/v1/things/' && method === 'POST')
      return Promise.resolve(mockResponse({ code: 'NEW001' }));
    if (/\/collections\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(collection));
    if (/\/things\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(thing));
    return Promise.resolve(mockResponse({}));
  });
}

async function renderEdit(thing, patch) {
  setApi({ thing: { ...LOAN, ...thing }, patch });
  const view = render(
    <MemoryRouter initialEntries={['/things/THG001/edit']}>
      <Routes>
        <Route path="/things/:thingCode/edit" element={<EditThingPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
  await settle(apiFetch);
  await screen.findByDisplayValue(thing.headline ?? 'Drill');
  return view;
}

const patchBody = () => {
  const call = apiFetch.mock.calls.find(([, o]) => o?.method === 'PATCH');
  return call && JSON.parse(call[1].body);
};

const typeDate = (container, id, value) => {
  const input = container.querySelector(`#${id}`);
  fireEvent.change(input, { target: { value } });
  fireEvent.blur(input);
};

const toggle = (container) => container.querySelector('#edit-thing-pause');

const booking = (start, end, status = 'ACCEPTED', code = 'BKG001') => ({
  code,
  status,
  start_date: start,
  end_date: end,
});

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
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

describe('the words of the pause', () => {
  test('the switch is fixed letter by letter in the three languages', () => {
    expect(es.thingPause.toggleLabel).toBe(
      'Pausar reservas: entre esas dos fechas nadie puede pedirla ni reservarla; las reservas ya hechas no se anulan.'
    );
    expect(ca.thingPause.toggleLabel).toBe(
      "Pausar les reserves: entre aquestes dues dates ningú no la pot demanar ni reservar; les reserves ja fetes no s'anul·len."
    );
    expect(en.thingPause.toggleLabel).toBe(
      'Pause bookings: between these two dates nobody can request or book it; bookings already made are not cancelled.'
    );
  });

  test('the two days are named in the three languages', () => {
    expect([es, ca, en].map((l) => [l.thingPause.fromLabel, l.thingPause.untilLabel])).toEqual([
      ['Desde', 'Hasta'],
      ['Des de', 'Fins a'],
      ['From', 'Until'],
    ]);
  });

  test('the warning is fixed, singular and plural, in the three languages', () => {
    const keys = [
      'bookingsInRange_one',
      'bookingsInRange_other',
      'loansInRange_one',
      'loansInRange_other',
    ];
    const expected = {
      es: [
        'Hay {{count}} reserva en esas fechas: la pausa no la anula. Si hace falta, puedes cancelarla en <1>Solicitudes para mí</1>.',
        'Hay {{count}} reservas en esas fechas: la pausa no las anula. Si hace falta, puedes cancelarlas en <1>Solicitudes para mí</1>.',
        'Hay {{count}} solicitud en esas fechas: la pausa no la anula. Si está pendiente, puedes rechazarla en <1>Solicitudes para mí</1>; si ya está aceptada, sigue en pie.',
        'Hay {{count}} solicitudes en esas fechas: la pausa no las anula. Las pendientes puedes rechazarlas en <1>Solicitudes para mí</1>; las aceptadas siguen en pie.',
      ],
      ca: [
        "Hi ha {{count}} reserva en aquestes dates: la pausa no l'anul·la. Si cal, la pots cancel·lar a <1>Sol·licituds per a mi</1>.",
        'Hi ha {{count}} reserves en aquestes dates: la pausa no les anul·la. Si cal, les pots cancel·lar a <1>Sol·licituds per a mi</1>.',
        "Hi ha {{count}} sol·licitud en aquestes dates: la pausa no l'anul·la. Si està pendent, la pots rebutjar a <1>Sol·licituds per a mi</1>; si ja està acceptada, es manté.",
        'Hi ha {{count}} sol·licituds en aquestes dates: la pausa no les anul·la. Les pendents les pots rebutjar a <1>Sol·licituds per a mi</1>; les acceptades es mantenen.',
      ],
      en: [
        'There is {{count}} booking on those dates: the pause does not cancel it. If need be, you can cancel it in <1>Requests to me</1>.',
        'There are {{count}} bookings on those dates: the pause does not cancel them. If need be, you can cancel them in <1>Requests to me</1>.',
        'There is {{count}} request on those dates: the pause does not cancel it. If it is still pending, you can decline it in <1>Requests to me</1>; if it has been accepted, it stands.',
        'There are {{count}} requests on those dates: the pause does not cancel them. Pending ones you can decline in <1>Requests to me</1>; accepted ones stand.',
      ],
    };
    const langs = { es, ca, en };
    for (const [l, texts] of Object.entries(expected)) {
      expect(keys.map((k) => langs[l].thingPause[k])).toEqual(texts);
    }
  });

  test('no word of the pause sends the manager to their own bookings', () => {
    for (const l of [es, ca, en]) {
      for (const text of Object.values(l.thingPause)) {
        expect(text).not.toMatch(/tus reservas|les teves reserves|your bookings/i);
      }
    }
  });

  test('the rows of the thing and the refusal are fixed in the three languages', () => {
    expect([es, ca, en].map((l) => l.thingPage.pausedRange)).toEqual([
      'Sin reservas del {{from}} al {{until}}',
      'Sense reserves del {{from}} al {{until}}',
      'No bookings from {{from}} to {{until}}',
    ]);
    expect([es, ca, en].map((l) => l.thingPage.pausedDay)).toEqual([
      'Sin reservas el {{date}}',
      'Sense reserves el {{date}}',
      'No bookings on {{date}}',
    ]);
    expect([es, ca, en].map((l) => l.requestErrors.thing_paused)).toEqual([
      'Esta cosa está en pausa en esas fechas.',
      'Aquesta cosa està en pausa en aquestes dates.',
      'This thing is paused on those dates.',
    ]);
  });
});

describe('where the switch is', () => {
  test.each([
    ['a loan', { type: 'LEND_THING' }],
    ['a rental', { type: 'RENT_THING' }],
    [
      'a shed’s space',
      {
        type: 'RESERVE_THING',
        collection_kind: 'SHED',
        collection_allowed_thing_types: ['RESERVE_THING'],
      },
    ],
  ])('%s has it', async (_, thing) => {
    const { container } = await renderEdit(thing);

    expect(toggle(container)).not.toBeNull();
    expect(toggle(container)).toHaveAttribute('aria-pressed', 'false');
    expect(
      container.querySelector('label[for="edit-thing-pause"], #edit-thing-pause-label')
    ).toBeTruthy();
  });

  test('a gift does not', async () => {
    const { container } = await renderEdit({
      type: 'GIFT_THING',
      collection_kind: 'STALL',
      collection_allowed_thing_types: ['GIFT_THING', 'SELL_THING'],
    });

    expect(toggle(container)).toBeNull();
  });

  test('the page that adds a thing does not, in any kind', async () => {
    for (const [kind, verbs] of [
      ['LIBRARY', ['LEND_THING', 'RENT_THING']],
      ['SHED', ['RESERVE_THING']],
      ['STALL', ['GIFT_THING', 'SELL_THING']],
    ]) {
      setApi({
        collection: { kind, headline: 'Group', mode: 'PROPRIETARY', allowed_thing_types: verbs },
      });
      const { container, unmount } = render(
        <MemoryRouter initialEntries={['/collections/COL001/add']}>
          <Routes>
            <Route path="/collections/:code/add" element={<AddThingPage />} />
          </Routes>
        </MemoryRouter>
      );
      await settle(apiFetch);
      await screen.findByLabelText(/Title/);

      expect(container.querySelector('#edit-thing-pause, [id$="-pause"]')).toBeNull();
      expect(container.querySelector('[id$="paused-from"]')).toBeNull();
      unmount();
    }
  });
});

describe('what is shown and sent', () => {
  test('a pause in force loads as on, with its two days', async () => {
    const { container } = await renderEdit({
      paused_from: '2026-06-10',
      paused_until: '2026-06-12',
    });

    expect(toggle(container)).toHaveAttribute('aria-pressed', 'true');
    expect(container.querySelector('#edit-thing-paused-from')).toHaveValue('10/06/2026');
    expect(container.querySelector('#edit-thing-paused-until')).toHaveValue('12/06/2026');
  });

  test('a thing with no pause (or one that has passed, read back empty) loads as off', async () => {
    const { container } = await renderEdit({ paused_from: null, paused_until: null });

    expect(toggle(container)).toHaveAttribute('aria-pressed', 'false');
    expect(container.querySelector('#edit-thing-paused-from')).toBeNull();
  });

  test('turning it on shows the two days, in order, with their labels', async () => {
    const { container } = await renderEdit({});

    fireEvent.click(toggle(container));

    expect(toggle(container)).toHaveAttribute('aria-pressed', 'true');
    expect(container.querySelector('label[for="edit-thing-paused-from"]')).toHaveTextContent(
      'From'
    );
    expect(container.querySelector('label[for="edit-thing-paused-until"]')).toHaveTextContent(
      'Until'
    );
  });

  test('on, with two days, saving sends both as ISO days', async () => {
    const { container } = await renderEdit({});
    fireEvent.click(toggle(container));
    typeDate(container, 'edit-thing-paused-from', '10/06/2026');
    typeDate(container, 'edit-thing-paused-until', '12/06/2026');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toMatchObject({ paused_from: '2026-06-10', paused_until: '2026-06-12' });
  });

  test('turning a loaded pause off sends both days empty', async () => {
    const { container } = await renderEdit({
      paused_from: '2026-06-10',
      paused_until: '2026-06-12',
    });

    fireEvent.click(toggle(container));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody().paused_from).toBeNull();
    expect(patchBody().paused_until).toBeNull();
  });

  test('a thing never paused saves with both days empty, which changes nothing', async () => {
    await renderEdit({});

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toMatchObject({ paused_from: null, paused_until: null });
  });

  test('on with only one day sends the other empty, for the server to refuse in its field', async () => {
    const { container } = await renderEdit({});
    fireEvent.click(toggle(container));
    typeDate(container, 'edit-thing-paused-from', '10/06/2026');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toMatchObject({ paused_from: '2026-06-10', paused_until: null });
  });

  test('a gift saves without the keys', async () => {
    await renderEdit({
      type: 'GIFT_THING',
      collection_kind: 'STALL',
      collection_allowed_thing_types: ['GIFT_THING', 'SELL_THING'],
    });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).not.toHaveProperty('paused_from');
    expect(patchBody()).not.toHaveProperty('paused_until');
  });

  test('what the server says about a day is said in that day’s field, not in a toast', async () => {
    const { container } = await renderEdit(
      {},
      mockResponse({ paused_until: ['The pause cannot end in the past.'] }, false, 400)
    );
    fireEvent.click(toggle(container));
    typeDate(container, 'edit-thing-paused-from', '10/06/2020');
    typeDate(container, 'edit-thing-paused-until', '12/06/2020');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    const message = await screen.findByText('The pause cannot end in the past.');
    const describedBy = container
      .querySelector('#edit-thing-paused-until')
      .getAttribute('aria-describedby');
    expect(describedBy.split(' ')).toContain(message.closest('[id]').id);
    expect(screen.queryByText(en.editThing.errorSaving)).toBeNull();
    expect(screen.queryByTestId('navigated')).toBeNull();
  });

  test('the error goes away on the next save', async () => {
    const { container } = await renderEdit(
      {},
      mockResponse({ paused_from: ['A pause needs both days, or none.'] }, false, 400)
    );
    fireEvent.click(toggle(container));
    typeDate(container, 'edit-thing-paused-until', '12/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    await screen.findByText('A pause needs both days, or none.');

    // The next save fails for another reason: the page stays, and the old message
    // about the day must not.
    setApi({ thing: { ...LOAN }, patch: mockResponse({}, false, 500) });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await screen.findByText(en.editThing.errorSaving);
    expect(screen.queryByText('A pause needs both days, or none.')).toBeNull();
  });
});

describe('the warning about bookings in the pause', () => {
  const withDays = async (bookings) => {
    const view = await renderEdit({ bookings });
    fireEvent.click(toggle(view.container));
    typeDate(view.container, 'edit-thing-paused-from', '10/06/2026');
    typeDate(view.container, 'edit-thing-paused-until', '12/06/2026');
    return view;
  };

  const noticeText = async () =>
    (await screen.findByRole('link', { name: en.home.requestsToMe })).closest(
      '[class*="Notification"], .hds-notification, [role="status"] > *'
    ).textContent;

  test('a loan: says how many, in the plural, with two, and what can be done', async () => {
    await withDays([
      booking('2026-06-11', '2026-06-12', 'ACCEPTED', 'BKG001'),
      booking('2026-06-08', '2026-06-15', 'PENDING', 'BKG002'),
    ]);

    const link = await screen.findByRole('link', { name: en.home.requestsToMe });
    expect(link).toHaveAttribute('href', '/owner-bookings');
    expect(await noticeText()).toContain(
      'There are 2 requests on those dates: the pause does not cancel them. Pending ones you can decline in Requests to me; accepted ones stand.'
    );
    expect(screen.queryByText(/cancel it|you can cancel/i)).toBeNull();
  });

  test('a loan: says it in the singular with one', async () => {
    await withDays([booking('2026-06-11', '2026-06-12')]);

    expect(await noticeText()).toContain(
      'There is 1 request on those dates: the pause does not cancel it. If it is still pending, you can decline it in Requests to me; if it has been accepted, it stands.'
    );
  });

  test('a reservation: says it can be cancelled, with the link to Requests to me', async () => {
    const view = await renderEdit({
      type: 'RESERVE_THING',
      collection_kind: 'SHED',
      collection_allowed_thing_types: ['RESERVE_THING'],
      bookings: [booking('2026-06-11', '2026-06-12')],
    });
    fireEvent.click(toggle(view.container));
    typeDate(view.container, 'edit-thing-paused-from', '10/06/2026');
    typeDate(view.container, 'edit-thing-paused-until', '12/06/2026');

    const link = await screen.findByRole('link', { name: en.home.requestsToMe });
    expect(link).toHaveAttribute('href', '/owner-bookings');
    expect(await noticeText()).toContain(
      'There is 1 booking on those dates: the pause does not cancel it. If need be, you can cancel it in Requests to me.'
    );
  });

  test('says nothing with none', async () => {
    await withDays([booking('2026-07-01', '2026-07-03')]);

    expect(screen.queryByText(/(bookings?|requests?) on those dates/)).toBeNull();
  });

  test('does not count a booking that only touches an end', async () => {
    await withDays([
      booking('2026-06-07', '2026-06-10', 'ACCEPTED', 'BKG001'),
      booking('2026-06-13', '2026-06-15', 'ACCEPTED', 'BKG002'),
    ]);

    expect(screen.queryByText(/(bookings?|requests?) on those dates/)).toBeNull();
  });

  test('says nothing while the pause is off, however many bookings there are', async () => {
    await renderEdit({ bookings: [booking('2026-06-11', '2026-06-12')] });

    expect(screen.queryByText(/(bookings?|requests?) on those dates/)).toBeNull();
  });

  test('sits in a live region that was already there when the message came', async () => {
    const { container } = await withDays([booking('2026-06-11', '2026-06-12')]);
    await screen.findByText(/(bookings?|requests?) on those dates/);

    const region = container.querySelector(
      '[role="status"]:has(.hds-notification, [class*="Notification"])'
    );
    expect(region).not.toBeNull();
  });

  test('axe finds nothing wrong with the form with the pause on and a warning showing', async () => {
    const { container } = await withDays([booking('2026-06-11', '2026-06-12')]);
    await screen.findByText(/(bookings?|requests?) on those dates/);

    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('ThingInfoRows — the pause', () => {
  test('says the days when there are several', () => {
    render(
      <ThingInfoRows
        thing={{ type: 'LEND_THING', paused_from: '2026-06-10', paused_until: '2026-06-12' }}
        isDateBased
      />
    );

    expect(screen.getByText('No bookings from 10/06/2026 to 12/06/2026')).toBeInTheDocument();
  });

  test('says the day when it is one', () => {
    render(
      <ThingInfoRows
        thing={{ type: 'LEND_THING', paused_from: '2026-06-10', paused_until: '2026-06-10' }}
        isDateBased
      />
    );

    expect(screen.getByText('No bookings on 10/06/2026')).toBeInTheDocument();
    expect(screen.queryByText(/from/)).toBeNull();
  });

  test.each([
    ['no pause', {}],
    ['a pause that has passed, read back empty', { paused_from: null, paused_until: null }],
    ['only one day (never sent)', { paused_from: '2026-06-10', paused_until: null }],
  ])('has no row for %s', (_, pause) => {
    render(<ThingInfoRows thing={{ type: 'LEND_THING', ...pause }} isDateBased />);

    expect(screen.queryByText(/No bookings/)).toBeNull();
  });
});

describe('RequestThingPage — a request that meets the pause', () => {
  const RESERVE = {
    code: 'RSV01',
    type: 'RESERVE_THING',
    headline: 'Lathe',
    fee: null,
    collection_code: 'COL001',
    rental_weekdays: [],
    reservation_max_days: 1,
    available_today: true,
    next_available: null,
  };

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 5, 1, 12, 0, 0));
  });
  afterEach(() => vi.useRealTimers());

  test('the refusal is said in the reader’s language, not as a generic overlap', async () => {
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        return Promise.resolve(
          mockResponse(
            { error: 'This thing is paused on those dates.', code: 'thing_paused' },
            false,
            409
          )
        );
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url)) return Promise.resolve(mockResponse(RESERVE));
      return Promise.resolve(mockResponse({}));
    });
    const { container } = render(
      <MemoryRouter
        initialEntries={[{ pathname: '/collections/COL001/things/RSV01/request', state: {} }]}
      >
        <Routes>
          <Route
            path="/collections/:code/things/:thingCode/request"
            element={<RequestThingPage />}
          />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByText(/Reserve Lathe/);
    const input = container.querySelector('#reservation-pickup-date');
    fireEvent.change(input, { target: { value: '03/06/2026' } });
    fireEvent.blur(input);

    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    expect(await screen.findByText(en.requestErrors.thing_paused)).toBeInTheDocument();
    expect(screen.queryByText(en.request.dateOverlap)).toBeNull();
  });
});
