/**
 * Centralised fetch wrapper with auth headers and 401 handling.
 */

export async function apiFetch(url, options = {}) {
  const token = localStorage.getItem('token');
  const headers = { ...options.headers };

  if (token) {
    headers['Authorization'] = `Bearer ${token}`;
  }

  if (options.body && !headers['Content-Type']) {
    headers['Content-Type'] = 'application/json';
  }

  const res = await fetch(url, { ...options, headers });

  if (res.status === 401) {
    localStorage.removeItem('token');
    localStorage.removeItem('refresh');
    localStorage.removeItem('userCode');
    window.location.href = '/login';
    throw new Error('Unauthorised');
  }

  return res;
}
