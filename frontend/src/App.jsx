import './i18n';
import 'hds-design-tokens';
import 'hds-core/lib/base.css';
import './fonts/oiueei-fonts.css';
import './styles/oiueei-theme.css';
import { useEffect, useRef } from 'react';
import { BrowserRouter, Routes, Route, useLocation } from 'react-router-dom';
import { useTranslation } from 'react-i18next';
import i18n from './i18n';
import LoginPage from './pages/LoginPage';
import VerifyPage from './pages/VerifyPage';
import HomePage from './pages/HomePage';
import CollectionPage from './pages/CollectionPage';
import AddThingPage from './pages/AddThingPage';
import EditThingPage from './pages/EditThingPage';
import ThingPage from './pages/ThingPage';
import CreateCollectionPage from './pages/CreateCollectionPage';
import EditCollectionPage from './pages/EditCollectionPage';
import EditProfilePage from './pages/EditProfilePage';
import NotificationsPage from './pages/NotificationsPage';
import ManageInvitesPage from './pages/ManageInvitesPage';
import LogoutPage from './pages/LogoutPage';
import UserPage from './pages/UserPage';
import RequestThingPage from './pages/RequestThingPage';
import RespondWishPage from './pages/RespondWishPage';
import DeleteThingPage from './pages/DeleteThingPage';
import DeleteCollectionPage from './pages/DeleteCollectionPage';
import RemoveGuestPage from './pages/RemoveGuestPage';
import MyBookingsPage from './pages/MyBookingsPage';
import WelcomePage from './pages/WelcomePage';
import PopInPage from './pages/PopInPage';
import SharePage from './pages/SharePage';
import NotFoundPage from './pages/NotFoundPage';
import RequireAuth from './components/RequireAuth';
import './App.css';

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

        {/* Protected routes — RequireAuth redirects to /login when signed out */}
        <Route element={<RequireAuth />}>
          <Route path="/" element={<HomePage />} />
          <Route path="/me" element={<UserPage />} />
          <Route path="/me/edit" element={<EditProfilePage />} />
          <Route path="/collections/new" element={<CreateCollectionPage />} />
          <Route path="/collections/:code" element={<CollectionPage />} />
          <Route path="/collections/:code/edit" element={<EditCollectionPage />} />
          <Route path="/collections/:code/delete" element={<DeleteCollectionPage />} />
          <Route path="/collections/:code/invites" element={<ManageInvitesPage />} />
          <Route path="/collections/:code/add" element={<AddThingPage />} />
          <Route path="/collections/:code/things/:thingCode" element={<ThingPage />} />
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
          <Route path="/things/:thingCode" element={<ThingPage />} />
          <Route path="/things/:thingCode/edit" element={<EditThingPage />} />
          <Route path="/things/:thingCode/request" element={<RequestThingPage />} />
          <Route path="/things/:thingCode/respond/:kind" element={<RespondWishPage />} />
          <Route path="/things/:thingCode/delete" element={<DeleteThingPage />} />
          <Route path="/my-bookings" element={<MyBookingsPage />} />
          <Route path="/:userCode" element={<UserPage />} />
        </Route>

        <Route path="*" element={<NotFoundPage />} />
        </Routes>
      </main>
    </BrowserRouter>
  );
}

export default App;
