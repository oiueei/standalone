import { render, screen, fireEvent } from '@testing-library/react';
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
import RequestThingPage from '../pages/RequestThingPage';

/**
 * A shed can ask, on the request page, for an optional contact phone. The field exists
 * only when the thing says its collection asks, is never required, and is sent only when
 * it holds something. The texts are fixed letter by letter.
 */
const LABEL = {
  es: '¿Puedes dejarnos un teléfono de contacto? Es por si pasa algo inesperado con lo que has reservado o con la reserva. Lo borraremos el día después de la reserva.',
  ca: "Ens pots deixar un telèfon de contacte? És per si passa alguna cosa inesperada amb el que has reservat o amb la reserva. L'esborrarem l'endemà de la reserva.",
  en: "Could you leave us a contact phone number? It's in case something unexpected happens with what you've booked or with the booking. We'll delete it the day after the booking.",
};

const mockResponse = (data, ok = true, status = ok ? 200 : 400) => ({
  ok,
  status,
  json: () => Promise.resolve(data),
});

const SHED_THING = {
  code: 'RSV01',
  type: 'RESERVE_THING',
  headline: 'Lathe',
  fee: null,
  collection_code: 'COL001',
  rental_weekdays: [],
  reservation_max_days: 1,
  available_today: true,
  next_available: null,
  collection_reservation_asks_phone: true,
};

function setApi(thing, post = mockResponse({ booking_code: 'B1' })) {
  apiFetch.mockImplementation((url, opts = {}) => {
    if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
      return Promise.resolve(post);
    }
    if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
    if (/\/things\/[^/]+\/(\?.*)?$/.test(url)) return Promise.resolve(mockResponse(thing));
    return Promise.resolve(mockResponse({}));
  });
}

function renderPage() {
  return render(
    <MemoryRouter
      initialEntries={[{ pathname: '/collections/COL001/things/RSV01/request', state: {} }]}
    >
      <Routes>
        <Route path="/collections/:code/things/:thingCode/request" element={<RequestThingPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

function typePickup(container, display) {
  const input = container.querySelector('#reservation-pickup-date');
  fireEvent.change(input, { target: { value: display } });
  fireEvent.blur(input);
}

const sentBody = () => {
  const call = apiFetch.mock.calls.find(
    ([url, opts]) => /\/request\//.test(url) && opts?.method === 'POST'
  );
  return call ? JSON.parse(call[1].body) : null;
};

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  localStorage.setItem('koro', 'basic');
  vi.clearAllMocks();
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 5, 1, 12, 0, 0));
});

afterEach(() => {
  vi.useRealTimers();
});

describe('the words of the phone field and of the switch', () => {
  test('the request page label is fixed in the three languages', () => {
    expect(en.reservation.phoneLabel).toBe(LABEL.en);
    expect(es.reservation.phoneLabel).toBe(LABEL.es);
    expect(ca.reservation.phoneLabel).toBe(LABEL.ca);
  });

  test('the collection switch is fixed in the three languages', () => {
    expect(es.reservation.asksPhoneFull).toBe(
      'Pedir un teléfono de contacto al reservar (opcional)'
    );
    expect(ca.reservation.asksPhoneFull).toBe(
      'Demanar un telèfon de contacte en reservar (opcional)'
    );
    expect(en.reservation.asksPhoneFull).toBe('Ask for a contact phone when booking (optional)');
  });
});

const HOURLY_SHED_THING = {
  ...SHED_THING,
  reservation_unit: 'HOUR',
  reservation_horizon_days: 90,
  reservation_min_minutes: 60,
  reservation_max_minutes: 180,
  opening_hours: { 0: [['10:00', '14:00']] },
};

describe('RequestThingPage — the phone comes before the project note', () => {
  const NOTE = en.reservation.projectNoteLabel;
  const precedes = (a, b) =>
    Boolean(a.compareDocumentPosition(b) & Node.DOCUMENT_POSITION_FOLLOWING);

  test.each([
    ['by the day', SHED_THING],
    ['by the hour', HOURLY_SHED_THING],
  ])('%s: the phone field is above the note', async (_unit, thing) => {
    setApi(thing);
    renderPage();
    await screen.findByText(/Reserve Lathe/);

    const phone = screen.getByLabelText(LABEL.en);
    const note = screen.getByLabelText(NOTE);

    expect(precedes(phone, note)).toBe(true);
    expect(precedes(note, phone)).toBe(false);
  });

  test.each([
    ['by the day', SHED_THING, '#reservation-project-note-phone'],
    ['by the hour', HOURLY_SHED_THING, '#reservation-project-note-hourly-phone'],
  ])('%s: the phone keeps its id, derived from the note’s', async (_unit, thing, selector) => {
    setApi(thing);
    const { container } = renderPage();
    await screen.findByText(/Reserve Lathe/);

    expect(container.querySelector(selector)).toBe(screen.getByLabelText(LABEL.en));
  });

  test.each([
    ['by the day', SHED_THING],
    ['by the hour', HOURLY_SHED_THING],
  ])('%s: with no phone asked, the note is there alone', async (_unit, thing) => {
    setApi({ ...thing, collection_reservation_asks_phone: false });
    renderPage();
    await screen.findByText(/Reserve Lathe/);

    expect(screen.getByLabelText(NOTE)).toBeInTheDocument();
    expect(screen.queryByLabelText(LABEL.en)).toBeNull();
  });
});

describe('RequestThingPage — the optional contact phone', () => {
  test('it is a telephone field, optional, when the collection asks', async () => {
    setApi(SHED_THING);
    renderPage();
    await screen.findByText(/Reserve Lathe/);

    const field = screen.getByLabelText(LABEL.en);
    expect(field).toHaveAttribute('type', 'tel');
    expect(field).toHaveAttribute('autocomplete', 'tel');
    expect(field).toHaveAttribute('maxlength', '32');
    expect(field).not.toBeRequired();
  });

  test('it is not there when the collection does not ask', async () => {
    setApi({ ...SHED_THING, collection_reservation_asks_phone: false });
    renderPage();
    await screen.findByText(/Reserve Lathe/);

    expect(screen.queryByLabelText(LABEL.en)).toBeNull();
  });

  test('a number typed is sent, trimmed, with the rest of the reservation', async () => {
    setApi(SHED_THING);
    const { container } = renderPage();
    await screen.findByText(/Reserve Lathe/);

    fireEvent.change(screen.getByLabelText(LABEL.en), { target: { value: '  600 123 456 ' } });
    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    await screen.findByText(/Your reservation is confirmed/);
    expect(sentBody()).toMatchObject({
      start_date: '2026-06-03',
      duration_days: 1,
      contact_phone: '600 123 456',
    });
  });

  test('left empty, the key is not sent at all and the reservation goes through', async () => {
    setApi(SHED_THING);
    const { container } = renderPage();
    await screen.findByText(/Reserve Lathe/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    await screen.findByText(/Your reservation is confirmed/);
    expect(sentBody()).not.toHaveProperty('contact_phone');
  });

  test('only spaces count as empty', async () => {
    setApi(SHED_THING);
    const { container } = renderPage();
    await screen.findByText(/Reserve Lathe/);

    fireEvent.change(screen.getByLabelText(LABEL.en), { target: { value: '   ' } });
    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    await screen.findByText(/Your reservation is confirmed/);
    expect(sentBody()).not.toHaveProperty('contact_phone');
  });

  test('a refusal of the number is said in the field and sends nobody away', async () => {
    setApi(
      SHED_THING,
      mockResponse({ contact_phone: ['Enter a phone number: digits…'] }, false, 400)
    );
    const { container } = renderPage();
    await screen.findByText(/Reserve Lathe/);

    fireEvent.change(screen.getByLabelText(LABEL.en), { target: { value: '12345' } });
    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    const message = await screen.findByText(en.reservation.phoneInvalid);
    // The error belongs to the field: HDS ties it to the input by `aria-describedby`.
    const describedBy = screen.getByLabelText(LABEL.en).getAttribute('aria-describedby');
    expect(describedBy.split(' ')).toContain(message.closest('[id]').id);
    expect(screen.queryByText(/Your reservation is confirmed/)).toBeNull();
  });

  test('typing again clears the field error', async () => {
    setApi(
      SHED_THING,
      mockResponse({ contact_phone: ['Enter a phone number: digits…'] }, false, 400)
    );
    const { container } = renderPage();
    await screen.findByText(/Reserve Lathe/);
    fireEvent.change(screen.getByLabelText(LABEL.en), { target: { value: '12345' } });
    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));
    await screen.findByText(en.reservation.phoneInvalid);

    fireEvent.change(screen.getByLabelText(LABEL.en), { target: { value: '123456' } });

    expect(screen.queryByText(en.reservation.phoneInvalid)).toBeNull();
  });

  test('axe finds nothing wrong with the page that asks', async () => {
    setApi(SHED_THING);
    const { container } = renderPage();
    await screen.findByLabelText(LABEL.en);

    expect(await axe(container)).toHaveNoViolations();
  });
});
