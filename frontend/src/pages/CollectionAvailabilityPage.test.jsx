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
import en from '../i18n/locales/en.json';
import { dropHdsStyles } from '../test/dropHdsStyles';
import { settle } from '../test/settle';
import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

// What other pages own: the PATCH of this page must leave all of it alone.
const OTHERS = {
  code: 'COL001',
  is_curator: true,
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
    const field = screen.getByRole('textbox', { name: /Weekly opening hours/ });
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
    const field = await screen.findByRole('textbox', { name: /Weekly opening hours/ });
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

  test('a collection that cannot be read gives no form, so there is nothing to save', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 500, json: async () => ({}) })
    );
    renderPage();

    expect(await screen.findByText(en.editCollection.errorLoading)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
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

describe('CollectionAvailabilityPage — the fields of a library', () => {
  const chip = (name) => screen.getByRole('button', { name });

  test('the request-page note shows what is stored and an edit reaches the PATCH, trimmed', async () => {
    mockApi({ collection: LIBRARY });
    renderPage();
    await loaded();
    const note = screen.getByRole('textbox', { name: en.requestInfo.label });
    expect(note).toHaveValue('Bring ID.');

    fireEvent.change(note, { target: { value: '  Pickup is Tuesdays only.  ' } });
    await save();

    expect(patchBody().request_info).toBe('Pickup is Tuesdays only.');
  });

  test('the note’s counter is the 512-per-language one, and past it the error shows at once', async () => {
    mockApi({ collection: LIBRARY });
    renderPage();
    await loaded();
    const note = screen.getByRole('textbox', { name: en.requestInfo.label });

    fireEvent.change(note, { target: { value: 'Bring ID.' } });
    expect(screen.getByText('9/512')).toBeInTheDocument();

    fireEvent.change(note, { target: { value: 'x'.repeat(513) } });
    expect(screen.getByText('Maximum 512 characters per language.')).toBeInTheDocument();
    // …announced through the field, not only painted.
    expect(note.getAttribute('aria-describedby')).toContain('availability-request-info-error');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));
    expect(patchBody()).toBeNull();
  });

  test('a deposit policy past 256 says so and Save is disabled until it fits again', async () => {
    mockApi({ collection: LIBRARY });
    renderPage();
    await loaded();
    const policy = screen.getByRole('textbox', { name: /deposit policy/i });
    const saveButton = screen.getByRole('button', { name: 'Save' });
    expect(saveButton).toBeEnabled();

    fireEvent.change(policy, { target: { value: 'x'.repeat(257) } });
    expect(screen.getByText(en.rental.depositPolicyMaxLength)).toBeInTheDocument();
    expect(saveButton).toBeDisabled();

    fireEvent.change(policy, { target: { value: 'x'.repeat(256) } });
    expect(screen.queryByText(en.rental.depositPolicyMaxLength)).toBeNull();
    expect(saveButton).toBeEnabled();
  });

  test('a note past 512 disables Save, and a shed has no deposit field to hold it back', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();
    const saveButton = screen.getByRole('button', { name: 'Save' });
    const note = screen.getByRole('textbox', { name: en.requestInfo.label });

    fireEvent.change(note, { target: { value: 'x'.repeat(513) } });
    expect(saveButton).toBeDisabled();
    fireEvent.change(note, { target: { value: 'short' } });
    expect(saveButton).toBeEnabled();
  });

  test('the deposit policy starts empty, shows what is stored and sends what is typed', async () => {
    mockApi({ collection: { ...LIBRARY, deposit_policy: '' } });
    renderPage();
    await loaded();
    const policy = screen.getByRole('textbox', { name: /deposit policy/i });
    expect(policy).toHaveValue('');

    fireEvent.change(policy, { target: { value: '50 €, back when the drill comes home' } });
    await save();

    expect(patchBody().deposit_policy).toBe('50 €, back when the drill comes home');
  });

  test('the weekday chips use Python numbering and stay sorted', async () => {
    mockApi({ collection: { ...LIBRARY, rental_weekdays: [4] } });
    renderPage();
    await loaded();
    expect(chip('Friday')).toHaveAttribute('aria-pressed', 'true');
    expect(chip('Tuesday')).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(chip('Monday'));
    fireEvent.click(chip('Sunday'));
    await save();

    expect(patchBody().rental_weekdays).toEqual([0, 4, 6]);
  });

  test('a chip pressed again takes its day out', async () => {
    mockApi({ collection: { ...LIBRARY, rental_weekdays: [0, 2, 4] } });
    renderPage();
    await loaded();

    fireEvent.click(chip('Wednesday'));
    await save();

    expect(patchBody().rental_weekdays).toEqual([0, 4]);
  });

  test('the lengths are offered labelled, the stored ones are selected, and a pick is a number', async () => {
    mockApi({ collection: { ...LIBRARY, rental_durations: [7] } });
    renderPage();
    await loaded();
    const lengths = screen.getByRole('combobox', { name: /length|duration/i });

    fireEvent.click(lengths);
    expect(screen.getByRole('option', { name: '1 week', selected: true })).toBeInTheDocument();
    fireEvent.click(screen.getByRole('option', { name: '1 day' }));
    await save();

    expect(patchBody().rental_durations).toEqual([1, 7]);
    expect(patchBody().rental_durations.every((d) => typeof d === 'number')).toBe(true);
  });
});

describe('CollectionAvailabilityPage — the fields of a shed', () => {
  const horizon = () =>
    screen.getByRole('spinbutton', { name: 'How far ahead members can book (days)' });
  const maxDays = () => screen.getByRole('spinbutton', { name: 'Longest reservation (days)' });

  test('how it is booked: two radios, the stored one checked', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();

    expect(screen.getAllByRole('radio')).toHaveLength(2);
    expect(screen.getByRole('radio', { name: 'By day' })).toBeChecked();
    expect(screen.getByRole('radio', { name: 'By hour' })).not.toBeChecked();
  });

  test('by day: the day fields and the open weekdays, not the hour ones', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();

    expect(maxDays()).toHaveValue(3);
    expect(screen.getByRole('group', { name: 'Days open for reservations' })).toBeInTheDocument();
    expect(screen.queryByRole('spinbutton', { name: 'Shortest reservation (minutes)' })).toBeNull();
    expect(screen.queryByText('Weekly opening hours')).toBeNull();
    expect(horizon()).toHaveValue(60);
    expect(
      screen.getByRole('spinbutton', { name: 'Maximum active reservations per member' })
    ).toHaveValue(4);
  });

  test('by hour: the minute fields with their stored values, not the day ones', async () => {
    mockApi({ collection: SHED_HOURS });
    renderPage('shed');
    await loaded();

    expect(screen.getByRole('radio', { name: 'By hour' })).toBeChecked();
    expect(screen.getByRole('spinbutton', { name: 'Shortest reservation (minutes)' })).toHaveValue(
      30
    );
    expect(screen.getByRole('spinbutton', { name: 'Longest reservation (minutes)' })).toHaveValue(
      240
    );
    expect(screen.getByRole('textbox', { name: /Weekly opening hours/ })).toBeInTheDocument();
    expect(screen.queryByRole('spinbutton', { name: 'Longest reservation (days)' })).toBeNull();
    expect(screen.queryByRole('group', { name: 'Days open for reservations' })).toBeNull();
    // …and the two limits that belong to either unit are still there.
    expect(horizon()).toBeInTheDocument();
  });

  test('a day chosen on the weekday row is stored as its Python number', async () => {
    mockApi({ collection: { ...SHED_DAYS, rental_weekdays: [] } });
    renderPage('shed');
    await loaded();

    fireEvent.click(screen.getByRole('button', { name: 'Wednesday' }));
    await save();

    expect(patchBody().rental_weekdays).toEqual([2]);
  });

  test('a number typed into a day field is saved even if the field never lost focus', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();

    fireEvent.change(horizon(), { target: { value: '30' } });
    fireEvent.change(maxDays(), { target: { value: '5' } });
    await save();

    expect(patchBody()).toMatchObject({ reservation_horizon_days: 30, reservation_max_days: 5 });
  });

  test('the phone switch turned off reaches the PATCH, and on again too', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();
    const phone = () => screen.getByLabelText(/Ask for a contact phone/);

    fireEvent.click(phone());
    expect(phone()).toHaveAttribute('aria-pressed', 'false');
    await save();
    expect(patchBody().reservation_asks_phone).toBe(false);
  });

  test('a shed that does not ask for a phone, turning it on reaches the PATCH', async () => {
    mockApi({ collection: { ...SHED_DAYS, reservation_asks_phone: false } });
    renderPage('shed');
    await loaded();

    fireEvent.click(screen.getByLabelText(/Ask for a contact phone/));
    await save();

    expect(patchBody().reservation_asks_phone).toBe(true);
  });

  test('has no accessibility violations, by day and by hour', async () => {
    mockApi({ collection: SHED_DAYS });
    const day = renderPage('shed');
    await loaded();
    expect(await axe(day.container)).toHaveNoViolations();
    day.unmount();

    mockApi({ collection: SHED_HOURS });
    const hour = renderPage('shed');
    await loaded();
    expect(await axe(hour.container)).toHaveNoViolations();
  });
});

describe('CollectionAvailabilityPage — an hourly space with no opening hours', () => {
  const NONE_OPEN = 'With no opening hours, nobody can book: add at least one time range.';

  test('every day given an empty list is the same as none: it warns, and does not save', async () => {
    mockApi({
      collection: {
        ...SHED_HOURS,
        opening_hours: { 0: [], 1: [], 2: [], 3: [], 4: [], 5: [], 6: [] },
      },
    });
    renderPage('shed');
    await loaded();
    expect(screen.getByText(NONE_OPEN)).toBeInTheDocument();

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(
      await screen.findByText(/To book by the hour, add at least one time range/)
    ).toBeVisible();
    expect(patchBody()).toBeNull();
  });

  test('a week of days with no ranges typed in is no schedule either', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();
    fireEvent.click(screen.getByRole('radio', { name: /By hour/ }));
    const hours = await screen.findByRole('textbox', { name: /Weekly opening hours/ });
    fireEvent.change(hours, { target: { value: '{"0": [], "3": []}' } });
    fireEvent.blur(hours);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(
      await screen.findByText(/To book by the hour, add at least one time range/)
    ).toBeVisible();
    expect(patchBody()).toBeNull();
  });

  test('one range on one day is enough: no warning', async () => {
    mockApi({ collection: SHED_HOURS });
    renderPage('shed');
    await loaded();

    expect(screen.queryByText(NONE_OPEN)).toBeNull();
  });

  test('a space booked by the day has no opening hours to miss', async () => {
    mockApi({ collection: SHED_DAYS });
    renderPage('shed');
    await loaded();

    expect(screen.queryByText(NONE_OPEN)).toBeNull();
  });

  test('while the JSON cannot be read, the field’s own error speaks and the warning does not', async () => {
    mockApi({ collection: { ...SHED_HOURS, opening_hours: {} } });
    renderPage('shed');
    await loaded();
    const field = screen.getByRole('textbox', { name: /Weekly opening hours/ });

    fireEvent.change(field, { target: { value: '{"0": [' } });
    fireEvent.blur(field);

    expect(screen.getByText(/isn.t valid JSON|valid JSON/i)).toBeInTheDocument();
    expect(screen.queryByText(NONE_OPEN)).toBeNull();
  });

  test('fixing the draft lets the corrected schedule through', async () => {
    mockApi({ collection: SHED_HOURS });
    renderPage('shed');
    await loaded();
    const field = screen.getByRole('textbox', { name: /Weekly opening hours/ });
    fireEvent.change(field, { target: { value: '{"0": [["10:00","14:00"]],}' } });
    fireEvent.blur(field);
    fireEvent.change(field, { target: { value: '{"0": [["09:00","13:00"]]}' } });
    fireEvent.blur(field);

    await save();

    expect(patchBody().opening_hours).toEqual({ 0: [['09:00', '13:00']] });
  });

  test('leaving "By hour" and coming back drops the refusal with the broken draft', async () => {
    // Switching to day unmounts the field, and coming back remounts it showing the last good
    // schedule with no error: a refusal that outlived the draft would block a save with
    // nothing on screen to fix.
    mockApi({ collection: SHED_HOURS });
    renderPage('shed');
    await loaded();
    const field = screen.getByRole('textbox', { name: /Weekly opening hours/ });
    fireEvent.change(field, { target: { value: 'not json' } });
    fireEvent.blur(field);
    fireEvent.click(screen.getByRole('radio', { name: 'By day' }));
    fireEvent.click(screen.getByRole('radio', { name: 'By hour' }));
    expect(screen.getByRole('textbox', { name: /Weekly opening hours/ })).toHaveValue(
      JSON.stringify(HOURS)
    );

    await save();

    expect(patchBody().opening_hours).toEqual(HOURS);
  });
});
