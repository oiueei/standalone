import { render, waitFor } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

expect.extend(toHaveNoViolations);

// ── Mock data ──────────────────────────────────────────────────────────
const MOCK_USER = {
  code: 'ABC123',
  email: 'test@example.com',
  name: 'Test User',
  headline: '',
  about: 'Contact me at [my site](https://example.com)\n- one\n- two',
  photo: 'oiueei/users/abc',
  photo_url: 'https://res.cloudinary.com/demo/image/upload/oiueei/users/abc.jpg',
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
  thumbnail_url: 'https://res.cloudinary.com/demo/image/upload/oiueei/things/cover.jpg',
  gallery: ['oiueei/things/g1', 'oiueei/things/g2'],
  gallery_urls: [
    'https://res.cloudinary.com/demo/image/upload/oiueei/things/g1.jpg',
    'https://res.cloudinary.com/demo/image/upload/oiueei/things/g2.jpg',
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
  { code: 'BUU331', name: 'Bussi', color_01: 'bus', color_02: 'suomenlinna-light', color_03: 'copper', color_04: 'black', color_05: 'white', color_06: 'white' },
];

function mockResponse(data, ok = true) {
  return { ok, status: ok ? 200 : 400, json: () => Promise.resolve(data) };
}

// ── Mock apiFetch ──────────────────────────────────────────────────────
vi.mock('../services/api', () => ({
  apiFetch: vi.fn((url) => {
    if (url.includes('/auth/me/')) return Promise.resolve(mockResponse(MOCK_USER));
    if (url.includes('/notifications/token/')) return Promise.resolve(mockResponse({ notify_activity: true, notify_news: true }));
    if (url.includes('/theeemes/')) return Promise.resolve(mockResponse(MOCK_THEEEMES));
    if (url.includes('/my-bookings/')) return Promise.resolve(mockResponse({ results: [] }));
    if (url.includes('/my-invitations/')) return Promise.resolve(mockResponse({ results: [] }));
    if (url.includes('/invited-collections/')) return Promise.resolve(mockResponse([]));
    if (url.includes('/invited-things/')) return Promise.resolve(mockResponse({ results: [] }));
    if (url.match(/\/things\/[^/]+\/faq\//)) return Promise.resolve(mockResponse({ results: [] }));
    if (url.match(/\/things\/[^/]+\/calendar\//)) return Promise.resolve(mockResponse({ results: [] }));
    if (url.match(/\/things\/[^/]+\//)) return Promise.resolve(mockResponse(MOCK_THING));
    if (url.includes('/things/')) return Promise.resolve(mockResponse({ results: [] }));
    if (url.match(/\/collections\/[^/]+\//)) return Promise.resolve(mockResponse(MOCK_COLLECTION));
    if (url.includes('/collections/')) return Promise.resolve(mockResponse({ results: [] }));
    if (url.match(/\/users\/[^/]+\//)) return Promise.resolve(mockResponse({ ...MOCK_USER, collections: [] }));
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
  const initialEntry = state ? { pathname: entry || '/', state } : (entry || '/');
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
import LoginPage from '../pages/LoginPage';
import LogoutPage from '../pages/LogoutPage';
import VerifyPage from '../pages/VerifyPage';
import WelcomePage from '../pages/WelcomePage';
import CreateCollectionPage from '../pages/CreateCollectionPage';
import AddThingPage from '../pages/AddThingPage';
import MyBookingsPage from '../pages/MyBookingsPage';
import DeleteThingPage from '../pages/DeleteThingPage';
import RemoveGuestPage from '../pages/RemoveGuestPage';
import EditCollectionPage from '../pages/EditCollectionPage';
import EditProfilePage from '../pages/EditProfilePage';
import NotificationsPage from '../pages/NotificationsPage';
import ManageInvitesPage from '../pages/ManageInvitesPage';
import HomePage from '../pages/HomePage';
import CollectionPage from '../pages/CollectionPage';
import ThingPage from '../pages/ThingPage';
import EditThingPage from '../pages/EditThingPage';
import RequestThingPage from '../pages/RequestThingPage';
import RespondWishPage from '../pages/RespondWishPage';
import UserPage from '../pages/UserPage';
import SharePage from '../pages/SharePage';
import PopInPage from '../pages/PopInPage';
import JoinPage from '../pages/JoinPage';
import DeleteCollectionPage from '../pages/DeleteCollectionPage';
import NotFoundPage from '../pages/NotFoundPage';

// ── Setup ──────────────────────────────────────────────────────────────
beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  localStorage.setItem('theeemeColors', JSON.stringify(MOCK_USER.theeeme_colors));
  localStorage.setItem('koro', 'basic');
  vi.clearAllMocks();
});

// ── Smoke + axe helper ─────────────────────────────────────────────────
function smokeAndAxe(name, Component, routeOpts) {
  describe(name, () => {
    test('renders without crashing', async () => {
      const { container } = renderWithRoute(Component, routeOpts);
      await waitFor(() => {
        expect(container.querySelector('.form-page, .page-container, form, [data-testid="navigated"]')).toBeTruthy();
      });
    });

    test('has no accessibility violations', async () => {
      const { container } = renderWithRoute(Component, routeOpts);
      // Wait for async rendering to settle
      await waitFor(() => {
        expect(container.querySelector('.form-page, .page-container, form, [data-testid="navigated"]')).toBeTruthy();
      });
      const results = await axe(container);
      expect(results).toHaveNoViolations();
    });
  });
}

// ── Pages without route params ─────────────────────────────────────────
smokeAndAxe('LoginPage', LoginPage);
smokeAndAxe('WelcomePage', WelcomePage);
smokeAndAxe('CreateCollectionPage', CreateCollectionPage);
smokeAndAxe('MyBookingsPage', MyBookingsPage);
smokeAndAxe('HomePage', HomePage);
smokeAndAxe('EditProfilePage', EditProfilePage);
smokeAndAxe('NotificationsPage', NotificationsPage);

// ── Pages with route params ────────────────────────────────────────────
smokeAndAxe('AddThingPage', AddThingPage, {
  path: '/collections/:code/add',
  entry: '/collections/COL001/add',
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

smokeAndAxe('RespondWishPage (know-where)', RespondWishPage, {
  path: '/things/:thingCode/respond/:kind',
  entry: '/things/THG001/respond/know-where',
});

smokeAndAxe('RespondWishPage (can-make)', RespondWishPage, {
  path: '/things/:thingCode/respond/:kind',
  entry: '/things/THG001/respond/can-make',
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

smokeAndAxe('VerifyPage', VerifyPage, {
  path: '/verify/:code',
  entry: '/verify/RSVP01',
});

smokeAndAxe('LogoutPage', LogoutPage);

smokeAndAxe('PopInPage', PopInPage);

smokeAndAxe('SharePage', SharePage, {
  path: '/share/:token',
  entry: '/share/aB3xK_9-pQrS2tUvWx1y',
});

smokeAndAxe('NotFoundPage', NotFoundPage);
