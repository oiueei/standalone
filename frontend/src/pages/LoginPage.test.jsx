import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter } from 'react-router-dom';
import { describe, test, expect, vi, afterEach } from 'vitest';
import LoginPage from './LoginPage';

function renderLogin() {
  return render(
    <MemoryRouter>
      <LoginPage />
    </MemoryRouter>
  );
}

function submitEmail(email = 'lala@example.com') {
  fireEvent.change(screen.getByLabelText(/Email/), { target: { value: email } });
  fireEvent.click(screen.getByRole('button', { name: 'Sign in' }));
}

describe('LoginPage magic-link request (the front door)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('submitting sends the typed email and shows the unified sent message', async () => {
    // The backend answers 200 whether or not the email exists (anti-enumeration),
    // so the page must show one unified message, never "unknown email".
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: 'Magic link sent' }),
    });
    renderLogin();

    submitEmail('lala@example.com');

    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    const [url, options] = globalThis.fetch.mock.calls[0];
    expect(url).toBe('/api/v1/auth/request-link/');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ email: 'lala@example.com' });

    expect(
      await screen.findByText(/If this email is registered, your magic link is on its way/)
    ).toBeInTheDocument();
    // The form is replaced — no double submits from this screen.
    expect(screen.queryByLabelText(/Email/)).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Try another email' })).toBeInTheDocument();
  });

  test('a rate-limited submit says "wait", not "broken"', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 429,
      json: async () => ({ detail: 'Request was throttled.' }),
    });
    renderLogin();

    submitEmail();

    expect(
      await screen.findByText('Too many attempts — please wait a moment and try again.')
    ).toBeInTheDocument();
  });

  test('a server failure shows a readable error instead of a dead end', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({ error: 'boom' }),
    });
    renderLogin();

    submitEmail();

    expect(await screen.findByText('Error sending link.')).toBeInTheDocument();
  });

  test('a network failure shows the connection error, and "try another email" restores the form', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    renderLogin();

    submitEmail();

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();

    // The locked-out user can always get back to a working form.
    fireEvent.click(screen.getByRole('button', { name: 'Try another email' }));
    expect(screen.getByLabelText(/Email/)).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Sign in' })).toBeInTheDocument();
  });
});

describe('LoginPage hero title-logo (S9)', () => {
  test('the h1 keeps the accessible name "OIUEEI" even though the logo replaces the text', () => {
    render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );
    // The logo is a decorative masked <span>, not text — aria-label on the h1
    // is what actually carries the accessible name here.
    const heading = screen.getByRole('heading', { name: 'OIUEEI' });
    expect(heading.tagName).toBe('H1');
    expect(heading).toHaveTextContent('');
  });

  test('the hero suppresses the 40px watermark so there is never a double logo', () => {
    const { container } = render(
      <MemoryRouter>
        <LoginPage />
      </MemoryRouter>
    );
    expect(container.querySelector('.form-hero')).toHaveClass('form-hero--no-watermark');
  });
});
