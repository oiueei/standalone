import { act, render, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
}));

import { apiFetch } from '../services/api';
import CollectionPage from '../pages/CollectionPage';
import ThingPage from '../pages/ThingPage';
import RequestThingPage from '../pages/RequestThingPage';
import JoinPage from '../pages/JoinPage';
import SharePage from '../pages/SharePage';
import AddThingPage from '../pages/AddThingPage';
import EditThingPage from '../pages/EditThingPage';
import DeleteThingPage from '../pages/DeleteThingPage';
import EditCollectionPage from '../pages/EditCollectionPage';
import DeleteCollectionPage from '../pages/DeleteCollectionPage';
import ManageInvitesPage from '../pages/ManageInvitesPage';
import ImportInvitesPage from '../pages/ImportInvitesPage';
import ImportThingsPage from '../pages/ImportThingsPage';
import RemoveGuestPage from '../pages/RemoveGuestPage';
import LeaveCollectionPage from '../pages/LeaveCollectionPage';
import HomePage from '../pages/HomePage';

/**
 * A collection's pages are painted with **its** palette, not the app's.
 *
 * Every page that belongs to a collection declares the colours its API answer carries
 * (`theeeme_colors` on the collection, `collection_theeeme_colors` on a thing,
 * the share preview's) and its hero wears them; Home and the other app pages wear the
 * app's own. The palette below is nothing like the app's, so a page that forgot to
 * declare it would show `braaanding-03` in its hero instead of `tram`.
 *
 * Pages that paint their hero before they have their data would show the app's palette
 * for an instant: they wait for the answer (one more test below pins it).
 */
const GROUP = {
  color_01: 'metro',
  color_02: 'gold',
  color_03: 'tram',
  color_04: 'black',
  color_05: 'white',
  color_06: 'black',
};

const COLLECTION = {
  code: 'COL001',
  owner: 'OWNER1',
  owner_name: 'Owner',
  created: '2026-01-01T00:00:00Z',
  headline: 'Kitchen',
  description: '',
  status: 'ACTIVE',
  kind: 'LIBRARY',
  mode: 'PROPRIETARY',
  visibility: 'PUBLIC',
  digest_frequency: 'NONE',
  allow_member_proposals: false,
  language: '',
  theeeme: 'JMPA01',
  theeeme_colors: GROUP,
  koro: 'wave',
  allowed_thing_types: ['LEND_THING', 'RENT_THING'],
  rental_durations: [],
  rental_weekdays: [],
  reservation_max_days: 1,
  reservation_horizon_days: 90,
  reservation_max_active_per_member: 10,
  reservation_unit: 'DAY',
  opening_hours: {},
  reservation_min_minutes: 60,
  reservation_max_minutes: 180,
  closed_dates: [],
  home_page: '',
  deposit_policy: '',
  request_info: '',
  email_note: '',
  tags: [],
  thumbnail: '',
  thumbnail_url: null,
  welcome_doc: '',
  welcome_doc_url: null,
  pause_message: '',
  is_paused: false,
  is_onboarding: false,
  things: [],
  invites: [],
  pending_invites: [],
  is_member: false,
  is_curator: true,
  co_owners: [],
  is_digest_muted: false,
  pending_proposals: [],
};

const THING = {
  code: 'THG001',
  type: 'LEND_THING',
  owner: 'OWNER1',
  owner_name: 'Owner',
  created: '2026-01-01T00:00:00Z',
  headline: 'Drill',
  description: '',
  thumbnail: '',
  thumbnail_url: null,
  gallery: [],
  gallery_urls: [],
  tags: [],
  collection_tags: [],
  status: 'ACTIVE',
  faqs: [],
  fee: null,
  deposit: null,
  availability: '',
  location: '',
  condition: '',
  available_today: true,
  next_available: null,
  deal: [],
  pending_booking: null,
  bookings: null,
  my_pending_booking: null,
  pending_questions: 0,
  can_manage: true,
  collection_code: 'COL001',
  collection_kind: 'LIBRARY',
  collection_allowed_thing_types: ['LEND_THING', 'RENT_THING'],
  collection_headline: 'Kitchen',
  collection_owner: 'OWNER1',
  collection_is_onboarding: false,
  collection_request_info: '',
  collection_language: '',
  collection_theeeme_colors: GROUP,
  collection_koro: 'wave',
  collection_menu: null,
  rental_durations: [],
  rental_weekdays: [],
  reservation_max_days: 1,
  reservation_horizon_days: 90,
  reservation_unit: 'DAY',
  opening_hours: {},
  reservation_min_minutes: 60,
  reservation_max_minutes: 180,
  closed_dates: [],
  transfer_count: 0,
  is_endless: false,
};

const PREVIEW = {
  headline: 'Kitchen',
  description: '',
  language: '',
  kind: 'LIBRARY',
  theeeme_colors: GROUP,
  koro: 'wave',
};

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
const refused = () => Promise.resolve({ ok: false, status: 403, json: () => Promise.resolve({}) });

// What the API answers, by address. Anything not named is an empty success.
function answer(url, { thing = THING, collection = COLLECTION } = {}) {
  const path = String(url).split('?')[0];
  if (path === '/api/v1/collections/COL001/') return ok(collection);
  if (path === '/api/v1/things/THG001/') return ok(thing);
  if (path === '/api/v1/things/THG001/faq/') return ok({ results: [], next: null });
  if (path === '/api/v1/things/THG001/transfers/') return ok({ total_transfers: 0, transfers: [] });
  if (path.startsWith('/api/v1/things/THG001/calendar/')) return ok([]);
  if (path === '/api/v1/share/TOK/preview/') return ok(PREVIEW);
  if (path === '/api/v1/auth/me/') return ok({ capabilities: {} });
  return ok({});
}

const heroColour = (container) =>
  container.querySelector('.form-hero')?.getAttribute('style') || '';

function renderAt(Page, pattern, entry) {
  return render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path={pattern} element={<Page />} />
      </Routes>
    </MemoryRouter>
  );
}

const PAGES = [
  ['CollectionPage', CollectionPage, '/collections/:code', '/collections/COL001'],
  [
    'ThingPage (through a collection)',
    ThingPage,
    '/collections/:code/things/:thingCode',
    '/collections/COL001/things/THG001',
  ],
  ['ThingPage (standalone)', ThingPage, '/things/:thingCode', '/things/THG001'],
  [
    'RequestThingPage',
    RequestThingPage,
    '/collections/:code/things/:thingCode/request',
    '/collections/COL001/things/THG001/request',
  ],
  ['JoinPage', JoinPage, '/collections/:code/join', '/collections/COL001/join'],
  ['SharePage', SharePage, '/share/:token', '/share/TOK'],
  ['AddThingPage', AddThingPage, '/collections/:code/add', '/collections/COL001/add'],
  [
    'EditThingPage',
    EditThingPage,
    '/collections/:code/things/:thingCode/edit',
    '/collections/COL001/things/THG001/edit',
  ],
  [
    'DeleteThingPage',
    DeleteThingPage,
    '/collections/:code/things/:thingCode/delete',
    '/collections/COL001/things/THG001/delete',
  ],
  ['EditCollectionPage', EditCollectionPage, '/collections/:code/edit', '/collections/COL001/edit'],
  [
    'DeleteCollectionPage',
    DeleteCollectionPage,
    '/collections/:code/delete',
    '/collections/COL001/delete',
  ],
  [
    'ManageInvitesPage',
    ManageInvitesPage,
    '/collections/:code/invites',
    '/collections/COL001/invites',
  ],
  [
    'ImportInvitesPage',
    ImportInvitesPage,
    '/collections/:code/invites/import',
    '/collections/COL001/invites/import',
  ],
  ['ImportThingsPage', ImportThingsPage, '/collections/:code/import', '/collections/COL001/import'],
  [
    'LeaveCollectionPage',
    LeaveCollectionPage,
    '/collections/:code/leave',
    '/collections/COL001/leave',
  ],
];

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'OWNER1');
  apiFetch.mockReset();
  apiFetch.mockImplementation((url) => answer(url));
});
afterEach(() => vi.restoreAllMocks());

describe('a collection’s page wears its collection’s palette', () => {
  test.each(PAGES)('%s', async (_name, Page, pattern, entry) => {
    const { container } = renderAt(Page, pattern, entry);

    await waitFor(() => expect(heroColour(container)).toContain('--color-tram'));
    expect(heroColour(container)).not.toContain('braaanding');
  });

  test('RemoveGuestPage (the palette comes with the navigation state)', async () => {
    const { container } = renderAt(RemoveGuestPage, '/collections/:code/invites/remove', {
      pathname: '/collections/COL001/invites/remove',
      state: {
        guestCode: 'GUEST1',
        guestName: 'Guest',
        palette: { colors: GROUP, koro: 'wave' },
      },
    });

    // No fetch to wait for: it is the group's from the first frame.
    expect(heroColour(container)).toContain('--color-tram');
    expect(apiFetch).not.toHaveBeenCalled();
  });
});

describe('the app’s pages keep the app’s palette', () => {
  test('Home wears the app’s, and a collection page leaves nothing behind when it goes', async () => {
    const group = renderAt(CollectionPage, '/collections/:code', '/collections/COL001');
    await waitFor(() => expect(heroColour(group.container)).toContain('--color-tram'));
    group.unmount();

    const home = renderAt(HomePage, '/', '/');

    await waitFor(() => expect(heroColour(home.container)).toContain('--color-braaanding-03'));
    expect(heroColour(home.container)).not.toContain('tram');
  });
});

describe('a page does not paint its hero before it knows whose colours to wear', () => {
  test.each([
    ['JoinPage', JoinPage, '/collections/:code/join', '/collections/COL001/join'],
    ['SharePage', SharePage, '/share/:token', '/share/TOK'],
    ['AddThingPage', AddThingPage, '/collections/:code/add', '/collections/COL001/add'],
    [
      'ImportInvitesPage',
      ImportInvitesPage,
      '/collections/:code/invites/import',
      '/collections/COL001/invites/import',
    ],
    [
      'ImportThingsPage',
      ImportThingsPage,
      '/collections/:code/import',
      '/collections/COL001/import',
    ],
    [
      'LeaveCollectionPage',
      LeaveCollectionPage,
      '/collections/:code/leave',
      '/collections/COL001/leave',
    ],
  ])(
    '%s: no hero in the app’s palette while the answer is pending',
    async (_n, Page, pattern, entry) => {
      const release = [];
      apiFetch.mockImplementation(
        () =>
          new Promise((resolve) => {
            release.push(() => resolve({ ok: true, status: 200, json: () => Promise.resolve({}) }));
          })
      );

      const { container } = renderAt(Page, pattern, entry);

      expect(container.querySelector('.form-hero')).toBeNull();

      // Let the answers land inside act, so the test ends with the page settled.
      await act(async () => release.forEach((answerNow) => answerNow()));
    }
  );

  test.each([
    ['JoinPage', JoinPage, '/collections/:code/join', '/collections/COL001/join'],
    ['SharePage', SharePage, '/share/:token', '/share/TOK'],
    ['AddThingPage', AddThingPage, '/collections/:code/add', '/collections/COL001/add'],
    [
      'ImportThingsPage',
      ImportThingsPage,
      '/collections/:code/import',
      '/collections/COL001/import',
    ],
    [
      'LeaveCollectionPage',
      LeaveCollectionPage,
      '/collections/:code/leave',
      '/collections/COL001/leave',
    ],
  ])(
    '%s: a collection it cannot read still shows, in the app’s palette',
    async (_n, Page, pattern, entry) => {
      apiFetch.mockImplementation(() => refused());

      const { container } = renderAt(Page, pattern, entry);

      await waitFor(() => expect(container.querySelector('.form-hero')).not.toBeNull());
      expect(heroColour(container)).toContain('--color-braaanding-03');
    }
  );
});
