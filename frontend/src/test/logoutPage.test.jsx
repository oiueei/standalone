import { render, screen, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// `useNavigate` gives a new function whenever the address moves; this wrapper gives one
// on every render, the same property without depending on how a router version memoises it.
vi.mock('react-router', async (orig) => {
  const actual = await orig();
  return {
    ...actual,
    useNavigate: () => {
      const navigate = actual.useNavigate();
      return (...args) => navigate(...args);
    },
  };
});
vi.mock('../services/api', () => ({ apiFetch: vi.fn() }));

import { apiFetch } from '../services/api';
import LogoutPage from '../pages/LogoutPage';

function Landing() {
  const { pathname } = useLocation();
  return <p>{`landed on ${pathname}`}</p>;
}

// `Routes` keeps the location it was given, so the page stays up as it does while the
// next page's chunk loads, and it renders again when the router's location moves.
const STAYED = { pathname: '/logout', search: '', hash: '', state: null, key: 'k' };

describe('LogoutPage', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('userCode', 'USR001');
    vi.clearAllMocks();
  });

  test('ends the session once, even though going to the login moves the address under it', async () => {
    // A few more answers than one would show a repeat; the cap only keeps a regression
    // from looping for ever.
    let calls = 0;
    apiFetch.mockImplementation(() =>
      ++calls > 5 ? new Promise(() => {}) : Promise.resolve({ ok: true })
    );
    render(
      <MemoryRouter initialEntries={['/logout']}>
        <Routes location={STAYED}>
          <Route path="/logout" element={<LogoutPage />} />
        </Routes>
        <Landing />
      </MemoryRouter>
    );

    expect(await screen.findByText('landed on /login')).toBeInTheDocument();
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(apiFetch).toHaveBeenCalledTimes(1);
    expect(localStorage.getItem('userCode')).toBeNull();
  });
});
