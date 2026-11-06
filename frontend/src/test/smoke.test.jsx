import { render, waitFor } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { nestedTabStops } from './nestedInteractive';
import { settle } from './settle';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

expect.extend(toHaveNoViolations);

// ── Mock data ──────────────────────────────────────────────────────────
const MOCK_USER = {
  code: 'ABC123',
  email: 'lili3@your-domain.test',
  name: 'Test User',
  headline: '',
  about: 'Contact me at [my site](https://your-domain.test)\n- one\n- two',
  photo: 'oiueei/users/abc',
  photo_url: 'https://bucket.your-domain.test/oiueei/users/abc.jpg',
  thumbnail: '',
  koro: 'basic',
  notify_activity: true,
  notify_news: true,
  theeeme_colors: {
    color_01: 'bus',
    color_02: 'suomenlinna-light',
    color_03: 'copper',
    color_04: 'black',
    color_05: 'white',
    color_06: 'white',
  },
};

const MOCK_COLLECTION = {
  code: 'COL001',
  headline: 'Test Collection',
  description: 'A test collection',
  status: 'ACTIVE',
  owner: 'ABC123',
  owner_name: 'Test User',
  thumbnail_url: '',
  tags: ['Vintage', 'Kitchen'],
  things: [],
  invites: [],
};

const MOCK_THING = {
  code: 'THG001',
  type: 'GIFT_THING',
  headline: 'Test Thing',
  description: 'A test thing',
  status: 'ACTIVE',
  owner: 'ABC123',
  owner_name: 'Test User',
  fee: null,
  availability: '',
  location: '',
  condition: '',
  thumbnail_url: 'https://bucket.your-domain.test/oiueei/things/cover.jpg',
  gallery: ['oiueei/things/g1', 'oiueei/things/g2'],
  gallery_urls: [
    'https://bucket.your-domain.test/oiueei/things/g1.jpg',
    'https://bucket.your-domain.test/oiueei/things/g2.jpg',
  ],
  available_today: null,
  next_available: null,
  tags: ['Vintage'],
  collection_tags: ['Vintage', 'Kitchen'],
  pending_questions: 0,
  my_pending_booking: null,
  pending_booking: null,
};

const MOCK_THEEEMES = [
  {
    code: 'BUU331',
    name: 'Bussi',
    color_01: 'bus',
    color_02: 'suomenlinna-light',
    color_03: 'copper',
    color_04: 'black',
    color_05: 'white',
    color_06: 'white',
  },
];

function mockResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

// ── Mock apiFetch ──────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  apiFetch: vi.fn((url) => {
    if (url.includes('/auth/me/')) return Promise.resolve(mockResponse(MOCK_USER));
    if (url.includes('/notifications/token/'))
      return Promise.resolve(mockResponse({ notify_activity: true, notify_news: true }));
    if (url.includes('/theeemes/')) return Promise.resolve(mockResponse(MOCK_THEEEMES));
    if (url.match(/\/share\/[^/]+\/preview\//))
      return Promise.resolve(
        mockResponse({ headline: 'The Tool Library', description: 'Borrow, do not buy.' })
      );
    if (url.includes('/my-bookings/')) return Promise.resolve(mockResponse({ results: [] }));
    if (url.includes('/my-invitations/')) return Promise.resolve(mockResponse({ results: [] }));
    if (url.includes('/invited-collections/')) return Promise.resolve(mockResponse([]));
    if (url.match(/\/things\/[^/]+\/faq\//)) return Promise.resolve(mockResponse({ results: [] }));
    if (url.match(/\/things\/[^/]+\/calendar\//))
      return Promise.resolve(mockResponse({ results: [] }));
    if (url.match(/\/things\/[^/]+\//)) return Promise.resolve(mockResponse(MOCK_THING));
    if (url.includes('/things/')) return Promise.resolve(mockResponse({ results: [] }));
    if (url.match(/\/collections\/[^/]+\//)) return Promise.resolve(mockResponse(MOCK_COLLECTION));
    if (url.includes('/collections/')) return Promise.resolve(mockResponse({ results: [] }));
    if (url.match(/\/users\/[^/]+\//))
      return Promise.resolve(mockResponse({ ...MOCK_USER, collections: [] }));
    return Promise.resolve(mockResponse({}));
  }),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

// ── Mock global fetch (LoginPage, VerifyPage use fetch directly) ──────
globalThis.fetch = vi.fn(() =>
  Promise.resolve({ ok: false, status: 400, json: () => Promise.resolve({ error: 'mock' }) })
);

// ── Helper: render with route params ──────────────────────────────────
function renderWithRoute(Component, { path, entry, state } = {}) {
  const initialEntry = state ? { pathname: entry || '/', state } : entry || '/';
  return render(
    <MemoryRouter initialEntries={[initialEntry]}>
      <Routes>
        <Route path={path || '/'} element={<Component />} />
        {/* Catch-all so navigations don't crash */}
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

// ── Imports ────────────────────────────────────────────────────────────
import { apiFetch } from '../services/api';
import LoginPage from '../pages/LoginPage';
import LogoutPage from '../pages/LogoutPage';
import VerifyPage from '../pages/VerifyPage';
import NewCollectionPage from '../pages/NewCollectionPage';
import CreateCollectionPage from '../pages/CreateCollectionPage';
import AddThingPage from '../pages/AddThingPage';
import ImportThingsPage from '../pages/ImportThingsPage';
import ImportInvitesPage from '../pages/ImportInvitesPage';
import MyBookingsPage from '../pages/MyBookingsPage';
import OwnerBookingsPage from '../pages/OwnerBookingsPage';
import DeleteThingPage from '../pages/DeleteThingPage';
import RemoveGuestPage from '../pages/RemoveGuestPage';
import LeaveCollectionPage from '../pages/LeaveCollectionPage';
import EditCollectionPage from '../pages/EditCollectionPage';
import EditProfilePage from '../pages/EditProfilePage';
import DeleteAccountPage from '../pages/DeleteAccountPage';
import DataExportPage from '../pages/DataExportPage';
import LegalPage from '../pages/LegalPage';
import ContactPage from '../pages/ContactPage';
import DigestMutePage from '../pages/DigestMutePage';
import NotificationsPage from '../pages/NotificationsPage';
import OrganisationPage from '../pages/OrganisationPage';
import ManageInvitesPage from '../pages/ManageInvitesPage';
import HomePage from '../pages/HomePage';
import CollectionPage from '../pages/CollectionPage';
import ThingPage from '../pages/ThingPage';
import EditThingPage from '../pages/EditThingPage';
import RequestThingPage from '../pages/RequestThingPage';
import UserPage from '../pages/UserPage';
import SharePage from '../pages/SharePage';
import JoinPage from '../pages/JoinPage';
import DeleteCollectionPage from '../pages/DeleteCollectionPage';
import NotFoundPage from '../pages/NotFoundPage';

// ── Setup ──────────────────────────────────────────────────────────────
beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  vi.clearAllMocks();
});

// Nesting that predates the invariant, named per surface so it can only shrink.
// **It is empty, and that is the state to keep it in.** The 25 entries it was born
// with were all `<Link>` wrapping an HDS `<Button>` — one control, two tab stops —
// and every one of them is now `ButtonLink`. An entry that no longer matches fails
// as loudly as a new violation: a surface that has been cleaned up must lose its
// line, or the list stops describing the app and starts hiding it.
const KNOWN_NESTING = {};

// ── Smoke + axe helper ─────────────────────────────────────────────────
function smokeAndAxe(name, Component, routeOpts) {
  describe(name, () => {
    test('renders without crashing', async () => {
      const { container } = renderWithRoute(Component, routeOpts);
      await waitFor(() => {
        expect(
          container.querySelector('.form-page, .page-container, form, [data-testid="navigated"]')
        ).toBeTruthy();
      });
      await settle(apiFetch, globalThis.fetch);
    });

    test('has no accessibility violations', async () => {
      const { container } = renderWithRoute(Component, routeOpts);
      // Wait for async rendering to settle
      await waitFor(() => {
        expect(
          container.querySelector('.form-page, .page-container, form, [data-testid="navigated"]')
        ).toBeTruthy();
      });
      await settle(apiFetch, globalThis.fetch);
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });

    // axe returns no violation for `<a href><button></a>` and jsx-a11y has no
    // rule for it, so this invariant is the only thing standing between the app
    // and another 28 of them. See `nestedInteractive.js` for why it counts tab
    // stops rather than roles, and KNOWN_NESTING below for the debt it carries.
    test('no tab stop contains another', async () => {
      const { container } = renderWithRoute(Component, routeOpts);
      await settle(apiFetch, globalThis.fetch);
      const found = nestedTabStops(container);
      const allowed = KNOWN_NESTING[name] || [];
      expect(
        found.filter((f) => !allowed.includes(f)),
        `${name}: new nesting. One control, two tab stops — use Link + useButtonStyles`
      ).toEqual([]);
      expect(
        allowed.filter((a) => !found.includes(a)),
        `${name}: KNOWN_NESTING entry no longer matches — delete it`
      ).toEqual([]);
    });
  });
}

// ── Pages without route params ─────────────────────────────────────────
smokeAndAxe('LoginPage', LoginPage);
smokeAndAxe('NewCollectionPage', NewCollectionPage);
smokeAndAxe('CreateCollectionPage', CreateCollectionPage);
smokeAndAxe('MyBookingsPage', MyBookingsPage);
smokeAndAxe('OwnerBookingsPage', OwnerBookingsPage);
smokeAndAxe('HomePage', HomePage);
smokeAndAxe('EditProfilePage', EditProfilePage);
smokeAndAxe('DeleteAccountPage', DeleteAccountPage);
smokeAndAxe('DataExportPage', DataExportPage);
smokeAndAxe('LegalPage', LegalPage);
smokeAndAxe('ContactPage', ContactPage);
smokeAndAxe('DigestMutePage', DigestMutePage);
smokeAndAxe('NotificationsPage', NotificationsPage);

// ── Pages with route params ────────────────────────────────────────────
smokeAndAxe('AddThingPage', AddThingPage, {
  path: '/collections/:code/add',
  entry: '/collections/COL001/add',
});

smokeAndAxe('OrganisationPage', OrganisationPage, {
  path: '/collections/:code/organisation',
  entry: '/collections/COL001/organisation',
});

smokeAndAxe('ImportThingsPage', ImportThingsPage, {
  path: '/collections/:code/import',
  entry: '/collections/COL001/import',
});

smokeAndAxe('CollectionPage', CollectionPage, {
  path: '/collections/:code',
  entry: '/collections/COL001',
});

smokeAndAxe('EditCollectionPage', EditCollectionPage, {
  path: '/collections/:code/edit',
  entry: '/collections/COL001/edit',
});

smokeAndAxe('ManageInvitesPage', ManageInvitesPage, {
  path: '/collections/:code/invites',
  entry: '/collections/COL001/invites',
});

smokeAndAxe('ImportInvitesPage', ImportInvitesPage, {
  path: '/collections/:code/invites/import',
  entry: '/collections/COL001/invites/import',
});

smokeAndAxe('DeleteCollectionPage', DeleteCollectionPage, {
  path: '/collections/:code/delete',
  entry: '/collections/COL001/delete',
});

smokeAndAxe('JoinPage', JoinPage, {
  path: '/collections/:code/join',
  entry: '/collections/COL001/join',
  state: { collectionHeadline: 'Test Collection' },
});

smokeAndAxe('ThingPage', ThingPage, {
  path: '/things/:thingCode',
  entry: '/things/THG001',
});

smokeAndAxe('EditThingPage', EditThingPage, {
  path: '/things/:thingCode/edit',
  entry: '/things/THG001/edit',
});

smokeAndAxe('DeleteThingPage', DeleteThingPage, {
  path: '/things/:thingCode/delete',
  entry: '/things/THG001/delete',
});

smokeAndAxe('RequestThingPage', RequestThingPage, {
  path: '/things/:thingCode/request',
  entry: '/things/THG001/request',
});

smokeAndAxe('UserPage', UserPage, {
  path: '/:userCode',
  entry: '/ABC123',
});

smokeAndAxe('RemoveGuestPage', RemoveGuestPage, {
  path: '/collections/:code/invites/remove',
  entry: '/collections/COL001/invites/remove',
  state: { guestCode: 'GUE001', guestName: 'Guest User', backLabel: 'Test' },
});

smokeAndAxe('LeaveCollectionPage', LeaveCollectionPage, {
  path: '/collections/:code/leave',
  entry: '/collections/COL001/leave',
  state: { headline: 'Test Collection' },
});

smokeAndAxe('VerifyPage', VerifyPage, {
  path: '/verify/:code',
  entry: '/verify/RSVP01',
});

smokeAndAxe('LogoutPage', LogoutPage);

smokeAndAxe('SharePage', SharePage, {
  path: '/share/:token',
  entry: '/share/aB3xK_9-pQrS2tUvWx1y',
});

smokeAndAxe('NotFoundPage', NotFoundPage);
