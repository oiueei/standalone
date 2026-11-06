import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';
import { axe, toHaveNoViolations } from 'jest-axe';
import MyBookingsPage from './MyBookingsPage';
import { mockMatchMedia, PHONE } from '../test/matchMedia';
import { settle } from '../test/settle';

expect.extend(toHaveNoViolations);

// The JSON shape `/api/v1/my-bookings/` returns (the subset the page reads).
const booking = (over = {}) => ({
  code: 'BKG001',
  status: 'PENDING',
  thing_code: 'THG001',
  thing_headline: 'Cordless drill',
  thing_type: 'LEND_THING',
  owner_name: 'Lala',
  start_date: '2026-09-01',
  end_date: '2026-09-08',
  created: '2026-08-01T10:00:00Z',
  ...over,
});

function mockList(results, next = null) {
  globalThis.fetch = vi.fn().mockResolvedValue({
    ok: true,
    status: 200,
    json: async () => ({ results, next }),
  });
}

function renderPage() {
  return render(
    <MemoryRouter>
      <MyBookingsPage />
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'USR001');
});
afterEach(() => {
  vi.restoreAllMocks();
});

describe('MyBookingsPage listing', () => {
  test('splits pending requests from settled ones', async () => {
    // The split is the page's whole organising idea: what still needs the
    // owner's answer is actionable, everything else is history.
    mockList([
      booking({ code: 'BKG001', status: 'PENDING', thing_headline: 'Cordless drill' }),
      booking({ code: 'BKG002', status: 'ACCEPTED', thing_headline: 'Tent' }),
    ]);
    renderPage();

    await screen.findByText('Cordless drill');
    expect(screen.getByRole('heading', { name: 'Pending' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Past requests' })).toBeInTheDocument();
    expect(screen.getByText('Tent')).toBeInTheDocument();
  });

  test('both tables carry a name, so they can be told apart in a rotor', async () => {
    // A <table> with no <caption> is announced as "table, 2 columns" and nothing
    // else. This page has two of them, one under each heading — and a heading is
    // not a table's name, so a reader listing the tables on this page got two
    // identical nameless entries. The captions are screen-reader-only: the
    // headings already say it on screen.
    renderPage();

    expect(
      await screen.findByRole('table', { name: 'Requests waiting for an answer' })
    ).toBeInTheDocument();
    expect(screen.getByRole('table', { name: 'Requests already closed' })).toBeInTheDocument();
  });

  test('the column holding the cancel control has a name a screen reader can say', async () => {
    // It was an empty <th> (axe empty-table-header): moving through the row, a
    // reader reached the cancel control under a column with no name at all.
    mockList([booking()]);
    renderPage();

    await screen.findByText('Cordless drill');
    expect(screen.getAllByRole('columnheader', { name: 'Actions' }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('columnheader', { name: '' })).not.toBeInTheDocument();
  });

  test('the thing is one column, when it was asked and when it runs is the next', async () => {
    // The first column used to hold everything. Now "Thing" is the
    // link and whose it is; "When" is the request date and the dates (or "No dates").
    mockList([
      booking({ owner_name: 'Lala' }),
      booking({
        code: 'BKG002',
        status: 'ACCEPTED',
        thing_type: 'GIFT_THING',
        thing_headline: 'Tent',
        start_date: null,
        end_date: null,
      }),
    ]);
    renderPage();

    await screen.findByText('Cordless drill');
    const headers = within(screen.getAllByRole('table')[0])
      .getAllByRole('columnheader')
      .map((th) => th.textContent);
    expect(headers).toEqual(['Thing', 'When', 'Status', 'Actions']);

    const [thing, when] = within(
      screen.getByRole('link', { name: 'Cordless drill' }).closest('tr')
    ).getAllByRole('cell');
    expect(within(thing).getByRole('link', { name: 'Cordless drill' })).toBeInTheDocument();
    expect(thing).toHaveTextContent('Lala');
    expect(thing).not.toHaveTextContent(/Requested/);
    expect(when).toHaveTextContent(/Requested/);
    expect(when).toHaveTextContent('01/09/2026');
    expect(within(when).queryByRole('link')).toBeNull();

    // A gift has no dates, and shows the dash (`myBookings.noDates`) in the same cell.
    const [, giftWhen] = within(
      screen.getByRole('link', { name: 'Tent' }).closest('tr')
    ).getAllByRole('cell');
    expect(giftWhen).toHaveTextContent('—');
  });

  test('the lines of a cell touch: they carry the shared class and no margin of their own', async () => {
    // The look is `.table-cell-lines p { margin: 0 }`,
    // pinned in `tableCellStyles.test.js`; an inline margin on a line would beat it.
    mockList([booking({ owner_name: 'Lala' })]);
    renderPage();

    await screen.findByText('Cordless drill');
    const cells = within(
      screen.getByRole('link', { name: 'Cordless drill' }).closest('tr')
    ).getAllByRole('cell');
    for (const cell of cells.slice(0, 2)) {
      expect(cell.querySelector('.table-cell-lines')).not.toBeNull();
      for (const line of cell.querySelectorAll('p')) {
        expect(line.getAttribute('style')).toBeNull();
      }
    }
  });

  test('the type and the state sit in a status cell that sizes each label to its word', async () => {
    // Both labels filled the column (a bare flex column stretches
    // its children), and since Tag centres and StatusLabel does not, one read
    // centred and the other left. The layout is the class; its rule is pinned in
    // `tableCellStyles.test.js`. The type shows only in a table that mixes verbs,
    // so there are two of them.
    mockList([
      booking({ status: 'EXPIRED' }),
      booking({
        code: 'BKG002',
        status: 'REJECTED',
        thing_type: 'GIFT_THING',
        thing_headline: 'Tent',
        start_date: null,
        end_date: null,
      }),
    ]);
    renderPage();

    await screen.findByText('Cordless drill');
    const cell = screen.getByText('Lend').closest('.table-status-cell');
    expect(cell).not.toBeNull();
    // The type, the state and the "expired" explanation all live inside it.
    expect(within(cell).getByText('Expired')).toBeInTheDocument();
    expect(within(cell).getByText(/expired/i, { selector: 'p' })).toBeInTheDocument();
  });

  test('with nothing pending, the section says so instead of vanishing', async () => {
    // An empty pending table would read as "the page is broken", not "you have
    // no open requests".
    mockList([booking({ status: 'REJECTED', thing_headline: 'Tent' })]);
    renderPage();

    await screen.findByText('Tent');
    expect(screen.getByText('No pending requests.')).toBeInTheDocument();
  });

  test('each status carries its own semantic label', async () => {
    mockList([
      booking({ code: 'B1', status: 'PENDING' }),
      booking({ code: 'B2', status: 'ACCEPTED' }),
      booking({ code: 'B3', status: 'REJECTED' }),
      booking({ code: 'B4', status: 'CANCELLED' }),
      booking({ code: 'B5', status: 'EXPIRED' }),
    ]);
    renderPage();

    await screen.findByText('Confirmed');
    expect(screen.getByText('Rejected')).toBeInTheDocument();
    expect(screen.getByText('Cancelled')).toBeInTheDocument();
    expect(screen.getByText('Expired')).toBeInTheDocument();
    // An expired request is the one status a user cannot explain to themselves,
    // so it must say why it lapsed.
    expect(screen.getByText(/expired automatically/)).toBeInTheDocument();
  });

  test('a booking with no dates shows the placeholder, not "Invalid Date"', async () => {
    // GIFT/SELL holds carry no range; formatting null through toLocaleDateString
    // would print "Invalid Date" into the table.
    mockList([booking({ start_date: null, end_date: null, thing_type: 'GIFT_THING' })]);
    renderPage();

    await screen.findByText('Cordless drill');
    expect(screen.queryByText(/Invalid Date/)).not.toBeInTheDocument();
  });

  test('dates render DD/MM/YYYY, matching the picker — not ISO, not US order', async () => {
    mockList([booking({ start_date: '2026-09-01', end_date: '2026-09-08' })]);
    renderPage();

    await screen.findByText('Cordless drill');
    expect(screen.getByText(/01\/09\/2026\s*—\s*08\/09\/2026/)).toBeInTheDocument();
    expect(screen.queryByText(/2026-09-01/)).not.toBeInTheDocument();
    expect(screen.queryByText(/9\/1\/2026/)).not.toBeInTheDocument();
  });

  test('an HOUR-unit reservation shows the date once and both clock times', async () => {
    mockList([
      booking({
        thing_type: 'RESERVE_THING',
        status: 'ACCEPTED',
        start_date: '2026-09-01',
        end_date: '2026-09-02', // the day-based "free again" marker — must not show
        start_time: '11:00:00',
        end_time: '13:00:00',
      }),
    ]);
    renderPage();

    await screen.findByText('Cordless drill');
    expect(screen.getByText(/01\/09\/2026, 11:00–13:00/)).toBeInTheDocument();
    expect(screen.queryByText(/02\/09\/2026/)).not.toBeInTheDocument();
  });

  test('a one-day reservation lists as one day, not up to the day the space frees up', async () => {
    mockList([
      booking({
        thing_type: 'RESERVE_THING',
        status: 'ACCEPTED',
        start_date: '2026-09-01',
        end_date: '2026-09-02', // start + 1 day: free again on the 2nd
      }),
    ]);
    renderPage();

    await screen.findByText('Cordless drill');
    expect(screen.getByText('01/09/2026')).toBeInTheDocument();
    expect(screen.queryByText(/02\/09\/2026/)).not.toBeInTheDocument();
  });

  test('the thing links to its page and names the owner', async () => {
    mockList([booking()]);
    renderPage();

    const link = await screen.findByRole('link', { name: 'Cordless drill' });
    expect(link).toHaveAttribute('href', '/things/THG001');
    expect(screen.getByText('Lala')).toBeInTheDocument();
  });

  test('an empty list offers a way out rather than a dead end', async () => {
    mockList([]);
    renderPage();

    await screen.findByText('You have no booking requests yet.');
    expect(screen.getByRole('link', { name: 'Browse collections' })).toHaveAttribute('href', '/');
  });

  test('that way out sits in a wide row, so on a phone it is the width of the screen', async () => {
    mockList([]);
    renderPage();

    const link = await screen.findByRole('link', { name: 'Browse collections' });
    expect(link.parentElement).toHaveClass('button-row-wide');
  });

  test('a failed load says so instead of spinning forever', async () => {
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: false,
      status: 500,
      json: async () => ({}),
    });
    renderPage();

    expect(await screen.findByText('Error loading bookings.')).toBeInTheDocument();
  });
});

describe('MyBookingsPage when the list cannot be read', () => {
  test('without a connection it says so, not that the bookings failed to load', async () => {
    globalThis.fetch = vi.fn().mockRejectedValue(new TypeError('Failed to fetch'));
    renderPage();

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
    expect(screen.queryByText('Error loading bookings.')).toBeNull();
  });
});

describe('MyBookingsPage cancelling', () => {
  test('only a pending request offers the cancel control', async () => {
    // Cancelling a settled request is meaningless, and offering it would invite
    // an error the user cannot undo.
    mockList([booking({ code: 'B1', status: 'ACCEPTED' })]);
    renderPage();

    await screen.findByText('Confirmed');
    expect(
      screen.queryByRole('button', { name: 'Cancel this booking request' })
    ).not.toBeInTheDocument();
  });

  test('cancelling posts to the booking and moves the row to Cancelled', async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ results: [booking()] }),
      })
      .mockResolvedValueOnce({ ok: true, status: 200, json: async () => ({}) });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Cancel this booking request' }));

    await screen.findByText('Cancelled');
    const [url, options] = globalThis.fetch.mock.calls[1];
    expect(url).toBe('/api/v1/bookings/BKG001/cancel/');
    expect(options.method).toBe('POST');
    // The row must leave the pending section, not merely relabel in place.
    expect(screen.getByText('No pending requests.')).toBeInTheDocument();
    expect(screen.getByText('Request cancelled.')).toBeInTheDocument();
  });

  test('a rejected cancel leaves the request pending and says so', async () => {
    // The dangerous failure is a request that *looks* cancelled but is not: the
    // owner still holds it, and the user stops waiting for an answer.
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ results: [booking()] }),
      })
      .mockResolvedValueOnce({ ok: false, status: 400, json: async () => ({}) });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Cancel this booking request' }));

    expect(await screen.findByText('Error cancelling request.')).toBeInTheDocument();
    expect(screen.queryByText('Cancelled')).not.toBeInTheDocument();
    expect(screen.queryByText('No pending requests.')).not.toBeInTheDocument();
    // Still cancellable — the user has to be able to try again.
    expect(screen.getByRole('button', { name: 'Cancel this booking request' })).toBeInTheDocument();
  });
});

/**
 * A reservation auto-confirms, so cancelling one tells the group, frees the slot
 * for anybody else, and cannot be undone. It used to go on one press of an icon
 * in a table row; now the press asks first, naming what would go. (Withdrawing a
 * *pending* request stays one press — pinned by the block above, whose POST is
 * the very next call after the click.)
 */
describe('MyBookingsPage cancelling a confirmed reservation', () => {
  const reservation = booking({
    thing_type: 'RESERVE_THING',
    thing_headline: 'Laser cutter',
    status: 'ACCEPTED',
    start_date: '2099-01-10',
    end_date: '2099-01-11',
    start_time: '10:00:00',
    end_time: '11:30:00',
  });
  const posts = () => globalThis.fetch.mock.calls.filter(([, o]) => o?.method === 'POST');

  beforeEach(() => {
    globalThis.fetch = vi.fn((url, opts) =>
      Promise.resolve(
        opts?.method === 'POST'
          ? { ok: true, status: 200, json: async () => ({}) }
          : { ok: true, status: 200, json: async () => ({ results: [reservation] }) }
      )
    );
  });

  test('one press asks first, names what would go, and sends nothing', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel reservation' }));

    const dialog = await screen.findByRole('dialog', { name: 'Cancel this reservation?' });
    expect(dialog).toHaveTextContent('Laser cutter — 10/01/2099, 10:00–11:30');
    expect(dialog).toHaveTextContent(/can't be undone/);
    expect(posts()).toHaveLength(0);
    // Scoped to the dialog, which is what this adds. `region` is off: the render
    // has no app landmarks to hold it (as in a11yInteractive.test.jsx).
    await settle(globalThis.fetch);
    expect(await axe(dialog, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  test('confirming cancels it, once, and says it was the reservation', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel reservation' }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel reservation' }));

    expect(await screen.findByText('Reservation cancelled.')).toBeInTheDocument();
    expect(posts().map(([u]) => u)).toEqual(['/api/v1/bookings/BKG001/cancel/']);
    expect(screen.getByText('Cancelled')).toBeInTheDocument();
    expect(screen.queryByRole('dialog')).not.toBeInTheDocument();
  });

  test('backing out leaves the reservation standing', async () => {
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel reservation' }));
    const dialog = await screen.findByRole('dialog');

    // Its way out is "Back": a "Cancel" beside "Cancel reservation" would read
    // as the same action.
    expect(within(dialog).queryByRole('button', { name: 'Cancel' })).not.toBeInTheDocument();
    fireEvent.click(within(dialog).getByRole('button', { name: 'Back' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument());
    expect(posts()).toHaveLength(0);
    expect(screen.getByText('Confirmed')).toBeInTheDocument();
  });
});

describe('MyBookingsPage pagination', () => {
  test('the pager sits in a wide row, so on a phone it is the width of the screen', async () => {
    mockList([booking()], 'http://testserver/api/v1/my-bookings/?page=2');
    renderPage();

    const more = await screen.findByRole('button', { name: 'Load more' });
    expect(more.parentElement).toHaveClass('button-row-wide');
  });

  test('"Load more" appends the next page and keeps the request same-origin', async () => {
    // DRF returns an absolute `next`; sending it verbatim would leave the Vite
    // proxy in dev and drop the auth cookies with it.
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          results: [booking({ code: 'B1', thing_headline: 'Cordless drill' })],
          next: 'http://testserver/api/v1/my-bookings/?page=2',
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          results: [booking({ code: 'B2', thing_headline: 'Tent' })],
          next: null,
        }),
      });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Load more' }));

    await screen.findByText('Tent');
    expect(globalThis.fetch.mock.calls[1][0]).toBe('/api/v1/my-bookings/?page=2');
    // Appended, not replaced.
    expect(screen.getByText('Cordless drill')).toBeInTheDocument();
    // Exhausted: the button must go, or it re-fetches the same page forever.
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument()
    );
  });

  test('a refused second page says so and keeps the first one on screen', async () => {
    // Regression: `!res.ok` had no branch. The button re-enabled, nothing
    // appeared and nothing said why — which reads as a broken app rather than
    // a failed request.
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          results: [booking({ code: 'B1', thing_headline: 'Cordless drill' })],
          next: 'http://testserver/api/v1/my-bookings/?page=2',
        }),
      })
      .mockResolvedValueOnce({ ok: false, status: 500, json: async () => ({}) });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Load more' }));

    expect(await screen.findByText(/couldn't load more/i)).toBeInTheDocument();
    expect(screen.getByText('Cordless drill')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load more' })).toBeEnabled();
  });

  test('no "Load more" when the first page is the only page', async () => {
    mockList([booking()], null);
    renderPage();

    await screen.findByText('Cordless drill');
    expect(screen.queryByRole('button', { name: 'Load more' })).not.toBeInTheDocument();
  });
});

/**
 * On a phone each of my requests is a card instead of a row (`ResponsiveTable`).
 * Withdrawing one is a button with its words on it, and it must do
 * what the icon in the table does: one press for a pending request, a question
 * first for a reservation that is coming up.
 */
describe('MyBookingsPage on a phone', () => {
  let media;
  const posts = () => globalThis.fetch.mock.calls.filter(([, o]) => o?.method === 'POST');
  const mockBookings = (...results) => {
    globalThis.fetch = vi.fn((url, opts) =>
      Promise.resolve(
        opts?.method === 'POST'
          ? { ok: true, status: 200, json: async () => ({}) }
          : { ok: true, status: 200, json: async () => ({ results, next: null }) }
      )
    );
  };

  beforeEach(() => {
    media = mockMatchMedia({ [PHONE]: true });
  });
  afterEach(() => media.restore());

  test('a request is a card holding the thing, its owner, when, both labels and the cancel', async () => {
    // The verb's label is there because this table mixes verbs.
    mockBookings(
      booking(),
      booking({
        code: 'BKG002',
        thing_type: 'GIFT_THING',
        thing_headline: 'Tent',
        start_date: null,
        end_date: null,
      })
    );
    renderPage();

    const list = await screen.findByRole('list', { name: 'Requests waiting for an answer' });
    expect(screen.queryByRole('table')).toBeNull();
    const [card] = within(list).getAllByRole('listitem');
    expect(within(card).getByRole('link', { name: 'Cordless drill' })).toHaveAttribute(
      'href',
      '/things/THG001'
    );
    expect(within(card).getByText('Lala')).toBeInTheDocument();
    expect(within(card).getByText('Requested 01/08/2026')).toBeInTheDocument();
    expect(within(card).getByText('01/09/2026 — 08/09/2026')).toBeInTheDocument();
    expect(within(card).getByText('Lend')).toBeInTheDocument();
    expect(within(card).getByText('Pending')).toBeInTheDocument();
    const cancel = within(card).getByRole('button', { name: 'Cancel this booking request' });
    expect(cancel.parentElement).toHaveClass('button-row-wide');
  });

  test('cancelling a pending request sends what the icon sends, and the card settles', async () => {
    mockBookings(booking());
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Cancel this booking request' }));

    await waitFor(() =>
      expect(posts().map(([u]) => u)).toEqual(['/api/v1/bookings/BKG001/cancel/'])
    );
    expect(await screen.findByText('Cancelled')).toBeInTheDocument();
  });

  test('a settled request is still a card, with no cancel', async () => {
    mockBookings(booking({ status: 'REJECTED' }));
    renderPage();

    const list = await screen.findByRole('list', { name: 'Requests already closed' });
    expect(within(list).getByRole('link', { name: 'Cordless drill' })).toBeInTheDocument();
    expect(within(list).queryByRole('button')).toBeNull();
  });

  test('a coming reservation asks first, naming what would go, as the table does', async () => {
    mockBookings(
      booking({
        thing_type: 'RESERVE_THING',
        thing_headline: 'Laser cutter',
        status: 'ACCEPTED',
        start_date: '2099-01-10',
        end_date: '2099-01-11',
        start_time: '10:00:00',
        end_time: '11:30:00',
      })
    );
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Cancel reservation' }));

    const dialog = await screen.findByRole('dialog', { name: 'Cancel this reservation?' });
    expect(dialog).toHaveTextContent('Laser cutter');
    expect(posts()).toHaveLength(0);
  });

  test('the cards have no axe violations', async () => {
    mockBookings(booking(), booking({ code: 'BKG002', status: 'REJECTED' }));
    const { container } = renderPage();
    await screen.findByRole('list', { name: 'Requests waiting for an answer' });

    await settle(globalThis.fetch);
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

/**
 * The verb's label ("Rental", "Reservation"…) over the state in the status cell tells
 * rows apart only when a table mixes verbs: many collections hold
 * one verb, and the label repeated the same word in every row. It is decided per table
 * — each page has two, what is waiting or current and what is past — from that table's
 * own rows, and again whenever more rows are loaded. The state label and the "expired"
 * note are not part of it.
 */
describe('MyBookingsPage — the verb’s label only where a table mixes verbs', () => {
  const rental = (code, status = 'PENDING') =>
    booking({ code, status, thing_type: 'RENT_THING', thing_headline: `Drill ${code}` });
  const gift = (code, status = 'PENDING') =>
    booking({
      code,
      status,
      thing_type: 'GIFT_THING',
      thing_headline: `Tent ${code}`,
      start_date: null,
      end_date: null,
    });
  const inTable = (name) => within(screen.getByRole('table', { name }));
  const WAITING = 'Requests waiting for an answer';
  const CLOSED = 'Requests already closed';

  test('a table of one verb has no label on any row, and every row still has its state', async () => {
    mockList([rental('B1'), rental('B2')]);
    renderPage();

    await screen.findByText('Drill B1');
    expect(screen.queryByText('Rental')).toBeNull();
    // (The heading over the table also says "Pending", hence the table.)
    expect(inTable(WAITING).getAllByText('Pending')).toHaveLength(2);
  });

  test('a table that mixes verbs gives every row its verb', async () => {
    mockList([rental('B1'), gift('B2')]);
    renderPage();

    await screen.findByText('Drill B1');
    const rows = within(screen.getByRole('table', { name: WAITING })).getAllByRole('row');
    const [, first, second] = rows; // the header row, then one per request
    expect(within(first).getByText('Rental')).toBeInTheDocument();
    expect(within(second).getByText('Gift')).toBeInTheDocument();
  });

  test('the two tables decide apart: one verb waiting, a mix already closed', async () => {
    mockList([rental('B1'), rental('B2'), rental('B3', 'REJECTED'), gift('B4', 'CANCELLED')]);
    renderPage();

    await screen.findByText('Drill B1');
    expect(inTable(WAITING).queryByText('Rental')).toBeNull();
    expect(inTable(CLOSED).getByText('Rental')).toBeInTheDocument();
    expect(inTable(CLOSED).getByText('Gift')).toBeInTheDocument();
  });

  test('and the other way round: a mix waiting, one verb already closed', async () => {
    mockList([rental('B1'), gift('B2'), rental('B3', 'REJECTED'), rental('B4', 'CANCELLED')]);
    renderPage();

    await screen.findByText('Drill B1');
    expect(inTable(WAITING).getByText('Rental')).toBeInTheDocument();
    expect(inTable(WAITING).getByText('Gift')).toBeInTheDocument();
    expect(inTable(CLOSED).queryByText('Rental')).toBeNull();
  });

  test('loading more rows of another verb puts the label back on the whole table', async () => {
    globalThis.fetch = vi
      .fn()
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({
          results: [rental('B1'), rental('B2')],
          next: 'http://testserver/api/v1/my-bookings/?page=2',
        }),
      })
      .mockResolvedValueOnce({
        ok: true,
        status: 200,
        json: async () => ({ results: [gift('B3')], next: null }),
      });
    renderPage();
    await screen.findByText('Drill B1');
    expect(screen.queryByText('Rental')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));

    await screen.findByText('Tent B3');
    expect(screen.getAllByText('Rental')).toHaveLength(2); // the two that had none
    expect(screen.getByText('Gift')).toBeInTheDocument();
  });

  test('a single request is a table of one verb: no label', async () => {
    mockList([rental('B1')]);
    renderPage();

    await screen.findByText('Drill B1');
    expect(screen.queryByText('Rental')).toBeNull();
  });

  describe('on a phone, where each request is a card', () => {
    let media;
    beforeEach(() => {
      media = mockMatchMedia({ [PHONE]: true });
    });
    afterEach(() => media.restore());

    test('the cards of a table of one verb have no label; those of a mix have it', async () => {
      mockList([rental('B1'), rental('B2'), rental('B3', 'REJECTED'), gift('B4', 'CANCELLED')]);
      renderPage();

      const waiting = await screen.findByRole('list', { name: WAITING });
      const closed = screen.getByRole('list', { name: CLOSED });
      expect(within(waiting).queryByText('Rental')).toBeNull();
      expect(within(waiting).getAllByText('Pending')).toHaveLength(2);
      expect(within(closed).getByText('Rental')).toBeInTheDocument();
      expect(within(closed).getByText('Gift')).toBeInTheDocument();
    });
  });
});

// The thing's name is a bold link: one rule in App.css for the
// text links inside the component's own class, `.responsive-table` — see
// `test/tableLinkWeight.test.jsx`. These pin that this page's links are inside it, in
// the table and in the cards.
describe('MyBookingsPage — the bold links of the table', () => {
  const SELECTOR = ".responsive-table a:not([class*='hds-button'])";

  test('the thing’s link is inside the component’s class, in the table', async () => {
    mockList([booking(), booking({ code: 'BKG002', status: 'REJECTED', thing_headline: 'Tent' })]);
    renderPage();

    await screen.findByText('Cordless drill');
    for (const name of ['Cordless drill', 'Tent']) {
      expect(screen.getByRole('link', { name }).matches(SELECTOR)).toBe(true);
    }
  });

  test('and in the cards of a phone', async () => {
    const media = mockMatchMedia({ [PHONE]: true });
    try {
      mockList([booking()]);
      renderPage();

      const link = await screen.findByRole('link', { name: 'Cordless drill' });
      expect(link.matches(SELECTOR)).toBe(true);
    } finally {
      media.restore();
    }
  });

  test('the cancel control of a card is a button, not a link: the rule does not reach it', async () => {
    const media = mockMatchMedia({ [PHONE]: true });
    try {
      mockList([booking()]);
      renderPage();

      const cancel = await screen.findByRole('button', { name: 'Cancel this booking request' });
      expect(cancel.matches('a')).toBe(false);
    } finally {
      media.restore();
    }
  });
});

describe('MyBookingsPage — a request for several', () => {
  test('names the thing with how many, in the table', async () => {
    mockList([booking({ quantity: 4 }), booking({ code: 'BKG002', thing_headline: 'Tent' })]);
    renderPage();

    expect(await screen.findByText('4 × Cordless drill')).toBeInTheDocument();
    // One is the name as it was.
    expect(screen.getByText('Tent')).toBeInTheDocument();
    expect(screen.getAllByText(/×/)).toHaveLength(1);
  });

  test('and on a phone’s card', async () => {
    mockMatchMedia(PHONE);
    mockList([booking({ quantity: 3 })]);
    renderPage();

    expect(await screen.findByText('3 × Cordless drill')).toBeInTheDocument();
  });
});
