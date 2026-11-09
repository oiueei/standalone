import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';

window.scrollTo = vi.fn();

const navigate = vi.fn();
vi.mock('react-router', async () => ({
  ...(await vi.importActual('react-router')),
  useNavigate: () => navigate,
}));

// Keep the real `extractApiError` — the 400 tests below feed it real response
// bodies and check the message it pulls out reaches the toast.
vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
  getCsrfToken: () => 'tok',
}));

vi.mock('../hooks/useCollectionLanguage', () => ({ default: vi.fn() }));

import { apiFetch } from '../services/api';
import useCollectionLanguage from '../hooks/useCollectionLanguage';
import EditCollectionPage from './EditCollectionPage';
import { dropHdsStyles } from '../test/dropHdsStyles';
import { settle } from '../test/settle';
import en from '../i18n/locales/en.json';
import es from '../i18n/locales/es.json';
import ca from '../i18n/locales/ca.json';

// `collectionForm.test.jsx` covers the shape of this form (which fields are
// visible, the pause section). These cover what
// hangs off the save: a save the backend refuses because narrowing the type
// list would orphan things. The downloads (calendar,
// stats, the whole collection) live in the collection menu now
// (`collectionMenu.test.jsx`); this page offers none.

const COLLECTION = {
  code: 'COL001',
  is_curator: true,
  headline: 'Kitchen Collection',
  description: 'Things from the kitchen',
  mode: 'PROPRIETARY',
  status: 'ACTIVE',
  visibility: 'PRIVATE',
  owner: 'USR001', // matches the userCode set in beforeEach — the viewer is the founder
  // A library: the kind whose form has all of what the notes and the rental rules
  // below hang from (a stall has no request page, a shed has its own rules).
  kind: 'LIBRARY',
  allowed_thing_types: ['LEND_THING', 'RENT_THING'],
  rental_durations: [],
  rental_weekdays: [],
  tags: [],
  is_paused: false,
};

function mockApi({ save = { ok: true } } = {}) {
  apiFetch.mockImplementation((url, opts) => {
    if (opts?.method === 'PATCH') {
      return Promise.resolve({
        ok: save.ok,
        status: save.status ?? (save.ok ? 200 : 400),
        json: async () => save.body ?? {},
      });
    }
    return Promise.resolve({ ok: true, status: 200, json: async () => COLLECTION });
  });
}

const renderPage = () =>
  render(
    <MemoryRouter initialEntries={['/collections/COL001/edit']}>
      <Routes>
        <Route path="/collections/:code/edit" element={<EditCollectionPage />} />
      </Routes>
    </MemoryRouter>
  );

beforeEach(() => {
  dropHdsStyles(); // ByRole queries cost ~10x less without them; see the helper
  localStorage.clear();
  localStorage.setItem('userCode', 'USR001');
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

describe('EditCollectionPage — saving', () => {
  test('a successful save returns to the collection', async () => {
    mockApi();
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalledWith('/collections/COL001'));
  });

  test('a narrowing that would orphan things shows which types, not "Error saving"', async () => {
    // The backend refuses to drop a type while things of that type still live
    // here, and its message names them. Swallowing it for a generic error would
    // leave the owner with a save that fails and nothing to act on — they can't
    // guess which of four types is the blocker.
    mockApi({
      save: {
        ok: false,
        status: 400,
        body: { non_field_errors: ['Remove the LEND_THING items first: 3 would be orphaned.'] },
      },
    });
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');
    navigate.mockClear();

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(
      await screen.findByText('Remove the LEND_THING items first: 3 would be orphaned.')
    ).toBeInTheDocument();
    expect(screen.queryByText('Error saving.')).toBeNull();
    expect(navigate).not.toHaveBeenCalled();
  });

  test('a refusal the server coded is said in the reader’s language, not in its English', async () => {
    mockApi({
      save: {
        ok: false,
        status: 400,
        body: {
          non_field_errors: [
            'Cannot restrict the allowed types: existing things would be orphaned.',
          ],
          code: 'priced_things_remain',
        },
      },
    });
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText(en.requestErrors.priced_things_remain)).toBeInTheDocument();
    expect(screen.queryByText(/would be orphaned/)).toBeNull();
  });

  test('a 400 with a DRF `detail` is surfaced the same way', async () => {
    mockApi({ save: { ok: false, status: 400, body: { detail: 'That headline is too long.' } } });
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('That headline is too long.')).toBeInTheDocument();
  });

  test('a 400 with nothing readable in it still says something', async () => {
    mockApi({ save: { ok: false, status: 400, body: {} } });
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Error saving.')).toBeInTheDocument();
  });

  test('a rate-limited save says "too many", not "error"', async () => {
    mockApi({ save: { ok: false, status: 429 } });
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText(/[Tt]oo many/)).toBeInTheDocument();
  });

  test('the PATCH carries exactly the six fields of this page', async () => {
    mockApi();
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');
    await settle(apiFetch);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    const [, patch] = apiFetch.mock.calls.find(([, o]) => o?.method === 'PATCH');
    const body = JSON.parse(patch.body);
    // The boundary of the page: what a settings page owns is never sent from here, so
    // saving this form cannot reset a logo, a language, a welcome PDF or a rule.
    expect(Object.keys(body).sort()).toEqual([
      'allowed_thing_types',
      'description',
      'headline',
      'mode',
      'status',
      'visibility',
    ]);
    expect(body).toEqual({
      headline: 'Kitchen Collection',
      description: 'Things from the kitchen',
      status: 'ACTIVE',
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
      allowed_thing_types: ['LEND_THING', 'RENT_THING'],
    });
  });

  test('a shed saves as PROPRIETARY with its one verb and none of its rules', async () => {
    const shed = { ...COLLECTION, kind: 'SHED', allowed_thing_types: ['RESERVE_THING'] };
    apiFetch.mockImplementation((url, opts) =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => (opts?.method === 'PATCH' ? {} : shed),
      })
    );
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');
    await settle(apiFetch);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(navigate).toHaveBeenCalled());
    const [, patch] = apiFetch.mock.calls.find(([, o]) => o?.method === 'PATCH');
    const body = JSON.parse(patch.body);
    expect(body).toMatchObject({ mode: 'PROPRIETARY', allowed_thing_types: ['RESERVE_THING'] });
    expect(body).not.toHaveProperty('reservation_unit');
  });

  test('the tab says General settings of the collection once it is known, and General settings before', async () => {
    apiFetch.mockImplementation(() => new Promise(() => {}));
    const pending = renderPage();
    expect(document.title).toBe('General settings — OIUEEI');
    pending.unmount();

    mockApi();
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');
    expect(document.title).toBe('General settings of Kitchen Collection — OIUEEI');
  });

  test('the three titles of the page are fixed in the three languages', () => {
    expect([es, ca, en].map((l) => l.editCollection.pageTitle)).toEqual([
      'General',
      'General',
      'General',
    ]);
    expect([es, ca, en].map((l) => l.titles.editCollection)).toEqual([
      'Ajustes generales de {{headline}} — OIUEEI',
      'Configuració general de {{headline}} — OIUEEI',
      'General settings of {{headline}} — OIUEEI',
    ]);
    expect([es, ca, en].map((l) => l.titles.editCollectionDefault)).toEqual([
      'Ajustes generales — OIUEEI',
      'Configuració general — OIUEEI',
      'General settings — OIUEEI',
    ]);
    expect([es, ca, en].map((l) => l.collectionSettings.general)).toEqual([
      'General',
      'General',
      'General',
    ]);
  });

  test('nothing reads the old button’s words any more', () => {
    for (const l of [es, ca, en]) expect(l.collectionPage).not.toHaveProperty('editCollection');
  });

  test('the shape of the page: a notice, the title, the description and the state, then mode and visibility', async () => {
    mockApi();
    const { container } = renderPage();
    await screen.findByDisplayValue('Kitchen Collection');

    expect(screen.getByRole('heading', { level: 1, name: 'General' })).toBeVisible();
    expect(screen.getByText(/Write in one language only if you prefer/)).toBeVisible();
    expect(screen.getByRole('heading', { level: 2, name: 'Visibility' })).toBeVisible();
    expect(screen.queryByRole('button', { name: 'More options' })).toBeNull();
    for (const field of ['thumbnail', 'welcome-doc', 'digest', 'language', 'home-page']) {
      expect(container.querySelector(`[id="edit-collection-${field}"]`), field).toBeNull();
    }
  });

  test('a collection that cannot be read gives no form, so there is nothing to save', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({ ok: false, status: 500, json: async () => ({}) })
    );
    renderPage();

    expect(await screen.findByText(en.editCollection.errorLoading)).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).toBeNull();
    expect(apiFetch.mock.calls.some(([, o]) => o?.method === 'PATCH')).toBe(false);
  });
});

describe('EditCollectionPage — useCollectionLanguage gets the saved value, never the typed one', () => {
  // The page follows the collection's stored language and its texts as saved: rewriting the
  // title (into another language, say) must not move the page's own language under the hands.
  test('rewriting the title does not change what the hook is called with', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ ...COLLECTION, language: 'ca' }),
      })
    );
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');
    const SAVED_TEXTS = ['Kitchen Collection', 'Things from the kitchen'];
    await waitFor(() => expect(useCollectionLanguage).toHaveBeenLastCalledWith('ca', SAVED_TEXTS));

    fireEvent.change(screen.getByDisplayValue('Kitchen Collection'), {
      target: { value: '{"es": "Cocina", "en": "Kitchen"}' },
    });

    expect(useCollectionLanguage).toHaveBeenLastCalledWith('ca', SAVED_TEXTS);
  });
});

describe('EditCollectionPage — the delete button', () => {
  // Save, pause, stats and export carry no client-side gate at all — the
  // server has always been the only thing that decides, and a co-owner
  // reaching this page now succeeds at every one of them exactly as the
  // founder would. Delete stays the one exception: never a co-owner power,
  // so it isn't worth showing a control the server would 403.
  test('the founder sees it', async () => {
    mockApi();
    renderPage();

    expect(await screen.findByRole('button', { name: 'Delete' })).toBeInTheDocument();
    await settle(apiFetch);
  });

  test('a co-owner reaching this page does not see it', async () => {
    apiFetch.mockImplementation(() =>
      Promise.resolve({
        ok: true,
        status: 200,
        json: async () => ({ ...COLLECTION, owner: 'FOUNDER1' }),
      })
    );
    renderPage();

    await screen.findByDisplayValue('Kitchen Collection');
    expect(screen.queryByRole('button', { name: 'Delete' })).not.toBeInTheDocument();
  });
});

describe('EditCollectionPage — no downloads', () => {
  // The calendar, the stats and the whole-collection export left the foot of
  // this page for the collection menu, with the two notes that
  // went with them. A page that offered them again would be a second place to
  // run the group's data from, which is what the move was for.
  test('the page offers no download, and asks for no file', async () => {
    mockApi();
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');
    await settle(apiFetch);

    expect(screen.queryByRole('button', { name: /download/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('link', { name: /download/i })).not.toBeInTheDocument();
    const asked = apiFetch.mock.calls.map(([url]) => url);
    expect(asked.filter((url) => /\/(stats|export|calendar-export)\//.test(url))).toEqual([]);
  });
});

describe('EditCollectionPage — a deployment that has narrowed since', () => {
  /* A collection opened while COMMUNITY was on offer, on a deployment that has
     since stopped handing it out. The server judges only a **change**, so this
     owner may still save it as it stands — and the form has to keep saying so.

     The bug this pins: the filter keyed on the live `mode` state rather than
     the stored one, so the moment the owner clicked the other radio to compare,
     COMMUNITY stopped being "current", failed `isOfferable`, and unmounted.
     There was then no way back to the mode the collection was actually in
     without reloading the page — a form that had quietly become unable to
     express the row it was editing. Invisible upstream, where nothing is
     withheld, which is exactly why it needs a test. */
  const COMMUNITY_COLLECTION = { ...COLLECTION, mode: 'COMMUNITY' };

  function mockNarrowedApi() {
    apiFetch.mockImplementation((url) => {
      if (url.includes('/auth/me/')) {
        return Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            capabilities: {
              collection_modes: ['PROPRIETARY'],
              thing_types: ['GIFT_THING', 'SELL_THING'],
              request_url: 'https://your-domain.test/request-access/',
            },
          }),
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: async () => COMMUNITY_COLLECTION });
    });
  }

  beforeEach(() => {
    // The capabilities cache is module-scope and keyed by account; a fresh code
    // keeps these independent of the tests above without a reset export.
    localStorage.setItem('userCode', `NARROW${Math.random()}`);
    mockNarrowedApi();
  });

  test('the stored mode stays on offer after the owner tries the other one', async () => {
    renderPage();
    await screen.findByDisplayValue('Kitchen Collection');

    const community = () => screen.queryByRole('radio', { name: /community/i });
    // It is offered to begin with, because the collection is in it.
    await waitFor(() => expect(community()).not.toBeNull());

    // The owner compares: clicks the mode the deployment does allow...
    fireEvent.click(screen.getByRole('radio', { name: /just mine|proprietary/i }));

    // ...and can still change their mind. This is the assertion that failed.
    expect(community()).not.toBeNull();
    fireEvent.click(community());
    expect(community()).toBeChecked();
  });
});

/**
 * Pausing is what stops every new request in the group, and resuming is what lets
 * them in again: both are their own PATCH of `pause_message`, apart from Save.
 * `collectionForm.test.jsx` pins which controls show in each state; these press them.
 */
describe('EditCollectionPage — pausing and resuming', () => {
  const pauseCalls = () =>
    apiFetch.mock.calls.filter(
      (c) => c[1]?.method === 'PATCH' && 'pause_message' in JSON.parse(c[1].body)
    );

  function mockPausable({ collection = COLLECTION, patch } = {}) {
    apiFetch.mockImplementation((url, opts) => {
      if (opts?.method === 'PATCH') return patch();
      return Promise.resolve({ ok: true, status: 200, json: async () => collection });
    });
  }

  const ok = () => Promise.resolve({ ok: true, status: 200, json: async () => ({}) });

  // The page is loaded when the form is there *and* what it asked for on mounting
  // (the deployment's capabilities, for the mode notice) has answered: that answer
  // sets state a moment later, and a test that ends first leaves it outside `act`.
  async function renderLoaded(findControl) {
    renderPage();
    const control = await findControl();
    await settle(apiFetch);
    return control;
  }

  test('nothing can be paused without a message for the members', async () => {
    mockPausable({ patch: ok });
    const pause = await renderLoaded(() =>
      screen.findByRole('button', { name: 'Pause collection' })
    );

    expect(pause).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Message to members'), { target: { value: '   ' } });
    expect(pause).toBeDisabled();
    fireEvent.change(screen.getByLabelText('Message to members'), {
      target: { value: 'Back in a week' },
    });
    expect(pause).toBeEnabled();
  });

  test('pausing sends the message alone, trimmed, and shows it as the members will', async () => {
    mockPausable({ patch: ok });
    fireEvent.change(await renderLoaded(() => screen.findByLabelText('Message to members')), {
      target: { value: '  Back in a week  ' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Pause collection' }));

    expect(await screen.findByText('Collection paused.')).toBeInTheDocument();
    expect(pauseCalls()).toHaveLength(1);
    const [url, opts] = pauseCalls()[0];
    expect(url).toBe('/api/v1/collections/COL001/');
    // Only the pause: an unsaved edit elsewhere on the form must not ride along.
    expect(JSON.parse(opts.body)).toEqual({ pause_message: 'Back in a week' });
    expect(screen.getByText('Back in a week').tagName).toBe('BLOCKQUOTE');
    expect(screen.getByRole('button', { name: 'Resume collection' })).toBeEnabled();
    expect(screen.queryByLabelText('Message to members')).toBeNull();
  });

  test('resuming clears the message and offers an empty field again', async () => {
    mockPausable({
      collection: { ...COLLECTION, is_paused: true, pause_message: 'Back in a week' },
      patch: ok,
    });
    fireEvent.click(
      await renderLoaded(() => screen.findByRole('button', { name: 'Resume collection' }))
    );

    expect(await screen.findByText('Collection resumed.')).toBeInTheDocument();
    expect(JSON.parse(pauseCalls()[0][1].body)).toEqual({ pause_message: '' });
    expect(screen.getByLabelText('Message to members')).toHaveValue('');
    expect(screen.getByRole('button', { name: 'Pause collection' })).toBeDisabled();
  });

  test.each([
    [
      'a refusal',
      () => Promise.resolve({ ok: false, status: 400, json: async () => ({}) }),
      'Error',
    ],
    ['a dropped connection', () => Promise.reject(new TypeError('offline')), 'Connection error.'],
  ])('%s leaves the group open and says so', async (_label, patch, message) => {
    mockPausable({ patch });
    fireEvent.change(await renderLoaded(() => screen.findByLabelText('Message to members')), {
      target: { value: 'Back in a week' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Pause collection' }));

    expect(await screen.findByRole('alert')).toHaveTextContent(message);
    expect(screen.queryByText('Collection paused.')).toBeNull();
    expect(screen.getByRole('button', { name: 'Pause collection' })).toBeEnabled();
    expect(screen.getByLabelText('Message to members')).toHaveValue('Back in a week');
  });
});
