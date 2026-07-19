import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { describe, test, expect, vi, afterEach, beforeEach } from 'vitest';
import ManageInvitesPage from './ManageInvitesPage';

// The same JSON shape CollectionSerializer emits (subset the page reads).
const COLLECTION = {
  code: 'COL001',
  headline: 'Book Club',
  owner: 'OWNER1',
  invites: [{ code: 'GST001', email: 'ana@example.com', name: 'Ana' }],
  pending_invites: [{ code: 'RSVP01', email: 'pending@example.com' }],
};

function mockRoutes({ collection = COLLECTION, invite = { status: 200 } } = {}) {
  globalThis.fetch = vi.fn((url) => {
    const respond = (status, body) =>
      Promise.resolve({ ok: status < 400, status, json: async () => body });
    if (url.endsWith('/invite/')) {
      return respond(invite.status, invite.body ?? { message: 'Invitation sent' });
    }
    return respond(200, collection);
  });
}

function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/collections/COL001/invites']}>
      <Routes>
        <Route path="/collections/:code/invites" element={<ManageInvitesPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('ManageInvitesPage (the guest list)', () => {
  beforeEach(() => {
    localStorage.setItem('userCode', 'OWNER1');
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  test('the owner invites by email: POST contract, optimistic pending row, cleared input', async () => {
    mockRoutes();
    renderPage();
    await screen.findByText(/Ana/);

    fireEvent.change(screen.getByLabelText('Guest email'), {
      target: { value: 'new@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Invite' }));

    await screen.findByText('Invitation sent.');
    const [url, options] = globalThis.fetch.mock.calls.find(([u]) => u.endsWith('/invite/'));
    expect(url).toBe('/api/v1/collections/COL001/invite/');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ email: 'new@example.com' });
    // The new address appears as Pending without waiting for a refetch.
    expect(screen.getByText('new@example.com')).toBeInTheDocument();
    expect(screen.getByLabelText('Guest email')).toHaveValue('');
  });

  test('a rejected invite surfaces the backend detail, not a generic error', async () => {
    mockRoutes({ invite: { status: 400, body: { error: 'User is already a member' } } });
    renderPage();
    await screen.findByText(/Ana/);

    fireEvent.change(screen.getByLabelText('Guest email'), {
      target: { value: 'ana@example.com' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Invite' }));

    expect(await screen.findByText('User is already a member')).toBeInTheDocument();
  });

  test('resend fires the invite POST for that pending guest', async () => {
    mockRoutes();
    renderPage();

    fireEvent.click(
      await screen.findByRole('button', { name: 'Resend invitation to this guest' })
    );

    await screen.findByText('Invitation resent.');
    const [, options] = globalThis.fetch.mock.calls.find(([u]) => u.endsWith('/invite/'));
    expect(JSON.parse(options.body)).toEqual({ email: 'pending@example.com' });
  });

  test('a non-owner sees the list but no invite controls', async () => {
    localStorage.setItem('userCode', 'GUEST9');
    mockRoutes();
    renderPage();
    await screen.findByText(/Ana/);

    expect(screen.queryByLabelText('Guest email')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Remove guest from this collection' })
    ).not.toBeInTheDocument();
    await waitFor(() => {
      expect(globalThis.fetch.mock.calls.some(([u]) => u.endsWith('/invite/'))).toBe(false);
    });
  });
});
