/**
 * Centralised fetch wrapper with cookie-based auth and 401 handling.
 */

export function getCsrfToken() {
  const match = document.cookie.match(/csrftoken=([^;]+)/);
  return match ? match[1] : '';
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
    // Try refreshing the token once
    const refreshRes = await fetch('/api/v1/auth/refresh/', {
      method: 'POST',
      credentials: 'include',
      headers: { 'X-CSRFToken': getCsrfToken() },
    });
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
