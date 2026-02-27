/**
 * Centralised fetch wrapper with cookie-based auth and 401 handling.
 */

export async function apiFetch(url, options = {}) {
  const headers = { ...options.headers };

  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, { ...options, headers, credentials: 'include' });

  if (res.status === 401) {
    // Try refreshing the token once
    const refreshRes = await fetch('/api/v1/auth/refresh/', {
      method: 'POST',
      credentials: 'include',
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
