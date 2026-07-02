import './i18n';
import 'hds-design-tokens';
import 'hds-core/lib/base.css';
import './fonts/oiueei-fonts.css';
import './styles/oiueei-theme.css';
import { useEffect, useRef, lazy, Suspense } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import i18n from './i18n';
import RequireAuth from './components/RequireAuth';
import LoadingSpinner from './components/LoadingSpinner';
import './App.css';

// Pages are lazy-loaded so each route ships as its own chunk: the initial bundle
// no longer carries all 25 pages (and page-only deps like papaparse/qrcode load
// only with the routes that use them). The Suspense fallback below covers the
// brief chunk fetch on first visit to each route.
const LoginPage = lazy(() => import('./pages/LoginPage'));
const VerifyPage = lazy(() => import('./pages/VerifyPage'));
const HomePage = lazy(() => import('./pages/HomePage'));
const CollectionPage = lazy(() => import('./pages/CollectionPage'));
const AddThingPage = lazy(() => import('./pages/AddThingPage'));
const EditThingPage = lazy(() => import('./pages/EditThingPage'));
const ThingPage = lazy(() => import('./pages/ThingPage'));
const CreateCollectionPage = lazy(() => import('./pages/CreateCollectionPage'));
const EditCollectionPage = lazy(() => import('./pages/EditCollectionPage'));
const EditProfilePage = lazy(() => import('./pages/EditProfilePage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));
const ManageInvitesPage = lazy(() => import('./pages/ManageInvitesPage'));
const LogoutPage = lazy(() => import('./pages/LogoutPage'));
const UserPage = lazy(() => import('./pages/UserPage'));
const RequestThingPage = lazy(() => import('./pages/RequestThingPage'));
const RespondWishPage = lazy(() => import('./pages/RespondWishPage'));
const DeleteThingPage = lazy(() => import('./pages/DeleteThingPage'));
const DeleteCollectionPage = lazy(() => import('./pages/DeleteCollectionPage'));
const RemoveGuestPage = lazy(() => import('./pages/RemoveGuestPage'));
const LeaveCollectionPage = lazy(() => import('./pages/LeaveCollectionPage'));
const MyBookingsPage = lazy(() => import('./pages/MyBookingsPage'));
const WelcomePage = lazy(() => import('./pages/WelcomePage'));
const PopInPage = lazy(() => import('./pages/PopInPage'));
const SharePage = lazy(() => import('./pages/SharePage'));
const JoinPage = lazy(() => import('./pages/JoinPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));

/**
 * On every route change (but not the initial mount), move focus to the main
 * landmark and scroll to top so keyboard and screen-reader users start at the
 * new page's content rather than wherever focus was left on the previous page.
 *
 * The initial mount is skipped on purpose: stealing focus into `<main>` on load
 * would make the skip link — which precedes `<main>` — unreachable by the first
 * forward Tab, defeating its purpose. On a fresh load focus stays at the top so
 * the skip link is the first tab stop.
 */
function RouteFocusReset() {
  const { pathname } = useLocation();
  // Seed with the initial path so the first mount is a no-op. Comparing the
  // path (rather than a "first render" boolean) is also robust to StrictMode's
  // double effect-invocation in dev, which re-runs the effect with the same
  // path and would otherwise defeat a boolean guard.
  const prevPath = useRef(pathname);
  useEffect(() => {
    if (prevPath.current === pathname) return;
    prevPath.current = pathname;
    const main = document.getElementById('main');
    if (main) main.focus();
    window.scrollTo(0, 0);
  }, [pathname]);
  return null;
}

function App() {
  const { t } = useTranslation();

  useEffect(() => {
    fetch('/api/v1/auth/me/', { credentials: 'same-origin' }).catch(() => {});
  }, []);

  useEffect(() => {
    document.documentElement.lang = i18n.language;
    const handleLangChange = (lng) => { document.documentElement.lang = lng; };
    i18n.on('languageChanged', handleLangChange);
    return () => i18n.off('languageChanged', handleLangChange);
  }, []);

  return (
    <BrowserRouter>
      <a href="#main" className="skip-link">{t('common.skipToContent')}</a>
      <RouteFocusReset />
      <main id="main" tabIndex={-1}>
        <Suspense fallback={<LoadingSpinner />}>
        <Routes>
        {/* Public routes — reachable without signing in */}
        <Route path="/login" element={<LoginPage />} />
        <Route path="/logout" element={<LogoutPage />} />
        <Route path="/verify/:code" element={<VerifyPage />} />
        <Route path="/rsvp/:code" element={<VerifyPage />} />
        <Route path="/magic-link/:code" element={<VerifyPage />} />
        <Route path="/me/notifications/:token" element={<NotificationsPage />} />
        <Route path="/welcome" element={<WelcomePage />} />
        <Route path="/popin" element={<PopInPage />} />
        <Route path="/share/:token" element={<SharePage />} />

        {/* Public read of PUBLIC collections/things — anonymous visitors can
            browse; can_view() gates it server-side (PUBLIC + ACTIVE only) and the
            pages hide every owner/member action behind an auth check. */}
        <Route path="/collections/:code" element={<CollectionPage />} />
        <Route path="/collections/:code/things/:thingCode" element={<ThingPage />} />
        <Route path="/things/:thingCode" element={<ThingPage />} />
        <Route path="/collections/:code/join" element={<JoinPage />} />

        {/* Protected routes — RequireAuth redirects to /login when signed out */}
        <Route element={<RequireAuth />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/me" element={<UserPage />} />
          <Route path="/me/edit" element={<EditProfilePage />} />
          <Route path="/collections/new" element={<CreateCollectionPage />} />
          <Route path="/collections/:code/edit" element={<EditCollectionPage />} />
          <Route path="/collections/:code/delete" element={<DeleteCollectionPage />} />
          <Route path="/collections/:code/invites" element={<ManageInvitesPage />} />
          <Route path="/collections/:code/leave" element={<LeaveCollectionPage />} />
          <Route path="/collections/:code/add" element={<AddThingPage />} />
          <Route path="/collections/:code/things/:thingCode/edit" element={<EditThingPage />} />
          <Route
            path="/collections/:code/things/:thingCode/request"
            element={<RequestThingPage />}
          />
          <Route
            path="/collections/:code/things/:thingCode/respond/:kind"
            element={<RespondWishPage />}
          />
          <Route
            path="/collections/:code/things/:thingCode/delete"
            element={<DeleteThingPage />}
          />
          <Route path="/collections/:code/invites/remove" element={<RemoveGuestPage />} />
          <Route path="/things/:thingCode/edit" element={<EditThingPage />} />
          <Route path="/things/:thingCode/request" element={<RequestThingPage />} />
          <Route path="/things/:thingCode/respond/:kind" element={<RespondWishPage />} />
          <Route path="/things/:thingCode/delete" element={<DeleteThingPage />} />
          <Route path="/my-bookings" element={<MyBookingsPage />} />
          <Route path="/:userCode" element={<UserPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
        </Routes>
        </Suspense>
      </main>
    </BrowserRouter>
  );
}

export default App;
