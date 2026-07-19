import { render, screen, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, test, expect, vi, afterEach } from 'vitest';
import NotificationsPage from './NotificationsPage';

// The page lives behind the signed token from the email footer — an
// unauthenticated reader must be able to manage their preferences with it.
function renderWithToken(path = '/me/notifications/TOK123') {
  return render(
    <MemoryRouter initialEntries={[path]}>
      <Routes>
        <Route path="/me/notifications/:token" element={<NotificationsPage />} />
        <Route path="/me/notifications" element={<NotificationsPage />} />
        <Route path="/me/edit" element={<div>EDIT PROFILE PAGE</div>} />
      </Routes>
    </MemoryRouter>
  );
}

const activityToggle = () =>
  screen.getByRole('button', { name: /Activity between users/ });
const newsToggle = () => screen.getByRole('button', { name: /News and announcements/ });

describe('NotificationsPage (email prefs via the signed footer token)', () => {
  afterEach(() => {
    vi.restoreAllMocks();
  });

  test('the emailed token loads the saved preferences — no login involved', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ notify_activity: true, notify_news: false }),
    });
    renderWithToken();

    expect(await screen.findByRole('heading', { name: 'Email preferences' })).toBeInTheDocument();
    expect(globalThis.fetch.mock.calls[0][0]).toBe('/api/v1/notifications/token/TOK123/');
    expect(activityToggle()).toHaveAttribute('aria-pressed', 'true');
    expect(newsToggle()).toHaveAttribute('aria-pressed', 'false');
    // Cat. 1 can never be switched off.
    expect(screen.getByRole('button', { name: /Sign-in links and invitations/ })).toBeDisabled();
  });

  test('an invalid or expired token shows the error and no form', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 401,
      json: async () => ({ error: 'Invalid token' }),
    });
    renderWithToken();

    expect(
      await screen.findByText(/This link is invalid or has expired/)
    ).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Save' })).not.toBeInTheDocument();
  });

  test('saving PATCHes the flipped toggles through the same token', async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ notify_activity: true, notify_news: false }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ notify_activity: true, notify_news: true }),
      });
    renderWithToken();

    await screen.findByRole('heading', { name: 'Email preferences' });
    fireEvent.click(newsToggle()); // opt in to news
    fireEvent.click(screen.getByRole('button', { name: 'Save' }));

    expect(await screen.findByText('Preferences saved.')).toBeInTheDocument();
    const [url, options] = globalThis.fetch.mock.calls[1];
    expect(url).toBe('/api/v1/notifications/token/TOK123/');
    expect(options.method).toBe('PATCH');
    expect(JSON.parse(options.body)).toEqual({ notify_activity: true, notify_news: true });
  });

  test('without a token it redirects to the profile editor instead of rendering', async () => {
    globalThis.fetch = vi.fn();
    renderWithToken('/me/notifications');

    expect(await screen.findByText('EDIT PROFILE PAGE')).toBeInTheDocument();
    expect(globalThis.fetch).not.toHaveBeenCalled();
  });
});
