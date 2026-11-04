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
    fireEvent.click(screen.getByRole('button', { name: /^Create (stall|library|shed)$/ }));

    await waitFor(() => expect(createBody()?.visibility).toBe('PUBLIC'));
    expect(createBody()?.mode).toBe('COMMUNITY');
  });

  test('a Community group whose switch was never touched ships as PRIVATE', async () => {
    const { container } = await renderCreate();
    await fillTheRequiredFields(container, 'A quiet community');

    fireEvent.click(screen.getByRole('radio', { name: /^Community:/ }));
    fireEvent.click(screen.getByRole('button', { name: /^Create (stall|library|shed)$/ }));

    await waitFor(() => expect(createBody()?.visibility).toBe('PRIVATE'));
    expect(createBody()?.mode).toBe('COMMUNITY');
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

    fireEvent.click(screen.getByRole('button', { name: /^Create (stall|library|shed)$/ }));

    // At the kind's address, from the kind the server answered with.
    expect(await screen.findByTestId('landed')).toHaveTextContent('/library/NEW001');
  });

  test('a blank title sends nothing and says it is needed', async () => {
    const { container } = await renderCreateWith(() =>
      Promise.resolve(mockResponse({ code: 'X' }))
    );
    typeTheTitle(container, '   ');

    fireEvent.click(screen.getByRole('button', { name: /^Create (stall|library|shed)$/ }));

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

    fireEvent.click(screen.getByRole('button', { name: /^Create (stall|library|shed)$/ }));

    expect(await screen.findByText(said)).toBeInTheDocument();
    expect(screen.queryByTestId('landed')).toBeNull();
    expect(container.querySelector('#create-collection-headline')).toHaveValue('The street');
    await waitFor(() =>
      expect(screen.getByRole('button', { name: /^Create (stall|library|shed)$/ })).toBeEnabled()
    );
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

  // The recommend switch lives on the Notifications page, and so does every other setting:
  // saving this form sends none of them, so it can never reset one.
  test.each([true, false])(
    'saving sends no allow_member_proposals, whatever the collection has (%s)',
    async (saved) => {
      const { container } = await renderEdit({
        headline: 'Comm',
        mode: 'PROPRIETARY',
        allowed_thing_types: ['GIFT_THING'],
        allow_member_proposals: saved,
      });
      await screen.findByDisplayValue('Comm');
      expect(container.querySelector('#edit-collection-allow-proposals')).toBeNull();

      fireEvent.click(screen.getByRole('button', { name: 'Save' }));

      await waitFor(() => expect(screen.getByTestId('navigated')).toBeInTheDocument());
      const patch = apiFetch.mock.calls.find(([, o]) => o?.method === 'PATCH');
      expect(JSON.parse(patch[1].body)).not.toHaveProperty('allow_member_proposals');
    }
  );

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
      expect(screen.queryByRole('button', { name: /^Create (stall|library|shed)$/ })).toBeNull();
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

    fireEvent.click(screen.getByRole('button', { name: /^Create (stall|library|shed)$/ }));

    await waitFor(() => expect(createBody()).toBeTruthy());
    const body = createBody();
    expect(body.kind).toBe('SHED');
    expect(body.allowed_thing_types).toEqual(['RESERVE_THING']);
    expect(body.mode).toBe('PROPRIETARY');
    expect(body.visibility).toBe('PRIVATE');
  });

  test('its rules (by day, the limits, the hours) are the model’s, not sent from here', async () => {
    const { container } = await renderShed();
    nameIt(container);

    fireEvent.click(screen.getByRole('button', { name: /^Create (stall|library|shed)$/ }));

    await waitFor(() => expect(createBody()).toBeTruthy());
    const body = createBody();
    for (const key of [
      'reservation_unit',
      'reservation_max_days',
      'reservation_horizon_days',
      'reservation_max_active_per_member',
      'reservation_asks_phone',
      'opening_hours',
    ]) {
      expect(body, key).not.toHaveProperty(key);
    }
  });
});

// ════════════════════════════════════════════════════════════════════════
// The short form: what /{kind}/new asks and what it sends
// ════════════════════════════════════════════════════════════════════════
describe('CreateCollectionPage — the short form', () => {
  const createBody = () => {
    const post = apiFetch.mock.calls.find(
      ([u, o]) => u === '/api/v1/collections/' && o?.method === 'POST'
    );
    return post && JSON.parse(post[1].body);
  };
  const create = (kind) =>
    fireEvent.click(screen.getByRole('button', { name: new RegExp(`^Create ${kind}$`) }));
  const type = (container, id, value) =>
    fireEvent.change(container.querySelector(id), { target: { value } });

  test.each([
    ['stall', 'STALL', { mode: 'PROPRIETARY', verbs: ['GIFT_THING', 'SELL_THING'] }],
    ['library', 'LIBRARY', { mode: 'PROPRIETARY', verbs: ['LEND_THING', 'RENT_THING'] }],
    ['shed', 'SHED', { mode: 'PROPRIETARY', verbs: ['RESERVE_THING'] }],
  ])(
    'a %s sends exactly its kind, title, description, mode, visibility, verbs and language',
    async (prefix, kind, { mode, verbs }) => {
      const { container } = await renderCreate(prefix);
      type(container, '#create-collection-headline', '  The street  ');
      type(container, '#create-collection-description', 'Things for all');

      create(prefix);

      await waitFor(() => expect(createBody()).toBeTruthy());
      // The boundary of the form: anything else the collection has (palette, tags, digest,
      // rules…) is the model’s default and has a settings page of its own.
      expect(Object.keys(createBody()).sort()).toEqual([
        'allowed_thing_types',
        'description',
        'headline',
        'kind',
        'language',
        'mode',
        'visibility',
      ]);
      expect(createBody()).toEqual({
        kind,
        headline: 'The street',
        description: 'Things for all',
        mode,
        visibility: 'PRIVATE',
        allowed_thing_types: verbs,
        language: 'en',
      });
    }
  );

  test('a description left empty is not sent', async () => {
    const { container } = await renderCreate();
    type(container, '#create-collection-headline', 'No words');

    create('stall');

    await waitFor(() => expect(createBody()).toBeTruthy());
    expect(createBody()).not.toHaveProperty('description');
  });

  test('it has no accordion and none of the fields that moved to the settings pages', async () => {
    const { container } = await renderCreate('library');

    expect(screen.queryByRole('button', { name: 'More options' })).toBeNull();
    for (const field of [
      'thumbnail',
      'welcome-doc',
      'digest',
      'language',
      'home-page',
      'allow-proposals',
      'request-info',
      'email-note',
      'closed-dates',
      'rental-durations',
      'deposit-policy',
    ]) {
      expect(container.querySelector(`[id="create-collection-${field}"]`), field).toBeNull();
    }
    expect(screen.queryByText('Koro')).toBeNull();
  });

  test('it opens with a notice about writing in several languages, with its code sample', async () => {
    const { container } = await renderCreate();

    expect(screen.getByText(/Write in one language only if you prefer/)).toBeInTheDocument();
    expect(screen.getByText('{"es": "Las cosas de mamá", "ca": "Les coses de mama"}')).toHaveClass(
      'localized-example'
    );
    expect(screen.getByText(/Everyone then reads it in their own language/)).toBeInTheDocument();
    // …above the title, not under it.
    const notice = screen.getByText(/Write in one language only if you prefer/);
    const title = container.querySelector('#create-collection-headline');
    expect(notice.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test('Visibility is a section of its own, after the mode', async () => {
    await renderCreate();

    const heading = screen.getByRole('heading', { level: 2, name: 'Visibility' });
    const mode = screen.getByRole('radio', { name: /^Proprietary:/ });
    expect(mode.compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test('the members’ price switch is under the mode, only for a community, in its long words', async () => {
    const { container } = await renderCreate('library');
    const price = () => container.querySelector('#create-collection-members-price');
    expect(price()).toBeNull();

    fireEvent.click(screen.getByRole('radio', { name: /^Community:/ }));

    expect(price()).toHaveAccessibleName(
      'Members can rent out: Each member can set a price on what they lend. Turn off so they can only lend it for free.'
    );
    expect(price()).toHaveAttribute('aria-pressed', 'true');
    const heading = screen.getByRole('heading', { level: 2, name: 'Visibility' });
    expect(
      price().compareDocumentPosition(heading) & Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
  });

  test('a community stall whose members may not set a price ships only the free verb', async () => {
    const { container } = await renderCreate('stall');
    type(container, '#create-collection-headline', 'Giveaways');
    fireEvent.click(screen.getByRole('radio', { name: /^Community:/ }));
    expect(container.querySelector('#create-collection-members-price')).toHaveAccessibleName(
      'Members can sell: Each member can set a price on their own things. Turn off so they can only give them away.'
    );
    fireEvent.click(container.querySelector('#create-collection-members-price'));

    create('stall');

    await waitFor(() => expect(createBody()).toBeTruthy());
    expect(createBody()).toMatchObject({ mode: 'COMMUNITY', allowed_thing_types: ['GIFT_THING'] });
  });

  test('the language it sends is the one the interface is in', async () => {
    const { container } = await renderCreate();
    type(container, '#create-collection-headline', 'In English');

    create('stall');

    await waitFor(() => expect(createBody()?.language).toBe('en'));
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
  const STATUS = en.editCollection.statusHelper;

  const field = (name) => screen.getByRole('combobox', { name });

  test('Edit: the status', async () => {
    await renderEdit({
      headline: 'Loaded Name',
      mode: 'PROPRIETARY',
      allowed_thing_types: ['GIFT_THING'],
    });
    await screen.findByDisplayValue('Loaded Name');

    expect(await screen.findByText(STATUS)).toBeInTheDocument();
    expect(field(/^Status/)).toHaveAccessibleName(expect.stringContaining(STATUS));
  });

  test('the forms have no accessibility violations', async () => {
    const create = await renderCreate();
    expect(await axe(create.container)).toHaveNoViolations();
    create.unmount();

    const edit = await renderEdit({
      headline: 'Loaded Name',
      mode: 'COMMUNITY',
      allowed_thing_types: ['GIFT_THING'],
    });
    await screen.findByDisplayValue('Loaded Name');
    expect(await axe(edit.container)).toHaveNoViolations();
  });
});

// ════════════════════════════════════════════════════════════════════════
describe('the switch that asks for a contact phone when booking', () => {
  const SHED = {
    code: 'COL001',
    headline: 'Tool shed',
    description: 'Tools',
    status: 'ACTIVE',
    mode: 'PROPRIETARY',
    visibility: 'PRIVATE',
    kind: 'SHED',
    allowed_thing_types: ['RESERVE_THING'],
    reservation_unit: 'DAY',
    reservation_max_days: 2,
    reservation_horizon_days: 30,
    reservation_max_active_per_member: 4,
  };
  const SWITCH = en.reservation.asksPhoneFull;
  const patchBody = () => {
    const call = apiFetch.mock.calls.find(([, o]) => o?.method === 'PATCH');
    return call && JSON.parse(call[1].body);
  };

  test('editing a shed sends no such key either', async () => {
    await renderEdit({ ...SHED, reservation_asks_phone: true });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).not.toHaveProperty('reservation_asks_phone');
  });

  test('editing a library sends no such key', async () => {
    await renderEdit({
      code: 'COL001',
      headline: 'Tools',
      description: '',
      status: 'ACTIVE',
      mode: 'PROPRIETARY',
      visibility: 'PRIVATE',
      kind: 'LIBRARY',
      allowed_thing_types: ['LEND_THING', 'RENT_THING'],
    });

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).not.toHaveProperty('reservation_asks_phone');
  });
});
