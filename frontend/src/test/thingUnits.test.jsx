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
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import AddThingPage from '../pages/AddThingPage';
import EditThingPage from '../pages/EditThingPage';
import RequestThingPage from '../pages/RequestThingPage';
import ThingInfoRows from '../components/ThingInfoRows';
import { clampUnits } from '../constants/things';
import { settle } from './settle';
import declarePalette from './declarePalette';

/**
 * A shed's space can have several identical units, up to 20: the form asks how many
 * (only there), the info rows say it when there are several, the request page asks
 * for the calendar as a member sees it, and the "one at a time" refusal is worded in
 * the reader's language.
 */
const mockResponse = (data, ok = true, status = ok ? 200 : 400) => ({
  ok,
  status,
  json: () => Promise.resolve(data),
});

const SHED = {
  kind: 'SHED',
  headline: 'Shed',
  mode: 'PROPRIETARY',
  allowed_thing_types: ['RESERVE_THING'],
};

function setApi({ collection = {}, thing = {} } = {}) {
  apiFetch.mockImplementation((url, opts = {}) => {
    const method = opts.method || 'GET';
    if (method === 'PATCH') return Promise.resolve(mockResponse({}));
    if (url === '/api/v1/things/' && method === 'POST')
      return Promise.resolve(mockResponse({ code: 'NEW001' }));
    if (/\/collections\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(collection));
    if (/\/things\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(thing));
    return Promise.resolve(mockResponse({}));
  });
}

async function renderAdd(collection) {
  setApi({ collection });
  const view = render(
    <MemoryRouter initialEntries={['/collections/COL001/add']}>
      <Routes>
        <Route path="/collections/:code/add" element={<AddThingPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
  await settle(apiFetch);
  return view;
}

async function renderEdit(thing) {
  setApi({ thing });
  const view = render(
    <MemoryRouter initialEntries={['/things/THG001/edit']}>
      <Routes>
        <Route path="/things/:thingCode/edit" element={<EditThingPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
  await settle(apiFetch);
  return view;
}

// The number box, by its id: the label also names the stepper buttons HDS draws beside it,
// so a lookup by label finds several elements.
const unitsInput = (container, prefix) =>
  waitFor(() => {
    const field = container.querySelector(`#${prefix}-units`);
    expect(field).not.toBeNull();
    return field;
  });

const sentBody = (method) => {
  const call = apiFetch.mock.calls.find(([, o]) => o?.method === method);
  return call && JSON.parse(call[1].body);
};

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

describe('the words of the units field', () => {
  test('are fixed letter by letter in the three languages', () => {
    expect(es.thingForm.unitsLabel).toBe('¿Cuántas iguales hay?');
    expect(es.thingForm.unitsHelp).toBe(
      'Si tienes varias iguales, se pueden reservar a la vez hasta este número. Cada persona reserva una.'
    );
    expect(ca.thingForm.unitsLabel).toBe("Quantes n'hi ha d'iguals?");
    expect(ca.thingForm.unitsHelp).toBe(
      "Si en tens diverses d'iguals, es poden reservar alhora fins a aquest nombre. Cada persona en reserva una."
    );
    expect(en.thingForm.unitsLabel).toBe('How many identical ones are there?');
    expect(en.thingForm.unitsHelp).toBe(
      'If you have several identical ones, they can be booked at the same time up to this number. Each person books one.'
    );
  });

  test('the refusal of a second unit at the same time is fixed in the three languages', () => {
    expect(es.requestErrors.reservation_one_per_person).toBe(
      'Ya tienes una reserva de esto a esa hora.'
    );
    expect(ca.requestErrors.reservation_one_per_person).toBe(
      "Ja tens una reserva d'això a aquesta hora."
    );
    expect(en.requestErrors.reservation_one_per_person).toBe(
      'You already have a booking of this at that time.'
    );
  });
});

describe('clampUnits', () => {
  test.each([
    ['3', 3],
    [3, 3],
    ['20', 20],
    ['21', 20],
    ['1000', 20],
    ['0', 1],
    ['-4', 1],
    ['', 1],
    ['abc', 1],
    ['2.6', 3],
    [undefined, 1],
  ])('%j goes to the server as %j', (typed, sent) => {
    expect(clampUnits(typed)).toBe(sent);
  });
});

describe('the units field of the thing form', () => {
  test('a shed asks for it, starting at 1', async () => {
    const { container } = await renderAdd(SHED);

    const field = await unitsInput(container, 'add-thing');
    expect(field).toHaveValue(1);
    expect(field).toHaveAttribute('min', '1');
    expect(field).toHaveAttribute('max', '20');
    expect(container.querySelector('label[for="add-thing-units"]')).toHaveTextContent(
      en.thingForm.unitsLabel
    );
    expect(screen.getByText(en.thingForm.unitsHelp)).toBeInTheDocument();
  });

  test.each([
    ['a stall', { kind: 'STALL', allowed_thing_types: ['GIFT_THING', 'SELL_THING'] }],
    ['a library', { kind: 'LIBRARY', allowed_thing_types: ['LEND_THING', 'RENT_THING'] }],
  ])('%s does not ask for it', async (_, collection) => {
    const { container } = await renderAdd({ ...collection, headline: 'Group' });
    await screen.findByLabelText(/Title/);

    expect(container.querySelector('[id$="-units"]')).toBeNull();
    expect(screen.queryByLabelText(en.thingForm.unitsLabel)).toBeNull();
  });

  test('what is typed is sent when a shed’s space is created', async () => {
    const { container } = await renderAdd(SHED);
    fireEvent.change(container.querySelector('#add-thing-headline'), {
      target: { value: 'Lathe' },
    });
    fireEvent.change(await unitsInput(container, 'add-thing'), { target: { value: '4' } });

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(sentBody('POST')).toBeTruthy());
    expect(sentBody('POST').units).toBe(4);
  });

  test('left alone, a shed’s space is created with 1', async () => {
    const { container } = await renderAdd(SHED);
    fireEvent.change(container.querySelector('#add-thing-headline'), {
      target: { value: 'Lathe' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(sentBody('POST')).toBeTruthy());
    expect(sentBody('POST').units).toBe(1);
  });

  test('a number out of range is brought into it, never sent as it is', async () => {
    const { container } = await renderAdd(SHED);
    fireEvent.change(container.querySelector('#add-thing-headline'), {
      target: { value: 'Lathe' },
    });
    fireEvent.change(await unitsInput(container, 'add-thing'), { target: { value: '99' } });

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(sentBody('POST')).toBeTruthy());
    expect(sentBody('POST').units).toBe(20);
  });

  test('a stall’s request has no such key', async () => {
    const { container } = await renderAdd({
      kind: 'STALL',
      headline: 'Group',
      allowed_thing_types: ['GIFT_THING', 'SELL_THING'],
    });
    fireEvent.change(container.querySelector('#add-thing-headline'), {
      target: { value: 'Chair' },
    });

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(sentBody('POST')).toBeTruthy());
    expect(sentBody('POST')).not.toHaveProperty('units');
  });

  test('editing a shed’s space shows the saved number and saves a change', async () => {
    const { container } = await renderEdit({
      code: 'THG001',
      type: 'RESERVE_THING',
      collection_kind: 'SHED',
      collection_allowed_thing_types: ['RESERVE_THING'],
      headline: 'Lathe',
      description: '',
      units: 4,
    });
    const field = await unitsInput(container, 'edit-thing');
    expect(field).toHaveValue(4);

    fireEvent.change(field, { target: { value: '2' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(sentBody('PATCH')).toBeTruthy());
    expect(sentBody('PATCH').units).toBe(2);
  });

  test('editing a space saved without a number shows 1', async () => {
    const { container } = await renderEdit({
      code: 'THG001',
      type: 'RESERVE_THING',
      collection_kind: 'SHED',
      collection_allowed_thing_types: ['RESERVE_THING'],
      headline: 'Lathe',
      description: '',
    });

    expect(await unitsInput(container, 'edit-thing')).toHaveValue(1);
  });

  test('editing a loan neither shows nor sends it', async () => {
    const { container } = await renderEdit({
      code: 'THG001',
      type: 'LEND_THING',
      collection_kind: 'LIBRARY',
      collection_allowed_thing_types: ['LEND_THING', 'RENT_THING'],
      headline: 'Drill',
      description: '',
    });
    await screen.findByDisplayValue('Drill');
    expect(container.querySelector('#edit-thing-units')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(sentBody('PATCH')).toBeTruthy());
    expect(sentBody('PATCH')).not.toHaveProperty('units');
  });

  test('axe finds nothing wrong with the form that asks', async () => {
    const { container } = await renderAdd(SHED);
    await unitsInput(container, 'add-thing');

    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('ThingInfoRows — the units row', () => {
  test('says how many when there are several', () => {
    render(<ThingInfoRows thing={{ type: 'RESERVE_THING', units: 4 }} isDateBased />);

    expect(screen.getByText('4 units')).toBeInTheDocument();
  });

  test.each([[1], [undefined], [null], [0]])('has no such row with %j', (units) => {
    render(<ThingInfoRows thing={{ type: 'RESERVE_THING', units }} isDateBased />);

    expect(screen.queryByText(/unit/i)).toBeNull();
  });

  test('is worded with the language’s own plural', () => {
    const { rerender } = render(<ThingInfoRows thing={{ type: 'RESERVE_THING', units: 2 }} />);
    expect(screen.getByText('2 units')).toBeInTheDocument();
    rerender(<ThingInfoRows thing={{ type: 'RESERVE_THING', units: 20 }} />);
    expect(screen.getByText('20 units')).toBeInTheDocument();
  });

  test('is worded in the three languages (the plural, the same count)', () => {
    expect(es.thingPage.unitsCount_other).toBe('{{count}} unidades');
    expect(ca.thingPage.unitsCount_other).toBe('{{count}} unitats');
    expect(en.thingPage.unitsCount_other).toBe('{{count}} units');
  });
});

describe('RequestThingPage — a booking with several units', () => {
  const RESERVE_THING = {
    code: 'RSV01',
    type: 'RESERVE_THING',
    headline: 'Lathe',
    fee: null,
    collection_code: 'COL001',
    rental_weekdays: [],
    reservation_max_days: 1,
    available_today: true,
    next_available: null,
    units: 3,
  };

  function setRequestApi(post) {
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        return Promise.resolve(post ?? mockResponse({ booking_code: 'B1' }));
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url))
        return Promise.resolve(mockResponse(RESERVE_THING));
      return Promise.resolve(mockResponse({}));
    });
  }

  function renderRequest() {
    return render(
      <MemoryRouter
        initialEntries={[{ pathname: '/collections/COL001/things/RSV01/request', state: {} }]}
      >
        <Routes>
          <Route
            path="/collections/:code/things/:thingCode/request"
            element={<RequestThingPage />}
          />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </MemoryRouter>
    );
  }

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 5, 1, 12, 0, 0));
  });
  afterEach(() => vi.useRealTimers());

  test('asks for the calendar as a member is served it, with ?for=request', async () => {
    setRequestApi();
    renderRequest();
    await screen.findByText(/Reserve Lathe/);

    const urls = apiFetch.mock.calls.map(([url]) => url).filter((url) => /\/calendar\//.test(url));
    expect(urls).toEqual(['/api/v1/things/RSV01/calendar/?for=request']);
  });

  test('says the one-at-a-time refusal in the reader’s language', async () => {
    setRequestApi(
      mockResponse(
        {
          error: 'You already have a booking of this at that time.',
          code: 'reservation_one_per_person',
        },
        false,
        409
      )
    );
    const { container } = renderRequest();
    await screen.findByText(/Reserve Lathe/);
    const input = container.querySelector('#reservation-pickup-date');
    fireEvent.change(input, { target: { value: '03/06/2026' } });
    fireEvent.blur(input);

    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    expect(
      await screen.findByText(en.requestErrors.reservation_one_per_person)
    ).toBeInTheDocument();
    // Not the generic "those dates are taken" this page says for any other 409.
    expect(screen.queryByText(en.request.dateOverlap)).toBeNull();
  });

  test('axe finds nothing wrong with the page', async () => {
    setRequestApi();
    const { container } = renderRequest();
    await screen.findByText(/Reserve Lathe/);

    expect(await axe(container)).toHaveNoViolations();
  });
});
