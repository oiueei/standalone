import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, test, expect, vi, afterEach, beforeEach } from 'vitest';
import JoinToAct from './JoinToAct';

function renderJoin() {
  return render(
    <MemoryRouter>
      <JoinToAct collectionCode="PUB001" collectionHeadline="Tool Library" />
    </MemoryRouter>
  );
}

function submitEmail(email = 'visitor@example.com') {
  fireEvent.change(screen.getByLabelText(/Email/), { target: { value: email } });
  fireEvent.click(screen.getByRole('button', { name: 'Send me a magic link' }));
}

describe('JoinToAct (login-to-act on a public collection)', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('joining sends the email, the collection code and the page language', async () => {
    localStorage.setItem('seenWelcome', 'true');
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: 'Magic link sent' }),
    });
    renderJoin();

    // The intro names the collection the visitor is about to join.
    expect(screen.getByText(/Tool Library/)).toBeInTheDocument();
    submitEmail('visitor@example.com');

    await screen.findByText(/We've sent you a magic link to join/);
    const [url, options] = globalThis.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/auth/pop-in/');
    expect(JSON.parse(options.body)).toEqual({
      email: 'visitor@example.com',
      collection_code: 'PUB001',
      language: 'en',
    });
    // A joiner may be brand-new on this browser: their first-time welcome box
    // must not be suppressed by a stale flag.
    expect(localStorage.getItem('seenWelcome')).toBeNull();
  });

  test('a server failure reports inline and keeps the form usable', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ error: 'boom' }),
    });
    renderJoin();

    submitEmail();

    expect(await screen.findByRole('alert')).toHaveTextContent(
      'Something went wrong. Please try again.'
    );
    // Unlike the boxed pages, this inline variant keeps the form on error.
    expect(screen.getByLabelText(/Email/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Send me a magic link' })).toBeInTheDocument();
  });
});
