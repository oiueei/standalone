import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// Mock the api service so we can drive what /auth/me/ returns during the
// cookie-probe path (userCode absent from localStorage).
vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
}));

import { apiFetch } from '../services/api';
import RequireAuth from '../components/RequireAuth';

function renderAt(path) {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/login" element={<div>Login Page</div>} />
        <Route element={<RequireAuth />}>
          <Route path="/secret" element={<div>Secret Page</div>} />
        </Route>
      </Routes>
    </MemoryRouter>,
  );
}

describe('RequireAuth', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });

  test('renders the protected route immediately when a userCode is present', () => {
    localStorage.setItem('userCode', 'ABC123');
    renderAt('/secret');
    expect(screen.getByText('Secret Page')).toBeInTheDocument();
    // Fast path — no cookie probe.
    expect(apiFetch).not.toHaveBeenCalled();
  });

  test('redirects to /login when no userCode and /auth/me/ is unauthorised', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 401, json: () => Promise.resolve(null) });
    renderAt('/secret');
    expect(await screen.findByText('Login Page')).toBeInTheDocument();
    expect(screen.queryByText('Secret Page')).toBeNull();
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/auth/me/', expect.anything());
  });

  test('recovers the session when cookies are valid but userCode was missing', async () => {
    apiFetch.mockResolvedValue({ ok: true, status: 200, json: () => Promise.resolve({ code: 'ABC123' }) });
    renderAt('/secret');
    expect(await screen.findByText('Secret Page')).toBeInTheDocument();
    // userCode is re-seeded so downstream ownership checks work.
    expect(localStorage.getItem('userCode')).toBe('ABC123');
  });
});
