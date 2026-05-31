/**
 * Centralised fetch wrapper with cookie-based auth and 401 handling.
 */

export function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
}

// Single-flight token refresh: when several authenticated requests race on a
// just-expired access token they all get 401 at once. Without a shared promise
// each would POST its own /auth/refresh/, and with rotating refresh tokens the
// later ones present an already-rotated (blacklisted) token, fail, and log the
// user out mid-session. Funnel every concurrent 401 through one refresh.
let refreshPromise = null;

function refreshTokens() {
  if (!refreshPromise) {
    refreshPromise = fetch('/api/v1/auth/refresh/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'X-CSRFToken': getCsrfToken() },
    }).finally(() => {
      // Clear once settled so a later expiry can refresh again.
      refreshPromise = null;
    });
  }
  // All awaiters share one Response — only read `.ok` here, never the body.
  return refreshPromise;
}

export async function apiFetch(url, options = {}) {
  const headers = { ...options.headers };

  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const method = (options.method || 'GET').toUpperCase();
  if (!['GET', 'HEAD', 'OPTIONS', 'TRACE'].includes(method) && !headers['X-CSRFToken']) {
    headers['X-CSRFToken'] = getCsrfToken();
  }

  const res = await fetch(url, { ...options, headers, credentials: 'include' });

  if (res.status === 401) {
    // Try refreshing the token once (shared across concurrent 401s)
    const refreshRes = await refreshTokens();
    if (refreshRes.ok) {
      // Retry the original request with fresh cookies
      const retryRes = await fetch(url, { ...options, headers, credentials: 'include' });
      if (retryRes.status === 401) {
        localStorage.removeItem('userCode');
        window.location.href = '/login';
        throw new Error('Unauthorised');
      }
      return retryRes;
    }
    localStorage.removeItem('userCode');
    window.location.href = '/login';
    throw new Error('Unauthorised');
  }

  return res;
}
