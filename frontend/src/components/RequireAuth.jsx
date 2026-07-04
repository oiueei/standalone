import { useEffect, useState } from 'react';
import { Navigate, Outlet } from 'react-router-dom';
import { apiFetch } from '../services/api';
import LoadingSpinner from './LoadingSpinner';

/**
 * Route guard for authenticated pages. Renders the nested protected routes when
 * the user is authenticated; otherwise redirects to `/login`.
 *
 * Centralises the per-page `if (!userCode) navigate('/login')` check that was
 * duplicated across ~18 pages. `userCode` is the only auth marker kept in
 * localStorage (the JWT lives in HttpOnly cookies), so its presence is the fast
 * path — when it's there we render immediately.
 *
 * Session resilience: `userCode` can be missing while the HttpOnly auth cookies
 * are still valid — a fresh tab before HomePage has run, or a partial
 * localStorage clear. Rather than bounce those users to `/login`, we confirm
 * with `/auth/me/` first (via `apiFetch`, so a merely-expired access token is
 * transparently refreshed from the refresh cookie). On success we re-seed
 * `userCode` and render the route; only a genuine 401 sends them to `/login`.
 */
export default function RequireAuth() {
  // 'authed' — userCode present (or /auth/me/ confirmed); 'checking' — probing
  // cookies; 'anon' — no valid session, redirect to /login.
  const [status, setStatus] = useState(() =>
    localStorage.getItem('userCode') ? 'authed' : 'checking'
  );

  useEffect(() => {
    if (status !== 'checking') return undefined;
    const controller = new AbortController();
    let cancelled = false;
    (async () => {
      try {
        const res = await apiFetch('/api/v1/auth/me/', { signal: controller.signal });
        if (cancelled) return;
        if (res.ok) {
          const data = await res.json().catch(() => null);
          if (data?.code) localStorage.setItem('userCode', data.code);
          setStatus('authed');
        } else {
          setStatus('anon');
        }
      } catch {
        // apiFetch hard-redirects to /login on an unrecoverable 401; the catch
        // just covers an aborted/failed probe so we still settle to 'anon'.
        if (!cancelled) setStatus('anon');
      }
    })();
    return () => {
      cancelled = true;
      controller.abort();
    };
  }, [status]);

  if (status === 'checking') return <LoadingSpinner />;
  if (status === 'anon') return <Navigate to="/login" replace />;
  return <Outlet />;
}
