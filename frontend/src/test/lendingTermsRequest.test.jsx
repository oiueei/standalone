import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import { axe, toHaveNoViolations } from 'jest-axe';
import en from '../i18n/locales/en.json';
import declarePalette from './declarePalette';
import { settle } from './settle';
import { requestPageReady } from './requestPageReady';

expect.extend(toHaveNoViolations);
window.scrollTo = vi.fn();

// The real error readers are kept: a refused box is worded from `requestErrors.<code>`.
vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import RequestThingPage from '../pages/RequestThingPage';

/**
 * A library may ask whoever borrows to accept its terms, which are its welcome document.
 * When it does (and still has the document), the request page shows a required box with a
 * link to the PDF, right after the line about what whoever runs the thing is sent and
 * before the button, which waits for the tick. The request carries `accepts_terms`, and a
 * refusal is said on the box. When the library does not ask, the page is what it was.
 * Nothing is kept in the browser. (jsdom paints nothing: where the box sits on screen is
 * for a person to see.)
 */
const PDF = 'https://files.test/oiueei/documents/terms.pdf';
const LEND_THING = {
  code: 'LEND01',
  type: 'LEND_THING',
  headline: 'Ladder',
  fee: null,
  deposit: null,
  collection_code: 'COL001',
  collection_lending_asks_terms: true,
  collection_menu: { is_member: true, welcome_doc_url: PDF },
  available_today: true,
  next_available: null,
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

const box = () =>
  screen.getByRole('checkbox', { name: /I have read and accept the lending terms/ });
const maybeBox = () => screen.queryByRole('checkbox');
const link = () => screen.getByRole('link', { name: /Read them/ });
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

describe('RequestThingPage — a library that asks borrowers to accept its terms', () => {
  test('shows a required box with the label, and a link to the document', async () => {
    setApi(LEND_THING);
    renderPage(LEND_THING);
    await pageReady();

    expect(box()).toBeRequired();
    expect(box()).not.toBeChecked();
    expect(screen.getByText(/I have read and accept the lending terms/)).toBeInTheDocument();
  });

  test('comes after what whoever runs the thing is sent and before the button', async () => {
    setApi(LEND_THING);
    renderPage(LEND_THING);
    await pageReady();

    const shared = screen.getByText(en.request.contactShared);
    const follows = (a, b) => a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING;
    expect(follows(shared, box())).toBeTruthy();
    expect(follows(box(), borrow())).toBeTruthy();
  });

  test('the link goes to the document in another tab, and says so to a screen reader', async () => {
    setApi(LEND_THING);
    renderPage(LEND_THING);
    await pageReady();

    expect(link()).toHaveAttribute('href', PDF);
    expect(link()).toHaveAttribute('target', '_blank');
    expect(link().getAttribute('rel')).toMatch(/noopener/);
    expect(link().getAttribute('rel')).toMatch(/noreferrer/);
    expect(link()).toHaveAccessibleName(`${en.lendingTerms.read}. ${en.common.opensInNewTab}`);
  });

  test('following the link does not tick the box', async () => {
    setApi(LEND_THING);
    renderPage(LEND_THING);
    await pageReady();

    fireEvent.click(link());

    expect(box()).not.toBeChecked();
    fireEvent.click(box());
    expect(box()).toBeChecked();
    fireEvent.click(link());
    expect(box()).toBeChecked();
  });

  test('the button waits for the tick', async () => {
    setApi(LEND_THING);
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);

    expect(borrow()).toBeDisabled();
    fireEvent.click(box());
    expect(borrow()).toBeEnabled();
    fireEvent.click(box());
    expect(borrow()).toBeDisabled();
  });

  test('when contact details are asked too, the button needs both', async () => {
    const both = { ...LEND_THING, collection_lending_asks_contact: true };
    setApi(both);
    const { container } = renderPage(both);
    await pageReady();
    dates(container);

    fireEvent.click(box());
    expect(borrow()).toBeDisabled();
    for (const [label, value] of [
      [/^Full name/, 'Laura Pérez'],
      [/^Address/, 'C/ Fusteria 12'],
      [/^Phone/, '600000000'],
      [/^Identity document/, '12345678Z'],
    ]) {
      fireEvent.change(screen.getByLabelText(label), { target: { value } });
    }
    expect(borrow()).toBeEnabled();
    fireEvent.click(box());
    expect(borrow()).toBeDisabled();
  });

  test('the request says it was accepted, beside the dates and the group', async () => {
    setApi(LEND_THING);
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    fireEvent.click(box());

    fireEvent.click(borrow());

    await waitFor(() => expect(posted()).toBeTruthy());
    expect(JSON.parse(posted()[1].body)).toEqual({
      start_date: '2026-06-06',
      end_date: '2026-06-08',
      collection_code: 'COL001',
      accepts_terms: true,
    });
  });

  test('a loan with fixed lengths says it too', async () => {
    const fixed = { ...LEND_THING, rental_durations: [7], rental_weekdays: [2] };
    setApi(fixed);
    const { container } = renderPage(fixed);
    await screen.findByRole('combobox', { name: /Rental length/ });
    await waitFor(() => expect(container.querySelector('#request-pickup-date')).not.toBeDisabled());
    typeInto(container, '#request-pickup-date', '03/06/2026'); // a Wednesday
    fireEvent.click(box());

    fireEvent.click(borrow());

    await waitFor(() => expect(posted()).toBeTruthy());
    expect(JSON.parse(posted()[1].body).accepts_terms).toBe(true);
  });

  test('a refusal is said on the box, in the reader’s language, and not in a toast', async () => {
    setApi(
      LEND_THING,
      res({ accepts_terms: ['Accept the lending terms to borrow.'], code: 'terms_required' }, 400)
    );
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    fireEvent.click(box());

    fireEvent.click(borrow());

    expect(await screen.findByText(en.requestErrors.terms_required)).toBeInTheDocument();
    expect(screen.getAllByText(en.requestErrors.terms_required)).toHaveLength(1);
    expect(box()).toHaveAccessibleDescription(en.requestErrors.terms_required);
    expect(screen.queryByRole('alert')).toBeNull();
  });

  test('ticking the box again clears what the server said about it', async () => {
    setApi(LEND_THING, res({ code: 'terms_required', accepts_terms: ['x'] }, 400));
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    fireEvent.click(box());
    fireEvent.click(borrow());
    await screen.findByText(en.requestErrors.terms_required);

    fireEvent.click(box()); // off
    fireEvent.click(box()); // on again

    expect(screen.queryByText(en.requestErrors.terms_required)).toBeNull();
  });

  test('keeps nothing in the browser', async () => {
    // The suite's storage is a plain object with no key listing, so what is watched is
    // every write the page makes to either store while the box is ticked and sent.
    const written = [vi.spyOn(localStorage, 'setItem'), vi.spyOn(sessionStorage, 'setItem')];
    setApi(LEND_THING);
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    fireEvent.click(box());
    fireEvent.click(borrow());
    await waitFor(() => expect(posted()).toBeTruthy());

    expect(written.flatMap((spy) => spy.mock.calls)).toEqual([]);
    expect(localStorage.getItem('accepts_terms')).toBeNull();
  });

  test('has no accessibility violations', async () => {
    setApi(LEND_THING);
    const { container } = renderPage(LEND_THING);
    await pageReady();

    expect(await axe(container)).toHaveNoViolations();
  });

  test('has none either with the refusal showing', async () => {
    setApi(LEND_THING, res({ code: 'terms_required', accepts_terms: ['x'] }, 400));
    const { container } = renderPage(LEND_THING);
    await pageReady();
    dates(container);
    fireEvent.click(box());
    fireEvent.click(borrow());
    await screen.findByText(en.requestErrors.terms_required);

    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('RequestThingPage — when no terms are asked', () => {
  test.each([
    ['the library does not ask', { collection_lending_asks_terms: false }],
    ['the flag is missing', { collection_lending_asks_terms: undefined }],
    [
      'there is no document to read',
      { collection_menu: { is_member: true, welcome_doc_url: null } },
    ],
    ['the page has no menu', { collection_menu: null }],
    ['it is a gift', { type: 'GIVE_THING' }],
    ['it is a reservation', { type: 'RESERVE_THING' }],
  ])('%s: there is no box', async (_name, override) => {
    const thing = { ...LEND_THING, ...override };
    setApi(thing);
    renderPage(thing);
    await screen.findByRole('heading', { level: 1 });
    await settle(apiFetch);

    expect(maybeBox()).toBeNull();
    expect(screen.queryByText(/lending terms/)).toBeNull();
  });

  test('a library that does not ask sends nothing about it, and the button is not held back', async () => {
    const thing = { ...LEND_THING, collection_lending_asks_terms: false };
    setApi(thing);
    const { container } = renderPage(thing);
    await pageReady();
    dates(container);

    expect(borrow()).toBeEnabled();
    fireEvent.click(borrow());

    await waitFor(() => expect(posted()).toBeTruthy());
    expect(JSON.parse(posted()[1].body)).not.toHaveProperty('accepts_terms');
  });

  test('a rental asks the same as a loan', async () => {
    const rent = { ...LEND_THING, type: 'RENT_THING' };
    setApi(rent);
    renderPage(rent);
    await pageReady();

    expect(box()).toBeRequired();
  });
});
