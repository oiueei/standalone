import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach } from 'vitest';

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import ShareCollectionMenu from './ShareCollectionMenu';

const props = {
  collectionCode: 'COL001',
  collectionHeadline: 'My Collection',
  ownerName: 'Owner',
};

function openMenu() {
  // HDS Select renders a button that toggles the options listbox.
  const trigger =
    screen.queryByRole('combobox') ||
    document.querySelector('[aria-haspopup="listbox"]') ||
    document.querySelector('#share-menu-COL001-main-button') ||
    document.querySelector('button');
  fireEvent.click(trigger);
}

beforeEach(() => {
  apiFetch.mockClear();
  apiFetch.mockResolvedValue({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ share_url: 'http://x/share/NEWTOKEN', share_token: 'NEWTOKEN' }),
  });
});

describe('ShareCollectionMenu revoke / rotate', () => {
  test('a PUBLIC collection offers no revoke/rotate (no token to pull back)', () => {
    render(<ShareCollectionMenu {...props} isPublic />);
    openMenu();
    expect(screen.queryByRole('option', { name: /stop sharing/i })).toBeNull();
    expect(screen.queryByRole('option', { name: /rotate link/i })).toBeNull();
  });

  test('revoking a PRIVATE share link confirms, then DELETEs the token', async () => {
    render(<ShareCollectionMenu {...props} isPublic={false} />);
    openMenu();
    fireEvent.click(screen.getByRole('option', { name: /stop sharing/i }));

    // Consequence confirm appears before any request fires.
    expect(screen.getByText(/the invite link stops working for everyone/i)).toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalled();

    fireEvent.click(screen.getByRole('button', { name: /^stop sharing$/i }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/collections/COL001/share-link/',
        expect.objectContaining({ method: 'DELETE' })
      )
    );
  });

  test('rotating a PRIVATE share link POSTs rotate:true', async () => {
    render(<ShareCollectionMenu {...props} isPublic={false} />);
    openMenu();
    fireEvent.click(screen.getByRole('option', { name: /rotate link/i }));
    fireEvent.click(screen.getByRole('button', { name: /^rotate link$/i }));
    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/collections/COL001/share-link/',
        expect.objectContaining({ method: 'POST', body: JSON.stringify({ rotate: true }) })
      )
    );
  });
});
