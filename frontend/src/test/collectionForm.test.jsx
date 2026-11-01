import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import { axe, toHaveNoViolations } from 'jest-axe';

expect.extend(toHaveNoViolations);

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  ),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch, extractApiError } from '../services/api';
import CreateCollectionPage from '../pages/CreateCollectionPage';
import EditCollectionPage from '../pages/EditCollectionPage';
import { dropHdsStyles } from './dropHdsStyles';
import { settle } from './settle';
import en from '../i18n/locales/en.json';
import declarePalette from './declarePalette';

// This file is about what a deployment with no forms of its own hosted elsewhere shows
// — the app's own contact page, `VITE_FEEDBACK_URL`, the server's request address. A
// core test cannot assume what `deployment/` holds, so the
// `externalForms` a deployment may have are switched off here by stubbing the helper
// that reads them; `externalForms.test.jsx` pins them on, with the module mocked.
vi.mock('../utils/externalForms', () => ({ externalFormUrl: () => null }));
// The pages a deployment may send "Request access" to (`requestAccessPaths`) are switched
// off the same way: this file pins what the standalone shows, whatever `deployment/` holds.
vi.mock('../deployment', async (orig) => ({ ...(await orig()), requestAccessPaths: {} }));

function mockResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

// `collection` feeds EditCollectionPage's load fetch; Create POSTs, Edit PATCHes.
function setApi({ collection = {} } = {}) {
  apiFetch.mockImplementation((url, opts = {}) => {
    const method = opts.method || 'GET';
    if (url === '/api/v1/collections/' && method === 'POST')
      return Promise.resolve(mockResponse({ code: 'NEW001', kind: 'STALL' }));
    if (/\/collections\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(collection));
    return Promise.resolve(mockResponse({}));
  });
}

// A collection's form is the one for its kind, and the kind is in the address:
// `/stall/new`, `/library/new`, `/shed/new`.
// The create page asks the deployment what it allows before it shows anything, so the
// form is there a moment after the render: the helper hands it back once it is.
async function formShown(view) {
  await waitFor(() =>
    expect(view.container.querySelector('#create-collection-headline')).toBeInTheDocument()
  );
  await settle(apiFetch);
  return view;
}

async function renderCreate(kind = 'stall') {
  setApi();
  const view = render(
    <MemoryRouter initialEntries={[`/${kind}/new`]}>
      <Routes>
        <Route path="/:kind/new" element={<CreateCollectionPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
  // A prefix that is no kind has no form to wait for: it is sent to the chooser.
  return kind === 'collections' ? view : formShown(view);
}

// What the server serves with a collection: its kind, which these older fixtures
// leave out, follows from the verbs they list.
const KIND_OF_VERB = {
  GIFT_THING: 'STALL',
  SELL_THING: 'STALL',
  LEND_THING: 'LIBRARY',
  RENT_THING: 'LIBRARY',
  RESERVE_THING: 'SHED',
};
const withKind = (collection) => ({
  kind: KIND_OF_VERB[collection.allowed_thing_types?.[0]] || 'STALL',
  ...collection,
});

async function renderEdit(collection) {
  collection = withKind(collection);
  setApi({ collection });
  const view = render(
    <MemoryRouter initialEntries={['/collections/COL001/edit']}>
      <Routes>
        <Route path="/collections/:code/edit" element={<EditCollectionPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
  await settle(apiFetch);
  return view;
}

beforeEach(() => {
  dropHdsStyles(); // ByRole queries cost ~10x less without them; see the helper
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
  localStorage.setItem('koro', 'basic');
  vi.clearAllMocks();
  setApi();
});

// ════════════════════════════════════════════════════════════════════════
// CreateCollectionPage — mode-gated toggles + submit
// ════════════════════════════════════════════════════════════════════════
describe('CreateCollectionPage', () => {
  test('PROPRIETARY (default): no album-mode toggle', async () => {
    await renderCreate();

    expect(screen.queryByRole('button', { name: /Album mode/ })).toBeNull();
  });

  // The mode picker is a radio group whose labels carry the title and its explanation in
  // one line, so the accessible name of each radio says both; no paragraph of its own.
  test('mode radios carry title and explanation in their name', async () => {
    const { container } = await renderCreate();

    expect(
      screen.getByRole('radio', {
        name: 'Proprietary: Only the team running the group adds things — you, to start with.',
      })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('radio', {
        name: 'Community: Every member can add their own things too.',
      })
    ).toBeInTheDocument();
    expect(container.querySelector('[aria-describedby$="-desc"]')).toBeNull();
  });

  test('the visibility switch is named by its title and its explanation together', async () => {
    const { container } = await renderCreate();

    expect(
      screen.getByRole('button', {
        name: 'Public collection: Anyone with the link can view it and join to take part. Turn off to keep it invite-only.',
      })
    ).toBeInTheDocument();
    expect(container.querySelector('#create-collection-visibility-help')).toBeNull();
  });

  // The mode radio does not decide who can read the group — only the switch does.
  // Community used to turn the switch on by itself, and again on
  // every re-choice even after the curator had switched it off; but whoever
  // contributes to a group is never shown whether it is public, so a group of
  // neighbours' families ended up readable by anyone without its members knowing.
  // Making a group public is now a deliberate act, in either mode.
  test('choosing a mode leaves the group private: only the switch changes that', async () => {
    const { container } = await renderCreate();
    const visibility = () => container.querySelector('#create-collection-visibility');

    expect(visibility()).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(screen.getByRole('radio', { name: /^Community:/ }));
    expect(visibility()).toHaveAttribute('aria-pressed', 'false');

    fireEvent.click(visibility());
    expect(visibility()).toHaveAttribute('aria-pressed', 'true');

    // What the curator chose survives a change of mode (it used to go private)…
    fireEvent.click(screen.getByRole('radio', { name: /^Proprietary:/ }));
    expect(visibility()).toHaveAttribute('aria-pressed', 'true');

    // …and a switch they turned off stays off when Community is chosen again (it
    // used to come back on).
    fireEvent.click(visibility());
    fireEvent.click(screen.getByRole('radio', { name: /^Community:/ }));
    expect(visibility()).toHaveAttribute('aria-pressed', 'false');
  });

  // Public is a decision, and it has to survive to the POST.
  test('a Community group the curator switched to public ships as COMMUNITY and PUBLIC', async () => {
    const { container } = await renderCreate();
    await fillTheRequiredFields(container, 'An open community');

    fireEvent.click(screen.getByRole('radio', { name: /^Community:/ }));
    fireEvent.click(container.querySelector('#create-collection-visibility'));
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createBody()?.visibility).toBe('PUBLIC'));
    expect(createBody()?.mode).toBe('COMMUNITY');
  });

  test('a Community group whose switch was never touched ships as PRIVATE', async () => {
    const { container } = await renderCreate();
    await fillTheRequiredFields(container, 'A quiet community');

    fireEvent.click(screen.getByRole('radio', { name: /^Community:/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createBody()?.visibility).toBe('PRIVATE'));
    expect(createBody()?.mode).toBe('COMMUNITY');
  });

  // The optional fields (thumbnail, welcome doc, tags, language, rental rules)
  // fold into a "More options" accordion, closed on load, so the happy path is
  // just title + mode + who-can-add. Nothing inside it is required or can block
  // submit, so the form is still completable without ever opening it.
  test('optional fields stay hidden until "More options" is opened', async () => {
    const { container } = await renderCreate();

    const thumb = () => container.querySelector('#create-collection-thumbnail');
    expect(thumb()).not.toBeVisible();
    expect(container.querySelector('#create-collection-welcome-doc')).not.toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: 'More options' }));

    await waitFor(() => expect(thumb()).toBeVisible());
    expect(container.querySelector('#create-collection-welcome-doc')).toBeVisible();
  });

  // The Create form used to omit the digest field entirely. That was survivable
  // while `digest_frequency` defaulted to NONE; it stopped being survivable when
  // the default became non-empty, because a group now mails its members from the
  // moment it exists. The owner has to see — and be able to change — that at the
  // moment they create it, which is exactly what these two pin.
  test('the digest field is on the Create form, folded into "More options"', async () => {
    const { container } = await renderCreate();

    const digest = () => container.querySelector('#create-collection-digest');
    expect(digest()).not.toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: 'More options' }));

    await waitFor(() => expect(digest()).toBeVisible());
  });

  // The headline is the one thing that can block submit, so this is the shortest
  // path to a valid Create.
  async function fillTheRequiredFields(container, headline) {
    fireEvent.change(container.querySelector('#create-collection-headline'), {
      target: { value: headline },
    });
  }

  const createBody = () => {
    const post = apiFetch.mock.calls.find(
      ([u, o]) => u === '/api/v1/collections/' && o?.method === 'POST'
    );
    return post && JSON.parse(post[1].body);
  };

  test('a new collection is created subscribed to its own digest', async () => {
    const { container } = await renderCreate();
    await fillTheRequiredFields(container, 'The street');

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    // Not "whatever the server defaults to": the value the owner was shown in
    // the form is the value that ships, so the field can never disagree with
    // the row it created.
    await waitFor(() => expect(createBody()?.digest_frequency).toBe('MONTHLY'));
  });

  test('turning the digest off at creation time is honoured', async () => {
    const { container } = await renderCreate();
    await fillTheRequiredFields(container, 'Quiet group');

    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    fireEvent.click(await screen.findByRole('combobox', { name: /Digest emails/ }));
    fireEvent.click(await screen.findByRole('option', { name: 'None' }));
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createBody()?.digest_frequency).toBe('NONE'));
  });

  // The toggle that decides whether members may recommend people at all: the
  // owner's answer to "am I willing to be asked". It has to reach the POST.
  test('the recommend-a-guest setting reaches the create request', async () => {
    const { container } = await renderCreate();
    await fillTheRequiredFields(container, 'Open group');

    fireEvent.click(container.querySelector('#create-collection-allow-proposals'));
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createBody()?.allow_member_proposals).toBe(true));
  });

  // A new collection asks its owner nothing until the owner says
  // so (it used to start ticked). What the owner was shown is what ships.
  test('left alone, a new group does not ask to be asked: it starts off and ships off', async () => {
    const { container } = await renderCreate();
    await fillTheRequiredFields(container, 'Quiet group');

    expect(container.querySelector('#create-collection-allow-proposals')).not.toBeChecked();
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createBody()?.allow_member_proposals).toBe(false));
  });

  test('the home-page URL, folded into "More options", reaches the create request', async () => {
    const { container } = await renderCreate();
    await fillTheRequiredFields(container, 'Ateneu');

    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    const homePage = container.querySelector('#create-collection-home-page');
    await waitFor(() => expect(homePage).toBeVisible());
    fireEvent.change(homePage, { target: { value: '  https://ateneu.example/  ' } });
    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createBody()?.home_page).toBe('https://ateneu.example/'));
  });
});

// ════════════════════════════════════════════════════════════════════════
// CreateCollectionPage — what pressing "Create" leads to
// ════════════════════════════════════════════════════════════════════════
describe('CreateCollectionPage — what pressing "Create" leads to', () => {
  // Where the page sends the reader, read off the router itself.
  function Landed() {
    return <div data-testid="landed">{useLocation().pathname}</div>;
  }

  async function renderCreateWith(postResponse) {
    apiFetch.mockImplementation((url, opts = {}) => {
      if (url === '/api/v1/collections/' && opts.method === 'POST') return postResponse();
      return Promise.resolve(mockResponse({}));
    });
    return formShown(
      render(
        <MemoryRouter initialEntries={['/library/new']}>
          <Routes>
            <Route path="/library/new" element={<CreateCollectionPage />} />
            <Route path="*" element={<Landed />} />
          </Routes>
        </MemoryRouter>
      )
    );
  }

  const typeTheTitle = (container, headline) =>
    fireEvent.change(container.querySelector('#create-collection-headline'), {
      target: { value: headline },
    });

  const posts = () =>
    apiFetch.mock.calls.filter(([u, o]) => u === '/api/v1/collections/' && o?.method === 'POST');

  test('a created collection opens on its own page', async () => {
    const { container } = await renderCreateWith(() =>
      Promise.resolve(mockResponse({ code: 'NEW001', kind: 'LIBRARY' }))
    );
    typeTheTitle(container, 'The street');

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    // At the kind's address, from the kind the server answered with.
    expect(await screen.findByTestId('landed')).toHaveTextContent('/library/NEW001');
  });

  test('a blank title sends nothing and says it is needed', async () => {
    const { container } = await renderCreateWith(() =>
      Promise.resolve(mockResponse({ code: 'X' }))
    );
    typeTheTitle(container, '   ');

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    expect(await screen.findByText('Title is required.')).toBeInTheDocument();
    expect(posts()).toHaveLength(0);
    expect(screen.queryByTestId('landed')).toBeNull();
  });

  // A refusal keeps the page and everything typed in it, says why, and lets the
  // reader press Create again.
  test.each([
    [
      'too many attempts',
      () => Promise.resolve({ ok: false, status: 429, json: () => Promise.resolve({}) }),
      null,
      'Too many attempts — please wait a moment and try again.',
    ],
    [
      'a refusal with a reason gives the server’s reason',
      () => Promise.resolve(mockResponse({}, false)),
      'You already run ten groups.',
      'You already run ten groups.',
    ],
    [
      'a refusal without one gives the page’s own words',
      () => Promise.resolve(mockResponse({}, false)),
      '',
      'Error creating collection.',
    ],
    [
      'a dropped connection',
      () => Promise.reject(new TypeError('offline')),
      null,
      'Connection error.',
    ],
  ])('%s', async (_case, postResponse, serverReason, said) => {
    if (serverReason !== null) extractApiError.mockResolvedValueOnce(serverReason);
    const { container } = await renderCreateWith(postResponse);
    typeTheTitle(container, 'The street');

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    expect(await screen.findByText(said)).toBeInTheDocument();
    expect(screen.queryByTestId('landed')).toBeNull();
    expect(container.querySelector('#create-collection-headline')).toHaveValue('The street');
    await waitFor(() => expect(screen.getByRole('button', { name: 'Create' })).toBeEnabled());
  });
});

describe('EditCollectionPage — load + pause + submit', () => {
  test('pre-populates the headline from the loaded collection', async () => {
    await renderEdit({
      headline: 'Loaded Name',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['GIFT_THING'],
    });

    expect(await screen.findByDisplayValue('Loaded Name')).toBeInTheDocument();
  });

  test('pause section shows the message field + "Pause collection" when not paused', async () => {
    const { container } = await renderEdit({
      headline: 'Comm',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['GIFT_THING'],
      is_paused: false,
    });

    await screen.findByDisplayValue('Comm');
    expect(container.querySelector('#pause-message')).toBeTruthy();
    expect(screen.getByRole('button', { name: 'Pause collection' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Resume collection' })).toBeNull();
  });

  test('pause section shows the message + "Resume collection" when paused', async () => {
    const { container } = await renderEdit({
      headline: 'Comm',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['GIFT_THING'],
      is_paused: true,
      pause_message: 'Back in a week',
    });

    await screen.findByDisplayValue('Comm');
    expect(container.querySelector('#pause-message')).toBeNull();
    expect(screen.getByText('Back in a week')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Resume collection' })).toBeInTheDocument();
  });

  // On Edit: digest, language, thumbnail and the welcome doc fold into the
  // same "More options" accordion; status, mode and the identity cluster stay
  // visible. The digest select lives on BOTH forms now (see the Create suite
  // above) — it is folded here, not exclusive to here.
  test('the digest select is hidden until "More options" is opened', async () => {
    const { container } = await renderEdit({
      headline: 'Comm',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['GIFT_THING'],
    });

    await screen.findByDisplayValue('Comm');
    const digest = () => container.querySelector('#edit-collection-digest');
    expect(digest()).not.toBeVisible();

    fireEvent.click(screen.getByRole('button', { name: 'More options' }));

    await waitFor(() => expect(digest()).toBeVisible());
  });

  test('PATCHes /api/v1/collections/{code}/ with the edited fields', async () => {
    const { container } = await renderEdit({
      headline: 'Old Name',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['GIFT_THING'],
    });

    await screen.findByDisplayValue('Old Name');
    fireEvent.change(container.querySelector('#edit-collection-headline'), {
      target: { value: 'New Name' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      const call = apiFetch.mock.calls.find(
        (c) =>
          c[0] === '/api/v1/collections/COL001/' &&
          c[1]?.method === 'PATCH' &&
          JSON.parse(c[1].body).headline !== undefined
      );
      expect(call).toBeTruthy();
      const body = JSON.parse(call[1].body);
      expect(body).toMatchObject({ headline: 'New Name', mode: 'PROPRIETARY' });
    });
  });

  test('loads the stored home page and PATCHes an edited one back', async () => {
    const { container } = await renderEdit({
      headline: 'Ateneu',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['GIFT_THING'],
      home_page: 'https://old.example/',
    });

    await screen.findByDisplayValue('Ateneu');
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    const homePage = () => container.querySelector('#edit-collection-home-page');
    await waitFor(() => expect(homePage()).toHaveValue('https://old.example/'));

    fireEvent.change(homePage(), { target: { value: 'https://new.example/' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      const call = apiFetch.mock.calls.find(
        (c) =>
          c[0] === '/api/v1/collections/COL001/' &&
          c[1]?.method === 'PATCH' &&
          JSON.parse(c[1].body).home_page === 'https://new.example/'
      );
      expect(call).toBeTruthy();
    });
  });

  /**
   * "Con cuánta antelación pueden reservar (días)" would not stay saved.
   * The number field only told the page about a new value when it
   * lost focus, so anything that saves without a blur first — Enter in the
   * field (implicit submission is a click on Save with no focus change), the
   * +/- stepper, a keyboard Save — sent the number the page had loaded, while
   * the field on screen showed the new one. A mouse click on Save happens to
   * blur first, which is why it mostly seemed to work.
   *
   * `fireEvent` moves no focus, so change → click here IS that path.
   */
  test('a number typed into a day field is saved even if the field never lost focus', async () => {
    const { container } = await renderEdit({
      headline: 'Ateneu spaces',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['RESERVE_THING'],
      reservation_max_days: 3,
      reservation_horizon_days: 120,
      reservation_max_active_per_member: 10,
    });

    await screen.findByDisplayValue('Ateneu spaces');
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    const horizon = () => container.querySelector('#edit-collection-reservation-horizon-days');
    await waitFor(() => expect(horizon()).toHaveValue(120));

    fireEvent.change(horizon(), { target: { value: '30' } });
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => {
      const call = apiFetch.mock.calls.find(
        (c) => c[0] === '/api/v1/collections/COL001/' && c[1]?.method === 'PATCH'
      );
      expect(call).toBeTruthy();
      expect(JSON.parse(call[1].body).reservation_horizon_days).toBe(30);
    });
  });

  // The smoke suite axe-sweeps every route, but its EditCollectionPage fixture
  // is a GIFT collection, so the reservations branch of "More options"
  // (ReservationRulesFields — two NumberInputs wrapped in role="group", the
  // WeekdayChips row) never reaches axe there. Sweep it here, opened.
  test('the reservations rules branch, opened, has no accessibility violations', async () => {
    const { container } = await renderEdit({
      headline: 'Ateneu spaces',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['RESERVE_THING'],
      reservation_max_days: 3,
      reservation_horizon_days: 120,
      rental_weekdays: [0, 2, 4],
    });

    await screen.findByDisplayValue('Ateneu spaces');
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    await waitFor(() =>
      expect(screen.getByRole('spinbutton', { name: 'Longest reservation (days)' })).toBeVisible()
    );
    // The reservations branch, not the rental one — otherwise the sweep proves
    // nothing about ReservationRulesFields.
    expect(screen.getByRole('group', { name: 'Days open for reservations' })).toBeInTheDocument();

    await settle(apiFetch);
    expect(await axe(container)).toHaveNoViolations();
  });

  test('a rejected closure date shows the backend’s reason, not a generic error', async () => {
    // The backend 400s a >2-years-out closure date rather than dropping it
    // silently; the owner has to be told which token and why.
    const { extractApiError } = await import('../services/api');
    extractApiError.mockResolvedValueOnce(
      "'25/12/2099' is more than two years away — check for a typo."
    );
    apiFetch.mockImplementation((url, opts = {}) => {
      const method = opts.method || 'GET';
      if (method === 'PATCH') return Promise.resolve(mockResponse({}, false)); // 400
      return Promise.resolve(mockResponse({ headline: 'X', allowed_thing_types: ['GIFT_THING'] }));
    });

    render(
      <MemoryRouter initialEntries={['/collections/COL001/edit']}>
        <Routes>
          <Route path="/collections/:code/edit" element={<EditCollectionPage />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findByDisplayValue('X');
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText(/more than two years away/)).toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════
// The kind a deployment hands out
//
// A narrowed deployment (e.g. one whose policy gives GIFT/SELL to everyone and
// LEND/RENT/RESERVE after approval) gives an unvetted account a stall and no more:
// its form for the others would only end in a refusal at Create, with no
// explanation. `collection_kinds` on `/auth/me/` is what says so, and the form
// page answers with the same line the chooser uses instead of the form.
// ════════════════════════════════════════════════════════════════════════
describe('CreateCollectionPage — collection_kinds capability', () => {
  function setApiWithCapabilities(capabilities) {
    apiFetch.mockImplementation((url, opts = {}) => {
      const method = opts.method || 'GET';
      if (url === '/api/v1/auth/me/') return Promise.resolve(mockResponse({ capabilities }));
      if (url === '/api/v1/collections/' && method === 'POST')
        return Promise.resolve(mockResponse({ code: 'NEW001', kind: 'STALL' }));
      return Promise.resolve(mockResponse({}));
    });
  }

  const CAPS = {
    collection_modes: ['PROPRIETARY', 'COMMUNITY'],
    collection_kinds: ['STALL'],
    thing_types: ['GIFT_THING', 'SELL_THING'],
    request_url: 'https://example.test/request-access/',
  };

  const open = (kind) =>
    render(
      <MemoryRouter initialEntries={[`/${kind}/new`]}>
        <Routes>
          <Route path="/:kind/new" element={<CreateCollectionPage />} />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </MemoryRouter>
    );

  test.each(['library', 'shed'])(
    'a withheld kind (%s) gets the notice and no form',
    async (kind) => {
      // The hook caches one request per signed-in account, so a code no other
      // test in this file uses keeps this answer from being served stale.
      localStorage.setItem('userCode', `POPIN-${kind}`);
      setApiWithCapabilities(CAPS);

      const { container } = open(kind);

      expect(await screen.findByText(/need approval on this deployment/)).toBeInTheDocument();
      expect(screen.getByRole('link', { name: /Request access/ })).toHaveAttribute(
        'href',
        'https://example.test/request-access/'
      );
      expect(container.querySelector('#create-collection-headline')).toBeNull();
      expect(screen.queryByRole('button', { name: 'Create' })).toBeNull();
    }
  );

  // What the deployment allows is asked for before the page decides what to show:
  // the form first and the notice after would swap under the person's fingers and
  // lose what they had typed.
  describe('while the deployment has not answered', () => {
    let release;
    const holdMe = (capabilities) => {
      const answer = new Promise((resolve) => {
        release = () => resolve(mockResponse({ capabilities }));
      });
      apiFetch.mockImplementation((url) =>
        url === '/api/v1/auth/me/' ? answer : Promise.resolve(mockResponse({}))
      );
    };

    test('there is neither the form nor the notice, and a denied kind then gets only the notice', async () => {
      localStorage.setItem('userCode', 'WAIT-denied');
      holdMe(CAPS);

      const { container } = open('library');
      await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/v1/auth/me/', {}));

      expect(container.querySelector('#create-collection-headline')).toBeNull();
      expect(screen.queryByText(/need approval on this deployment/)).toBeNull();

      release();

      expect(await screen.findByText(/need approval on this deployment/)).toBeInTheDocument();
      expect(container.querySelector('#create-collection-headline')).toBeNull();
    });

    test('a granted kind then gets its form', async () => {
      localStorage.setItem('userCode', 'WAIT-granted');
      holdMe(CAPS);

      const { container } = open('stall');
      await waitFor(() => expect(apiFetch).toHaveBeenCalledWith('/api/v1/auth/me/', {}));
      expect(container.querySelector('#create-collection-headline')).toBeNull();

      release();

      await waitFor(() =>
        expect(container.querySelector('#create-collection-headline')).toBeInTheDocument()
      );
    });
  });

  test('when the deployment cannot be asked the form shows: the server is the gate', async () => {
    localStorage.setItem('userCode', 'WAIT-failed');
    apiFetch.mockImplementation((url) =>
      url === '/api/v1/auth/me/'
        ? Promise.reject(new Error('offline'))
        : Promise.resolve(mockResponse({}))
    );

    const { container } = open('shed');

    await waitFor(() =>
      expect(container.querySelector('#create-collection-headline')).toBeInTheDocument()
    );
    expect(screen.queryByText(/need approval on this deployment/)).toBeNull();
  });

  test('the kind the policy hands out gets its form', async () => {
    localStorage.setItem('userCode', 'POPIN-stall');
    setApiWithCapabilities(CAPS);

    const { container } = open('stall');

    await waitFor(() =>
      expect(container.querySelector('#create-collection-headline')).toBeInTheDocument()
    );
    expect(screen.queryByText(/need approval/)).toBeNull();
  });

  test('a prefix that is no kind sends the reader to the chooser', async () => {
    renderCreate('collections');

    expect(await screen.findByTestId('navigated')).toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════
// A shed holds reservations, and is always PROPRIETARY.
// ════════════════════════════════════════════════════════════════════════
describe('CreateCollectionPage — a shed', () => {
  const createBody = () => {
    const post = apiFetch.mock.calls.find(
      ([u, o]) => u === '/api/v1/collections/' && o?.method === 'POST'
    );
    return post && JSON.parse(post[1].body);
  };

  const renderShed = () => renderCreate('shed');
  const nameIt = (container) =>
    fireEvent.change(container.querySelector('#create-collection-headline'), {
      target: { value: 'Ateneu spaces' },
    });

  test('it has no mode to choose, and ships its kind, RESERVE and PROPRIETARY', async () => {
    const { container } = await renderShed();
    nameIt(container);
    // An operator runs the premises: there is no radio for a community shed.
    expect(screen.queryByRole('radio')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createBody()).toBeTruthy());
    const body = createBody();
    expect(body.kind).toBe('SHED');
    expect(body.allowed_thing_types).toEqual(['RESERVE_THING']);
    expect(body.mode).toBe('PROPRIETARY');
    expect(body.visibility).toBe('PRIVATE');
    expect(body.reservation_max_days).toBe(1);
    expect(body.reservation_max_active_per_member).toBe(10);
  });

  test('an unparseable opening-hours draft stops Create instead of creating without it', async () => {
    // The field keeps the last good value ({} here), so creating anyway would
    // open an HOUR space with every day closed while the owner believes their
    // schedule went in.
    const { container } = await renderShed();
    nameIt(container);
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    fireEvent.click(screen.getByRole('radio', { name: 'By hour' }));
    const field = screen.getByLabelText(/Weekly opening hours/);
    fireEvent.change(field, { target: { value: '{"0": [["10:00","14:00"]],}' } });
    fireEvent.blur(field);

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    expect(await screen.findByText(/Nothing was saved: the weekly opening hours/)).toBeVisible();
    expect(createBody()).toBeUndefined();
    expect(screen.queryByTestId('navigated')).toBeNull();
  });

  test('booking by the hour makes the opening hours required, and Create sends nothing without a range', async () => {
    const { container } = await renderShed();
    nameIt(container);
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    fireEvent.click(screen.getByRole('radio', { name: 'By hour' }));
    expect(screen.getByLabelText(/Weekly opening hours/)).toBeRequired();

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    expect(
      await screen.findByText(/To book by the hour, add at least one time range/)
    ).toBeVisible();
    expect(createBody()).toBeUndefined();
    expect(screen.queryByTestId('navigated')).toBeNull();
  });

  test('a week of days with no ranges is no schedule either', async () => {
    const { container } = await renderShed();
    nameIt(container);
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    fireEvent.click(screen.getByRole('radio', { name: 'By hour' }));
    const hours = screen.getByLabelText(/Weekly opening hours/);
    fireEvent.change(hours, { target: { value: '{"0": [], "3": []}' } });
    fireEvent.blur(hours);

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    expect(
      await screen.findByText(/To book by the hour, add at least one time range/)
    ).toBeVisible();
    expect(createBody()).toBeUndefined();
  });

  test('by the day the opening hours are not asked for', async () => {
    const { container } = await renderShed();
    nameIt(container);

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createBody()).toBeTruthy());
    expect(createBody().reservation_unit).toBe('DAY');
  });

  test('a space booked by the hour is created with its schedule and its limits in minutes', async () => {
    // Nothing on the Create path sent an HOUR-unit collection before: the
    // owner's hours could have gone missing and the space opened with every
    // day closed, found only when a member saw nothing to book.
    const { container } = await renderShed();
    nameIt(container);
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    fireEvent.click(screen.getByRole('radio', { name: 'By hour' }));
    const hours = screen.getByLabelText(/Weekly opening hours/);
    fireEvent.change(hours, {
      target: {
        value: '{"0": [["10:00", "14:00"], ["16:00", "20:00"]], "4": [["10:00", "14:00"]]}',
      },
    });
    fireEvent.blur(hours);
    for (const [id, minutes] of [
      ['#create-collection-reservation-min-minutes', '30'],
      ['#create-collection-reservation-max-minutes', '120'],
    ]) {
      const input = container.querySelector(id);
      fireEvent.change(input, { target: { value: minutes } });
      fireEvent.blur(input);
    }

    fireEvent.click(screen.getByRole('button', { name: 'Create' }));

    await waitFor(() => expect(createBody()).toBeTruthy());
    const body = createBody();
    expect(body.reservation_unit).toBe('HOUR');
    expect(body.opening_hours).toEqual({
      0: [
        ['10:00', '14:00'],
        ['16:00', '20:00'],
      ],
      4: [['10:00', '14:00']],
    });
    expect(body.reservation_min_minutes).toBe(30);
    expect(body.reservation_max_minutes).toBe(120);
    // The day-unit cap is the other unit's: not sent, so it can't disagree.
    expect(body).not.toHaveProperty('reservation_max_days');
  });
});

describe('collection texts that open like a language map and are not one', () => {
  test('the headline says it will read as plain text, and stops once it parses', async () => {
    await renderCreate();
    const headline = document.querySelector('#create-collection-headline');
    const warning = /Read as plain text/;

    fireEvent.change(headline, { target: { value: '{"es": "Las cosas de mamá", "fr": "x"}' } });
    expect(screen.getByText(warning)).toBeInTheDocument();

    fireEvent.change(headline, { target: { value: '{"es": "Las cosas de mamá"}' } });
    expect(screen.queryByText(warning)).not.toBeInTheDocument();
  });

  test('prose that starts some other way never trips it', async () => {
    await renderCreate();
    fireEvent.change(document.querySelector('#create-collection-headline'), {
      target: { value: 'Herramientas {del taller}' },
    });
    expect(screen.queryByText(/Read as plain text/)).not.toBeInTheDocument();
  });
});

/**
 * Four selects were handed their help line as `helper=`, a prop the HDS 6 `Select`
 * does not read, so the sentence never reached the page. HDS 6 takes it as
 * `texts.assistive`; it prints the line and says it to a screen reader inside the
 * control's own `aria-label` (it sets no `aria-describedby`): these check that each
 * line is in the DOM *and* in its select's accessible name.
 */
describe('the help line of the selects reaches the page and the control’s accessible name', () => {
  const DIGEST = 'Automatically email members and whoever runs the group a summary of new things.';
  const LANGUAGE =
    "The language the group's emails are written in. Any member who has set their own language reads them in theirs.";
  const STATUS = en.editCollection.statusHelper;

  const field = (name) => screen.getByRole('combobox', { name });

  test('Create: the summary and the language of the group messages', async () => {
    await renderCreate();
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));

    expect(await screen.findByText(DIGEST)).toBeInTheDocument();
    expect(field(/Digest emails/)).toHaveAccessibleName(expect.stringContaining(DIGEST));
    expect(screen.getByText(LANGUAGE)).toBeInTheDocument();
    expect(field(/Language of the group messages/)).toHaveAccessibleName(
      expect.stringContaining(LANGUAGE)
    );
  });

  test('Edit: the status, the summary and the language of the group messages', async () => {
    await renderEdit({
      headline: 'Loaded Name',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['GIFT_THING'],
    });
    await screen.findByDisplayValue('Loaded Name');
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));

    expect(await screen.findByText(STATUS)).toBeInTheDocument();
    expect(field(/^Status/)).toHaveAccessibleName(expect.stringContaining(STATUS));
    expect(screen.getByText(DIGEST)).toBeInTheDocument();
    expect(field(/Digest emails/)).toHaveAccessibleName(expect.stringContaining(DIGEST));
    expect(field(/Language of the group messages/)).toHaveAccessibleName(
      expect.stringContaining(LANGUAGE)
    );
  });

  test('the forms have no accessibility violations with the help lines in', async () => {
    const { container } = await renderCreate();
    fireEvent.click(screen.getByRole('button', { name: 'More options' }));
    await screen.findByText(DIGEST);

    expect(await axe(container)).toHaveNoViolations();
  });
});
