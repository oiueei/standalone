import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { axe, toHaveNoViolations } from 'jest-axe';
import { vi, describe, test, expect, beforeEach } from 'vitest';

expect.extend(toHaveNoViolations);

window.scrollTo = vi.fn();

const navigateSpy = vi.fn();
vi.mock('react-router', async () => {
  const actual = await vi.importActual('react-router');
  return { ...actual, useNavigate: () => navigateSpy };
});

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch, extractApiError } from '../services/api';
import EditProfilePage from '../pages/EditProfilePage';

const PROFILE = {
  name: 'Lili',
  headline: 'Lends a drill',
  about: 'Long-time neighbour.',
  language: 'en',
  age_range: 'GEN_X',
  postal_code: '08038',
  notify_activity: true,
  notify_news: false,
};

const res = (data, { ok = true, status = 200 } = {}) =>
  Promise.resolve({ ok, status, json: () => Promise.resolve(data) });

/** Loads fine; `save` decides what the PUT answers. */
function setApi({ save = () => res({}), profile = PROFILE, profileOk = true } = {}) {
  apiFetch.mockImplementation((url, options) => {
    if (url === '/api/v1/auth/me/')
      return res(profile, { ok: profileOk, status: profileOk ? 200 : 500 });
    if (url === '/api/v1/theeemes/') return res([]);
    if (options?.method === 'PUT') return save();
    return res({});
  });
}

function renderPage(state) {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/me/edit', state }]}>
      <Routes>
        <Route path="/me/edit" element={<EditProfilePage />} />
      </Routes>
    </MemoryRouter>
  );
}

const save = () => fireEvent.click(screen.getByRole('button', { name: /save/i }));
const putBody = () => JSON.parse(apiFetch.mock.calls.find(([, o]) => o?.method === 'PUT')[1].body);
const putCalls = () => apiFetch.mock.calls.filter(([, o]) => o?.method === 'PUT');

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  // `resetAllMocks` would drop the `extractApiError` default too, and every test
  // here re-installs `apiFetch` anyway; clearing keeps the recorded calls out of
  // each other's way without disarming the module mock.
  vi.clearAllMocks();
  extractApiError.mockResolvedValue('');
  setApi();
});

/**
 * The profile form was carrying one behavioural test (the language Select)
 * and the generic axe smoke pass, which left validation, the payload and every
 * error path unguarded on the page that holds a person's name, bio and the two
 * demographic fields. These name what the page owes its user.
 */
describe('EditProfilePage — the limits the database also enforces', () => {
  // SQLite (local) ignores CharField(max_length); Postgres (CI and production)
  // does not. A value that gets past this client-side check is a 500 at the far
  // end, so these three limits are the only thing standing between a long name
  // and a broken save.
  test.each([
    ['name', /name/i, 33, 'Maximum 32 characters.'],
    ['bio headline', /bio/i, 65, 'Maximum 64 characters.'],
    ['about text', /about/i, 2001, 'Maximum 2000 characters.'],
  ])(
    "an over-long %s blocks the save and names that field's own limit",
    async (_label, labelRe, length, message) => {
      renderPage();
      const field = await screen.findByLabelText(labelRe);

      fireEvent.change(field, { target: { value: 'x'.repeat(length) } });
      save();

      // The exact message, not just "an error": all three fields refuse in the
      // same place, so a check that any error appeared would still pass if the
      // name rule fired for an over-long bio.
      await waitFor(() => expect(screen.getByText(message)).toBeInTheDocument());
      // Nothing was sent: the point of validating is to not make the request.
      expect(putCalls()).toHaveLength(0);
    }
  );

  test('a value exactly on the limit is accepted, not rejected', async () => {
    renderPage();
    const field = await screen.findByLabelText(/name/i);

    // Off-by-one guard: the check is `> 32`, so 32 must pass. Written as its own
    // test because a `>=` slip passes every "too long is refused" test there is.
    fireEvent.change(field, { target: { value: 'x'.repeat(32) } });
    save();

    await waitFor(() => expect(putCalls()).toHaveLength(1));
    expect(putBody().name).toHaveLength(32);
  });

  test('fixing the field clears the error and lets the save through', async () => {
    renderPage();
    const field = await screen.findByLabelText(/name/i);

    fireEvent.change(field, { target: { value: 'x'.repeat(40) } });
    save();
    await waitFor(() => expect(screen.getByText('Maximum 32 characters.')).toBeInTheDocument());

    // A validation error that never clears strands the user on a form that
    // refuses to submit with no way to tell they have fixed it.
    fireEvent.change(field, { target: { value: 'Lili' } });
    save();
    await waitFor(() => expect(putCalls()).toHaveLength(1));
    expect(screen.queryByText('Maximum 32 characters.')).not.toBeInTheDocument();
  });
});

describe('EditProfilePage — what the save actually sends', () => {
  test('the edited profile is sent trimmed, to this user, as a PUT', async () => {
    renderPage();
    const name = await screen.findByLabelText(/name/i);
    fireEvent.change(name, { target: { value: '  Lili Renamed  ' } });

    save();

    await waitFor(() => expect(putCalls()).toHaveLength(1));
    const [url, options] = putCalls()[0];
    expect(url).toBe('/api/v1/users/ABC123/');
    expect(options.method).toBe('PUT');
    // Trimmed, or a stray space silently becomes part of the person's name.
    expect(putBody().name).toBe('Lili Renamed');
  });

  test('the demographic fields the profile loaded are sent back unchanged', async () => {
    renderPage();
    await screen.findByDisplayValue('Lili');

    save();

    await waitFor(() => expect(putCalls()).toHaveLength(1));
    // These two are the only demographic data OIUEEI holds. A save that dropped
    // them would quietly erase what the user had already given.
    expect(putBody()).toMatchObject({ age_range: 'GEN_X', postal_code: '08038' });
  });

  test('an unset theeeme is left out of the payload rather than sent empty', async () => {
    renderPage();
    await screen.findByDisplayValue('Lili');

    save();

    await waitFor(() => expect(putCalls()).toHaveLength(1));
    // `if (theeeme) body.theeeme = theeeme` — sending `theeeme: ''` is a
    // different request from not sending the key, and the serializer treats it
    // as an attempt to blank the relation.
    expect(putBody()).not.toHaveProperty('theeeme');
  });

  test('a successful save returns the user home', async () => {
    renderPage();
    await screen.findByDisplayValue('Lili');

    save();

    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/'));
  });

  test('a save returns the person to the page that sent them, when it said which', async () => {
    renderPage({ backPath: '/library/COL001/things/THG001', backLabel: 'Drill' });
    await screen.findByDisplayValue('Lili');

    save();

    await waitFor(() => expect(navigateSpy).toHaveBeenCalledWith('/library/COL001/things/THG001'));
    expect(navigateSpy).not.toHaveBeenCalledWith('/');
  });
});

describe('EditProfilePage — when the save is refused', () => {
  test('a rate-limited save says so instead of blaming the form', async () => {
    setApi({ save: () => res({}, { ok: false, status: 429 }) });
    renderPage();
    await screen.findByDisplayValue('Lili');

    save();

    // The exact copy, not merely "an error appeared": falling through to the
    // generic "Error saving." also raises an alert, so anything vaguer passes
    // whether or not 429 is handled at all — and tells a rate-limited user that
    // their details are wrong.
    await waitFor(() =>
      expect(
        screen.getByText('Too many attempts — please wait a moment and try again.')
      ).toBeInTheDocument()
    );
    expect(screen.queryByText('Error saving.')).not.toBeInTheDocument();
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  test("a refused save surfaces the server's own reason", async () => {
    setApi({ save: () => res({ name: ['That name is taken.'] }, { ok: false, status: 400 }) });
    extractApiError.mockResolvedValue('That name is taken.');
    renderPage();
    await screen.findByDisplayValue('Lili');

    save();

    await waitFor(() => expect(screen.getByText('That name is taken.')).toBeInTheDocument());
  });

  test('a refused save with no usable body still says something', async () => {
    setApi({ save: () => res({}, { ok: false, status: 400 }) });
    extractApiError.mockResolvedValue(null);
    renderPage();
    await screen.findByDisplayValue('Lili');

    save();

    // Pinned to the fallback copy: this branch exists only for the case where
    // the server said nothing usable, so "some alert appeared" would pass even
    // if the detail path had swallowed it.
    await waitFor(() => expect(screen.getByText('Error saving.')).toBeInTheDocument());
    expect(navigateSpy).not.toHaveBeenCalled();
  });

  test('a dropped connection says so rather than hanging on "Saving…"', async () => {
    setApi({ save: () => Promise.reject(new Error('offline')) });
    renderPage();
    await screen.findByDisplayValue('Lili');

    save();

    await waitFor(() => expect(screen.getByText('Connection error.')).toBeInTheDocument());
    // The button has to come back, or a network blip costs the user the form.
    expect(screen.getByRole('button', { name: /save/i })).not.toBeDisabled();
  });
});

describe('EditProfilePage — when the profile will not load', () => {
  test('a failed load still renders the form instead of spinning forever', async () => {
    setApi({ profileOk: false });
    renderPage();

    // `finally { setLoading(false) }` is what makes this true; without it the
    // page is a permanent spinner with an error nobody can see.
    await waitFor(() => expect(screen.getByText('Error loading profile.')).toBeInTheDocument());
    expect(screen.getByRole('button', { name: /save/i })).toBeInTheDocument();
  });
});

describe('EditProfilePage — the two exits', () => {
  test('the download-your-data link comes before the delete-account link', async () => {
    renderPage();
    await screen.findByDisplayValue('Lili');

    const download = screen.getByRole('link', { name: /data/i });
    const del = screen.getByRole('link', { name: /delete/i });
    expect(download).toHaveAttribute('href', '/me/data');
    expect(del).toHaveAttribute('href', '/me/delete');

    // Deliberate order, not incidental layout: reading your own copy before
    // erasing it is the sane sequence and the legally solid one, and the page
    // comment says so. A refactor that reorders these inverts that.
    expect(download.compareDocumentPosition(del) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });
});

/**
 * The palette is a collection's, chosen by its curators in the collection's own form;
 * the profile has neither a palette nor a koro to pick, reads no list of palettes and
 * sends nothing of them.
 */
describe('EditProfilePage — no palette and no koro', () => {
  test('offers neither selector and does not ask for the list of palettes', async () => {
    renderPage();
    await screen.findByLabelText(/name/i);

    expect(screen.queryByText('Theeeme')).not.toBeInTheDocument();
    expect(screen.queryByText('Koro')).not.toBeInTheDocument();
    expect(screen.queryByRole('group', { name: /theeeme|koro/i })).not.toBeInTheDocument();
    expect(apiFetch.mock.calls.some(([url]) => url === '/api/v1/theeemes/')).toBe(false);
  });

  test('the save carries neither a koro nor a theeeme, even for a profile that still has them', async () => {
    setApi({ profile: { ...PROFILE, koro: 'wave', theeeme: 'BUU331' } });
    renderPage();
    await screen.findByLabelText(/name/i);

    save();

    await waitFor(() => expect(putCalls()).toHaveLength(1));
    expect(putBody()).not.toHaveProperty('theeeme');
    expect(putBody()).not.toHaveProperty('koro');
  });
});

describe('EditProfilePage — what the demographic fields say about who sees them', () => {
  test('it says the team sees them added up, never yours alone, and that they are never public', async () => {
    renderPage();
    await screen.findByDisplayValue('Lili');

    expect(screen.getByText(/Whoever runs your groups sees it in their stats/)).toBeInTheDocument();
    expect(screen.getByText(/never yours alone/)).toBeInTheDocument();
    expect(screen.getByText(/Never public\./)).toBeInTheDocument();
    expect(screen.queryByText(/Only owners of the groups/)).toBeNull();
  });
});

describe('EditProfilePage — the notice for minors under the birth year', () => {
  const NOTICE = /if you are a minor/i;

  async function pickGeneration(name) {
    const combobox = await screen.findByRole('combobox', { name: /birth year/i });
    fireEvent.click(combobox);
    fireEvent.click(await screen.findByRole('option', { name }));
  }

  test.each(['GEN_A', 'GEN_B'])(
    '%s shows the notice with a link to the legal page',
    async (age) => {
      setApi({ profile: { ...PROFILE, age_range: age } });
      renderPage();

      expect(await screen.findByText(NOTICE)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: 'legal page' })).toHaveAttribute('href', '/legal');
    }
  );

  test.each(['GEN_Z', ''])('"%s" shows no notice', async (age) => {
    setApi({ profile: { ...PROFILE, age_range: age } });
    renderPage();

    await screen.findByRole('combobox', { name: /birth year/i });
    expect(screen.queryByText(NOTICE)).not.toBeInTheDocument();
  });

  test('the notice goes away when another generation is chosen', async () => {
    setApi({ profile: { ...PROFILE, age_range: 'GEN_A' } });
    renderPage();
    expect(await screen.findByText(NOTICE)).toBeInTheDocument();

    await pickGeneration(/Generation X/);

    await waitFor(() => expect(screen.queryByText(NOTICE)).not.toBeInTheDocument());
  });

  test('has no accessibility violations with the notice showing', async () => {
    setApi({ profile: { ...PROFILE, age_range: 'GEN_A' } });
    const { container } = renderPage();
    await screen.findByText(NOTICE);

    expect(await axe(container)).toHaveNoViolations();
  });

  test('saving as GEN_A sends it unchanged: the notice does not block', async () => {
    setApi({ profile: { ...PROFILE, age_range: 'GEN_A' } });
    renderPage();
    await screen.findByText(NOTICE);

    save();

    await waitFor(() => expect(putCalls()).toHaveLength(1));
    expect(putBody().age_range).toBe('GEN_A');
  });
});
