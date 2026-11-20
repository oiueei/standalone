import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import { axe, toHaveNoViolations } from 'jest-axe';
import en from '../i18n/locales/en.json';
import declarePalette from './declarePalette';
import { requestPageReady } from './requestPageReady';

expect.extend(toHaveNoViolations);
window.scrollTo = vi.fn();

// The real error readers are kept: a refused field is worded from `requestErrors.<code>`.
vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import RequestThingPage from '../pages/RequestThingPage';

/**
 * A library may ask whoever borrows for a full name, an address, a phone and an identity
 * document. When it does, the request page asks for them after the dates and before the
 * deposit, all four required, and says so in the field when the server refuses one. When it
 * does not, the page is what it always was. Nothing is kept in the browser.
 */
const LEND_THING = {
  code: 'LEND01',
  type: 'LEND_THING',
  headline: 'Ladder',
  fee: null,
  deposit: '20.00',
  collection_code: 'COL001',
  collection_lending_asks_contact: true,
  available_today: true,
  next_available: null,
};

const DETAILS = {
  full_name: 'Laura Pérez Gómez',
  address: 'C/ de la Fusteria 12, 3r 2a\n08003 Barcelona',
  phone: '+34 600 000 000',
  identity_document: '12345678Z',
};

const res = (data, status = 200) => ({
  ok: status < 400,
  status,
  json: () => Promise.resolve(data),
});

function setApi(thing, post = res({ booking_code: 'B1' }, 201)) {
  apiFetch.mockImplementation((url, opts = {}) => {
    if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
      return Promise.resolve(post);
    }
    if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(res([]));
    if (/\/things\/[^/]+\/(\?.*)?$/.test(url)) return Promise.resolve(res(thing));
    return Promise.resolve(res({}));
  });
}

function renderPage(thing) {
  return render(
    <MemoryRouter
      initialEntries={[{ pathname: `/collections/COL001/things/${thing.code}/request`, state: {} }]}
    >
      <Routes>
        <Route path="/collections/:code/things/:thingCode/request" element={<RequestThingPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

const pageReady = (title = /Request: Ladder/) => requestPageReady(apiFetch, title);

const typeInto = (container, selector, display) => {
  const input = container.querySelector(selector);
  fireEvent.change(input, { target: { value: display } });
  fireEvent.blur(input);
};
const dates = (container) => {
  typeInto(container, '#request-start-date', '06/06/2026');
  typeInto(container, '#request-end-date', '08/06/2026');
};

const FIELDS = {
  full_name: () => screen.getByLabelText(/^Full name/),
  address: () => screen.getByLabelText(/^Address/),
  phone: () => screen.getByLabelText(/^Phone/),
  identity_document: () => screen.getByLabelText(/^Identity document/),
};
const fill = (details = DETAILS) => {
  for (const [field, value] of Object.entries(details)) {
    fireEvent.change(FIELDS[field](), { target: { value } });
  }
};
// HDS ties a field's error to it through `aria-describedby`, not `aria-invalid`.
const errorOf = (field) => FIELDS[field]().getAttribute('aria-describedby') || '';
const hasError = (field) => /-error/.test(errorOf(field));
const borrow = () => screen.getByRole('button', { name: 'Borrow' });
const posted = () =>
  apiFetch.mock.calls.find(([url, o]) => /\/request\/$/.test(url) && o?.method === 'POST');

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
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 5, 1, 12, 0, 0));
});
afterEach(() => vi.useRealTimers());

describe('RequestThingPage — a library that asks for contact details', () => {
  test('says why, then asks for the four, each required, with the right autocomplete', async () => {
    setApi(LEND_THING);
    renderPage(LEND_THING);
    await pageReady();

    expect(screen.getByText(en.lendingContact.intro)).toBeInTheDocument();
    for (const field of Object.values(FIELDS)) expect(field()).toBeRequired();
    expect(FIELDS.full_name()).toHaveAttribute('autocomplete', 'name');
    expect(FIELDS.address().tagName).toBe('TEXTAREA');
    expect(FIELDS.address()).toHaveAttribute('autocomplete', 'street-address');
    expect(FIELDS.phone()).toHaveAttribute('type', 'tel');
    expect(FIELDS.phone()).toHaveAttribute('autocomplete', 'tel');
    // No browser memory for an identity document.
    expect(FIELDS.identity_document()).toHaveAttribute('autocomplete', 'off');
    expect(screen.getByText(en.lendingContact.fullNameHelp)).toBeInTheDocument();
    expect(screen.getByText(en.lendingContact.addressHelp)).toBeInTheDocument();
    expect(screen.getByText(en.lendingContact.identityDocumentHelp)).toBeInTheDocument();
  });

  test('comes after the dates and before the deposit', async () => {
    setApi(LEND_THING);
    const { container } = renderPage(LEND_THING);
    await pageReady();

    const endDate = container.querySelector('#request-end-date');
    const intro = screen.getByText(en.lendingContact.intro);
    const deposit = screen.getByText(/Deposit/);
    const follows = (a, b) => a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING;
    expect(follows(endDate, intro)).toBeTruthy();
    expect(follows(intro, FIELDS.full_name())).toBeTruthy();
    expect(follows(FIELDS.identity_document(), deposit)).toBeTruthy();
  });

  test('the button waits until all four are there', async () => {
    setApi(LEND_THING);
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    expect(borrow()).toBeDisabled();

    for (const field of Object.keys(DETAILS)) {
      fireEvent.change(FIELDS[field](), { target: { value: DETAILS[field] } });
      if (field !== 'identity_document') expect(borrow()).toBeDisabled();
    }

    expect(borrow()).toBeEnabled();
  });

  test('a detail of only spaces is still missing', async () => {
    setApi(LEND_THING);
    renderPage(LEND_THING);
    await pageReady();
    fill({ ...DETAILS, phone: '   ' });

    expect(borrow()).toBeDisabled();
  });

  test('the request carries the four, trimmed, beside the dates and the group', async () => {
    setApi(LEND_THING);
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    fill(Object.fromEntries(Object.entries(DETAILS).map(([k, v]) => [k, `  ${v}  `])));

    fireEvent.click(borrow());

    await waitFor(() => expect(posted()).toBeTruthy());
    expect(JSON.parse(posted()[1].body)).toEqual({
      start_date: '2026-06-06',
      end_date: '2026-06-08',
      collection_code: 'COL001',
      lending_contact: DETAILS,
    });
  });

  test('a loan with fixed lengths sends them too', async () => {
    const fixed = { ...LEND_THING, rental_durations: [7], rental_weekdays: [2] };
    setApi(fixed);
    const { container } = renderPage(fixed);
    await screen.findByRole('combobox', { name: /Rental length/ });
    await waitFor(() => expect(container.querySelector('#request-pickup-date')).not.toBeDisabled());
    typeInto(container, '#request-pickup-date', '03/06/2026'); // a Wednesday
    fill();

    fireEvent.click(borrow());

    await waitFor(() => expect(posted()).toBeTruthy());
    expect(JSON.parse(posted()[1].body).lending_contact).toEqual(DETAILS);
  });

  test('a refused detail is said in its own field, in the reader’s language, and not in a toast', async () => {
    setApi(
      LEND_THING,
      res(
        {
          lending_contact: { phone: ['Enter a phone number'] },
          code: 'lending_contact_invalid',
        },
        400
      )
    );
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    fill();

    fireEvent.click(borrow());

    expect(await screen.findByText(en.requestErrors.lending_contact_invalid)).toBeInTheDocument();
    expect(hasError('phone')).toBe(true);
    expect(FIELDS.phone()).toHaveAccessibleDescription(en.requestErrors.lending_contact_invalid);
    expect(hasError('full_name')).toBe(false);
    expect(hasError('address')).toBe(false);
    expect(hasError('identity_document')).toBe(false);
    expect(screen.queryByRole('alert')).toBeNull();
    expect(screen.getAllByText(en.requestErrors.lending_contact_invalid)).toHaveLength(1);
  });

  test('a missing detail says it is missing', async () => {
    setApi(
      LEND_THING,
      res(
        {
          lending_contact: { identity_document: ['This field is required.'] },
          code: 'lending_contact_required',
        },
        400
      )
    );
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    fill();

    fireEvent.click(borrow());

    expect(await screen.findByText(en.requestErrors.lending_contact_required)).toBeInTheDocument();
    expect(hasError('identity_document')).toBe(true);
  });

  test('typing in a refused field clears its error', async () => {
    setApi(
      LEND_THING,
      res({ lending_contact: { phone: ['x'] }, code: 'lending_contact_invalid' }, 400)
    );
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    fill();
    fireEvent.click(borrow());
    await screen.findByText(en.requestErrors.lending_contact_invalid);

    fireEvent.change(FIELDS.phone(), { target: { value: '600123456' } });

    expect(screen.queryByText(en.requestErrors.lending_contact_invalid)).toBeNull();
    expect(hasError('phone')).toBe(false);
  });

  test('nothing is kept in the browser', async () => {
    const write = vi.spyOn(localStorage, 'setItem');
    setApi(LEND_THING);
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    fill();
    fireEvent.click(borrow());
    await waitFor(() => expect(posted()).toBeTruthy());

    expect(write).not.toHaveBeenCalled();
    expect(sessionStorage.length).toBe(0);
    write.mockRestore();
  });

  test('the page with the block has no axe violations', async () => {
    setApi(LEND_THING);
    const { container } = renderPage(LEND_THING);
    await pageReady();

    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

describe('RequestThingPage — a library that does not ask', () => {
  const plain = { ...LEND_THING, collection_lending_asks_contact: false };

  test('the page has none of it and asking is as before', async () => {
    setApi(plain);
    const { container } = renderPage(plain);
    await pageReady();
    dates(container);

    expect(screen.queryByText(en.lendingContact.intro)).toBeNull();
    expect(screen.queryByLabelText(/^Identity document/)).toBeNull();
    expect(borrow()).toBeEnabled();
    fireEvent.click(borrow());
    await waitFor(() => expect(posted()).toBeTruthy());
    expect(JSON.parse(posted()[1].body)).not.toHaveProperty('lending_contact');
  });

  test('a payload from before the field existed asks for nothing', async () => {
    const { collection_lending_asks_contact: _gone, ...older } = LEND_THING;
    setApi(older);
    renderPage(older);
    await pageReady();

    expect(screen.queryByText(en.lendingContact.intro)).toBeNull();
  });

  test('a reservation never shows the block, whatever the flag says', async () => {
    const space = {
      code: 'RSV01',
      type: 'RESERVE_THING',
      headline: 'Sala',
      fee: null,
      collection_code: 'COL001',
      collection_lending_asks_contact: true,
      rental_weekdays: [],
      reservation_max_days: 1,
      available_today: true,
      next_available: null,
    };
    setApi(space);
    renderPage(space);
    await pageReady(/Reserve: Sala|Sala/);

    expect(screen.queryByText(en.lendingContact.intro)).toBeNull();
    expect(within(document.body).queryByLabelText(/^Identity document/)).toBeNull();
  });
});
