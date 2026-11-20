import { render, screen, fireEvent, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import i18n from 'i18next';
import es from '../i18n/locales/es.json';

window.scrollTo = vi.fn();

// The real error readers (apiErrorMessage & co.) are kept — they turn a coded
// refusal into the reader's language, which these tests read back.
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
import { requestPageReady } from './requestPageReady';
import InboxNotifications from '../components/InboxNotifications';

function mockResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

const RESERVE_THING = {
  code: 'RSV01',
  type: 'RESERVE_THING',
  headline: 'Sala polivalent',
  fee: '5.00',
  location: 'Planta 1',
  collection_code: 'COL001',
  rental_weekdays: [],
  reservation_max_days: 3,
  available_today: true,
  next_available: null,
};

function setApi({ thing = RESERVE_THING, calendar = [], postOk = true } = {}) {
  apiFetch.mockImplementation((url, opts = {}) => {
    if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse(calendar));
    if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
      return Promise.resolve(
        mockResponse({ message: 'Reservation confirmed', booking_code: 'B1' }, postOk)
      );
    }
    if (/\/things\/[^/]+\/(\?.*)?$/.test(url)) return Promise.resolve(mockResponse(thing));
    return Promise.resolve(mockResponse({}));
  });
}

function renderPage(pathname = '/collections/COL001/things/RSV01/request') {
  return render(
    <MemoryRouter initialEntries={[{ pathname, state: {} }]}>
      <Routes>
        <Route path="/collections/:code/things/:thingCode/request" element={<RequestThingPage />} />
        <Route path="/things/:thingCode/request" element={<RequestThingPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  localStorage.setItem('koro', 'basic');
  vi.clearAllMocks();
  vi.useFakeTimers({ toFake: ['Date'] });
  vi.setSystemTime(new Date(2026, 5, 1, 12, 0, 0)); // Mon 2026-06-01
  setApi();
});

afterEach(() => {
  vi.useRealTimers();
});

// One day cell of an open HDS date picker, which must be rendered: HDS draws an
// offered day as a <button> and a refused one as a <span aria-disabled="true">,
// so a missing cell proves nothing either way.
function pickerDay(iso) {
  const day = document.querySelector(`[data-date="${iso}"]`);
  expect(day, `the picker should show ${iso}`).not.toBeNull();
  return day;
}

function typePickup(container, display) {
  const input = container.querySelector('#reservation-pickup-date');
  fireEvent.change(input, { target: { value: display } });
  fireEvent.blur(input);
}

const reservePosts = () =>
  apiFetch.mock.calls.filter(([url, opts]) => /\/request\//.test(url) && opts?.method === 'POST');

describe('RequestThingPage — RESERVE_THING', () => {
  test('with max 1 day there is no duration select, and a project note field is shown', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);
    expect(screen.queryByRole('combobox', { name: /How many days/ })).toBeNull();
    expect(screen.getByLabelText(/What do you need it for/)).toBeInTheDocument();
  });

  test('with a one-day cap the date is labelled “Day”', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    const label = container.querySelector('label[for="reservation-pickup-date"]');
    expect(label.textContent).toMatch(/^Day\b/);
  });

  test('with a longer cap the date is labelled “From”', async () => {
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    const label = container.querySelector('label[for="reservation-pickup-date"]');
    expect(label.textContent).toMatch(/^From\b/);
  });

  test('with a longer cap the duration select is offered', async () => {
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);
    expect(screen.getByRole('combobox', { name: /How many days/ })).toBeInTheDocument();
  });

  test('the date picker stops at the collection horizon, not the fixed 90', async () => {
    // horizon 7 days from Mon 2026-06-01 → pickup on 2026-06-08 is the last day,
    // and the backend's reservation_violation now agrees (it judges the pickup
    // day, not the exclusive end_date — Collection.reservation_violation).
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1, reservation_horizon_days: 7 } });
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);
    fireEvent.click(screen.getByRole('button', { name: 'Choose date' }));
    await waitFor(() => expect(document.querySelector('[data-date]')).toBeTruthy());
    // 2026-06-05 is within the 7-day window — selectable
    expect(document.querySelector('[data-date="2026-06-05"]')?.tagName).toBe('BUTTON');
    // 2026-06-08 is exactly the horizon — still selectable (the off-by-one the
    // server used to reject on this very day).
    expect(document.querySelector('[data-date="2026-06-08"]')?.tagName).toBe('BUTTON');
    // 2026-06-09 is past it — on screen, and refused.
    expect(pickerDay('2026-06-09')).toHaveAttribute('aria-disabled', 'true');
  });

  test('the pickup field explains why some days are greyed out', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);
    expect(screen.getByText(/greyed out/i)).toBeInTheDocument();
  });

  test('a multi-day reservation shows the span it will book before you confirm', async () => {
    // Default RESERVE_THING: max 3 days, weekdays unrestricted. System time is
    // Mon 2026-06-01, so 03/06 is a Wednesday and free.
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    fireEvent.click(screen.getByRole('combobox', { name: /How many days/ }));
    fireEvent.click(await screen.findByRole('option', { name: '3 days' }));
    typePickup(container, '03/06/2026');

    // Three days from the 3rd covers the 3rd, 4th and 5th — the last day is
    // inclusive, and the reservation auto-confirms with no owner step to catch
    // a wrong end.
    expect(await screen.findByText('Reserved from 03/06/2026 to 05/06/2026.')).toBeInTheDocument();
  });

  test('a date past the collection horizon is rejected with the collection’s own limit', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1, reservation_horizon_days: 7 } });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '30/06/2026'); // well past today + 7 days
    expect(await screen.findByText(/between today and 7 days from now/i)).toBeInTheDocument();
  });

  test('submitting posts a duration + note and shows the confirmed message', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    fireEvent.change(screen.getByLabelText(/What do you need it for/), {
      target: { value: 'A screen-printing workshop.' },
    });
    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    await screen.findByText(/Your reservation is confirmed/);
    // A member who reserved joined nothing, so nothing says they did.
    expect(screen.queryByText(/you've joined/)).not.toBeInTheDocument();
    const postCall = apiFetch.mock.calls.find(
      ([url, opts]) => /\/request\//.test(url) && opts?.method === 'POST'
    );
    const body = JSON.parse(postCall[1].body);
    expect(body).toMatchObject({
      start_date: '2026-06-03',
      duration_days: 1,
      project_note: 'A screen-printing workshop.',
      collection_code: 'COL001',
    });
  });

  test('Reserve with no pickup date says so and sends nothing', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);
    expect(screen.queryByText('Start date is required.')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    expect(await screen.findByText('Start date is required.')).toBeInTheDocument();
    expect(reservePosts()).toHaveLength(0);
  });

  test('Reserve with no length chosen says so, leaves the pickup closed and sends nothing', async () => {
    // With a cap over one day the pickup picker waits for a length (the open days
    // depend on it), so a missing length is reached with a missing date too.
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);
    expect(screen.queryByText('Please choose a length')).toBeNull();
    expect(container.querySelector('#reservation-pickup-date')).toBeDisabled();

    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    expect(await screen.findAllByText('Please choose a length')).not.toHaveLength(0);
    expect(reservePosts()).toHaveLength(0);
  });

  test('the confirmation says back what was reserved and when — one day is one day', async () => {
    // A reservation confirms on the spot, so this notice is where a wrong day
    // would be caught. The server stores `end_date` as the day the space is free
    // again (the 4th here); the member reserved the 3rd, and only the 3rd.
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    const notice = (await screen.findByText(/Your reservation is confirmed/)).closest(
      '[role="region"], section, div'
    );
    expect(notice).toHaveTextContent('Sala polivalent');
    expect(notice).toHaveTextContent('03/06/2026');
    expect(notice).not.toHaveTextContent('04/06/2026');
  });

  test('a 403 (not a member) auto-joins the PUBLIC collection and completes the reservation, with no extra click', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    let joinCalled = false;
    let requestCalls = 0;
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/collections\/COL001\/join\//.test(url) && opts.method === 'POST') {
        joinCalled = true;
        return Promise.resolve(mockResponse({ message: 'Joined' }));
      }
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        requestCalls += 1;
        if (requestCalls === 1) {
          return Promise.resolve({
            ok: false,
            status: 403,
            json: () =>
              Promise.resolve({
                error: 'You need to be a member of this group to reserve.',
                code: 'not_a_member',
              }),
          });
        }
        return Promise.resolve(
          mockResponse({ message: 'Reservation confirmed', booking_code: 'B1' })
        );
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url))
        return Promise.resolve(mockResponse({ ...RESERVE_THING, reservation_max_days: 1 }));
      return Promise.resolve(mockResponse({}));
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    // one click, and it just works — no "not a member" text, no join button
    // ever shown, straight to the confirmation.
    expect(await screen.findByText(/Your reservation is confirmed/)).toBeInTheDocument();
    expect(joinCalled).toBe(true);
    expect(requestCalls).toBe(2); // the failed attempt, then the auto-retry
    expect(
      screen.queryByText('You need to be a member of this group to reserve.')
    ).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Join this group' })).not.toBeInTheDocument();
  });

  test('a failed auto-join falls back to the reason plus a manual retry button', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/collections\/COL001\/join\//.test(url) && opts.method === 'POST') {
        return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
      }
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        return Promise.resolve({
          ok: false,
          status: 403,
          json: () =>
            Promise.resolve({
              error: 'You need to be a member of this group to reserve.',
              code: 'not_a_member',
            }),
        });
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url))
        return Promise.resolve(mockResponse({ ...RESERVE_THING, reservation_max_days: 1 }));
      return Promise.resolve(mockResponse({}));
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    // the auto-join attempt failed silently in the background, so the reader
    // sees the original reason plus a way to try again themselves
    expect(
      await screen.findByText('You need to be a member of this group to reserve.')
    ).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Join this group' })).toBeInTheDocument();
    // In a wide row, so on a phone it is the width of the screen.
    expect(screen.getByRole('button', { name: 'Join this group' }).parentElement).toHaveClass(
      'button-row-wide'
    );
    expect(screen.queryByText(/Your reservation is confirmed/)).not.toBeInTheDocument();
  });

  test('the manual fallback button retries the join and the exact same reservation', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    let joinCalls = 0;
    let requestCalls = 0;
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/collections\/COL001\/join\//.test(url) && opts.method === 'POST') {
        joinCalls += 1;
        // fails the first (automatic) attempt, succeeds the second (manual)
        if (joinCalls === 1) {
          return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
        }
        return Promise.resolve(mockResponse({ message: 'Joined' }));
      }
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        requestCalls += 1;
        if (requestCalls === 1) {
          return Promise.resolve({
            ok: false,
            status: 403,
            json: () =>
              Promise.resolve({
                error: 'You need to be a member of this group to reserve.',
                code: 'not_a_member',
              }),
          });
        }
        return Promise.resolve(
          mockResponse({ message: 'Reservation confirmed', booking_code: 'B1' })
        );
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url))
        return Promise.resolve(mockResponse({ ...RESERVE_THING, reservation_max_days: 1 }));
      return Promise.resolve(mockResponse({}));
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));
    await screen.findByRole('button', { name: 'Join this group' });

    fireEvent.click(screen.getByRole('button', { name: 'Join this group' }));

    expect(await screen.findByText(/Your reservation is confirmed/)).toBeInTheDocument();
    expect(joinCalls).toBe(2);
    expect(requestCalls).toBe(2); // never re-typed — the form still says 03/06
  });

  test('a 403 without the not_a_member marker never auto-joins — it just shows the reason', async () => {
    // The thing going INACTIVE while this form was open, say: still a 403,
    // still carries an `error`, but not the one auto-join is for.
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    let joinCalled = false;
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/collections\/COL001\/join\//.test(url) && opts.method === 'POST') {
        joinCalled = true;
        return Promise.resolve(mockResponse({ message: 'Joined' }));
      }
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        return Promise.resolve({
          ok: false,
          status: 403,
          json: () => Promise.resolve({ error: 'Not authorized to request this thing' }),
        });
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url))
        return Promise.resolve(mockResponse({ ...RESERVE_THING, reservation_max_days: 1 }));
      return Promise.resolve(mockResponse({}));
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    expect(await screen.findByText('Not authorized to request this thing')).toBeInTheDocument();
    expect(joinCalled).toBe(false);
    expect(screen.queryByRole('button', { name: 'Join this group' })).not.toBeInTheDocument();
  });

  // A 403 `not_a_member` on every request, and a record of every join the page
  // attempts — for the two tests below about *which* collection gets joined.
  function notAMemberApi(joins) {
    apiFetch.mockImplementation((url, opts = {}) => {
      const join = /\/collections\/([^/]+)\/join\//.exec(url);
      if (join && opts.method === 'POST') {
        joins.push(join[1]);
        return Promise.resolve(mockResponse({ message: 'Joined' }));
      }
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        return Promise.resolve({
          ok: false,
          status: 403,
          json: () =>
            Promise.resolve({
              error: 'You need to be a member of this group to reserve.',
              code: 'not_a_member',
            }),
        });
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      // The server resolves the thing to its own collection (COL001) whatever
      // the route named: `?collection=` is ignored when it names a collection
      // the thing doesn't live in.
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url))
        return Promise.resolve(mockResponse({ ...RESERVE_THING, reservation_max_days: 1 }));
      return Promise.resolve(mockResponse({}));
    });
  }

  test('a route naming another collection never joins it — the reader is only told why', async () => {
    // The link someone could send: their own PUBLIC group in the path, a real
    // space's thing after it. Joining the path's collection handed that
    // group's curator the reader's email address on a single Reserve click.
    const joins = [];
    notAMemberApi(joins);
    const { container } = renderPage('/collections/EVIL01/things/RSV01/request');
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    expect(
      await screen.findByText('You need to be a member of this group to reserve.')
    ).toBeInTheDocument();
    expect(joins).toEqual([]);
    expect(screen.queryByRole('button', { name: 'Join this group' })).not.toBeInTheDocument();
  });

  test('after an auto-join the confirmation says which group the reader joined', async () => {
    const thing = {
      ...RESERVE_THING,
      reservation_max_days: 1,
      collection_headline: '{"es": "Taller del barrio", "en": "Neighbourhood workshop"}',
    };
    let requestCalls = 0;
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/collections\/COL001\/join\//.test(url) && opts.method === 'POST')
        return Promise.resolve(mockResponse({ message: 'Joined' }));
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        requestCalls += 1;
        if (requestCalls === 1) {
          return Promise.resolve({
            ok: false,
            status: 403,
            json: () => Promise.resolve({ error: 'Not a member.', code: 'not_a_member' }),
          });
        }
        return Promise.resolve(mockResponse({ message: 'Reservation confirmed' }));
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url)) return Promise.resolve(mockResponse(thing));
      return Promise.resolve(mockResponse({}));
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    await screen.findByText(/Your reservation is confirmed/);
    // In the reader's own language, like every other owner text.
    expect(
      screen.getByText(
        "To reserve here you've joined Neighbourhood workshop. You can leave it from your profile."
      )
    ).toBeInTheDocument();
  });

  test('the join is still announced when the retried reservation fails', async () => {
    // The slot was taken while the join ran: the reservation fails, the
    // membership doesn't — and there is no success message left to carry it.
    const thing = { ...RESERVE_THING, reservation_max_days: 1, collection_headline: 'Taller' };
    let requestCalls = 0;
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/collections\/COL001\/join\//.test(url) && opts.method === 'POST')
        return Promise.resolve(mockResponse({ message: 'Joined' }));
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        requestCalls += 1;
        return Promise.resolve({
          ok: false,
          status: requestCalls === 1 ? 403 : 409,
          json: () =>
            Promise.resolve(
              requestCalls === 1
                ? { error: 'Not a member.', code: 'not_a_member' }
                : { error: 'Those dates are already taken.' }
            ),
        });
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url)) return Promise.resolve(mockResponse(thing));
      return Promise.resolve(mockResponse({}));
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    const notice = await screen.findByText(
      "To reserve here you've joined Taller. You can leave it from your profile."
    );
    // Inside the live region, so a screen reader hears it too.
    expect(notice.closest('[role="status"]')).not.toBeNull();
    expect(screen.queryByText(/Your reservation is confirmed/)).not.toBeInTheDocument();
  });

  test('the standalone route joins the collection the server resolved the thing to', async () => {
    const joins = [];
    notAMemberApi(joins);
    const { container } = renderPage('/things/RSV01/request');
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    await waitFor(() => expect(joins).toEqual(['COL001']));
  });

  test('the manual fallback books the date on screen now, not the one from the failed attempt', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    let joinCalls = 0;
    const requestDates = [];
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/collections\/COL001\/join\//.test(url) && opts.method === 'POST') {
        joinCalls += 1;
        if (joinCalls === 1) {
          return Promise.resolve({ ok: false, status: 500, json: () => Promise.resolve({}) });
        }
        return Promise.resolve(mockResponse({ message: 'Joined' }));
      }
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST') {
        const parsed = JSON.parse(opts.body);
        requestDates.push(parsed.start_date);
        if (requestDates.length === 1) {
          return Promise.resolve({
            ok: false,
            status: 403,
            json: () =>
              Promise.resolve({
                error: 'You need to be a member of this group to reserve.',
                code: 'not_a_member',
              }),
          });
        }
        return Promise.resolve(
          mockResponse({ message: 'Reservation confirmed', booking_code: 'B1' })
        );
      }
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url))
        return Promise.resolve(mockResponse({ ...RESERVE_THING, reservation_max_days: 1 }));
      return Promise.resolve(mockResponse({}));
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));
    await screen.findByRole('button', { name: 'Join this group' });

    // the reader changes their mind about the date while the fallback is showing
    typePickup(container, '05/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Join this group' }));

    expect(await screen.findByText(/Your reservation is confirmed/)).toBeInTheDocument();
    expect(requestDates).toEqual(['2026-06-03', '2026-06-05']);
  });
});

describe('RequestThingPage — reads the thing through the collection it was opened from', () => {
  test('the detail fetch names the route collection, the same one the POST will name', async () => {
    // A thing can live in two reservations collections, one by the day and
    // one by the hour; the form must show the rules of the collection the
    // request is made through, or the server refuses what the form offered.
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    const reads = apiFetch.mock.calls
      .map(([url, opts]) => (!opts?.method ? url : null))
      .filter((url) => url && /\/things\/RSV01\/(\?|$)/.test(url));
    expect(reads).toEqual(['/api/v1/things/RSV01/?collection=COL001']);
  });
});

describe("RequestThingPage — the collection's request-page note", () => {
  test('renders as Markdown under the title when the collection set one', async () => {
    setApi({
      thing: {
        ...RESERVE_THING,
        reservation_max_days: 1,
        collection_request_info: 'Bring **photo ID** to the front desk.',
      },
    });
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    const strong = screen.getByText('photo ID');
    expect(strong.tagName).toBe('STRONG');
    expect(strong.closest('.form-hero-text')).toBeInTheDocument();
  });

  test('is absent when the collection has no note', async () => {
    setApi({ thing: { ...RESERVE_THING, reservation_max_days: 1 } });
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    expect(document.querySelector('.form-hero-text')).toBeNull();
  });
});

const HOURLY_RESERVE_THING = {
  code: 'RSV01',
  type: 'RESERVE_THING',
  headline: 'Sala amb hores',
  location: 'Planta 1',
  collection_code: 'COL001',
  reservation_unit: 'HOUR',
  reservation_horizon_days: 90,
  reservation_min_minutes: 60,
  reservation_max_minutes: 180,
  // The schedule: Mon-Thu 10-14 & 16-20, Fri 10-14, weekend closed.
  opening_hours: {
    0: [
      ['10:00', '14:00'],
      ['16:00', '20:00'],
    ],
    1: [
      ['10:00', '14:00'],
      ['16:00', '20:00'],
    ],
    2: [
      ['10:00', '14:00'],
      ['16:00', '20:00'],
    ],
    3: [
      ['10:00', '14:00'],
      ['16:00', '20:00'],
    ],
    4: [['10:00', '14:00']],
  },
  available_today: true,
  next_available: null,
};

function typeHourlyPickup(container, display) {
  const input = container.querySelector('#reservation-pickup-date-hourly');
  fireEvent.change(input, { target: { value: display } });
  fireEvent.blur(input);
}

describe('RequestThingPage — RESERVE_THING (HOUR unit)', () => {
  test('the hourly date is asked as “Which day?”', async () => {
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    const label = container.querySelector('label[for="reservation-pickup-date-hourly"]');
    expect(label.textContent).toMatch(/^Which day\?/);
  });

  test('renders the hourly pickup field, not the day-count select', async () => {
    setApi({ thing: HOURLY_RESERVE_THING });
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);
    expect(screen.queryByRole('combobox', { name: /How many days/ })).toBeNull();
    expect(document.querySelector('#reservation-pickup-date-hourly')).toBeInTheDocument();
  });

  test('picking a day reveals the duration radios, capped at reservation_max_minutes', async () => {
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    typeHourlyPickup(container, '03/06/2026'); // a Wednesday, both blocks open

    expect(await screen.findByRole('radio', { name: '1 hour' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: '2 hours' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: '3 hours' })).toBeInTheDocument();
    // 4 hours exceeds the 3h cap — not offered. ("Half day"/"Full day" are
    // gone entirely, 2026-09 — plain multiples only.)
    expect(screen.queryByRole('radio', { name: '4 hours' })).toBeNull();
  });

  test('a single-block day (Friday) offers plain durations up to the cap, no named presets', async () => {
    // The single 10:00-14:00 block's whole span shows up as the plain "4
    // hours" multiple — what "Full day" used to name before its removal.
    setApi({ thing: { ...HOURLY_RESERVE_THING, reservation_max_minutes: 240 } });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    typeHourlyPickup(container, '05/06/2026'); // Friday, single 10:00-14:00 block

    expect(await screen.findByRole('radio', { name: '4 hours' })).toBeInTheDocument();
    expect(screen.queryByRole('radio', { name: 'Half day' })).toBeNull();
    expect(screen.queryByRole('radio', { name: 'Full day' })).toBeNull();
  });

  test('a minimum/maximum not aligned to whole hours offers minute-stepped durations with mixed labels', async () => {
    // The feature's whole point: 20/40/60/80/100-minute options, and a
    // 20-minute step for start times too — not the old fixed hourly grid.
    setApi({
      thing: { ...HOURLY_RESERVE_THING, reservation_min_minutes: 20, reservation_max_minutes: 100 },
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    typeHourlyPickup(container, '03/06/2026'); // Wednesday, both blocks open

    expect(await screen.findByRole('radio', { name: '20 minutes' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: '1 hour' })).toBeInTheDocument(); // 60min, reuses the plain hour key
    expect(screen.getByRole('radio', { name: '1h 40min' })).toBeInTheDocument(); // 100min, the mixed label

    fireEvent.click(screen.getByRole('radio', { name: '20 minutes' }));
    // 10:00-14:00 and 16:00-20:00 stepped every 20 minutes: 24 starts, so a
    // dropdown rather than radios (OptionPicker's RADIO_MAX).
    fireEvent.click(await screen.findByRole('combobox', { name: /Starting at/ }));
    expect(await screen.findByRole('option', { name: '10:20' })).toBeInTheDocument();
    expect(screen.getByRole('option', { name: '13:40' })).toBeInTheDocument();
    expect(screen.queryByRole('option', { name: '10:15' })).toBeNull(); // not a 20-minute step
  });

  // A short minimum makes both lists long: 15 minutes over this 8-hour day is
  // 29 start times, and 15 up to 180 minutes is 12 durations. As radios, one
  // question ran longer than a phone screen (DESIGN §4).
  test('a long list of durations or start times is a dropdown, not a column of radios', async () => {
    setApi({
      thing: { ...HOURLY_RESERVE_THING, reservation_min_minutes: 15, reservation_max_minutes: 180 },
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);
    typeHourlyPickup(container, '03/06/2026');

    const durations = await screen.findByRole('combobox', { name: /How long/ });
    expect(screen.queryAllByRole('radio')).toHaveLength(0);
    fireEvent.click(durations);
    fireEvent.click(await screen.findByRole('option', { name: '1h 30min' }));

    fireEvent.click(await screen.findByRole('combobox', { name: /Starting at/ }));
    fireEvent.click(await screen.findByRole('option', { name: '10:15' }));

    // Picked through the dropdowns, the slot reads back the same way.
    expect(
      await screen.findByText('Reserved on 03/06/2026, from 10:15 to 11:45.')
    ).toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));
    await screen.findByText(/Your reservation is confirmed/);
    const postCall = apiFetch.mock.calls.find(
      ([url, opts]) => /\/request\//.test(url) && opts?.method === 'POST'
    );
    expect(JSON.parse(postCall[1].body)).toMatchObject({
      start_time: '10:15',
      end_time: '11:45',
    });
  });

  test('a missing choice in a dropdown still says so and takes focus to it', async () => {
    setApi({
      thing: { ...HOURLY_RESERVE_THING, reservation_min_minutes: 15, reservation_max_minutes: 180 },
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);
    typeHourlyPickup(container, '03/06/2026');
    const durations = await screen.findByRole('combobox', { name: /How long/ });

    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    // HDS Select prints its error twice (on screen, and for its live region).
    expect((await screen.findAllByText('Please choose a length'))[0]).toBeVisible();
    expect(durations).toHaveFocus();
  });

  test('picking a duration reveals the start-time radios, stepped hour by hour', async () => {
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    typeHourlyPickup(container, '03/06/2026');
    fireEvent.click(await screen.findByRole('radio', { name: '2 hours' }));

    // 10:00-14:00 fits 10:00,11:00,12:00 for a 2h slot; 16:00-20:00 fits
    // 16:00,17:00,18:00.
    for (const hm of ['10:00', '11:00', '12:00', '16:00', '17:00', '18:00']) {
      expect(await screen.findByRole('radio', { name: hm })).toBeInTheDocument();
    }
    expect(screen.queryByRole('radio', { name: '13:00' })).toBeNull(); // would end at 15:00
  });

  test('a fully booked day is disabled in the picker itself', async () => {
    setApi({
      thing: HOURLY_RESERVE_THING,
      calendar: [
        {
          start_date: '2026-06-03',
          end_date: '2026-06-04',
          start_time: '10:00',
          end_time: '14:00',
        },
        {
          start_date: '2026-06-03',
          end_date: '2026-06-04',
          start_time: '16:00',
          end_time: '20:00',
        },
      ],
    });
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    fireEvent.click(screen.getByRole('button', { name: 'Choose date' }));
    await waitFor(() => expect(document.querySelector('[data-date]')).toBeTruthy());
    // The day has to be on screen and refused — "absent" used to pass too, so a
    // picker opening on another month, or disabling everything, went unseen.
    expect(pickerDay('2026-06-03')).toHaveAttribute('aria-disabled', 'true');
    // The Thursday after it has the same hours and no bookings: still offered.
    expect(pickerDay('2026-06-04').tagName).toBe('BUTTON');
  });

  test('choosing a duration that fits nowhere that day shows the fallback notice', async () => {
    // Two separate 1h gaps remain (13:00-14:00 and 19:00-20:00): the day still
    // has a free hour, so the picker allows it, but no 2h+ slot fits either
    // gap — "2 hours" should fall back to the notice, not an empty radio group.
    setApi({
      thing: HOURLY_RESERVE_THING,
      calendar: [
        {
          start_date: '2026-06-03',
          end_date: '2026-06-04',
          start_time: '10:00',
          end_time: '13:00',
        },
        {
          start_date: '2026-06-03',
          end_date: '2026-06-04',
          start_time: '16:00',
          end_time: '19:00',
        },
      ],
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    typeHourlyPickup(container, '03/06/2026');
    fireEvent.click(await screen.findByRole('radio', { name: '1 hour' }));
    expect(await screen.findByRole('radio', { name: '13:00' })).toBeInTheDocument();
    expect(await screen.findByRole('radio', { name: '19:00' })).toBeInTheDocument();

    // The live region must already be mounted BEFORE the dead-end duration is
    // picked — a screen reader only announces a change made inside a region
    // that already existed (WCAG 4.1.3). Capturing the reference now, then
    // asserting the notice lands inside this same node, is what actually pins
    // that: a Notification that only gets created once the fallback fires
    // would pass a text-only assertion while announcing nothing. Queried by
    // class, not `getByRole('status')`: HDS's own LoadingSpinner leaves a
    // second, unrelated `role="status"` announcer behind in the document. All of
    // them, not the first: the page has more than one region (the joined-group
    // notice has its own), and what matters is that one that was already there
    // holds the notice.
    const statusRegions = [...container.querySelectorAll('.status-region')];
    expect(statusRegions.length).toBeGreaterThan(0);

    fireEvent.click(screen.getByRole('radio', { name: '2 hours' }));
    const notice = await screen.findByText(/No start times are free/);
    expect(screen.getByText('No times available')).toBeInTheDocument();
    expect(statusRegions.some((region) => region.contains(notice))).toBe(true);
    expect(screen.queryByRole('radio', { name: '13:00' })).toBeNull();
  });

  test('submitting posts start_time/end_time (never duration_days) for an hourly reservation', async () => {
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    typeHourlyPickup(container, '03/06/2026');
    fireEvent.click(await screen.findByRole('radio', { name: '2 hours' }));
    fireEvent.click(await screen.findByRole('radio', { name: '11:00' }));
    fireEvent.change(screen.getByLabelText(/What do you need it for/), {
      target: { value: 'A repair workshop.' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    await screen.findByText(/Your reservation is confirmed/);
    const postCall = apiFetch.mock.calls.find(
      ([url, opts]) => /\/request\//.test(url) && opts?.method === 'POST'
    );
    const body = JSON.parse(postCall[1].body);
    expect(body).toEqual({
      start_date: '2026-06-03',
      start_time: '11:00',
      end_time: '13:00',
      project_note: 'A repair workshop.',
      collection_code: 'COL001',
    });
    expect(body.duration_days).toBeUndefined();
  });

  test('once day, length and start are picked, the whole slot is shown before booking', async () => {
    // The end time appears nowhere else on the page, and the slot auto-confirms.
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    typeHourlyPickup(container, '03/06/2026');
    fireEvent.click(await screen.findByRole('radio', { name: '2 hours' }));
    expect(screen.queryByText(/Reserved on/)).toBeNull(); // no start yet, nothing to say
    fireEvent.click(await screen.findByRole('radio', { name: '11:00' }));

    const summary = await screen.findByText('Reserved on 03/06/2026, from 11:00 to 13:00.');
    // Read out when the start time is chosen, not only visible.
    const regions = screen.getAllByRole('status');
    expect(regions.some((region) => region.contains(summary))).toBe(true);
  });

  test('a rule the server refuses is explained from the page’s own catalogue', async () => {
    // core has no gettext: the refusal arrives in English with a code, and the
    // page says it in the reader's language — here English, but not the
    // server's sentence, which is how the test tells the two apart.
    setApi({ thing: HOURLY_RESERVE_THING });
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST')
        return Promise.resolve({
          ok: false,
          status: 400,
          json: () =>
            Promise.resolve({
              error: "You've reached the maximum number of active reservations for this space.",
              code: 'reservation_max_active',
              params: { max: 2 },
            }),
        });
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url))
        return Promise.resolve(mockResponse(HOURLY_RESERVE_THING));
      return Promise.resolve(mockResponse({}));
    });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);
    typeHourlyPickup(container, '03/06/2026');
    fireEvent.click(await screen.findByRole('radio', { name: '2 hours' }));
    fireEvent.click(await screen.findByRole('radio', { name: '11:00' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    expect(
      await screen.findByText(
        'You already have 2 active reservations here — the most this collection allows.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByText(/maximum number of active reservations/)).toBeNull();
  });

  test('the confirmation restates the booked slot, end time included', async () => {
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    typeHourlyPickup(container, '03/06/2026');
    fireEvent.click(await screen.findByRole('radio', { name: '2 hours' }));
    fireEvent.click(await screen.findByRole('radio', { name: '11:00' }));
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    await screen.findByText(/Your reservation is confirmed/);
    expect(screen.getByText('03/06/2026, 11:00–13:00')).toBeInTheDocument();
  });

  // The picker stops offering a slot that already began today — the server
  // refuses one as well, by the deployment's clock, but the form shouldn't
  // offer what the server will refuse (found in review, 2026-09-18). The
  // clock is faked at Monday 01/06/2026 12:00 in beforeEach.
  test('today only offers starts that have not begun yet', async () => {
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    typeHourlyPickup(container, '01/06/2026'); // today, a Monday
    fireEvent.click(await screen.findByRole('radio', { name: '1 hour' }));

    expect(await screen.findByRole('radio', { name: '12:00' })).toBeInTheDocument();
    expect(screen.getByRole('radio', { name: '16:00' })).toBeInTheDocument();
    expect(screen.queryByRole('radio', { name: '10:00' })).toBeNull();
    expect(screen.queryByRole('radio', { name: '11:00' })).toBeNull();
  });

  test('a start picked before it passed is not sent once it has', async () => {
    vi.setSystemTime(new Date(2026, 5, 1, 11, 59));
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);
    typeHourlyPickup(container, '01/06/2026');
    fireEvent.click(await screen.findByRole('radio', { name: '1 hour' }));
    fireEvent.click(await screen.findByRole('radio', { name: '12:00' }));
    expect(screen.getByRole('radio', { name: '12:00' })).toBeChecked();

    // Two minutes later 12:00 has begun, and the page re-renders (any
    // keystroke will do).
    vi.setSystemTime(new Date(2026, 5, 1, 12, 1));
    fireEvent.change(screen.getByLabelText(/What do you need it for/), {
      target: { value: 'Late.' },
    });
    await waitFor(() => expect(screen.queryByRole('radio', { name: '12:00' })).toBeNull());
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    // Not sent — and not silently: the start-time group asks again.
    expect(await screen.findByText('Please choose a start time')).toBeVisible();
    const postCall = apiFetch.mock.calls.find(
      ([url, opts]) => /\/request\//.test(url) && opts?.method === 'POST'
    );
    expect(postCall).toBeUndefined();
  });

  test('today is disabled in the picker once its last start has passed', async () => {
    vi.setSystemTime(new Date(2026, 5, 5, 13, 30)); // Friday: only 10:00-14:00, last 1h start 13:00
    setApi({ thing: HOURLY_RESERVE_THING });
    renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    fireEvent.click(screen.getByRole('button', { name: 'Choose date' }));
    await waitFor(() => expect(document.querySelector('[data-date]')).toBeTruthy());
    expect(pickerDay('2026-06-05')).toHaveAttribute('aria-disabled', 'true');
    // Next Monday (the weekend is closed) is untouched by today's clock.
    expect(pickerDay('2026-06-08').tagName).toBe('BUTTON');
  });

  // A Reserve click the page can't send used to do nothing visible here —
  // the radio groups had no error state (found in review, 2026-09-18). HDS
  // links a SelectionGroup's error text to nothing, so focus moving onto the
  // group is what a screen reader hears.
  const posts = () =>
    apiFetch.mock.calls.filter(([url, opts]) => /\/request\//.test(url) && opts?.method === 'POST');

  test('Reserve with a day but no duration says so and takes focus to the durations', async () => {
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);
    typeHourlyPickup(container, '03/06/2026');
    await screen.findByRole('radio', { name: '1 hour' });

    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    expect(await screen.findByText('Please choose a length')).toBeVisible();
    expect(screen.getByRole('radio', { name: '1 hour' })).toHaveFocus();
    expect(posts()).toHaveLength(0);
  });

  test('Reserve with a duration but no start time says so and takes focus to the times', async () => {
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);
    typeHourlyPickup(container, '03/06/2026');
    fireEvent.click(await screen.findByRole('radio', { name: '2 hours' }));
    await screen.findByRole('radio', { name: '10:00' });

    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    expect(await screen.findByText('Please choose a start time')).toBeVisible();
    expect(screen.getByRole('radio', { name: '10:00' })).toHaveFocus();
    expect(screen.queryByText('Please choose a length')).toBeNull();
    expect(posts()).toHaveLength(0);
  });

  test('changing the day resets an already-chosen duration and start time', async () => {
    setApi({ thing: HOURLY_RESERVE_THING });
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala amb hores/);

    typeHourlyPickup(container, '03/06/2026');
    fireEvent.click(await screen.findByRole('radio', { name: '2 hours' }));
    fireEvent.click(await screen.findByRole('radio', { name: '11:00' }));

    typeHourlyPickup(container, '04/06/2026'); // Thursday, same schedule
    await waitFor(() => expect(screen.queryByRole('radio', { name: '11:00' })).toBeNull());
    expect(screen.queryByRole('radio', { checked: true })).toBeNull();
  });
});

/**
 * A clash is the refusal a member is likeliest to meet: two people after the
 * same slot, the other one a moment faster. The server answers 409 with a
 * coded body (`time_taken` for an hourly slot, `dates_taken` for days), and the
 * page says it from its own catalogue — in the reader's language, since core
 * has no gettext — falling back to its own clash copy when the body carries no
 * code it knows (or no body at all).
 */
describe('RequestThingPage — a clash (409)', () => {
  const clash = (body) => ({
    ok: false,
    status: 409,
    json: () =>
      body === undefined ? Promise.reject(new SyntaxError('empty body')) : Promise.resolve(body),
  });

  function clashApi(thing, response) {
    apiFetch.mockImplementation((url, opts = {}) => {
      if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse([]));
      if (/\/things\/[^/]+\/request\//.test(url) && opts.method === 'POST')
        return Promise.resolve(response);
      if (/\/things\/[^/]+\/(\?.*)?$/.test(url)) return Promise.resolve(mockResponse(thing));
      return Promise.resolve(mockResponse({}));
    });
  }

  afterEach(async () => {
    await act(async () => {
      await i18n.changeLanguage('en');
    });
  });

  test('an hourly slot taken meanwhile is told as taken, in the reader’s language', async () => {
    i18n.addResourceBundle('es', 'translation', es, true, true);
    await act(async () => {
      await i18n.changeLanguage('es');
    });
    clashApi(
      HOURLY_RESERVE_THING,
      clash({ error: 'That time is already taken.', code: 'time_taken' })
    );
    const { container } = renderPage();
    await screen.findByText(i18n.t('reservation.pageTitle', { headline: 'Sala amb hores' }));

    typeHourlyPickup(container, '03/06/2026');
    fireEvent.click(
      await screen.findByRole('radio', { name: i18n.t('reservation.hours', { count: 2 }) })
    );
    fireEvent.click(await screen.findByRole('radio', { name: '11:00' }));
    fireEvent.click(screen.getByRole('button', { name: i18n.t('thingCard.action.RESERVE_THING') }));

    expect(await screen.findByText(es.requestErrors.time_taken)).toBeInTheDocument();
    // Neither the server's English nor this page's generic failure.
    expect(screen.queryByText('That time is already taken.')).toBeNull();
    expect(screen.queryByText(es.request.errorSending)).toBeNull();
    expect(screen.queryByText(es.reservation.successMessage)).toBeNull();
  });

  test('a clash with no body it can read still says the dates clash', async () => {
    clashApi({ ...RESERVE_THING, reservation_max_days: 1 }, clash(undefined));
    const { container } = renderPage();
    await requestPageReady(apiFetch, /Reserve Sala polivalent/);

    typePickup(container, '03/06/2026');
    fireEvent.click(screen.getByRole('button', { name: 'Reserve' }));

    expect(await screen.findByText('Date overlaps with another booking.')).toBeInTheDocument();
    expect(screen.queryByText('Error sending request.')).toBeNull();
    expect(screen.queryByText(/Your reservation is confirmed/)).toBeNull();
  });
});

describe('InboxNotifications — reservation notices render (not the blank broadcast fallback)', () => {
  function setInbox(rows) {
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox')) return Promise.resolve(mockResponse(rows));
      return Promise.resolve(mockResponse({}));
    });
  }

  test('RESERVATION_MADE', async () => {
    setInbox([
      {
        code: 'N1',
        type: 'RESERVATION_MADE',
        payload: { requester_name: 'Lele', thing_headline: 'Sala 2', thing_code: 'T1' },
        created: '2026-06-01T10:00:00Z',
      },
    ]);
    render(
      <MemoryRouter>
        <InboxNotifications />
      </MemoryRouter>
    );
    expect(await screen.findByText('New reservation')).toBeInTheDocument();
    expect(screen.getByText('Lele reserved Sala 2.')).toBeInTheDocument();
  });

  test('RESERVATION_CANCELLED', async () => {
    setInbox([
      {
        code: 'N2',
        type: 'RESERVATION_CANCELLED',
        payload: { other_name: 'Lala', thing_headline: 'Sala 2', thing_code: 'T1' },
        created: '2026-06-01T10:00:00Z',
      },
    ]);
    render(
      <MemoryRouter>
        <InboxNotifications />
      </MemoryRouter>
    );
    expect(await screen.findByText('Reservation cancelled')).toBeInTheDocument();
    expect(screen.getByText('Lala cancelled a reservation of Sala 2.')).toBeInTheDocument();
  });
});
