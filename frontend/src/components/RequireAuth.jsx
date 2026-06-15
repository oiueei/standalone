import { Navigate, Outlet } from 'react-router-dom';

/**
 * Route guard for authenticated pages. Renders the nested protected routes only
 * when a `userCode` is present in localStorage; otherwise redirects to `/login`.
 *
 * Centralises the per-page `if (!userCode) navigate('/login')` check that was
 * duplicated across ~18 pages. `userCode` is the only auth marker kept in
 * localStorage (the JWT lives in HttpOnly cookies), so its presence is the same
 * signal every page used.
 */
export default function RequireAuth() {
  const userCode = localStorage.getItem('userCode');
  if (!userCode) {
    return <Navigate to="/login" replace />;
  }
  return <Outlet />;
}
