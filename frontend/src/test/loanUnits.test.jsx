import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
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
import { amountTimes } from '../constants/things';
import { settle } from './settle';
import declarePalette from './declarePalette';

/**
 * A library's thing can have several identical units, and a request can ask for some
 * of them: the form asks how many there are, the request page asks how many are
 * wanted (and asks for the calendar again when that changes), shows the totals, and
 * says the three new refusals in the reader's language.
 */
const mockResponse = (data, ok = true, status = ok ? 200 : 400) => ({
  ok,
  status,
  json: () => Promise.resolve(data),
});

const LIBRARY = {
  kind: 'LIBRARY',
  headline: 'Library',
  mode: 'PROPRIETARY',
  allowed_thing_types: ['LEND_THING', 'RENT_THING'],
};

const sentBody = (method) => {
  const call = apiFetch.mock.calls.find(([, o]) => o?.method === method);
  return call && JSON.parse(call[1].body);
};

const unitsInput = (container, prefix) =>
  waitFor(() => {
    const field = container.querySelector(`#${prefix}-units`);
    expect(field).not.toBeNull();
    return field;
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

describe('the texts of the round, in the three languages', () => {
  test.each([
    ['request.quantityLabel', 'How many?', '¿Cuántos?', 'Quants?'],
    [
      'request.quantityHelp',
      'Up to {{units}}. Days with fewer than that free are greyed out in the calendar.',
      'Hasta {{units}}. Los días en que no quedan tantos libres salen en gris en el calendario.',
      'Fins a {{units}}. Els dies en què no en queden tants de lliures surten en gris al calendari.',
    ],
    [
      'request.priceTotal',
      'Price: {{count}} × {{unit}} = {{total}}',
      'Precio: {{count}} × {{unit}} = {{total}}',
      'Preu: {{count}} × {{unit}} = {{total}}',
    ],
    [
      'request.depositTotal',
      'Deposit: {{count}} × {{unit}} = {{total}}',
      'Fianza: {{count}} × {{unit}} = {{total}}',
      'Fiança: {{count}} × {{unit}} = {{total}}',
    ],
    [
      'thingForm.unitsHelpLibrary',
      'If you have several identical ones, people can borrow several at once, up to this number.',
      'Si tienes varias iguales, se pueden pedir varias a la vez, hasta este número.',
      "Si en tens unes quantes d'iguals, se'n poden demanar unes quantes alhora, fins a aquest nombre.",
    ],
    [
      'thingPage.unitsFreeToday',
      'Available today: {{free}} of {{units}}',
      'Disponibles hoy: {{free}} de {{units}}',
      'Disponibles avui: {{free}} de {{units}}',
    ],
    [
      'requestErrors.not_enough_units',
      "There aren't {{count}} free on those dates.",
      'No quedan {{count}} libres en esas fechas.',
      'No en queden {{count}} de lliures en aquestes dates.',
    ],
    [
      'requestErrors.loan_one_per_person',
      'You already have a request for this on those dates. To change how many, cancel it and ask again.',
      'Ya tienes una solicitud de esto en esas fechas. Para cambiar la cantidad, cancélala y vuelve a pedir.',
      "Ja tens una sol·licitud d'això en aquestes dates. Per canviar la quantitat, cancel·la-la i torna a demanar.",
    ],
    [
      'requestErrors.quantity_invalid',
      'Ask for between 1 and {{max}}.',
      'Pide entre 1 y {{max}}.',
      "Demana'n entre 1 i {{max}}.",
    ],
  ])('%s', (key, inEn, inEs, inCa) => {
    const read = (locale) => key.split('.').reduce((node, part) => node[part], locale);
    expect(read(en)).toBe(inEn);
    expect(read(es)).toBe(inEs);
    expect(read(ca)).toBe(inCa);
  });
});

describe('amountTimes', () => {
  test.each([
    ['5.00', 6, '30.00'],
    ['2.50', 3, '7.50'],
    ['5', 6, '30'],
    ['0.10', 3, '0.30'],
  ])('%j times %j is %j', (value, count, total) => {
    expect(amountTimes(value, count)).toBe(total);
  });
});

describe('the units field of the thing form in a library', () => {
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

  test('a library asks for it, starting at 1, with its own help', async () => {
    const { container } = await renderAdd(LIBRARY);

    const field = await unitsInput(container, 'add-thing');
    expect(field).toHaveValue(1);
    expect(field).toHaveAttribute('max', '20');
    expect(screen.getByText(en.thingForm.unitsHelpLibrary)).toBeInTheDocument();
    expect(screen.queryByText(en.thingForm.unitsHelp)).toBeNull();
  });

  test('what is typed is sent when a library’s thing is created', async () => {
    const { container } = await renderAdd(LIBRARY);
    fireEvent.change(container.querySelector('#add-thing-headline'), {
      target: { value: 'Arduino kit' },
    });
    fireEvent.change(await unitsInput(container, 'add-thing'), { target: { value: '6' } });

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(sentBody('POST')).toBeTruthy());
    expect(sentBody('POST').units).toBe(6);
  });

  test('a shed keeps the help it had', async () => {
    const { container } = await renderAdd({
      kind: 'SHED',
      headline: 'Shed',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['RESERVE_THING'],
    });
    await unitsInput(container, 'add-thing');

    expect(screen.getByText(en.thingForm.unitsHelp)).toBeInTheDocument();
    expect(screen.queryByText(en.thingForm.unitsHelpLibrary)).toBeNull();
  });

  test('editing a loan shows the saved number and saves a change', async () => {
    const { container } = await renderEdit({
      code: 'THG001',
      type: 'LEND_THING',
      collection_kind: 'LIBRARY',
      collection_allowed_thing_types: ['LEND_THING', 'RENT_THING'],
      headline: 'Drill',
      description: '',
      units: 6,
    });
    const field = await unitsInput(container, 'edit-thing');
    expect(field).toHaveValue(6);

    fireEvent.change(field, { target: { value: '3' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(sentBody('PATCH')).toBeTruthy());
    expect(sentBody('PATCH').units).toBe(3);
  });

  test('axe finds nothing wrong with the form that asks', async () => {
    const { container } = await renderAdd(LIBRARY);
    await unitsInput(container, 'add-thing');

    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('RequestThingPage — asking for several', () => {
  const LOAN = {
    code: 'LOAN01',
    type: 'LEND_THING',
    headline: 'Arduino kit',
    fee: '5.00',
    deposit: '20.00',
    collection_code: 'COL001',
    rental_durations: [],
    rental_weekdays: [],
    closed_dates: [],
    available_today: true,
    next_available: null,
    units: 6,
    units_free_today: 4,
  };

  let thing;
  let calendar;

  function setApi({ post, calendarFor } = {}) {
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        return Promise.resolve(post ?? mockResponse({ booking_code: 'B1' }));
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) {
        return Promise.resolve(mockResponse(calendarFor ? calendarFor(url) : calendar));
      }
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url)) return Promise.resolve(mockResponse(thing));
      return Promise.resolve(mockResponse({}));
    });
  }

  function renderRequest() {
    return render(
      <MemoryRouter
        initialEntries={[{ pathname: '/collections/COL001/things/LOAN01/request', state: {} }]}
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

  const calendarUrls = () =>
    apiFetch.mock.calls.map(([url]) => url).filter((url) => /\/calendar\//.test(url));

  const quantityInput = (container) => container.querySelector('#request-quantity');

  const pick = (container, id, value) => {
    const input = container.querySelector(`#${id}`);
    fireEvent.change(input, { target: { value } });
    fireEvent.blur(input);
  };

  beforeEach(() => {
    thing = LOAN;
    calendar = [];
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date(2026, 5, 1, 12, 0, 0));
  });
  afterEach(() => vi.useRealTimers());

  describe('the field', () => {
    test('is there when the thing has several units, with its label and help', async () => {
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);

      const field = quantityInput(container);
      expect(field).toHaveValue(1);
      expect(field).toHaveAttribute('min', '1');
      expect(field).toHaveAttribute('max', '6');
      expect(container.querySelector('label[for="request-quantity"]')).toHaveTextContent(
        'How many?'
      );
      expect(
        screen.getByText('Up to 6. Days with fewer than that free are greyed out in the calendar.')
      ).toBeInTheDocument();
    });

    test('comes before the dates', async () => {
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);

      const field = quantityInput(container);
      const start = container.querySelector('#request-start-date');
      expect(field.compareDocumentPosition(start) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    });

    test('comes before the pickup date when the lengths are fixed too', async () => {
      thing = { ...LOAN, rental_durations: [7] };
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);

      expect(quantityInput(container)).not.toBeNull();
    });

    test.each([
      ['one unit', { units: 1 }],
      ['no units said', { units: undefined }],
    ])('is not there with %s', async (_, extra) => {
      thing = { ...LOAN, ...extra };
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);

      expect(quantityInput(container)).toBeNull();
    });

    test('is not there for a reservation, whatever its units', async () => {
      thing = {
        ...LOAN,
        type: 'RESERVE_THING',
        reservation_max_days: 1,
        reservation_unit: 'DAY',
        fee: null,
        deposit: null,
      };
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Reserve Arduino kit/);

      expect(quantityInput(container)).toBeNull();
    });
  });

  describe('what is sent', () => {
    test('the request carries the quantity', async () => {
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      fireEvent.change(quantityInput(container), { target: { value: '4' } });
      pick(container, 'request-start-date', '10/06/2026');
      pick(container, 'request-end-date', '14/06/2026');

      fireEvent.click(screen.getByRole('button', { name: 'Borrow' }));

      await waitFor(() => expect(sentBody('POST')).toBeTruthy());
      expect(sentBody('POST')).toMatchObject({
        start_date: '2026-06-10',
        end_date: '2026-06-14',
        quantity: 4,
        collection_code: 'COL001',
      });
    });

    test('left alone it is 1', async () => {
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      pick(container, 'request-start-date', '10/06/2026');
      pick(container, 'request-end-date', '14/06/2026');

      fireEvent.click(screen.getByRole('button', { name: 'Borrow' }));

      await waitFor(() => expect(sentBody('POST')).toBeTruthy());
      expect(sentBody('POST').quantity).toBe(1);
    });

    test('with fixed lengths it travels too', async () => {
      thing = { ...LOAN, rental_durations: [7] };
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      fireEvent.change(quantityInput(container), { target: { value: '2' } });
      pick(container, 'request-pickup-date', '10/06/2026');

      fireEvent.click(screen.getByRole('button', { name: 'Borrow' }));

      await waitFor(() => expect(sentBody('POST')).toBeTruthy());
      expect(sentBody('POST')).toMatchObject({ end_date: '2026-06-17', quantity: 2 });
    });

    test('a number out of range is brought into it, never sent as it is', async () => {
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      fireEvent.change(quantityInput(container), { target: { value: '99' } });
      pick(container, 'request-start-date', '10/06/2026');
      pick(container, 'request-end-date', '14/06/2026');

      fireEvent.click(screen.getByRole('button', { name: 'Borrow' }));

      await waitFor(() => expect(sentBody('POST')).toBeTruthy());
      expect(sentBody('POST').quantity).toBe(6);
    });

    test('a thing with one unit sends no quantity at all', async () => {
      thing = { ...LOAN, units: 1, units_free_today: null };
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      pick(container, 'request-start-date', '10/06/2026');
      pick(container, 'request-end-date', '14/06/2026');

      fireEvent.click(screen.getByRole('button', { name: 'Borrow' }));

      await waitFor(() => expect(sentBody('POST')).toBeTruthy());
      expect(sentBody('POST')).not.toHaveProperty('quantity');
    });
  });

  describe('the calendar', () => {
    test('is asked as a member is served it, with no quantity until it is more than one', async () => {
      setApi();
      renderRequest();
      await screen.findByText(/Arduino kit/);

      await waitFor(() =>
        expect(calendarUrls()).toEqual(['/api/v1/things/LOAN01/calendar/?for=request'])
      );
    });

    test('is asked again with the quantity when it changes', async () => {
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);

      fireEvent.change(quantityInput(container), { target: { value: '3' } });

      await waitFor(() =>
        expect(calendarUrls()).toContain('/api/v1/things/LOAN01/calendar/?for=request&quantity=3')
      );
    });

    test('and back to none when it goes back to one', async () => {
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      fireEvent.change(quantityInput(container), { target: { value: '3' } });
      await waitFor(() => expect(calendarUrls()).toHaveLength(2));

      fireEvent.change(quantityInput(container), { target: { value: '1' } });

      await waitFor(() => expect(calendarUrls()).toHaveLength(3));
      expect(calendarUrls()[2]).toBe('/api/v1/things/LOAN01/calendar/?for=request');
    });

    test('the days it comes back as taken are greyed out in the pickup picker', async () => {
      setApi({
        calendarFor: (url) =>
          url.includes('quantity=3')
            ? [{ start_date: '2026-06-10', end_date: '2026-06-12', status: 'ACCEPTED' }]
            : [],
      });
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      fireEvent.change(quantityInput(container), { target: { value: '3' } });
      await waitFor(() => expect(calendarUrls()).toHaveLength(2));
      await settle(apiFetch);

      fireEvent.click(screen.getAllByRole('button', { name: 'Choose date' })[0]);
      await waitFor(() => expect(document.querySelector('[data-date]')).toBeTruthy());

      // The days it is served as taken are out; the day it is back (the 12th) is open.
      expect(document.querySelector('[data-date="2026-06-10"]').getAttribute('aria-disabled')).toBe(
        'true'
      );
      expect(document.querySelector('[data-date="2026-06-11"]').getAttribute('aria-disabled')).toBe(
        'true'
      );
      expect(document.querySelector('[data-date="2026-06-12"]').tagName).toBe('BUTTON');
    });

    test('the dates chosen are kept if they are still free for that many', async () => {
      setApi({ calendarFor: () => [] });
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      pick(container, 'request-start-date', '10/06/2026');
      pick(container, 'request-end-date', '14/06/2026');

      fireEvent.change(quantityInput(container), { target: { value: '3' } });
      await waitFor(() => expect(calendarUrls()).toHaveLength(2));
      await settle(apiFetch);

      expect(container.querySelector('#request-start-date')).toHaveValue('10/06/2026');
      expect(container.querySelector('#request-end-date')).toHaveValue('14/06/2026');
    });

    test('the dates chosen are emptied if they no longer fit', async () => {
      setApi({
        calendarFor: (url) =>
          url.includes('quantity=3')
            ? [{ start_date: '2026-06-12', end_date: '2026-06-13', status: 'ACCEPTED' }]
            : [],
      });
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      pick(container, 'request-start-date', '10/06/2026');
      pick(container, 'request-end-date', '14/06/2026');

      fireEvent.change(quantityInput(container), { target: { value: '3' } });

      await waitFor(() => expect(container.querySelector('#request-end-date')).toHaveValue(''));
      // The pickup is not over the busy day: it stays.
      expect(container.querySelector('#request-start-date')).toHaveValue('10/06/2026');
    });

    test('a pickup that lands on the busy days is emptied with it', async () => {
      setApi({
        calendarFor: (url) =>
          url.includes('quantity=3')
            ? [{ start_date: '2026-06-10', end_date: '2026-06-11', status: 'ACCEPTED' }]
            : [],
      });
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      pick(container, 'request-start-date', '10/06/2026');
      pick(container, 'request-end-date', '14/06/2026');

      fireEvent.change(quantityInput(container), { target: { value: '3' } });

      await waitFor(() => expect(container.querySelector('#request-start-date')).toHaveValue(''));
      expect(container.querySelector('#request-end-date')).toHaveValue('');
    });

    test('with fixed lengths the pickup is emptied when it no longer fits', async () => {
      thing = { ...LOAN, rental_durations: [7] };
      setApi({
        calendarFor: (url) =>
          url.includes('quantity=3')
            ? [{ start_date: '2026-06-12', end_date: '2026-06-13', status: 'ACCEPTED' }]
            : [],
      });
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      pick(container, 'request-pickup-date', '10/06/2026');

      fireEvent.change(quantityInput(container), { target: { value: '3' } });

      await waitFor(() => expect(container.querySelector('#request-pickup-date')).toHaveValue(''));
    });
  });

  describe('the totals', () => {
    test('with one, the price and the deposit are as they were', async () => {
      setApi();
      renderRequest();
      await screen.findByText(/Arduino kit/);

      expect(screen.getByText(en.request.priceLabel)).toBeInTheDocument();
      expect(screen.getByText('5.00 EUR', { exact: false })).toBeInTheDocument();
      expect(screen.getByText(en.thingPage.depositLabel)).toBeInTheDocument();
      expect(screen.queryByText(/×/)).toBeNull();
    });

    test('with several, both are per unit and the total is shown', async () => {
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);

      fireEvent.change(quantityInput(container), { target: { value: '6' } });

      expect(await screen.findByText('Price: 6 × 5.00 EUR = 30.00 EUR')).toBeInTheDocument();
      expect(screen.getByText(/Deposit: 6 × 20.00 € = 120.00 €/)).toBeInTheDocument();
      // The price label is the sentence's own now, not a second line.
      expect(screen.queryByText(en.request.priceLabel)).toBeNull();
    });

    test('a thing with no deposit shows no deposit line, with any quantity', async () => {
      thing = { ...LOAN, deposit: null };
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      fireEvent.change(quantityInput(container), { target: { value: '2' } });

      await screen.findByText('Price: 2 × 5.00 EUR = 10.00 EUR');
      expect(screen.queryByText(/Deposit/)).toBeNull();
    });

    test('a free thing has no price line, with any quantity', async () => {
      thing = { ...LOAN, fee: null };
      setApi();
      const { container } = renderRequest();
      await screen.findByText(/Arduino kit/);
      fireEvent.change(quantityInput(container), { target: { value: '2' } });

      await screen.findByText(/Deposit: 2 × 20.00 € = 40.00 €/);
      expect(screen.queryByText(/Price/)).toBeNull();
    });
  });

  describe('the refusals', () => {
    const ask = async (container) => {
      await screen.findByText(/Arduino kit/);
      fireEvent.change(quantityInput(container), { target: { value: '3' } });
      pick(container, 'request-start-date', '10/06/2026');
      pick(container, 'request-end-date', '14/06/2026');
      fireEvent.click(screen.getByRole('button', { name: 'Borrow' }));
    };

    test('not enough units', async () => {
      setApi({
        post: mockResponse(
          {
            error: "There aren't 3 free on those dates.",
            code: 'not_enough_units',
            params: { count: 3 },
          },
          false,
          409
        ),
      });
      const { container } = renderRequest();
      await ask(container);

      expect(await screen.findByText("There aren't 3 free on those dates.")).toBeInTheDocument();
      expect(screen.queryByText(en.request.dateOverlap)).toBeNull();
    });

    test('one request per person', async () => {
      setApi({
        post: mockResponse({ error: 'x', code: 'loan_one_per_person' }, false, 409),
      });
      const { container } = renderRequest();
      await ask(container);

      expect(await screen.findByText(en.requestErrors.loan_one_per_person)).toBeInTheDocument();
      expect(screen.queryByText(en.request.dateOverlap)).toBeNull();
    });

    test('a quantity out of range', async () => {
      setApi({
        post: mockResponse(
          { error: 'x', code: 'quantity_invalid', params: { max: 6 } },
          false,
          400
        ),
      });
      const { container } = renderRequest();
      await ask(container);

      expect(await screen.findByText('Ask for between 1 and 6.')).toBeInTheDocument();
    });
  });

  describe('how many are free today', () => {
    test('the availability notice says it, next to what it always said', async () => {
      setApi();
      renderRequest();
      await screen.findByText(/Arduino kit/);

      expect(screen.getByText(en.request.availableToday)).toBeInTheDocument();
      expect(screen.getByText('Available today: 4 of 6')).toBeInTheDocument();
    });

    test.each([
      ['none free', { units_free_today: 0, available_today: false }],
      ['not said', { units_free_today: null }],
      ['one unit', { units: 1, units_free_today: null }],
    ])('and says nothing of it with %s', async (_, extra) => {
      thing = { ...LOAN, ...extra };
      setApi();
      renderRequest();
      await screen.findByText(/Arduino kit/);

      expect(screen.queryByText(/of 6/)).toBeNull();
    });
  });

  test('axe finds nothing wrong with the page', async () => {
    setApi();
    const { container } = renderRequest();
    await screen.findByText(/Arduino kit/);

    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('ThingInfoRows — how many are free today', () => {
  test('says it for a loan with several, beside the units row', () => {
    render(
      <ThingInfoRows thing={{ type: 'LEND_THING', units: 6, units_free_today: 4 }} isDateBased />
    );

    expect(screen.getByText('6 units')).toBeInTheDocument();
    expect(screen.getByText('Available today: 4 of 6')).toBeInTheDocument();
  });

  test.each([
    ['none free', { units: 6, units_free_today: 0 }],
    ['not said', { units: 6, units_free_today: null }],
    ['one unit', { units: 1, units_free_today: null }],
  ])('has no such row with %s', (_, extra) => {
    render(<ThingInfoRows thing={{ type: 'LEND_THING', ...extra }} isDateBased />);

    expect(screen.queryByText(/of \d/)).toBeNull();
  });

  test('is worded in the language on screen', () => {
    expect(within(document.body).queryByText(/Disponibles/)).toBeNull();
  });
});
