import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, test, expect, beforeEach } from 'vitest';
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
  });

  test('redirects to /login when there is no userCode', () => {
    renderAt('/secret');
    expect(screen.getByText('Login Page')).toBeInTheDocument();
    expect(screen.queryByText('Secret Page')).toBeNull();
  });

  test('renders the protected route when a userCode is present', () => {
    localStorage.setItem('userCode', 'ABC123');
    renderAt('/secret');
    expect(screen.getByText('Secret Page')).toBeInTheDocument();
  });
});
