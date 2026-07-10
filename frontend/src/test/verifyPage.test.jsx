import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { StrictMode } from 'react';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import VerifyPage from '../pages/VerifyPage';

// VerifyPage talks to the backend via raw `fetch` (not the apiFetch wrapper), so
// we drive both legs of the auto-commit (GET preview, POST commit) from here.
// FRONTEND B1: the `requires_confirmation → POST` auto-commit and its
// `committedRef` StrictMode guard had zero behavioural coverage — the smoke
// test mocks fetch to 400, so this path never executed.

const CODE = 'RSVPTEST123';

function mockResponse(body, ok = true, status = 200) {
  return { ok, status, json: () => Promise.resolve(body) };
}

function renderVerify(wrapInStrictMode = false) {
  const tree = (
    <MemoryRouter initialEntries={[`/verify/${CODE}`]}>
      <Routes>
        <Route path="/verify/:code" element={<VerifyPage />} />
        {/* catch-all so the login/invite/user navigations don't crash */}
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
  return render(wrapInStrictMode ? <StrictMode>{tree}</StrictMode> : tree);
}

const postCalls = (mock) => mock.mock.calls.filter(([, opts]) => opts?.method === 'POST');
const getCalls = (mock) => mock.mock.calls.filter(([, opts]) => !opts?.method);

describe('VerifyPage auto-commit', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('commits a booking ACCEPT with a single POST when GET requires confirmation', async () => {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({ action: 'BOOKING_ACCEPT' }))
        : Promise.resolve(mockResponse({ requires_confirmation: true })),
    );

    renderVerify();

    expect(await screen.findByText('The hold has been confirmed!')).toBeInTheDocument();
    expect(screen.getByText('Confirmed!')).toBeInTheDocument();

    // One preview GET + exactly one committing POST — nothing more.
    expect(getCalls(globalThis.fetch)).toHaveLength(1);
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
    expect(globalThis.fetch.mock.calls[1][0]).toBe(`/api/v1/auth/verify/${CODE}/`);
  });

  test('commits a booking REJECT and shows the rejected screen', async () => {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({ action: 'BOOKING_REJECT' }))
        : Promise.resolve(mockResponse({ requires_confirmation: true })),
    );

    renderVerify();

    expect(await screen.findByText('The hold has been rejected.')).toBeInTheDocument();
    expect(screen.getByText('Rejected')).toBeInTheDocument();
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
  });

  test('treats an unknown commit action as an invalid/expired link', async () => {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({ action: 'SOMETHING_ELSE' }))
        : Promise.resolve(mockResponse({ requires_confirmation: true })),
    );

    renderVerify();

    expect(await screen.findByText('Invalid or expired link.')).toBeInTheDocument();
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
  });

  test('never commits when the GET preview is non-OK (expired link)', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(mockResponse({ error: 'expired' }, false, 400)));

    renderVerify();

    expect(await screen.findByText('Invalid or expired link.')).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1); // the GET only — no POST
    expect(postCalls(globalThis.fetch)).toHaveLength(0);
  });

  test('never commits when the GET request throws (offline)', async () => {
    globalThis.fetch = vi.fn(() => Promise.reject(new Error('network down')));

    renderVerify();

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    expect(postCalls(globalThis.fetch)).toHaveLength(0);
  });

  test('StrictMode double-invoke fires the committing POST exactly once', async () => {
    // StrictMode (dev build) mounts → runs the effect twice. committedRef must
    // keep the irreversible booking-decision POST to a single fire even though
    // the preview GET runs twice. Method-keyed mock so the assertion is robust
    // to the async interleaving of the two effect runs.
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({ action: 'BOOKING_ACCEPT' }))
        : Promise.resolve(mockResponse({ requires_confirmation: true })),
    );

    renderVerify(true);

    expect(await screen.findByText('The hold has been confirmed!')).toBeInTheDocument();
    // The preview GET ran twice (proving the double-invoke actually happened,
    // so this test is not vacuous) …
    expect(getCalls(globalThis.fetch)).toHaveLength(2);
    // … but the commit POST fired exactly once.
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
  });
});
