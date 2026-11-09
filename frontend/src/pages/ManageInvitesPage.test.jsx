import { render, screen, fireEvent, waitFor, within, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { describe, test, expect, vi, afterEach, beforeEach } from 'vitest';
import ManageInvitesPage from './ManageInvitesPage';
import { switchLanguage } from '../test/settle';

// The same JSON shape CollectionSerializer emits (subset the page reads).
const COLLECTION = {
  code: 'COL001',
  headline: 'Book Club',
  owner: 'OWNER1',
  is_curator: true,
  co_owners: [],
  invites: [{ code: 'GST001', email: 'lala1@your-domain.test', name: 'Ana' }],
  pending_invites: [{ code: 'RSVP01', email: 'lili2@your-domain.test' }],
};

// A member's suggestion, as `CollectionSerializer.pending_proposals` emits it.
const PROPOSAL = {
  code: 'PRP001',
  email: 'lili@your-domain.test',
  note: 'my downstairs neighbour',
  proposer_name: 'Lele',
};

function mockRoutes({
  collection = COLLECTION,
  invite = { status: 200 },
  // The batch endpoint (several addresses typed in the field): by default it
  // sends everybody; `reject` is a request that never arrives.
  bulk = { status: 200 },
  proposal = { status: 200 },
} = {}) {
  // An answered suggestion stops being pending server-side, so the reload an
  // approval triggers must not hand the same card straight back. Modelling that
  // is what makes "it disappears" a claim about the page and not about the mock.
  let answered = false;
  globalThis.fetch = vi.fn((url) => {
    const respond = (status, body) =>
      Promise.resolve({ ok: status < 400, status, json: async () => body });
    if (url.endsWith('/invite/bulk/')) {
      if (bulk.reject) return Promise.reject(new TypeError('Failed to fetch'));
      return respond(bulk.status, bulk.body ?? { invited: 0, skipped: [] });
    }
    if (url.endsWith('/invite/')) {
      return respond(invite.status, invite.body ?? { message: 'Invitation sent' });
    }
    if (url.includes('/proposals/')) {
      if (proposal.status < 400) answered = true;
      return respond(proposal.status, proposal.body ?? { message: 'Invitation sent' });
    }
    return respond(200, answered ? { ...collection, pending_proposals: [] } : collection);
  });
}

const proposalCalls = () => globalThis.fetch.mock.calls.filter(([u]) => u.includes('/proposals/'));

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

  test('the column holding each guest’s controls has a name a screen reader can say', async () => {
    // It was an empty <th> (axe empty-table-header) above Resend / Remove.
    mockRoutes();
    renderPage();
    await screen.findByText(/Ana/);

    expect(screen.getAllByRole('columnheader', { name: 'Actions' }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('columnheader', { name: '' })).not.toBeInTheDocument();
  });

  test('the owner invites by email: POST contract, optimistic pending row, cleared input', async () => {
    mockRoutes();
    renderPage();
    await screen.findByText(/Ana/);

    fireEvent.change(screen.getByLabelText('Guest email'), {
      target: { value: 'lele2@your-domain.test' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Invite' }));

    await screen.findByText('Invitation sent.');
    const [url, options] = globalThis.fetch.mock.calls.find(([u]) => u.endsWith('/invite/'));
    expect(url).toBe('/api/v1/collections/COL001/invite/');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ email: 'lele2@your-domain.test' });
    // The new address appears as Pending without waiting for a refetch.
    expect(screen.getByText('lele2@your-domain.test')).toBeInTheDocument();
    expect(screen.getByLabelText('Guest email')).toHaveValue('');
  });

  // The CSV of invitations was the last block of this page, under the form that
  // invites one address at a time; it has a page of its own,
  // reached from the collection menu. The one-by-one form stays.
  test('the CSV of invitations is not on this page any more — the form for one address is', async () => {
    mockRoutes();
    const { container } = renderPage();
    await screen.findByText(/Ana/);

    expect(screen.getByLabelText('Guest email')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Invite' })).toBeInTheDocument();
    expect(screen.queryByText('Invite many at once (CSV)')).toBeNull();
    expect(screen.queryByRole('heading', { name: /\(CSV\)/ })).toBeNull();
    expect(container.querySelector('input[type="file"]')).toBeNull();
    expect(container.querySelector('#bulk-invite-csv')).toBeNull();
  });

  // The bold links of the three request/groups tables hang from the class of
  // `ResponsiveTable`; this page's table is a plain HDS `Table` in
  // a `.table-wrap`, and the rule must not reach it.
  test('the guests’ table is not a ResponsiveTable: the bold links of the others do not reach it', async () => {
    mockRoutes();
    const { container } = renderPage();
    await screen.findByText(/Ana/);

    expect(container.querySelector('.table-wrap')).not.toBeNull();
    expect(container.querySelector('.responsive-table')).toBeNull();
    const selector = ".responsive-table a:not([class*='hds-button'])";
    for (const link of container.querySelectorAll('table a')) {
      expect(link.matches(selector)).toBe(false);
    }
  });

  test('the guest table carries a name', async () => {
    renderPage();

    expect(await screen.findByRole('table', { name: 'Members of this group' })).toBeInTheDocument();
  });

  test('a rejected invite surfaces the backend detail, not a generic error', async () => {
    mockRoutes({ invite: { status: 400, body: { error: 'User is already a member' } } });
    renderPage();
    await screen.findByText(/Ana/);

    fireEvent.change(screen.getByLabelText('Guest email'), {
      target: { value: 'lala1@your-domain.test' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Invite' }));

    expect(await screen.findByText('User is already a member')).toBeInTheDocument();
  });

  test('a pending guest can be withdrawn but not sent the invitation again', async () => {
    mockRoutes();
    renderPage();
    await screen.findByText(/lili2@your-domain.test/);

    const row = screen.getByText(/lili2@your-domain.test/).closest('tr');
    expect(
      within(row).getByRole('button', { name: 'Remove from this collection' })
    ).toBeInTheDocument();
    expect(within(row).getAllByRole('button')).toHaveLength(1);
    expect(screen.queryByRole('button', { name: /resend/i })).not.toBeInTheDocument();
    expect(globalThis.fetch.mock.calls.filter(([, o]) => o?.method === 'POST')).toEqual([]);
  });

  test('inviting someone who already had an invitation says why, and how else they can join', async () => {
    mockRoutes({
      invite: {
        status: 400,
        body: {
          error: 'This person has already been invited. They can join with the share link.',
          code: 'invite_already_asked',
        },
      },
    });
    renderPage();
    await screen.findByText(/Ana/);

    fireEvent.change(screen.getByLabelText('Guest email'), {
      target: { value: 'lili2@your-domain.test' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Invite' }));

    expect(
      await screen.findByText(/already had an invitation and can't get another by email/)
    ).toBeInTheDocument();
  });

  // ── Members' recommendations ──────────────────────────────────────────────
  //
  // A member suggests somebody and the owner decides. The guarantee running
  // through all of these: until the owner says yes, the person named has not
  // been contacted and does not know they were suggested — so the page must
  // never read as though an invitation already went out.

  test('a suggestion shows who was recommended, by whom, and their note', async () => {
    mockRoutes({ collection: { ...COLLECTION, pending_proposals: [PROPOSAL] } });
    renderPage();

    expect(await screen.findByText('lili@your-domain.test')).toBeInTheDocument();
    expect(screen.getByText(/recommended by Lele/)).toBeInTheDocument();
    // The note is the proposer's word FOR THE OWNER — it is the whole reason
    // this is a decision rather than a guess at an unfamiliar address.
    expect(screen.getByText(/my downstairs neighbour/)).toBeInTheDocument();
    expect(screen.getByText(/Nobody has been contacted/)).toBeInTheDocument();
  });

  test('approving posts to the proposal and clears it from the list', async () => {
    mockRoutes({ collection: { ...COLLECTION, pending_proposals: [PROPOSAL] } });
    renderPage();
    await screen.findByText('lili@your-domain.test');

    fireEvent.click(screen.getByRole('button', { name: 'Invite them' }));

    await waitFor(() => expect(proposalCalls()).toHaveLength(1));
    const [url, options] = proposalCalls()[0];
    expect(url).toBe('/api/v1/proposals/PRP001/approve/');
    expect(options.method).toBe('POST');
    // Answered means answered: an owner must not be asked the same question
    // twice, nor be able to approve it twice from a stale card.
    await waitFor(() => expect(screen.queryByText('lili@your-domain.test')).toBeNull());
  });

  test('declining goes to the reject endpoint, never to approve', async () => {
    mockRoutes({ collection: { ...COLLECTION, pending_proposals: [PROPOSAL] } });
    renderPage();
    await screen.findByText('lili@your-domain.test');

    fireEvent.click(screen.getByRole('button', { name: 'Not this time' }));

    await waitFor(() => expect(proposalCalls()).toHaveLength(1));
    expect(proposalCalls()[0][0]).toBe('/api/v1/proposals/PRP001/reject/');
    await waitFor(() => expect(screen.queryByText('lili@your-domain.test')).toBeNull());
  });

  test('a refused decision keeps the suggestion and surfaces the reason', async () => {
    mockRoutes({
      collection: { ...COLLECTION, pending_proposals: [PROPOSAL] },
      proposal: {
        status: 429,
        body: { error: 'Daily invitation limit reached. Try again tomorrow.' },
      },
    });
    renderPage();
    await screen.findByText('lili@your-domain.test');

    fireEvent.click(screen.getByRole('button', { name: 'Invite them' }));

    // The backend's own words: "not now" and "no" call for different replies
    // from the owner, and a generic error would hide which one this was.
    expect(await screen.findByText(/Daily invitation limit reached/)).toBeInTheDocument();
    // The card stays, so the owner can answer tomorrow.
    expect(screen.getByText('lili@your-domain.test')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Invite them' })).toBeInTheDocument();
  });

  test('a member never sees suggestions meant for the owner', async () => {
    localStorage.setItem('userCode', 'GUEST9');
    mockRoutes({
      collection: { ...COLLECTION, is_curator: false, pending_proposals: [PROPOSAL] },
    });
    renderPage();
    await screen.findByText(/Ana/);

    // The note is one member's private word about a third person, written for
    // the owner alone; the address is somebody who has not agreed to be here.
    expect(screen.queryByText('lili@your-domain.test')).toBeNull();
    expect(screen.queryByText(/my downstairs neighbour/)).toBeNull();
    expect(screen.queryByRole('button', { name: 'Invite them' })).toBeNull();
  });

  test('with nothing suggested the section stays out of the way', async () => {
    mockRoutes({ collection: { ...COLLECTION, pending_proposals: [] } });
    renderPage();
    await screen.findByText(/Ana/);

    expect(screen.queryByRole('heading', { name: 'Recommendations' })).toBeNull();
  });

  test('a non-owner sees the list but no invite controls', async () => {
    localStorage.setItem('userCode', 'GUEST9');
    mockRoutes({ collection: { ...COLLECTION, is_curator: false } });
    renderPage();
    await screen.findByText(/Ana/);

    expect(screen.queryByLabelText('Guest email')).not.toBeInTheDocument();
    expect(
      screen.queryByRole('button', { name: 'Remove from this collection' })
    ).not.toBeInTheDocument();
    await waitFor(() => {
      expect(globalThis.fetch.mock.calls.some(([u]) => u.endsWith('/invite/'))).toBe(false);
    });
  });
});

/**
 * A load failure must say so, not draw a page that contradicts reality.
 *
 * This was the only data page in the app with no persistent error state: a 403
 * or a dead network raised an auto-closing toast and then rendered isOwner=false
 * over an empty list, so the owner read "no guests, and you can't invite anyone"
 * with no explanation and no way to retry.
 */
describe('ManageInvitesPage load failures', () => {
  beforeEach(() => {
    localStorage.setItem('userCode', 'OWNER1');
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  const failWith = (status) => {
    globalThis.fetch = vi.fn(() => Promise.resolve({ ok: false, status, json: async () => ({}) }));
  };

  test('a server error stops the page instead of showing an empty guest list', async () => {
    failWith(500);
    renderPage();

    expect(await screen.findByText(/error loading/i)).toBeInTheDocument();
    // Crucially: it does not offer the invite form it has no right to show.
    expect(screen.queryByRole('button', { name: /^invite$/i })).not.toBeInTheDocument();
    expect(screen.getByRole('button', { name: /retry/i })).toBeInTheDocument();
  });

  test('Retry sits in a wide row, so on a phone it is the width of the screen', async () => {
    failWith(500);
    renderPage();

    const retry = await screen.findByRole('button', { name: /retry/i });
    expect(retry.parentElement).toHaveClass('button-row-wide');
  });

  test('a 403 says it is a permission problem, not a generic failure', async () => {
    failWith(403);
    renderPage();

    expect(
      await screen.findByText(/do not have access to this group's members/i)
    ).toBeInTheDocument();
  });

  test('Retry re-fetches, and a collection that loads the second time renders normally', async () => {
    let attempt = 0;
    globalThis.fetch = vi.fn(() => {
      attempt += 1;
      return attempt === 1
        ? Promise.resolve({ ok: false, status: 500, json: async () => ({}) })
        : Promise.resolve({ ok: true, status: 200, json: async () => COLLECTION });
    });

    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: /retry/i }));

    expect(await screen.findByText(/Ana/)).toBeInTheDocument();
    expect(screen.queryByText(/error loading/i)).not.toBeInTheDocument();
  });
});

describe('ManageInvitesPage — co-owners', () => {
  afterEach(async () => {
    vi.restoreAllMocks();
    localStorage.clear();
    // `useCollectionLanguage` moves the whole UI to the collection's language;
    // put it back so the next test starts in English.
    const { default: i18n } = await import('../i18n');
    await switchLanguage(i18n, 'en');
    localStorage.removeItem('i18nextLng');
  });

  const TWO_MEMBERS = {
    ...COLLECTION,
    invites: [
      { code: 'GST001', email: 'lala1@your-domain.test', name: 'Ana' },
      { code: 'GST002', email: 'lele3@your-domain.test', name: 'Bea' },
    ],
    pending_invites: [],
    co_owners: [{ code: 'GST002', name: 'Bea' }],
  };

  // The row's toggle and the dialog's confirm both say "Add to the team" now, so the
  // confirm is the one inside the dialog (the row sits behind the modal).
  const confirmButton = async () =>
    within(await screen.findByRole('dialog')).getByRole('button', { name: 'Add to the team' });

  function mockCoOwnerRoutes({ collection = TWO_MEMBERS, coOwner = { status: 200 } } = {}) {
    globalThis.fetch = vi.fn((url) => {
      const respond = (status, body) =>
        Promise.resolve({ ok: status < 400, status, json: async () => body });
      if (url.endsWith('/co-owners/')) {
        return respond(coOwner.status, coOwner.body ?? { message: 'ok' });
      }
      // A signed-in reader with no language saved on their profile — which is
      // what lets the collection's own language reach the page's chrome.
      if (url.endsWith('/auth/me/')) return respond(200, { code: 'OWNER1', language: '' });
      return respond(200, collection);
    });
  }

  test('the owner sees a promote toggle on a plain member and a demote toggle on a co-owner', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    mockCoOwnerRoutes();
    renderPage();

    await screen.findByText(/Ana/);
    expect(screen.getByRole('button', { name: 'Add to the team' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Remove from the team' })).toBeInTheDocument();
  });

  test('promoting confirms first, then posts to /co-owners/ with the member’s code', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    mockCoOwnerRoutes();
    renderPage();
    await screen.findByText(/Ana/);

    fireEvent.click(screen.getByRole('button', { name: 'Add to the team' }));

    // The star opens a confirm — promotion hands over the member list (emails
    // included) and the power to appoint more curators, so it is not one click.
    const dialog = await screen.findByRole('dialog');
    expect(dialog).toHaveTextContent(/everything you can except delete the collection/i);
    expect(globalThis.fetch.mock.calls.some(([u]) => u.endsWith('/co-owners/'))).toBe(false);

    fireEvent.click(within(dialog).getByRole('button', { name: 'Add to the team' }));

    await screen.findByText('Added to the team.');
    const [url, options] = globalThis.fetch.mock.calls.find(([u]) => u.endsWith('/co-owners/'));
    expect(url).toBe('/api/v1/collections/COL001/co-owners/');
    expect(options.method).toBe('POST');
    expect(JSON.parse(options.body)).toEqual({ user_code: 'GST001' });
  });

  test('cancelling the promote confirm posts nothing', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    mockCoOwnerRoutes();
    renderPage();
    await screen.findByText(/Ana/);

    fireEvent.click(screen.getByRole('button', { name: 'Add to the team' }));
    await screen.findByRole('dialog');
    fireEvent.click(screen.getByRole('button', { name: 'Cancel' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(globalThis.fetch.mock.calls.some(([u]) => u.endsWith('/co-owners/'))).toBe(false);
  });

  test('demoting sends DELETE with the co-owner’s code', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    mockCoOwnerRoutes();
    renderPage();
    await screen.findByText(/Bea/);

    fireEvent.click(screen.getByRole('button', { name: 'Remove from the team' }));

    await screen.findByText('Removed from the team.');
    const [, options] = globalThis.fetch.mock.calls.find(([u]) => u.endsWith('/co-owners/'));
    expect(options.method).toBe('DELETE');
    expect(JSON.parse(options.body)).toEqual({ user_code: 'GST002' });
  });

  // The server's own English sentence, as `CollectionCoOwnerView` sends it, and
  // the code + number that let this page say it in the reader's language.
  const CEILING = {
    error: 'This collection already has the maximum of 5 co-curators',
    code: 'co_owners_full',
    params: { max: 5 },
  };

  test('the co-curator ceiling is said in English from its code, not as the server’s sentence', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    mockCoOwnerRoutes({ coOwner: { status: 400, body: CEILING } });
    renderPage();
    await screen.findByText(/Ana/);

    fireEvent.click(screen.getByRole('button', { name: 'Add to the team' }));
    fireEvent.click(await confirmButton());

    expect(
      await screen.findByText(
        "This group's team already has 5 people besides the founder — the most it allows."
      )
    ).toBeInTheDocument();
    expect(screen.queryByText(/maximum of 5 co-curators/)).not.toBeInTheDocument();
  });

  test('in a Spanish group the ceiling comes out in castellano', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    mockCoOwnerRoutes({
      collection: { ...TWO_MEMBERS, language: 'es' },
      coOwner: { status: 400, body: CEILING },
    });
    renderPage();
    await screen.findByText(/Ana/);

    // The UI follows the collection's language once its first response lands.
    fireEvent.click(await screen.findByRole('button', { name: 'Sumar a la dinamización' }));
    fireEvent.click(
      within(await screen.findByRole('dialog')).getByRole('button', {
        name: 'Sumar a la dinamización',
      })
    );

    expect(
      await screen.findByText(
        'La dinamización de este grupo ya suma 5 personas además de quien lo creó: es el máximo que permite.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByText(/maximum of 5 co-curators/)).not.toBeInTheDocument();
  });

  test('a refusal with no code the page knows still shows the server’s sentence', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    mockCoOwnerRoutes({
      coOwner: { status: 400, body: { error: 'Only an existing member can be promoted' } },
    });
    renderPage();
    await screen.findByText(/Ana/);

    fireEvent.click(screen.getByRole('button', { name: 'Add to the team' }));
    fireEvent.click(await confirmButton());

    expect(await screen.findByText('Only an existing member can be promoted')).toBeInTheDocument();
  });

  test('a 429 on promoting says to wait, not the API’s bare error', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    mockCoOwnerRoutes({ coOwner: { status: 429, body: { detail: 'Request was throttled.' } } });
    renderPage();
    await screen.findByText(/Ana/);

    fireEvent.click(screen.getByRole('button', { name: 'Add to the team' }));
    fireEvent.click(await confirmButton());

    expect(await screen.findByText(/too many attempts/i)).toBeInTheDocument();
    expect(screen.queryByText('Request was throttled.')).not.toBeInTheDocument();
  });

  test('a 429 on demoting says to wait too', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    mockCoOwnerRoutes({ coOwner: { status: 429, body: { detail: 'Request was throttled.' } } });
    renderPage();
    await screen.findByText(/Bea/);

    fireEvent.click(screen.getByRole('button', { name: 'Remove from the team' }));

    expect(await screen.findByText(/too many attempts/i)).toBeInTheDocument();
    expect(screen.queryByText('Request was throttled.')).not.toBeInTheDocument();
  });

  test('a co-curator gets the promote toggle too (2026-09 — any curator may)', async () => {
    localStorage.setItem('userCode', 'GST002');
    mockCoOwnerRoutes({ collection: { ...TWO_MEMBERS, is_curator: true } });
    renderPage();
    await screen.findByText(/Ana/);

    expect(screen.getByLabelText('Guest email')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Add to the team' })).toBeInTheDocument();
  });

  test('the roster names Bea as a co-curator', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    mockCoOwnerRoutes();
    renderPage();

    // On Bea's own row, and only there: Ana is a plain member.
    const beaRow = (await screen.findByText(/Bea/)).closest('tr');
    const anaRow = screen.getByText(/Ana/).closest('tr');
    expect(within(beaRow).getByText('Team')).toBeInTheDocument();
    expect(within(anaRow).queryByText('Team')).not.toBeInTheDocument();
  });
});

/**
 * The invitations field takes several addresses: `lala@your-domain.test,
 * lele@your-domain.test`. One address is the invitation it always was (`invite/`); several are
 * one batch for `invite/bulk/`, summarised the way the CSV tool says it. The ones that
 * went out join the pending list and the field keeps the ones that did not.
 */
describe('ManageInvitesPage — several addresses in the invitations field', () => {
  beforeEach(() => {
    localStorage.setItem('userCode', 'OWNER1');
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  const field = () => screen.getByLabelText('Guest email');
  const type = (value) => fireEvent.change(field(), { target: { value } });
  const send = () => fireEvent.click(screen.getByRole('button', { name: 'Invite' }));
  const bulkCalls = () => globalThis.fetch.mock.calls.filter(([u]) => u.endsWith('/invite/bulk/'));
  const singleCalls = () =>
    globalThis.fetch.mock.calls.filter(([u]) => u.endsWith('/invite/') && !u.endsWith('/bulk/'));
  const bulkBody = () => JSON.parse(bulkCalls()[0][1].body);

  async function open(routes) {
    mockRoutes(routes);
    renderPage();
    await screen.findByText(/Ana/);
  }

  test('the field is a text field with the email keyboard, not type=email, and says it takes several', async () => {
    await open();

    // `type="email"` would strip a pasted list's line breaks, have no place for ";"
    // and take commas only with `multiple`; `inputMode` keeps the email keyboard.
    expect(field()).toHaveAttribute('type', 'text');
    expect(field()).toHaveAttribute('inputmode', 'email');
    expect(field()).toHaveAttribute('autocapitalize', 'none');
    expect(field()).toHaveAttribute('spellcheck', 'false');
    // The helper is the field's description — `aria-describedby`, which TextInput does.
    expect(field()).toHaveAccessibleDescription(
      'You can invite several people at once: separate the emails with commas.'
    );
  });

  test('one address is the invitation it always was: invite/, no batch', async () => {
    await open();

    type('lele2@your-domain.test');
    send();

    await screen.findByText('Invitation sent.');
    expect(singleCalls().filter(([, o]) => o?.method === 'POST')).toHaveLength(1);
    expect(bulkCalls()).toHaveLength(0);
    // …also with a comma left at the end, which is no second address.
    type('lolo@your-domain.test, ');
    send();
    await waitFor(() =>
      expect(singleCalls().filter(([, o]) => o?.method === 'POST')).toHaveLength(2)
    );
    expect(bulkCalls()).toHaveLength(0);
    expect(JSON.parse(singleCalls().at(-1)[1].body)).toEqual({ email: 'lolo@your-domain.test' });
  });

  test('two addresses with a comma — spaces around them, one repeated — are ONE batch of two', async () => {
    await open();

    type('lala@your-domain.test ,  lele@your-domain.test, LALA@your-domain.test');
    send();

    await waitFor(() => expect(bulkCalls()).toHaveLength(1));
    expect(bulkCalls()[0][0]).toBe('/api/v1/collections/COL001/invite/bulk/');
    expect(bulkCalls()[0][1].method).toBe('POST');
    expect(bulkBody()).toEqual({
      invites: [{ email: 'lala@your-domain.test' }, { email: 'lele@your-domain.test' }],
    });
    // Never one by one through the single endpoint.
    expect(singleCalls().filter(([, o]) => o?.method === 'POST')).toHaveLength(0);
  });

  // A one-line field never receives a line break (the browser — and jsdom — turns them
  // into spaces or drops them before the page sees the value), so the page can only be
  // shown ";" and spaces; the line breaks themselves are `utils/emailList.test.js`'s.
  test('";" separates too, and so do the spaces a browser makes of a pasted column’s line breaks', async () => {
    await open();

    type(
      'lele1@your-domain.test;lili1@your-domain.test; lala5@your-domain.test lele5@your-domain.test'
    );
    send();
    await waitFor(() => expect(bulkCalls()).toHaveLength(1));
    expect(bulkBody().invites.map((i) => i.email)).toEqual([
      'lele1@your-domain.test',
      'lili1@your-domain.test',
      'lala5@your-domain.test',
      'lele5@your-domain.test',
    ]);
  });

  test('the summary says how many went out, and the ones that did are pending; the field empties', async () => {
    await open({ bulk: { status: 200, body: { invited: 2, skipped: [] } } });

    type('lala@your-domain.test, lele@your-domain.test');
    send();

    // The CSV tool's own words and shape.
    expect(await screen.findByText('2 invitations sent.')).toBeInTheDocument();
    expect(screen.getByText('lala@your-domain.test')).toBeInTheDocument();
    expect(screen.getByText('lele@your-domain.test')).toBeInTheDocument();
    expect(field()).toHaveValue('');
    // It is a batch, not a single invitation: no "Invitation sent." toast.
    expect(screen.queryByText('Invitation sent.')).toBeNull();
  });

  test('what was skipped stays in the field, with its reason; what went out joins the pending list', async () => {
    await open({
      bulk: {
        status: 200,
        body: {
          invited: 1,
          skipped: [
            { email: 'nope', reason: 'invalid' },
            // The server lowercases what it validates: the field keeps what was typed.
            { email: 'lala1@your-domain.test', reason: 'already_member' },
          ],
        },
      },
    });

    type('lala@your-domain.test, nope, Lala1@Your-Domain.TEST');
    send();

    expect(await screen.findByText('1 invitations sent.')).toBeInTheDocument();
    expect(screen.getByText('2 skipped:')).toBeInTheDocument();
    expect(screen.getByText('nope — invalid email')).toBeInTheDocument();
    expect(screen.getByText('lala1@your-domain.test — already a member')).toBeInTheDocument();
    // The field holds exactly the ones that did not go, as typed, to correct or retry.
    expect(field()).toHaveValue('nope, Lala1@Your-Domain.TEST');
    // The one that did is pending now; the others were not added.
    expect(screen.getByText('lala@your-domain.test')).toBeInTheDocument();
    expect(screen.queryByText('nope')).toBeNull();
  });

  test('an address too long to be one is cut by the server at 64 characters and still stays in the field', async () => {
    const long = `${'x'.repeat(70)}@your-domain.test`;
    await open({
      bulk: {
        status: 200,
        body: { invited: 1, skipped: [{ email: long.slice(0, 64), reason: 'invalid' }] },
      },
    });

    type(`lala@your-domain.test, ${long}`);
    send();

    await screen.findByText('1 invitations sent.');
    expect(field()).toHaveValue(long);
  });

  test('past 100 addresses it is still one batch, and the server’s own message comes back', async () => {
    const many = Array.from({ length: 101 }, (_, i) => `lele${i}@your-domain.test`);
    await open({
      bulk: {
        status: 400,
        body: { error: 'At most 100 invitations can be sent at once.' },
      },
    });

    type(many.join(', '));
    send();

    expect(
      await screen.findByText('At most 100 invitations can be sent at once.')
    ).toBeInTheDocument();
    // Not split behind the reader's back: all 101 went in one call.
    expect(bulkCalls()).toHaveLength(1);
    expect(bulkBody().invites).toHaveLength(101);
    expect(singleCalls().filter(([, o]) => o?.method === 'POST')).toHaveLength(0);
    // Nothing went out, so nothing changes: the field keeps the whole list.
    expect(field()).toHaveValue(many.join(', '));
    expect(screen.queryByText(/invitations sent\./)).toBeNull();
  });

  test('too many attempts says so and keeps the field', async () => {
    await open({ bulk: { status: 429, body: {} } });

    type('lele1@your-domain.test, lili1@your-domain.test');
    send();

    expect(
      await screen.findByText('Too many attempts — please wait a moment and try again.')
    ).toBeInTheDocument();
    expect(field()).toHaveValue('lele1@your-domain.test, lili1@your-domain.test');
  });

  test('a request that never arrives says so and keeps the field', async () => {
    await open({ bulk: { reject: true } });

    type('lele1@your-domain.test, lili1@your-domain.test');
    send();

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
    expect(field()).toHaveValue('lele1@your-domain.test, lili1@your-domain.test');
    // …and the button is back, ready to try again.
    expect(screen.getByRole('button', { name: 'Invite' })).toBeEnabled();
  });

  test('the next send starts clean: the last batch’s summary goes', async () => {
    await open({ bulk: { status: 200, body: { invited: 2, skipped: [] } } });
    type('lele1@your-domain.test, lili1@your-domain.test');
    send();
    await screen.findByText('2 invitations sent.');

    type('lele2@your-domain.test');
    send();

    await screen.findByText('Invitation sent.');
    expect(screen.queryByText('2 invitations sent.')).toBeNull();
  });

  test('the button waits for an address: nothing, or only separators, is nothing to send', async () => {
    await open();
    const invite = screen.getByRole('button', { name: 'Invite' });

    expect(invite).toBeDisabled();
    type(' , ;  ');
    expect(invite).toBeDisabled();
    type('lele1@your-domain.test');
    expect(invite).toBeEnabled();
    type('lele1@your-domain.test, lili1@your-domain.test');
    expect(invite).toBeEnabled();
  });
});

// Removing a member deletes their things in the group, so the confirmation page is
// handed their titles with the guest: it cannot read them itself without a second
// request, and a stale list is worse than none.
describe('ManageInvitesPage hands the confirmation the removed member’s things', () => {
  beforeEach(() => {
    localStorage.setItem('userCode', 'OWNER1');
  });
  afterEach(() => {
    vi.restoreAllMocks();
    localStorage.clear();
  });

  function ConfirmationProbe() {
    return <pre data-testid="state">{JSON.stringify(useLocation().state)}</pre>;
  }

  async function removeAna(collection) {
    mockRoutes({ collection });
    render(
      <MemoryRouter initialEntries={['/collections/COL001/invites']}>
        <Routes>
          <Route path="/collections/:code/invites" element={<ManageInvitesPage />} />
          <Route path="/collections/:code/invites/remove" element={<ConfirmationProbe />} />
        </Routes>
      </MemoryRouter>
    );
    const row = (await screen.findByText(/Ana/)).closest('tr');
    fireEvent.click(within(row).getByRole('button', { name: 'Remove from this collection' }));
    return JSON.parse((await screen.findByTestId('state')).textContent);
  }

  const thing = (code, owner, headline) => ({ code, owner, headline, status: 'ACTIVE' });

  test('only the titles of that member’s things travel in the state', async () => {
    const state = await removeAna({
      ...COLLECTION,
      things: [
        thing('T1', 'GST001', 'Drill'),
        thing('T2', 'OWNER1', 'Ladder'),
        thing('T3', 'GST001', 'Saw'),
      ],
    });

    expect(state).toMatchObject({ guestCode: 'GST001', thingTitles: ['Drill', 'Saw'] });
  });

  test('a member with no things in the group travels with an empty list', async () => {
    const state = await removeAna({ ...COLLECTION, things: [thing('T2', 'OWNER1', 'Ladder')] });

    expect(state.thingTitles).toEqual([]);
  });
});

/**
 * An address the server has already invited gets no second email. The refusal is a notice
 * that stays under the field, with the button that copies the invitation link so the
 * curator can hand it over themselves, not a toast that fades before they have read it.
 */
describe('ManageInvitesPage — an invitation the server will not email again', () => {
  const ASKED_ONE = "This person has already had an invitation and can't get another by email.";
  const ASKED_MANY = "Some people have already had an invitation and can't get another by email.";
  const SHARE_URL = 'https://example.test/share/TOKEN123';
  let writeText;

  beforeEach(() => {
    localStorage.setItem('userCode', 'OWNER1');
    writeText = vi.fn(() => Promise.resolve());
    Object.defineProperty(navigator, 'clipboard', { value: { writeText }, configurable: true });
  });
  afterEach(() => {
    vi.useRealTimers();
    vi.restoreAllMocks();
    localStorage.clear();
  });

  const refusal = {
    status: 400,
    body: { error: 'x', code: 'invite_already_asked' },
  };
  const field = () => screen.getByLabelText('Guest email');
  const type = (value) => fireEvent.change(field(), { target: { value } });
  const send = () => fireEvent.click(screen.getByRole('button', { name: 'Invite' }));
  const copyButton = () => screen.getByRole('button', { name: 'Copy invite link' });
  const shareCalls = () => globalThis.fetch.mock.calls.filter(([u]) => u.endsWith('/share-link/'));

  async function open({ collection = COLLECTION, ...routes } = {}) {
    mockRoutes({ collection, ...routes });
    const inner = globalThis.fetch;
    globalThis.fetch = vi.fn((url, opts) =>
      url.endsWith('/share-link/')
        ? Promise.resolve({ ok: true, status: 200, json: async () => ({ share_url: SHARE_URL }) })
        : inner(url, opts)
    );
    renderPage();
    await screen.findByText(/Ana/);
  }

  test('a single refusal stays as a notice with the copy button, however long it takes', async () => {
    await open({ invite: refusal });
    type('lili2@your-domain.test');
    send();

    expect(await screen.findByText(ASKED_ONE, { exact: false })).toBeInTheDocument();
    expect(copyButton()).toBeInTheDocument();

    vi.useFakeTimers();
    act(() => vi.advanceTimersByTime(60000));
    expect(screen.getByText(ASKED_ONE, { exact: false })).toBeInTheDocument();
    expect(copyButton()).toBeInTheDocument();
  });

  test('a private group’s button asks for the link and copies the share_url', async () => {
    await open({ invite: refusal });
    type('lili2@your-domain.test');
    send();
    await screen.findByText(ASKED_ONE, { exact: false });

    fireEvent.click(copyButton());

    await waitFor(() => expect(writeText).toHaveBeenCalledWith(SHARE_URL));
    expect(shareCalls()).toHaveLength(1);
    expect(shareCalls()[0][1].method).toBe('POST');
    expect(await screen.findByText('Invite link copied to clipboard.')).toBeInTheDocument();
  });

  test('a public group’s button copies the collection’s own address and asks for nothing', async () => {
    await open({
      invite: refusal,
      collection: { ...COLLECTION, visibility: 'PUBLIC', kind: 'LIBRARY' },
    });
    type('lili2@your-domain.test');
    send();
    await screen.findByText(ASKED_ONE, { exact: false });

    fireEvent.click(copyButton());

    await waitFor(() =>
      expect(writeText).toHaveBeenCalledWith(`${window.location.origin}/library/COL001`)
    );
    expect(shareCalls()).toHaveLength(0);
  });

  test('a batch that skipped someone already asked shows the notice and the button', async () => {
    await open({
      bulk: {
        status: 200,
        body: {
          invited: 1,
          skipped: [{ email: 'lele@your-domain.test', reason: 'already_asked' }],
        },
      },
    });
    type('lala@your-domain.test, lele@your-domain.test');
    send();

    expect(await screen.findByText(ASKED_MANY, { exact: false })).toBeInTheDocument();
    expect(copyButton()).toBeInTheDocument();
  });

  test('a batch that skipped nobody for that reason shows no notice', async () => {
    await open({
      bulk: {
        status: 200,
        body: {
          invited: 1,
          skipped: [{ email: 'lele@your-domain.test', reason: 'already_member' }],
        },
      },
    });
    type('lala@your-domain.test, lele@your-domain.test');
    send();

    await screen.findByText(/lele@your-domain.test — already a member/);
    expect(screen.queryByRole('button', { name: 'Copy invite link' })).toBeNull();
    expect(screen.queryByText(ASKED_MANY, { exact: false })).toBeNull();
  });

  test('the next send takes the notice away', async () => {
    await open({ invite: refusal });
    type('lili2@your-domain.test');
    send();
    await screen.findByText(ASKED_ONE, { exact: false });

    mockRoutes({ invite: { status: 200 } });
    type('someone-new@your-domain.test');
    send();

    await waitFor(() =>
      expect(screen.queryByText(ASKED_ONE, { exact: false })).not.toBeInTheDocument()
    );
    expect(screen.queryByRole('button', { name: 'Copy invite link' })).toBeNull();
  });

  test('another refusal keeps its toast and shows no notice', async () => {
    await open({ invite: { status: 400, body: { error: 'Something else went wrong.' } } });
    type('lili2@your-domain.test');
    send();

    expect(await screen.findByText('Something else went wrong.')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Copy invite link' })).toBeNull();
  });
});
