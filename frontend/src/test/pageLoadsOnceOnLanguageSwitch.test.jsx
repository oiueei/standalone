import { render, screen, waitFor, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { useTranslation } from 'react-i18next';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

/**
 * A page of a collection written in another language asks for its data once.
 *
 * `useCollectionLanguage` switches the interface language when the page's first
 * response says the collection speaks one. That changes the identity of `t`, and
 * a load effect listing `t` among its dependencies runs a second time: a second
 * GET of everything, the heaviest payload the app has (the whole collection with
 * all its things) included, and for the edit pages a second `setState` of every
 * field from the server's copy — over whatever was typed in the meantime. Measured
 * on `CollectionPage` and `ThingPage` (2026-09-29): two GETs, and one once `t`
 * left the dependencies. It bites most where nobody has a session to hold a saved
 * language, i.e. a visitor reading a public collection.
 *
 * Here the real `useCollectionLanguage` and the real `../i18n` run against pages
 * whose response says `language: 'es'`, from an English browser. Each page must
 * have asked for its resource exactly once by the time Spanish has been painted.
 * (The load effects keep the *key* of an error and translate at render, which is
 * what lets them stop depending on `t`; the last describe pins that side.)
 *
 * The probe beside each page paints `common.home`. It is the sign that the
 * language switch has been committed — and that the page, subscribed to the same
 * event, re-rendered with the new `t` in that same pass — so the count is read
 * *after* the moment the bug would have fired rather than after a guessed delay.
 */

window.scrollTo = vi.fn();

vi.mock('../services/api', async (importOriginal) => ({
  ...(await importOriginal()),
  apiFetch: vi.fn(),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));
// Only who the visitor is on record as speaking is faked: "no saved preference",
// which is the case where the collection's language is allowed to apply.
vi.mock('../hooks/useCapabilities', async (importOriginal) => ({
  ...(await importOriginal()),
  loadUserLanguage: vi.fn(),
}));

import i18n from '../i18n';
import en from '../i18n/locales/en.json';
import es from '../i18n/locales/es.json';
import { apiFetch } from '../services/api';
import { loadUserLanguage } from '../hooks/useCapabilities';
import CollectionPage from '../pages/CollectionPage';
import ThingPage from '../pages/ThingPage';
import EditThingPage from '../pages/EditThingPage';
import EditCollectionPage from '../pages/EditCollectionPage';
import ManageInvitesPage from '../pages/ManageInvitesPage';
import AddThingPage from '../pages/AddThingPage';
import ImportThingsPage from '../pages/ImportThingsPage';
import ImportInvitesPage from '../pages/ImportInvitesPage';
import RequestThingPage from '../pages/RequestThingPage';
import DeleteThingPage from '../pages/DeleteThingPage';
import DeleteCollectionPage from '../pages/DeleteCollectionPage';
import JoinPage from '../pages/JoinPage';
import SharePage from '../pages/SharePage';
import OrganisationPage from '../pages/OrganisationPage';
import EntityPage from '../pages/EntityPage';
import CollectionAppearancePage from '../pages/CollectionAppearancePage';
import CollectionNotificationsPage from '../pages/CollectionNotificationsPage';
import CollectionAvailabilityPage from '../pages/CollectionAvailabilityPage';
import LeaveCollectionPage from '../pages/LeaveCollectionPage';

const STORAGE_KEY = 'i18nextLng';

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });
const refused = (status) =>
  Promise.resolve({ ok: false, status, json: () => Promise.resolve({ detail: 'no' }) });

// The subsets of the serializers' output these pages read, all saying `es`.
const COLLECTION = {
  code: 'COL001',
  headline: 'Test Collection',
  description: 'A test collection',
  status: 'ACTIVE',
  owner: 'ABC123',
  owner_name: 'Test User',
  is_curator: true,
  language: 'es',
  thumbnail_url: '',
  tags: [],
  things: [],
  invites: [],
  co_owners: [],
};
const THING = {
  code: 'THG001',
  type: 'LEND_THING',
  headline: 'Test Thing',
  description: 'A test thing',
  status: 'ACTIVE',
  owner: 'ABC123',
  owner_name: 'Test User',
  collection_code: 'COL001',
  collection_language: 'es',
  thumbnail_url: '',
  gallery: [],
  gallery_urls: [],
  tags: [],
  collection_tags: [],
  available_today: true,
  next_available: null,
};
const PREVIEW = { headline: 'The Tool Library', description: 'Borrow.', language: 'es' };

function respond(url) {
  const path = url.split('?')[0];
  if (/\/share\/[^/]+\/preview\/$/.test(path)) return ok(PREVIEW);
  if (/\/things\/[^/]+\/faq\/$/.test(path)) return ok({ results: [] });
  if (/\/things\/[^/]+\/transfers\/$/.test(path)) return ok({ total_transfers: 0, transfers: [] });
  if (/\/things\/[^/]+\/calendar\/$/.test(path)) return ok([]);
  if (/\/things\/[^/]+\/$/.test(path)) return ok(THING);
  if (/\/collections\/[^/]+\/$/.test(path)) return ok(COLLECTION);
  if (path.includes('/inbox/')) return ok([]);
  return ok({});
}

// `gets` are the exact URLs the page owes the network, each of them once.
const PAGES = [
  {
    name: 'CollectionPage',
    Page: CollectionPage,
    route: '/collections/:code',
    entry: '/collections/COL001',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'ThingPage',
    Page: ThingPage,
    route: '/collections/:code/things/:thingCode',
    entry: '/collections/COL001/things/THG001',
    gets: ['/api/v1/things/THG001/?collection=COL001', '/api/v1/things/THG001/transfers/'],
  },
  {
    name: 'EditThingPage',
    Page: EditThingPage,
    route: '/things/:thingCode/edit',
    entry: '/things/THG001/edit',
    gets: ['/api/v1/things/THG001/'],
  },
  {
    name: 'EditCollectionPage',
    Page: EditCollectionPage,
    route: '/collections/:code/edit',
    entry: '/collections/COL001/edit',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'ManageInvitesPage',
    Page: ManageInvitesPage,
    route: '/collections/:code/invites',
    entry: '/collections/COL001/invites',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'OrganisationPage',
    Page: OrganisationPage,
    route: '/collections/:code/organisation',
    entry: '/collections/COL001/organisation',
    gets: ['/api/v1/collections/COL001/', '/api/v1/collections/COL001/point/'],
  },
  // These never listed `t`; they are in the table so it stays that way.
  {
    name: 'AddThingPage',
    Page: AddThingPage,
    route: '/collections/:code/add',
    entry: '/collections/COL001/add',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'ImportThingsPage',
    Page: ImportThingsPage,
    route: '/collections/:code/import',
    entry: '/collections/COL001/import',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'ImportInvitesPage',
    Page: ImportInvitesPage,
    route: '/collections/:code/invites/import',
    entry: '/collections/COL001/invites/import',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'RequestThingPage',
    Page: RequestThingPage,
    route: '/things/:thingCode/request',
    entry: '/things/THG001/request',
    gets: ['/api/v1/things/THG001/'],
  },
  {
    name: 'DeleteThingPage',
    Page: DeleteThingPage,
    route: '/things/:thingCode/delete',
    entry: '/things/THG001/delete',
    gets: ['/api/v1/things/THG001/'],
  },
  {
    name: 'DeleteCollectionPage',
    Page: DeleteCollectionPage,
    route: '/collections/:code/delete',
    entry: '/collections/COL001/delete',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'JoinPage',
    Page: JoinPage,
    route: '/collections/:code/join',
    entry: '/collections/COL001/join',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'SharePage',
    Page: SharePage,
    route: '/share/:token',
    entry: '/share/aB3xK_9-pQrS2tUvWx1y',
    gets: ['/api/v1/share/aB3xK_9-pQrS2tUvWx1y/preview/'],
  },
  {
    name: 'EntityPage',
    Page: EntityPage,
    route: '/collections/:code/organisation/:userCode',
    entry: '/collections/COL001/organisation/ABC123',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'CollectionAppearancePage',
    Page: CollectionAppearancePage,
    route: '/collections/:code/settings/appearance',
    entry: '/collections/COL001/settings/appearance',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'CollectionNotificationsPage',
    Page: CollectionNotificationsPage,
    route: '/collections/:code/settings/notifications',
    entry: '/collections/COL001/settings/notifications',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'LeaveCollectionPage',
    Page: LeaveCollectionPage,
    route: '/collections/:code/leave',
    entry: '/collections/COL001/leave',
    gets: ['/api/v1/collections/COL001/'],
  },
  {
    name: 'CollectionAvailabilityPage',
    Page: CollectionAvailabilityPage,
    route: '/collections/:code/settings/availability',
    entry: '/collections/COL001/settings/availability',
    // Availability paints not-found for a stall, and the common collection is no one's kind.
    collection: { kind: 'LIBRARY' },
    gets: ['/api/v1/collections/COL001/'],
  },
];

function Probe() {
  const { t } = useTranslation();
  return <output data-testid="probe">{t('common.home')}</output>;
}

function renderPage(page) {
  const PageUnderTest = page.Page;
  return render(
    <MemoryRouter initialEntries={[page.entry]}>
      <Probe />
      <Routes>
        <Route path={page.route} element={<PageUnderTest />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

const timesAsked = (url) => apiFetch.mock.calls.filter(([asked]) => asked === url).length;

beforeEach(async () => {
  vi.clearAllMocks();
  loadUserLanguage.mockResolvedValue('');
  apiFetch.mockImplementation((url) => respond(url));
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  await act(async () => {
    await i18n.changeLanguage('en');
  });
  // The reset re-caches 'en' as a real choice; the app starts a fresh visitor
  // from "nothing cached", and so does every test here.
  localStorage.removeItem(STORAGE_KEY);
});

afterEach(async () => {
  await act(async () => {
    await i18n.changeLanguage('en');
  });
  localStorage.removeItem(STORAGE_KEY);
});

describe("a page of a collection in another language asks for its data once, whatever 't' does", () => {
  test.each(PAGES)('$name', async (page) => {
    if (page.collection) {
      apiFetch.mockImplementation((url) =>
        /\/collections\/[^/]+\/$/.test(url)
          ? ok({ ...COLLECTION, ...page.collection })
          : respond(url)
      );
    }
    renderPage(page);

    // The collection says Spanish, the browser English: the hook moves the UI.
    await waitFor(() => expect(i18n.language).toBe('es'));
    await waitFor(() => expect(screen.getByTestId('probe')).toHaveTextContent(es.common.home));
    // Passive effects of that commit — the ones that would fetch again — are
    // flushed before anything is counted.
    await act(async () => {});

    for (const url of page.gets) expect(timesAsked(url), url).toBe(1);
  });
});

describe("an owner who wrote the title in the reader's language keeps the reader's language", () => {
  test('OrganisationPage: a per-language title vetoes the collection language', async () => {
    const localized = { ...COLLECTION, headline: '{"es": "Las cosas", "en": "The things"}' };
    apiFetch.mockImplementation((url) =>
      /\/collections\/[^/]+\/$/.test(url) ? ok(localized) : respond(url)
    );

    renderPage(PAGES.find((page) => page.name === 'OrganisationPage'));

    // The page has painted its data (the group's title in English)...
    expect(await screen.findByText('The things')).toBeInTheDocument();
    await act(async () => {});
    // ...and the group's Spanish did not take the interface over.
    expect(i18n.language).toBe('en');
    expect(screen.getByTestId('probe')).toHaveTextContent(en.common.home);
  });
});

describe('a refused load still says why, in the language being read', () => {
  const PAGE_403 = [
    {
      name: 'CollectionPage',
      Page: CollectionPage,
      route: '/collections/:code',
      entry: '/collections/COL001',
      key: 'collectionPage.noPermission',
    },
    {
      name: 'ThingPage',
      Page: ThingPage,
      route: '/things/:thingCode',
      entry: '/things/THG001',
      key: 'thingPage.noPermission',
    },
    {
      name: 'ManageInvitesPage',
      Page: ManageInvitesPage,
      route: '/collections/:code/invites',
      entry: '/collections/COL001/invites',
      key: 'manageInvites.noPermission',
    },
  ];
  const at = (bundle, key) => key.split('.').reduce((node, part) => node[part], bundle);

  test.each(PAGE_403)('$name: a 403 paints noPermission', async (page) => {
    apiFetch.mockImplementation((url) =>
      /\/(collections|things)\/[^/]+\/(\?.*)?$/.test(url) ? refused(403) : respond(url)
    );

    renderPage(page);

    expect(await screen.findByText(at(en, page.key))).toBeInTheDocument();
  });

  test.each(PAGE_403)('$name: the message follows a language change after it', async (page) => {
    apiFetch.mockImplementation((url) =>
      /\/(collections|things)\/[^/]+\/(\?.*)?$/.test(url) ? refused(403) : respond(url)
    );
    renderPage(page);
    await screen.findByText(at(en, page.key));

    await act(async () => {
      await i18n.changeLanguage('es');
    });

    // The English sentence would still be here if the effect had translated it
    // on the way in and stored the result.
    expect(await screen.findByText(at(es, page.key))).toBeInTheDocument();
    expect(screen.queryByText(at(en, page.key))).not.toBeInTheDocument();
  });

  test('OrganisationPage: a refused point says it is not for them, in the language being read', async () => {
    apiFetch.mockImplementation((url) => (/\/point\/$/.test(url) ? refused(403) : respond(url)));

    renderPage(PAGES.find((page) => page.name === 'OrganisationPage'));

    // The group speaks Spanish: the sentence follows, it was not translated on the way in.
    expect(await screen.findByText(es.organisation.notACurator)).toBeInTheDocument();
    expect(screen.queryByText(en.organisation.notACurator)).not.toBeInTheDocument();
  });

  test('CollectionPage: a request that never arrives paints the connection error', async () => {
    apiFetch.mockImplementation((url) =>
      /\/collections\/[^/]+\/$/.test(url) ? Promise.reject(new Error('offline')) : respond(url)
    );

    renderPage(PAGES[0]);

    expect(await screen.findByText(en.common.connectionError)).toBeInTheDocument();
  });

  test.each([
    {
      name: 'EditThingPage',
      Page: EditThingPage,
      route: '/things/:thingCode/edit',
      entry: '/things/THG001/edit',
      key: 'editThing.errorLoading',
    },
    {
      name: 'EditCollectionPage',
      Page: EditCollectionPage,
      route: '/collections/:code/edit',
      entry: '/collections/COL001/edit',
      key: 'editCollection.errorLoading',
    },
  ])('$name: a failed load raises its toast', async (page) => {
    apiFetch.mockImplementation((url) =>
      /\/(collections|things)\/[^/]+\/$/.test(url) ? refused(500) : respond(url)
    );

    renderPage(page);

    expect(await screen.findByText(at(en, page.key))).toBeInTheDocument();
  });
});
