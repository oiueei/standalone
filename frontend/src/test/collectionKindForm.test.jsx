import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import { settle, press } from './settle';
import en from '../i18n/locales/en.json';

/**
 * The collection form is built around the collection's kind. A stall, a library and a
 * shed show the sections that mean something for them, the verbs it sends follow the
 * kind (a stall's are gift and sale, a library's lend and rent out, a shed's reserve),
 * and in a community one a single switch says whether members may set a price. The
 * kind is chosen before the form and never changes after it: Create sends it, Edit
 * shows it as a fact and sends it nowhere.
 */
window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));
vi.mock('../utils/externalForms', () => ({ externalFormUrl: () => null }));
// The pages a deployment may send "Request access" to (`requestAccessPaths`) are switched
// off the same way: this file pins what the standalone shows, whatever `deployment/` holds.
vi.mock('../deployment', async (orig) => ({ ...(await orig()), requestAccessPaths: {} }));

import { apiFetch, extractApiError } from '../services/api';
import CreateCollectionPage from '../pages/CreateCollectionPage';
import EditCollectionPage from '../pages/EditCollectionPage';
import { dropHdsStyles } from './dropHdsStyles';

const mockResponse = (data, ok = true) => ({
  ok,
  status: ok ? 200 : 400,
  json: () => Promise.resolve(data),
});

const VERBS = {
  STALL: ['GIFT_THING', 'SELL_THING'],
  LIBRARY: ['LEND_THING', 'RENT_THING'],
  SHED: ['RESERVE_THING'],
};

function setApi(collection = {}) {
  apiFetch.mockImplementation((url, opts = {}) => {
    const method = opts.method || 'GET';
    if (url === '/api/v1/collections/' && method === 'POST')
      return Promise.resolve(mockResponse({ code: 'NEW001', kind: 'STALL' }));
    if (/\/collections\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(collection));
    return Promise.resolve(mockResponse({}));
  });
}

// The create page asks the deployment what it allows before it shows anything, so the
// form is there a moment after the render: the helper hands it back once it is.
const renderCreate = async (kind) => {
  setApi();
  const view = render(
    <MemoryRouter initialEntries={[`/${kind.toLowerCase()}/new`]}>
      <Routes>
        <Route path="/:kind/new" element={<CreateCollectionPage />} />
        <Route path="*" element={<div />} />
      </Routes>
    </MemoryRouter>
  );
  await waitFor(() =>
    expect(view.container.querySelector('#create-collection-headline')).toBeInTheDocument()
  );
  await settle(apiFetch);
  return view;
};

const renderEdit = (collection) => {
  setApi({ headline: 'Loaded', mode: 'PROPRIETARY', ...collection });
  return render(
    <MemoryRouter initialEntries={[`/${collection.kind.toLowerCase()}/COL001/edit`]}>
      <Routes>
        <Route path="/:kind/:code/edit" element={<EditCollectionPage />} />
        <Route path="*" element={<div />} />
      </Routes>
    </MemoryRouter>
  );
};

const sent = (method, urlPattern) => {
  const call = apiFetch.mock.calls.find(
    ([url, opts]) => opts?.method === method && urlPattern.test(url)
  );
  return call && JSON.parse(call[1].body);
};
const createBody = () => sent('POST', /^\/api\/v1\/collections\/$/);
const patchBody = () => sent('PATCH', /\/collections\/COL001\//);

const name = (container, value = 'The street') =>
  fireEvent.change(container.querySelector('#create-collection-headline'), {
    target: { value },
  });
const create = (kind) =>
  fireEvent.click(screen.getByRole('button', { name: `Create ${kind.toLowerCase()}` }));

beforeEach(() => {
  dropHdsStyles();
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  vi.clearAllMocks();
  extractApiError.mockResolvedValue('');
});

describe('Create — the page is the kind’s', () => {
  test.each([
    ['STALL', 'Create stall'],
    ['LIBRARY', 'Create library'],
    ['SHED', 'Create shed'],
  ])('a %s says so in its title', async (kind, title) => {
    await renderCreate(kind);

    expect(screen.getByRole('heading', { level: 1, name: title })).toBeInTheDocument();
  });

  test.each(['STALL', 'LIBRARY', 'SHED'])('a %s has no choice of verbs to make', async (kind) => {
    const { container } = await renderCreate(kind);

    expect(
      container.querySelector('#create-collection-allowed-thing-types-main-button')
    ).toBeNull();
    expect(screen.queryByText('What can be added to this collection')).toBeNull();
  });

  test.each([
    ['STALL', true],
    ['LIBRARY', true],
    ['SHED', false],
  ])('the mode is a choice for a %s: %s', async (kind, choosable) => {
    await renderCreate(kind);

    expect(screen.queryAllByRole('radio').length > 0).toBe(choosable);
  });
});

describe('Create — which sections each kind shows', () => {
  // The short form is the same for every kind: what a kind has of its own (rental rules,
  // reservation rules, notes) is on the settings pages, not here.
  const SETTINGS_FIELDS = [
    'deposit-policy',
    'reservation-horizon-days',
    'closed-dates',
    'request-info',
    'thumbnail',
    'email-note',
    'home-page',
    'digest',
    'welcome-doc',
  ];

  test.each(['STALL', 'LIBRARY', 'SHED'])('a %s asks for none of them', async (kind) => {
    const { container } = await renderCreate(kind);

    for (const field of SETTINGS_FIELDS) {
      expect(container.querySelector(`#create-collection-${field}`), field).toBeNull();
    }
    expect(screen.queryByRole('button', { name: 'More options' })).toBeNull();
  });
});

describe('Create — the members-can-set-a-price switch', () => {
  const sw = (container) => container.querySelector('#create-collection-members-price');

  test.each([
    ['STALL', en.collectionForm.membersPriceStall],
    ['LIBRARY', en.collectionForm.membersPriceLibrary],
  ])('a %s that is Community has it, on, with its own words', async (kind, label) => {
    const { container } = await renderCreate(kind);
    expect(sw(container)).toBeNull();

    await press(screen.getByRole('radio', { name: /^Community:/ }));
    await settle(apiFetch);

    expect(sw(container)).toHaveAttribute('aria-pressed', 'true');
    expect(screen.getByText(label)).toBeInTheDocument();
  });

  test('a PROPRIETARY one and a shed have none', async () => {
    const stall = await renderCreate('STALL');
    expect(sw(stall.container)).toBeNull();
    stall.unmount();

    const shed = await renderCreate('SHED');
    expect(sw(shed.container)).toBeNull();
  });
});

describe('Create — what is sent, for each kind and mode', () => {
  test.each([
    ['STALL', 'PROPRIETARY', true, VERBS.STALL],
    ['STALL', 'COMMUNITY', true, VERBS.STALL],
    ['STALL', 'COMMUNITY', false, ['GIFT_THING']],
    ['LIBRARY', 'PROPRIETARY', true, VERBS.LIBRARY],
    ['LIBRARY', 'COMMUNITY', true, VERBS.LIBRARY],
    ['LIBRARY', 'COMMUNITY', false, ['LEND_THING']],
    ['SHED', 'PROPRIETARY', true, VERBS.SHED],
  ])('%s, %s, members may set a price: %s → %j', async (kind, mode, price, verbs) => {
    const { container } = await renderCreate(kind);
    name(container);
    if (mode === 'COMMUNITY') {
      fireEvent.click(screen.getByRole('radio', { name: /^Community:/ }));
      if (!price) fireEvent.click(container.querySelector('#create-collection-members-price'));
    }

    create(kind);

    await waitFor(() => expect(createBody()).toBeTruthy());
    expect(createBody()).toMatchObject({ kind, mode, allowed_thing_types: verbs });
  });

  test.each(['STALL', 'LIBRARY', 'SHED'])(
    'a %s sends none of the rules a settings page owns',
    async (kind) => {
      const { container } = await renderCreate(kind);
      name(container);

      create(kind);

      await waitFor(() => expect(createBody()).toBeTruthy());
      for (const key of [
        'rental_durations',
        'rental_weekdays',
        'closed_dates',
        'request_info',
        'deposit_policy',
        'reservation_unit',
        'reservation_max_days',
        'digest_frequency',
        'allow_member_proposals',
        'koro',
        'tags',
      ]) {
        expect(createBody(), key).not.toHaveProperty(key);
      }
    }
  );
});

describe('Edit — the kind is a fact, not a control', () => {
  test.each([
    ['STALL', ['GIFT_THING', 'SELL_THING'], 'Stall'],
    ['LIBRARY', ['LEND_THING', 'RENT_THING'], 'Library of Things'],
    ['SHED', ['RESERVE_THING'], 'Shed'],
  ])('a %s names itself and offers no way to change it', async (kind, verbs, long) => {
    const { container } = renderEdit({ kind, allowed_thing_types: verbs });

    await screen.findByDisplayValue('Loaded');
    expect(container.querySelector('.collection-kind')).toHaveTextContent(long);
    expect(container.querySelector('#edit-collection-allowed-thing-types-main-button')).toBeNull();
  });

  test('saving never sends the kind', async () => {
    renderEdit({ kind: 'LIBRARY', allowed_thing_types: VERBS.LIBRARY });
    await screen.findByDisplayValue('Loaded');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).not.toHaveProperty('kind');
    expect(patchBody().allowed_thing_types).toEqual(VERBS.LIBRARY);
  });

  test('a shed has no mode to change and saves as PROPRIETARY', async () => {
    renderEdit({ kind: 'SHED', allowed_thing_types: VERBS.SHED });
    await screen.findByDisplayValue('Loaded');
    expect(screen.queryAllByRole('radio').length).toBe(0);

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toMatchObject({ mode: 'PROPRIETARY', allowed_thing_types: VERBS.SHED });
  });

  test('a stall sends nothing of what only a library or a shed has', async () => {
    renderEdit({ kind: 'STALL', allowed_thing_types: VERBS.STALL });
    await screen.findByDisplayValue('Loaded');

    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    for (const key of ['rental_durations', 'closed_dates', 'request_info', 'deposit_policy']) {
      expect(patchBody()).not.toHaveProperty(key);
    }
  });
});

describe('Edit — the members-can-set-a-price switch shows what was saved', () => {
  const sw = (container) => container.querySelector('#edit-collection-members-price');

  test.each([
    ['STALL', ['GIFT_THING'], 'false'],
    ['STALL', VERBS.STALL, 'true'],
    ['LIBRARY', ['LEND_THING'], 'false'],
    ['LIBRARY', VERBS.LIBRARY, 'true'],
  ])('a Community %s saved with %j reads %s', async (kind, verbs, pressed) => {
    const { container } = renderEdit({ kind, mode: 'COMMUNITY', allowed_thing_types: verbs });

    await screen.findByDisplayValue('Loaded');
    expect(sw(container)).toHaveAttribute('aria-pressed', pressed);
  });

  test('turning it off saves the free verb alone', async () => {
    const { container } = renderEdit({
      kind: 'LIBRARY',
      mode: 'COMMUNITY',
      allowed_thing_types: VERBS.LIBRARY,
    });
    await screen.findByDisplayValue('Loaded');

    fireEvent.click(sw(container));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()?.allowed_thing_types).toEqual(['LEND_THING']));
  });

  test('turning it back on saves both verbs', async () => {
    const { container } = renderEdit({
      kind: 'LIBRARY',
      mode: 'COMMUNITY',
      allowed_thing_types: ['LEND_THING'],
    });
    await screen.findByDisplayValue('Loaded');

    fireEvent.click(sw(container));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()?.allowed_thing_types).toEqual(VERBS.LIBRARY));
  });

  test('becoming PROPRIETARY takes both verbs whatever the switch last said', async () => {
    renderEdit({
      kind: 'STALL',
      mode: 'COMMUNITY',
      allowed_thing_types: ['GIFT_THING'],
    });
    await screen.findByDisplayValue('Loaded');

    fireEvent.click(screen.getByRole('radio', { name: /^Proprietary:/ }));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    await waitFor(() => expect(patchBody()).toBeTruthy());
    expect(patchBody()).toMatchObject({ mode: 'PROPRIETARY', allowed_thing_types: VERBS.STALL });
  });

  test('the server’s refusal, with things of the other verb inside, is shown as it always was', async () => {
    const { container } = renderEdit({
      kind: 'STALL',
      mode: 'COMMUNITY',
      allowed_thing_types: VERBS.STALL,
    });
    await screen.findByDisplayValue('Loaded');
    extractApiError.mockResolvedValueOnce(
      "Cannot restrict the allowed types: existing things would be orphaned (types: ['SELL_THING'])."
    );
    apiFetch.mockImplementation((url, opts = {}) =>
      opts.method === 'PATCH'
        ? Promise.resolve(mockResponse({}, false))
        : Promise.resolve(mockResponse({}))
    );

    fireEvent.click(sw(container));
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText(/existing things would be orphaned/)).toBeInTheDocument();
  });
});
