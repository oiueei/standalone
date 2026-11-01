import './i18n';
import 'hds-design-tokens';
import 'hds-core/lib/base.css';
import './fonts/oiueei-fonts.css';
import './styles/oiueei-theme.css';
import { useEffect, useRef, lazy, Suspense } from 'react';
import {
  BrowserRouter,
  Routes,
  Route,
  Navigate,
  useLocation,
  useNavigationType,
  useParams,
} from 'react-router';
import { useTranslation } from 'react-i18next';
import i18n, { SUPPORTED_LANGUAGES } from './i18n';
import RequireAuth from './components/RequireAuth';
import LoadingSpinner from './components/LoadingSpinner';
import SiteFooter from './components/SiteFooter';
import NewVersionNotice from './components/NewVersionNotice';
import { deploymentRoutes } from './deployment';
import { COLLECTION_PREFIXES, COLLECTION_KINDS, isCodeShaped } from './utils/collectionPath';
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
const ImportThingsPage = lazy(() => import('./pages/ImportThingsPage'));
const ImportInvitesPage = lazy(() => import('./pages/ImportInvitesPage'));
const NetworkPointPage = lazy(() => import('./pages/NetworkPointPage'));
const EditThingPage = lazy(() => import('./pages/EditThingPage'));
const ThingPage = lazy(() => import('./pages/ThingPage'));
const CreateCollectionPage = lazy(() => import('./pages/CreateCollectionPage'));
const NewCollectionPage = lazy(() => import('./pages/NewCollectionPage'));
const EditCollectionPage = lazy(() => import('./pages/EditCollectionPage'));
const EditProfilePage = lazy(() => import('./pages/EditProfilePage'));
const DeleteAccountPage = lazy(() => import('./pages/DeleteAccountPage'));
const DataExportPage = lazy(() => import('./pages/DataExportPage'));
const NotificationsPage = lazy(() => import('./pages/NotificationsPage'));
const ManageInvitesPage = lazy(() => import('./pages/ManageInvitesPage'));
const LogoutPage = lazy(() => import('./pages/LogoutPage'));
const UserPage = lazy(() => import('./pages/UserPage'));
const RequestThingPage = lazy(() => import('./pages/RequestThingPage'));
const DeleteThingPage = lazy(() => import('./pages/DeleteThingPage'));
const DeleteCollectionPage = lazy(() => import('./pages/DeleteCollectionPage'));
const RemoveGuestPage = lazy(() => import('./pages/RemoveGuestPage'));
const LeaveCollectionPage = lazy(() => import('./pages/LeaveCollectionPage'));
const MyBookingsPage = lazy(() => import('./pages/MyBookingsPage'));
const OwnerBookingsPage = lazy(() => import('./pages/OwnerBookingsPage'));
const SharePage = lazy(() => import('./pages/SharePage'));
const JoinPage = lazy(() => import('./pages/JoinPage'));
const NotFoundPage = lazy(() => import('./pages/NotFoundPage'));
const LegalPage = lazy(() => import('./pages/LegalPage'));
const DigestMutePage = lazy(() => import('./pages/DigestMutePage'));
const ContactPage = lazy(() => import('./pages/ContactPage'));

/**
 * The pages of a collection, mounted once per prefix (`/stall`, `/library`,
 * `/shed` and the old `/collections`): the same components under four roots, so
 * the tree is written once and cannot drift between them. A function returning
 * `<Route>` elements rather than a component, because `<Routes>` only reads its
 * own `<Route>` children.
 *
 * **Every sub-route is `caseSensitive`.** A code is six letters and digits and the
 * sub-routes `delete` and `import` are six letters: React Router matches paths
 * without regard to case by default, so a member whose code is `DELETE` would open
 * `/library/ABC123/DELETE` — the address of a dinamizador's filter of the collection
 * — on the page that deletes it. Lowercase paths stay what they were.
 */
/**
 * The collection's page, or the collection filtered by one of a network's
 * dinamizadores (`/:curatorCode`). The optional segment is a user's code: six letters
 * and digits. Anything else there is not a page of the app (`/library/ABC123/foo`) and
 * gets the usual "not found"; a code that names nobody shows the collection as it is.
 */
function CollectionRoute() {
  const { curatorCode } = useParams();
  if (curatorCode !== undefined && !isCodeShaped(curatorCode)) return <NotFoundPage />;
  return <CollectionPage />;
}

const publicCollectionRoutes = (prefix) => [
  // One route for the collection and for the collection filtered by one of a network's
  // dinamizadores (`/:curatorCode`, optional): a single route so that moving between
  // filters keeps the page, and does not load the collection again. Its static sibling
  // routes (all case-sensitive) outrank the optional segment; a code that names nobody
  // shows the collection as it is.
  <Route
    key={`${prefix}-page`}
    path={`/${prefix}/:code/:curatorCode?`}
    element={<CollectionRoute />}
  />,
  <Route
    key={`${prefix}-thing`}
    caseSensitive
    path={`/${prefix}/:code/things/:thingCode`}
    element={<ThingPage />}
  />,
  <Route
    key={`${prefix}-join`}
    caseSensitive
    path={`/${prefix}/:code/join`}
    element={<JoinPage />}
  />,
];

const protectedCollectionRoutes = (prefix) =>
  [
    ['edit', <EditCollectionPage />],
    ['delete', <DeleteCollectionPage />],
    ['invites', <ManageInvitesPage />],
    ['leave', <LeaveCollectionPage />],
    ['add', <AddThingPage />],
    ['import', <ImportThingsPage />],
    ['things/:thingCode/edit', <EditThingPage />],
    ['things/:thingCode/request', <RequestThingPage />],
    ['things/:thingCode/delete', <DeleteThingPage />],
    ['invites/import', <ImportInvitesPage />],
    ['point', <NetworkPointPage />],
    ['invites/remove', <RemoveGuestPage />],
  ].map(([sub, element]) => (
    <Route
      key={`${prefix}-${sub}`}
      caseSensitive
      path={`/${prefix}/:code/${sub}`}
      element={element}
    />
  ));

/**
 * On every route change (but not the initial mount), move focus to the main
 * landmark and scroll to top so keyboard and screen-reader users start at the
 * new page's content rather than wherever focus was left on the previous page.
 *
 * The initial mount is skipped on purpose: stealing focus into `<main>` on load
 * would make the skip link — which precedes `<main>` — unreachable by the first
 * forward Tab, defeating its purpose. On a fresh load focus stays at the top so
 * the skip link is the first tab stop.
 *
 * A navigation carrying `state.keepFocus` (the network filter's) leaves focus and scroll
 * alone, unless it is a return to a history entry (`POP`); the path is still remembered.
 */
function RouteFocusReset() {
  const { pathname, state } = useLocation();
  const navigationType = useNavigationType();
  // Seed with the initial path so the first mount is a no-op. Comparing the
  // path (rather than a "first render" boolean) is also robust to StrictMode's
  // double effect-invocation in dev, which re-runs the effect with the same
  // path and would otherwise defeat a boolean guard.
  const prevPath = useRef(pathname);
  useEffect(() => {
    if (prevPath.current === pathname) return;
    prevPath.current = pathname;
    // A move that is only the same page showing another slice of itself (a network's
    // filter by dinamizador) asks to keep the reader where they are: the button they
    // pressed keeps the focus and the list does not jump to the top.
    // Not when coming *back* to such an entry (Back, Forward): the state travels with
    // the history entry, and the page being returned to is a different place to arrive at.
    if (state?.keepFocus && navigationType !== 'POP') return;
    const main = document.getElementById('main');
    // The page changes with a jump, not a glide: `html` smooths scrolling for the footer's
    // "Back to top" anchor, and a page change must not inherit that.
    if (main) main.focus({ preventScroll: true });
    window.scrollTo({ top: 0, left: 0, behavior: 'instant' });
  }, [pathname, state, navigationType]);
  return null;
}

function App() {
  const { t } = useTranslation();

  // Warm the csrftoken cookie — the original reason this call exists.
  // `MeView` carries `@ensure_csrf_cookie` precisely because the SPA hits it on
  // every app load, so this is the request that guarantees `getCsrfToken()` has
  // something to put in `X-CSRFToken` on the first unsafe request of a
  // brand-new visit.
  //
  // A plain `fetch`, deliberately not `apiFetch`: the endpoint is
  // `IsAuthenticated`, so it 401s for a signed-out visitor, and `apiFetch`
  // would then run its refresh-then-redirect-to-login dance over a request
  // nobody asked for — `ensure_csrf_cookie` has already set the cookie by
  // then, which is all this call needs. Nothing races it either:
  // `CookieJWTAuthentication` only enforces CSRF once the `access_token` cookie
  // has authenticated the request, so the anonymous POSTs that can happen this
  // early (request-link, join) are not checked at all.
  //
  // Since 2026-09-15 the response is also read for `language` — the top tier
  // of the hierarchy `useCollectionLanguage` (per-page) otherwise only ever
  // *vetoes*: a signed-in visitor's own deliberately-saved preference stopped
  // a collection's language from overriding it, but nothing actually applied
  // that preference on a device where it wasn't already the cached browser
  // default (found in review, 2026-09-15 — a member who saved Catalan on one
  // device saw plain Spanish on another, having asked for neither). This one
  // app-wide effect is where it now genuinely applies, once per visit, ahead
  // of every page — unlike the per-page override, a real preference is a
  // proper `changeLanguage`, meant to persist exactly like the profile page's
  // own Select already does.
  useEffect(() => {
    fetch('/api/v1/auth/me/', { credentials: 'same-origin' })
      .then((res) => (res.ok ? res.json() : null))
      .then((data) => {
        const language = data?.language;
        if (language && SUPPORTED_LANGUAGES.some((l) => l.code === language)) {
          i18n.changeLanguage(language);
        }
      })
      .catch(() => {});
  }, []);

  useEffect(() => {
    document.documentElement.lang = i18n.language;
    const handleLangChange = (lng) => {
      document.documentElement.lang = lng;
    };
    i18n.on('languageChanged', handleLangChange);
    return () => i18n.off('languageChanged', handleLangChange);
  }, []);

  return (
    <BrowserRouter>
      <a href="#main" className="skip-link">
        {t('common.skipToContent')}
      </a>
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
            <Route path="/legal" element={<LegalPage />} />
            {/* The digest footer's one-click unsubscribe — public by necessity. */}
            <Route path="/digest/mute/:token" element={<DigestMutePage />} />
            <Route path="/contact" element={<ContactPage />} />
            <Route path="/share/:token" element={<SharePage />} />

            {/* Public read of PUBLIC collections/things — anonymous visitors can
            browse; can_view() gates it server-side (PUBLIC + ACTIVE only) and the
            pages hide every owner/member action behind an auth check. */}
            {COLLECTION_PREFIXES.flatMap(publicCollectionRoutes)}
            <Route path="/things/:thingCode" element={<ThingPage />} />

            {/* Protected routes — RequireAuth redirects to /login when signed out */}
            <Route element={<RequireAuth />}>
              <Route path="/" element={<HomePage />} />
              <Route path="/me" element={<UserPage />} />
              <Route path="/me/edit" element={<EditProfilePage />} />
              <Route path="/me/data" element={<DataExportPage />} />
              <Route path="/me/delete" element={<DeleteAccountPage />} />
              <Route path="/new" element={<NewCollectionPage />} />
              <Route path="/collections/new" element={<Navigate to="/new" replace />} />
              {COLLECTION_KINDS.map((kind) => (
                <Route key={`start-${kind}`} path={`/${kind.toLowerCase()}`}>
                  <Route index element={<Navigate to={`/${kind.toLowerCase()}/new`} replace />} />
                  <Route path="new" element={<CreateCollectionPage />} />
                </Route>
              ))}
              {COLLECTION_PREFIXES.flatMap(protectedCollectionRoutes)}
              <Route path="/things/:thingCode/edit" element={<EditThingPage />} />
              <Route path="/things/:thingCode/request" element={<RequestThingPage />} />
              <Route path="/things/:thingCode/delete" element={<DeleteThingPage />} />
              <Route path="/my-bookings" element={<MyBookingsPage />} />
              <Route path="/owner-bookings" element={<OwnerBookingsPage />} />
              <Route path="/:userCode" element={<UserPage />} />
            </Route>

            {/* Routes this deployment adds (frontend/src/deployment). None upstream.
            They sit HERE, above the catch-all, for the same reason the backend
            mounts DEPLOYMENT_URLCONFS before its own: a route declared after a
            catch-all never matches, and the symptom is a deployment's page
            rendering as "not found" with nothing else looking wrong. */}
            {deploymentRoutes.map((route) => (
              <Route key={route.path} path={route.path} element={<route.Component />} />
            ))}

            <Route path="*" element={<NotFoundPage />} />
          </Routes>
        </Suspense>
      </main>
      <SiteFooter />
      <NewVersionNotice />
    </BrowserRouter>
  );
}

export default App;
