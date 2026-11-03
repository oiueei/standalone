import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';
import { settle } from './settle';

/**
 * A network is a library run by several entities. It is offered at creation to a
 * library only, shown but never changed afterwards, explained where it is chosen and
 * on the collection's page, and its founder alone names the team, edits the group and
 * takes people out: the controls a co-curator would not be allowed to use are not
 * offered to them.
 */
window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));
vi.mock('../utils/externalForms', () => ({ externalFormUrl: () => null }));
vi.mock('../deployment', async (orig) => ({ ...(await orig()), requestAccessPaths: {} }));

import { apiFetch, extractApiError } from '../services/api';
import CreateCollectionPage from '../pages/CreateCollectionPage';
import EditCollectionPage from '../pages/EditCollectionPage';
import ManageInvitesPage from '../pages/ManageInvitesPage';
import RemoveGuestPage from '../pages/RemoveGuestPage';
import { dropHdsStyles } from './dropHdsStyles';

const mockResponse = (data, ok = true) => ({
  ok,
  status: ok ? 200 : 400,
  json: () => Promise.resolve(data),
});

const NETWORK = {
  code: 'COL001',
  headline: 'Network',
  owner: 'FOUN01',
  kind: 'LIBRARY',
  mode: 'NETWORK',
  is_curator: true,
  co_owners: [{ code: 'ENTA01', name: 'Lele' }],
  invites: [
    { code: 'ENTA01', email: 'lele@your-domain.test', name: 'Lele' },
    { code: 'MEMB01', email: 'lolo@your-domain.test', name: 'Lolo' },
  ],
  pending_invites: [],
  things: [
    { code: 'THG001', owner: 'ENTA01', headline: 'Drill' },
    { code: 'THG002', owner: 'ENTA01', headline: 'Saw' },
  ],
};

function setApi(collection = {}) {
  apiFetch.mockImplementation((url, opts = {}) => {
    const method = opts.method || 'GET';
    if (url === '/api/v1/collections/' && method === 'POST')
      return Promise.resolve(mockResponse({ code: 'NEW001', kind: 'LIBRARY' }));
    if (/\/collections\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(collection));
    return Promise.resolve(mockResponse({}));
  });
}

const renderCreate = async (kind) => {
  setApi();
  const view = render(
    <MemoryRouter initialEntries={[`/${kind.toLowerCase()}/new`]}>
      <Routes>
        <Route path="/:kind/new" element={<CreateCollectionPage />} />
        <Route path="*" element={<div />} />
      </Routes>
    </MemoryRouter>
  );
  await waitFor(() =>
    expect(view.container.querySelector('#create-collection-headline')).toBeInTheDocument()
  );
  await settle(apiFetch);
  return view;
};

beforeEach(() => {
  dropHdsStyles();
  localStorage.clear();
  localStorage.setItem('userCode', 'FOUN01');
  vi.clearAllMocks();
});

describe('Creating a network', () => {
  test('a library offers the network, with a line saying what it is', async () => {
    await renderCreate('LIBRARY');

    expect(
      screen.getByRole('radio', { name: /^Network:.*each puts in its own things and lends them/i })
    ).toBeInTheDocument();
  });

  test.each(['STALL', 'SHED'])('a %s does not offer it', async (kind) => {
    await renderCreate(kind);

    expect(screen.queryByRole('radio', { name: /^Network:/ })).toBeNull();
  });

  test('choosing it sends the mode', async () => {
    const { container } = await renderCreate('LIBRARY');
    fireEvent.change(container.querySelector('#create-collection-headline'), {
      target: { value: 'The network' },
    });
    fireEvent.click(screen.getByRole('radio', { name: /^Network:/ }));

    fireEvent.click(screen.getByRole('button', { name: 'Create library' }));

    await waitFor(() => {
      const post = apiFetch.mock.calls.find(
        ([url, opts]) => opts?.method === 'POST' && url === '/api/v1/collections/'
      );
      expect(JSON.parse(post[1].body).mode).toBe('NETWORK');
    });
  });
});

describe('Editing a network', () => {
  const renderEdit = (collection) => {
    setApi(collection);
    return render(
      <MemoryRouter initialEntries={['/library/COL001/edit']}>
        <Routes>
          <Route path="/:kind/:code/edit" element={<EditCollectionPage />} />
          <Route path="*" element={<div />} />
        </Routes>
      </MemoryRouter>
    );
  };

  test('the mode is shown as a fact and there is no choice of it', async () => {
    renderEdit(NETWORK);

    expect(await screen.findByText(/This library is a network/i)).toBeInTheDocument();
    expect(screen.queryByRole('radio', { name: /^Community:/ })).toBeNull();
    expect(screen.queryByRole('radio', { name: /^Network:/ })).toBeNull();
  });

  test('another library still chooses between its two modes and is not offered a network', async () => {
    renderEdit({ ...NETWORK, mode: 'PROPRIETARY' });

    expect(await screen.findByRole('radio', { name: /^Community:/ })).toBeInTheDocument();
    expect(screen.queryByRole('radio', { name: /^Network:/ })).toBeNull();
  });
});

describe('Managing the members of a network', () => {
  const renderManage = (collection, userCode) => {
    localStorage.setItem('userCode', userCode);
    setApi(collection);
    return render(
      <MemoryRouter initialEntries={['/library/COL001/invites']}>
        <Routes>
          <Route path="/:kind/:code/invites" element={<ManageInvitesPage />} />
          <Route path="*" element={<div />} />
        </Routes>
      </MemoryRouter>
    );
  };

  test('the founder can name and remove', async () => {
    renderManage(NETWORK, 'FOUN01');

    await screen.findByText(/Lolo/);
    expect(screen.getByRole('button', { name: 'Add to the team' })).toBeInTheDocument();
    expect(screen.getAllByRole('button', { name: /remove/i }).length).toBeGreaterThan(0);
  });

  test('a dinamizador can name nobody and remove nobody, but still invites', async () => {
    renderManage(NETWORK, 'ENTA01');

    await screen.findByText(/Lolo/);
    expect(screen.queryByRole('button', { name: 'Add to the team' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Remove from the team' })).toBeNull();
    expect(screen.queryByRole('button', { name: /^remove$/i })).toBeNull();
    expect(screen.getByRole('button', { name: /invite/i })).toBeInTheDocument();
  });

  test('a co-curator of another mode keeps both controls', async () => {
    renderManage({ ...NETWORK, mode: 'PROPRIETARY' }, 'ENTA01');

    await screen.findByText(/Lolo/);
    expect(screen.getByRole('button', { name: 'Add to the team' })).toBeInTheDocument();
  });

  test('naming a dinamizador in a network promises only their own things', async () => {
    renderManage(NETWORK, 'FOUN01');
    await screen.findByText(/Lolo/);

    fireEvent.click(screen.getByRole('button', { name: 'Add to the team' }));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent(/message everyone and add their own things/i);
    expect(dialog).toHaveTextContent(/member list \(with everyone's email\)/i);
    expect(dialog).toHaveTextContent(/cannot remove members/i);
    expect(dialog).toHaveTextContent(/their things will be deleted with the role/i);
    expect(dialog).not.toHaveTextContent(/reservations/i);
    expect(dialog).not.toHaveTextContent(/everything you can except delete/i);
  });

  test('naming a co-curator elsewhere keeps the full promise', async () => {
    renderManage({ ...NETWORK, mode: 'PROPRIETARY' }, 'FOUN01');
    await screen.findByText(/Lolo/);

    fireEvent.click(screen.getByRole('button', { name: 'Add to the team' }));

    expect(await screen.findByRole('dialog')).toHaveTextContent(
      /everything you can except delete the collection/i
    );
  });

  test('demoting a dinamizador asks first and says how many things go', async () => {
    renderManage(NETWORK, 'FOUN01');
    await screen.findByText(/Lolo/);

    fireEvent.click(screen.getByRole('button', { name: 'Remove from the team' }));

    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent(/Their 2 things will be deleted from the network/i);
    expect(apiFetch.mock.calls.some(([, o]) => o?.method === 'DELETE')).toBe(false);
    fireEvent.click(within(dialog).getByRole('button', { name: 'Remove from the team' }));
    await waitFor(() =>
      expect(apiFetch.mock.calls.some(([, o]) => o?.method === 'DELETE')).toBe(true)
    );
  });
});

describe('Removing someone a network holds back', () => {
  test('the reason the server gives is what the founder reads, not a generic failure', async () => {
    apiFetch.mockResolvedValue({
      ok: false,
      status: 409,
      json: async () => ({ error: 'x', code: 'member_holds_loans', params: { things: 'Drill' } }),
    });
    extractApiError.mockResolvedValue('They have things in hand right now: Drill.');
    render(
      <MemoryRouter
        initialEntries={[
          {
            pathname: '/library/COL001/invites/remove',
            state: { guestCode: 'MEMB01', guestName: 'Lolo', thingTitles: [] },
          },
        ]}
      >
        <Routes>
          <Route path="/:kind/:code/invites/remove" element={<RemoveGuestPage />} />
        </Routes>
      </MemoryRouter>
    );

    fireEvent.click(await screen.findByRole('button', { name: /^remove$/i }));

    expect(
      await screen.findByText('They have things in hand right now: Drill.')
    ).toBeInTheDocument();
  });
});
