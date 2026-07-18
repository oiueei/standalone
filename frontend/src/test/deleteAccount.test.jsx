import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import VerifyPage from '../pages/VerifyPage';
import DeleteAccountPage from '../pages/DeleteAccountPage';

// The right-to-erasure flow has two safety-critical UI behaviours:
// 1. DeleteAccountPage never deletes anything — it only requests the
//    confirmation email.
// 2. VerifyPage must NOT auto-commit an ACCOUNT_DELETE preview the way it
//    auto-commits booking decisions: the deletion only fires from the explicit
//    confirm button.

const CODE = 'RSVPDELETE1';

function mockResponse(body, ok = true, status = 200) {
  return { ok, status, json: () => Promise.resolve(body) };
}

const postCalls = (mock) => mock.mock.calls.filter(([, opts]) => opts?.method === 'POST');

describe('DeleteAccountPage', () => {
  beforeEach(() => {
    localStorage.clear();
    localStorage.setItem('userCode', 'USER01');
  });

  function renderPage() {
    return render(
      <MemoryRouter initialEntries={['/me/delete']}>
        <Routes>
          <Route path="/me/delete" element={<DeleteAccountPage />} />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  test('states what goes and what stays, and sends nothing on render', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(mockResponse({})));
    renderPage();
    expect(await screen.findByText('What is deleted')).toBeInTheDocument();
    expect(screen.getByText('What stays')).toBeInTheDocument();
    expect(postCalls(globalThis.fetch)).toHaveLength(0);
  });

  test('the button requests the confirmation email and reports it', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(mockResponse({ message: 'sent' })));
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Send me the confirmation email' }));
    expect(await screen.findByText('Check your email')).toBeInTheDocument();
    const posts = postCalls(globalThis.fetch);
    expect(posts).toHaveLength(1);
    expect(posts[0][0]).toBe('/api/v1/auth/delete-account/');
  });

  test('a failed send shows the error and keeps the button', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(mockResponse({}, false, 500)));
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Send me the confirmation email' }));
    expect(
      await screen.findByText("We couldn't send the email. Please try again."),
    ).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Send me the confirmation email' }),
    ).toBeInTheDocument();
  });
});

describe('VerifyPage ACCOUNT_DELETE', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  function renderVerify() {
    return render(
      <MemoryRouter initialEntries={[`/verify/${CODE}`]}>
        <Routes>
          <Route path="/verify/:code" element={<VerifyPage />} />
          <Route path="*" element={<div data-testid="navigated" />} />
        </Routes>
      </MemoryRouter>,
    );
  }

  const preview = {
    action: 'ACCOUNT_DELETE',
    requires_confirmation: true,
    name: 'Test User',
    email: 'test@example.com',
    collections: 2,
    things: 5,
  };

  test('previews without auto-committing — the deletion waits for the button', async () => {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({ action: 'ACCOUNT_DELETE' }))
        : Promise.resolve(mockResponse(preview)),
    );

    renderVerify();

    expect(await screen.findByText('Delete your account?')).toBeInTheDocument();
    // Unlike a booking decision, NO POST fired from the load effect.
    expect(postCalls(globalThis.fetch)).toHaveLength(0);
    expect(
      screen.getByRole('button', { name: 'Delete my account forever' }),
    ).toBeInTheDocument();
  });

  test('the explicit confirm commits, clears local state and says goodbye', async () => {
    localStorage.setItem('userCode', 'USER01');
    localStorage.setItem('theeemeColors', '{}');
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({ action: 'ACCOUNT_DELETE' }))
        : Promise.resolve(mockResponse(preview)),
    );

    renderVerify();

    fireEvent.click(await screen.findByRole('button', { name: 'Delete my account forever' }));
    expect(await screen.findByText('Account deleted')).toBeInTheDocument();
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
    await waitFor(() => {
      expect(localStorage.getItem('userCode')).toBeNull();
      expect(localStorage.getItem('theeemeColors')).toBeNull();
    });
  });

  test('a failed commit shows the invalid-link error', async () => {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({}, false, 401))
        : Promise.resolve(mockResponse(preview)),
    );

    renderVerify();

    fireEvent.click(await screen.findByRole('button', { name: 'Delete my account forever' }));
    expect(await screen.findByText('Invalid or expired link.')).toBeInTheDocument();
  });
});
