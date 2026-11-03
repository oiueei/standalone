import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';

window.scrollTo = vi.fn();

const navigate = vi.fn();
vi.mock('react-router', async () => ({
  ...(await vi.importActual('react-router')),
  useNavigate: () => navigate,
}));

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
  getCsrfToken: () => 'tok',
}));

vi.mock('../hooks/useCollectionLanguage', () => ({ default: vi.fn() }));

import { apiFetch } from '../services/api';
import CollectionAvailabilityPage from './CollectionAvailabilityPage';
import { dropHdsStyles } from '../test/dropHdsStyles';
import { settle } from '../test/settle';

// What other pages own: the PATCH of this page must leave all of it alone.
const OTHERS = {
  code: 'COL001',
  headline: 'The Workshop',
  description: 'Tools and a bench',
  mode: 'PROPRIETARY',
  tags: ['Tools'],
  thumbnail: 'logo.png',
  theeeme: 'T2',
  koro: 'wave',
  home_page: 'https://example.test',
  allow_member_proposals: true,
  welcome_doc: 'welcome.pdf',
  digest_frequency: 'WEEKLY',
  language: 'ca',
  email_note: 'A note.',
  allowed_thing_types: ['LEND_THING'],
};

const LIBRARY = {
  ...OTHERS,
  kind: 'LIBRARY',
  request_info: 'Bring ID.',
  closed_dates: ['2099-12-25'],
  rental_durations: [7, 14],
  rental_weekdays: [5],
  deposit_policy: 'Back when returned.',
};

const SHED_DAYS = {
  ...OTHERS,
  kind: 'SHED',
  allowed_thing_types: ['RESERVE_THING'],
  request_info: 'Pickup Tuesdays.',
  closed_dates: [],
  rental_weekdays: [0, 1, 2, 3, 4],
  reservation_unit: 'DAY',
  reservation_max_days: 3,
  reservation_horizon_days: 60,
  reservation_max_active_per_member: 4,
  reservation_asks_phone: true,
  reservation_min_minutes: 30,
  reservation_max_minutes: 240,
  opening_hours: {},
};

const HOURS = { 0: [['10:00', '14:00']], 1: [['12:00', '16:00']] };
const SHED_HOURS = { ...SHED_DAYS, reservation_unit: 'HOUR', opening_hours: HOURS };

function mockApi({ collection, save = { ok: true } }) {
  apiFetch.mockImplementation((url, opts) => {
    if (opts?.method === 'PATCH') {
      return Promise.resolve({
        ok: save.ok,
        status: save.status ?? (save.ok ? 200 : 400),
        json: async () => save.body ?? {},
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => collection });
  });
}

const patchBody = () => {
  const call = apiFetch.mock.calls.find(([, opts]) => opts?.method === 'PATCH');
  return call ? JSON.parse(call[1].body) : null;
};
const keys = () => Object.keys(patchBody()).sort();

const renderPage = (kind = 'library') =>
  render(
    <MemoryRouter initialEntries={[`/${kind}/COL001/settings/availability`]}>
      <Routes>
        <Route path="/:kind/:code/settings/availability" element={<CollectionAvailabilityPage />} />
      </Routes>
    </MemoryRouter>
  );

const loaded = async () => {
  await screen.findByRole('heading', { level: 1, name: 'Availability' });
  await settle(apiFetch);
};
const save = async () => {
  fireEvent.click(screen.getByRole('button', { name: 'Save' }));
  await settle(apiFetch);
};

beforeEach(() => {
  dropHdsStyles();
  localStorage.clear();
  localStorage.setItem('userCode', 'USR001');
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

describe('CollectionAvailabilityPage — a library', () => {
  test('saves exactly its five fields and nothing the collection keeps elsewhere', async () => {
    mockApi({ collection: LIBRARY });
    renderPage();
    await loaded();

    await save();

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/library/COL001'));
    expect(keys()).toEqual([
      'closed_dates',
      'deposit_policy',
      'rental_durations',
      'rental_weekdays',
      'request_info',
    ]);
  });

  test('saving without touching anything sends what was loaded', async () => {
    mockApi({ collection: LIBRARY });
    renderPage();
    await loaded();

    await save();

    expect(patchBody()).toEqual({
      request_info: 'Bring ID.',
      closed_dates: '25/12/2099',
      rental_durations: [7, 14],
      rental_weekdays: [5],
      deposit_policy: 'Back when returned.',
    });
  });

  test('explains the languages of the note and of the policy above their fields', async () => {
    mockApi({ collection: LIBRARY });
    renderPage();
    await loaded();

    expect(screen.getByText(/The request-page note can hold one text per language/)).toBeVisible();
    expect(screen.getByText(/The deposit policy can hold one text per language/)).toBeVisible();
    expect(screen.getByText(/Shown at the top of the request page/)).toBeVisible();
    expect(screen.queryByText(/Leave empty if this collection/)).toBeNull();
  });
});

describe('CollectionAvailabilityPage — a shed by day', () => {
  test('saves its fields, with no opening hours and no minutes', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();

    await save();

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/shed/COL001'));
    expect(keys()).toEqual([
      'closed_dates',
      'rental_weekdays',
      'request_info',
      'reservation_asks_phone',
      'reservation_horizon_days',
      'reservation_max_active_per_member',
      'reservation_max_days',
      'reservation_unit',
    ]);
  });

  test('the saved phone switch is on after loading and is sent as it was', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();

    expect(screen.getByLabelText(/Ask for a contact phone/)).toHaveAttribute(
      'aria-pressed',
      'true'
    );
    await save();

    expect(patchBody()).toMatchObject({
      reservation_asks_phone: true,
      reservation_unit: 'DAY',
      reservation_max_days: 3,
      reservation_horizon_days: 60,
      reservation_max_active_per_member: 4,
      rental_weekdays: [0, 1, 2, 3, 4],
    });
  });
});

describe('CollectionAvailabilityPage — a shed by hour', () => {
  test('saves its fields, with the minutes and the hours and no longest-in-days', async () => {
    mockApi({ collection: SHED_HOURS });
    renderPage('shed');
    await loaded();

    await save();

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    expect(keys()).toEqual([
      'closed_dates',
      'opening_hours',
      'rental_weekdays',
      'request_info',
      'reservation_asks_phone',
      'reservation_horizon_days',
      'reservation_max_active_per_member',
      'reservation_max_minutes',
      'reservation_min_minutes',
      'reservation_unit',
    ]);
  });

  test('saving without touching anything leaves every saved value as it was', async () => {
    mockApi({ collection: SHED_HOURS });
    renderPage('shed');
    await loaded();

    await save();

    expect(patchBody()).toEqual({
      request_info: 'Pickup Tuesdays.',
      closed_dates: '',
      rental_weekdays: [0, 1, 2, 3, 4],
      reservation_horizon_days: 60,
      reservation_max_active_per_member: 4,
      reservation_asks_phone: true,
      reservation_unit: 'HOUR',
      reservation_min_minutes: 30,
      reservation_max_minutes: 240,
      opening_hours: HOURS,
    });
  });

  test('explains the format of the hours in a notice and leaves out the helper line', async () => {
    mockApi({ collection: SHED_HOURS });
    renderPage('shed');
    await loaded();

    expect(screen.getByText(/each a list of \["HH:MM","HH:MM"\] ranges — e\.g\./)).toBeVisible();
    expect(
      screen.getByText('{"0": [["10:00","14:00"],["16:00","20:00"]], "1": [["12:00","16:00"]]}')
    ).toBeVisible();
    expect(screen.getByText(/Leave a day out, or give it an empty list/)).toBeVisible();
    // The notice replaces the helper under the field: it is not said twice.
    expect(screen.getAllByText(/Leave a day out, or give it an empty list/)).toHaveLength(1);
  });

  test('going from day to hour with no opening hours does not save, and says why', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();

    fireEvent.click(screen.getByRole('radio', { name: /By hour/ }));
    expect(
      await screen.findByText(
        'With no opening hours, nobody can book: add at least one time range.'
      )
    ).toBeVisible();
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(
      await screen.findByText(
        'To book by the hour, add at least one time range to “Weekly opening hours”.'
      )
    ).toBeVisible();
    expect(patchBody()).toBeNull();
    expect(navigate).not.toHaveBeenCalled();
  });

  test('opening hours that are not valid JSON do not save either', async () => {
    mockApi({ collection: SHED_HOURS });
    renderPage('shed');
    await loaded();
    const field = screen.getByLabelText(/Weekly opening hours/);
    fireEvent.change(field, { target: { value: '{"0": [[' } });
    fireEvent.blur(field);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(
      await screen.findByText(
        "Nothing was saved: the weekly opening hours aren't valid JSON. Fix them and save again."
      )
    ).toBeVisible();
    expect(patchBody()).toBeNull();
  });

  test('pasting hours after switching to hours lets it save, with unit and hours together', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();
    fireEvent.click(screen.getByRole('radio', { name: /By hour/ }));
    const field = await screen.findByLabelText(/Weekly opening hours/);
    fireEvent.change(field, { target: { value: JSON.stringify(HOURS) } });
    fireEvent.blur(field);

    await save();

    expect(patchBody()).toMatchObject({ reservation_unit: 'HOUR', opening_hours: HOURS });
    expect(patchBody()).not.toHaveProperty('reservation_max_days');
  });
});

describe('CollectionAvailabilityPage — the rest', () => {
  test('a stall has no such page: the app’s not-found page', async () => {
    mockApi({ collection: { ...OTHERS, kind: 'STALL' } });
    renderPage('stall');

    expect(await screen.findByText('Page not found')).toBeVisible();
    expect(screen.queryByRole('heading', { name: 'Availability' })).toBeNull();
  });

  test('cannot be saved before the collection has loaded', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 500, json: async () => ({}) })
    );
    renderPage();

    const button = await screen.findByRole('button', { name: 'Save' });
    expect(button).toBeDisabled();
    fireEvent.click(button);
    expect(patchBody()).toBeNull();
  });

  test('a refusal of the server is shown as its own message', async () => {
    mockApi({
      collection: LIBRARY,
      save: { ok: false, status: 400, body: { closed_dates: ['Bad date, said the server.'] } },
    });
    renderPage();
    await loaded();

    await save();

    expect(await screen.findByText(/Bad date, said the server/)).toBeVisible();
    expect(navigate).not.toHaveBeenCalled();
  });
});
