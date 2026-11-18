import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { MemoryRouter } from 'react-router';
import { describe, test, expect, vi, beforeEach, afterEach } from 'vitest';

// `codedErrorMessage` is the real one: the 429 of "remind them to return it" is
// worded by `requestErrors.<code>`, and a copy of it here would test the copy.
vi.mock('../services/api', async (importOriginal) => {
  const { codedErrorMessage } = await importOriginal();
  return {
    apiFetch: vi.fn(),
    getCsrfToken: () => 'tok',
    extractApiError: () => null,
    codedErrorMessage,
  };
});

import { apiFetch } from '../services/api';
import OwnerBookingsPage from './OwnerBookingsPage';
import { axe, toHaveNoViolations } from 'jest-axe';
import { mockMatchMedia, PHONE } from '../test/matchMedia';
import en from '../i18n/locales/en.json';
import { settle } from '../test/settle';

expect.extend(toHaveNoViolations);

// The owner's mirror of /my-bookings, and the page that closed a real asymmetry:
// a requester has always had a list, while an owner had only the email, an inbox
// banner, or opening each collection in turn. `transferConfirm.test.jsx` covers
// the one path that needs a dialogue (accepting a gift hands it over for good);
// this file covers the rest of the page — deciding, the empty states, a failed
// load, and the pager — the same ground MyBookingsPage.test.jsx holds for the
// other side of the same booking.

// The JSON shape `/api/v1/owner-bookings/` returns (the subset the page reads).
const booking = (over = {}) => ({
  code: 'BKG001',
  status: 'PENDING',
  thing_code: 'THG001',
  thing_headline: 'Cordless drill',
  thing_type: 'LEND_THING',
  thing_is_endless: false,
  requester_name: 'Lele',
  // Well before the 90-day window of "On loan now": a confirmed row with these dates is
  // a settled one. A test about a loan out right now says its own dates.
  start_date: '2025-09-01',
  end_date: '2025-09-08',
  created: '2026-08-01T10:00:00Z',
  ...over,
});

/** GETs return `pages` in order; POSTs answer with `postOk` (a refusal says `postStatus` and `postBody`). */
function mockApi(pages, { postOk = true, postStatus = 400, postBody = {} } = {}) {
  let page = 0;
  apiFetch.mockImplementation((url, opts) => {
    if (opts?.method === 'POST') {
      return Promise.resolve({
        ok: postOk,
        status: postOk ? 200 : postStatus,
        json: async () => postBody,
      });
    }
    const body = pages[Math.min(page, pages.length - 1)];
    page += 1;
    return Promise.resolve({ ok: true, status: 200, json: async () => body });
  });
}

const renderPage = () =>
  render(
    <MemoryRouter>
      <OwnerBookingsPage />
    </MemoryRouter>
  );

const postUrls = () => apiFetch.mock.calls.filter(([, o]) => o?.method === 'POST').map(([u]) => u);

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'USR001');
  vi.clearAllMocks();
});
afterEach(() => vi.restoreAllMocks());

describe('OwnerBookingsPage in a network', () => {
  test('a request the reader may not decide offers rejecting it and no way to accept it', async () => {
    mockApi([{ results: [booking({ can_decide: false })], next: null }]);
    renderPage();

    await screen.findByText('Lele');

    expect(screen.getAllByRole('button', { name: /decline|reject/i }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /confirm|accept/i })).not.toBeInTheDocument();
  });

  test('a request the reader decides offers both answers', async () => {
    mockApi([{ results: [booking({ can_decide: true })], next: null }]);
    renderPage();

    await screen.findByText('Lele');

    expect(screen.getAllByRole('button', { name: /confirm|accept/i }).length).toBeGreaterThan(0);
    expect(screen.getAllByRole('button', { name: /decline|reject/i }).length).toBeGreaterThan(0);
  });
});

describe('OwnerBookingsPage listing', () => {
  test('names who is waiting and on what, and splits pending from settled', async () => {
    mockApi([
      {
        results: [
          booking(),
          booking({
            code: 'BKG002',
            status: 'ACCEPTED',
            thing_headline: 'Ladder',
            requester_name: 'Lili',
          }),
        ],
        next: null,
      },
    ]);
    renderPage();

    // The column an owner needs that the requester's page doesn't have: who asked.
    expect(await screen.findByText('Lele')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Cordless drill' })).toHaveAttribute(
      'href',
      '/things/THG001'
    );
    expect(screen.getByRole('heading', { name: 'Waiting on you' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Past requests' })).toBeInTheDocument();
  });

  test('the thing and its group are one column; who asked and when are two more, each with its own lines', async () => {
    // "Thing" is the link and the group it is in; "Who" is what the person said
    // (name, address, contact details, the project note); "When" is the request
    // date, the dates (or "No dates") and the reminder / return dates.
    mockApi([
      {
        results: [
          booking({
            thing_type: 'RESERVE_THING',
            collection_headline: 'Tool library',
            collection_code: 'COL001',
            project_note: 'Painting the hall',
            requester_email: 'lele@your-domain.test',
            return_reminded_at: '2026-08-02T10:00:00Z',
            returned_at: '2026-08-03T10:00:00Z',
          }),
        ],
        next: null,
      },
    ]);
    renderPage();

    await screen.findByText('Cordless drill');
    const headers = within(screen.getAllByRole('table')[0])
      .getAllByRole('columnheader')
      .map((th) => th.textContent);
    expect(headers).toEqual(['Thing', 'Who', 'When', 'Status', 'Actions']);

    const [thing, who, when] = within(
      screen.getByRole('link', { name: 'Cordless drill' }).closest('tr')
    ).getAllByRole('cell');
    expect(within(thing).getByRole('link', { name: 'Cordless drill' })).toBeInTheDocument();
    expect(thing).toHaveTextContent('Tool library');
    expect(thing).not.toHaveTextContent(/Asked by/);
    expect(thing).not.toHaveTextContent('Painting the hall');

    expect(who.querySelector('p').textContent).toBe('Lele');
    expect(who).not.toHaveTextContent('Asked by');
    expect(within(who).getByRole('link', { name: 'lele@your-domain.test' })).toBeInTheDocument();
    expect(who).toHaveTextContent('Painting the hall');
    expect(who).not.toHaveTextContent(/Requested/);
    expect(who).not.toHaveTextContent('01/09/2025');
    expect(who).not.toHaveTextContent(/Reminded on/);
    expect(who).not.toHaveTextContent(/Returned on/);

    expect(when).toHaveTextContent(/Requested/);
    expect(when).toHaveTextContent('01/09/2025');
    expect(when).toHaveTextContent(/Reminded on/);
    expect(when).toHaveTextContent(/Returned on/);
    expect(when).not.toHaveTextContent('Asked by');
    expect(when).not.toHaveTextContent('lele@your-domain.test');
    expect(when).not.toHaveTextContent('Painting the hall');
  });

  test('the lines of a cell touch: they carry the shared class and no margin of their own', async () => {
    mockApi([{ results: [booking({ collection_headline: 'Tool library' })], next: null }]);
    renderPage();

    await screen.findByText('Cordless drill');
    const cells = within(
      screen.getByRole('link', { name: 'Cordless drill' }).closest('tr')
    ).getAllByRole('cell');
    for (const cell of cells.slice(0, 3)) {
      expect(cell.querySelector('.table-cell-lines')).not.toBeNull();
      for (const line of cell.querySelectorAll('p')) {
        expect(line.getAttribute('style')).toBeNull();
      }
    }
  });

  test('the type and the state sit in a status cell that sizes each label to its word', async () => {
    // Same cell, same class as /my-bookings; the rule is pinned
    // in `tableCellStyles.test.js`. The type shows only in a table that mixes verbs,
    // so there are two of them.
    mockApi([
      {
        results: [
          booking({ status: 'ACCEPTED' }),
          booking({
            code: 'BKG002',
            status: 'REJECTED',
            thing_type: 'GIFT_THING',
            thing_headline: 'Tent',
            start_date: null,
            end_date: null,
          }),
        ],
        next: null,
      },
    ]);
    renderPage();

    await screen.findByText('Cordless drill');
    const cell = screen.getByText('Lend').closest('.table-status-cell');
    expect(cell).not.toBeNull();
    expect(within(cell).getByText('Confirmed')).toBeInTheDocument();
  });

  test('each request names its group, and the thing link carries that group', async () => {
    mockApi([
      {
        results: [booking({ collection_code: 'COL9', collection_headline: 'Ateneu tools' })],
        next: null,
      },
    ]);
    renderPage();

    expect(await screen.findByText('Ateneu tools')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Cordless drill' })).toHaveAttribute(
      'href',
      '/collections/COL9/things/THG001'
    );
  });

  test('both tables carry a name, so they can be told apart in a rotor', async () => {
    mockApi([
      {
        results: [booking(), booking({ code: 'BKG002', status: 'ACCEPTED' })],
        next: null,
      },
    ]);
    renderPage();

    expect(
      await screen.findByRole('table', { name: 'Requests waiting for your answer' })
    ).toBeInTheDocument();
    expect(
      screen.getByRole('table', { name: 'Requests you have already answered' })
    ).toBeInTheDocument();
  });

  test('the column holding the decisions has a name a screen reader can say', async () => {
    // It was an empty <th> (axe empty-table-header), above the confirm/decline
    // controls of every row.
    mockApi([{ results: [booking()], next: null }]);
    renderPage();

    await screen.findByRole('link', { name: 'Cordless drill' });
    expect(screen.getByRole('columnheader', { name: 'Actions' })).toBeInTheDocument();
    expect(screen.queryByRole('columnheader', { name: '' })).not.toBeInTheDocument();
  });

  test('with nothing pending, the section says so rather than vanishing', async () => {
    mockApi([{ results: [booking({ status: 'REJECTED' })], next: null }]);
    renderPage();

    expect(await screen.findByText('Nothing waiting on you right now.')).toBeInTheDocument();
    // "Past requests" still renders, so the settled row isn't orphaned.
    expect(screen.getByRole('heading', { name: 'Past requests' })).toBeInTheDocument();
  });

  test('an owner nobody has asked gets a way out, not a blank page', async () => {
    mockApi([{ results: [], next: null }]);
    renderPage();

    expect(
      await screen.findByText('Nobody has requested anything from you yet.')
    ).toBeInTheDocument();
    // The owner's own way forward, not the requester page's "Browse
    // collections": it goes to Home, where their collections are.
    expect(screen.getByRole('link', { name: 'See my collections' })).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Waiting on you' })).toBeNull();
  });

  test('that way out sits in a wide row, so on a phone it is the width of the screen', async () => {
    mockApi([{ results: [], next: null }]);
    renderPage();

    const link = await screen.findByRole('link', { name: 'See my collections' });
    expect(link.parentElement).toHaveClass('button-row-wide');
  });

  test('a failed load says so instead of spinning forever', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 500, json: async () => ({}) });
    renderPage();

    expect(await screen.findByText('Error loading requests.')).toBeInTheDocument();
    expect(screen.queryByRole('heading', { name: 'Waiting on you' })).toBeNull();
  });

  test('a dropped connection is reported, not swallowed into a spinner', async () => {
    apiFetch.mockRejectedValue(new Error('offline'));
    renderPage();

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
  });
});

describe('OwnerBookingsPage deciding', () => {
  // Rejecting is the half `transferConfirm.test.jsx` never touches, and it is
  // the one an owner reaches for most: it never transfers anything, so it must
  // commit on the first click with no dialogue in the way.
  test('rejecting posts once and moves the row out of the pending list', async () => {
    mockApi([{ results: [booking()], next: null }]);
    renderPage();
    await screen.findByRole('link', { name: 'Cordless drill' });

    fireEvent.click(screen.getByRole('button', { name: 'Decline this request' }));

    await waitFor(() => expect(postUrls()).toEqual(['/api/v1/bookings/BKG001/reject/']));
    expect(screen.queryByRole('dialog')).toBeNull();
    // The decision is reflected without a refetch, and the row leaves "Waiting
    // on you" — an answered request must stop looking like a question.
    expect(await screen.findByText('Rejected')).toBeInTheDocument();
    await waitFor(() =>
      expect(screen.getByText('Nothing waiting on you right now.')).toBeInTheDocument()
    );
  });

  test('accepting a loan commits straight away — it comes back', async () => {
    mockApi([{ results: [booking()], next: null }]);
    renderPage();
    await screen.findByRole('link', { name: 'Cordless drill' });

    fireEvent.click(screen.getByRole('button', { name: 'Confirm this request' }));

    await waitFor(() => expect(postUrls()).toEqual(['/api/v1/bookings/BKG001/accept/']));
    expect(await screen.findByText('Confirmed')).toBeInTheDocument();
  });

  test('a refused decision leaves the request pending and says so', async () => {
    mockApi([{ results: [booking()], next: null }], { postOk: false });
    renderPage();
    await screen.findByRole('link', { name: 'Cordless drill' });

    fireEvent.click(screen.getByRole('button', { name: 'Decline this request' }));

    expect(await screen.findByText(/Couldn't answer that request/i)).toBeInTheDocument();
    // The optimistic update must not run on a failure: the owner has to be able
    // to see the request is still unanswered and try again.
    expect(screen.getByText('Pending')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Decline this request' })).toBeInTheDocument();
  });

  test('a settled request offers no decision controls at all', async () => {
    mockApi([{ results: [booking({ status: 'ACCEPTED' })], next: null }]);
    renderPage();
    await screen.findByRole('link', { name: 'Cordless drill' });

    expect(screen.queryByRole('button', { name: 'Confirm this request' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Decline this request' })).toBeNull();
  });
});

/**
 * Cancelling a member's confirmed reservation tells them, frees the slot for
 * anybody else and cannot be undone — unlike declining a pending request above,
 * which stays one click. It used to go on a single press of a small button in a
 * table row; now that press asks first and says whose reservation it is.
 */
describe('OwnerBookingsPage cancelling a member’s reservation', () => {
  const reservation = booking({
    thing_type: 'RESERVE_THING',
    thing_headline: 'Laser cutter',
    status: 'ACCEPTED',
    requester_name: 'Lulu',
    start_date: '2099-01-10',
    end_date: '2099-01-11',
    start_time: '10:00:00',
    end_time: '11:30:00',
  });

  test('one press asks first, naming the reservation and whose it is', async () => {
    mockApi([{ results: [reservation], next: null }]);
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel reservation' }));

    const dialog = await screen.findByRole('dialog', { name: 'Cancel this reservation?' });
    expect(dialog).toHaveTextContent('Laser cutter — 10/01/2099, 10:00–11:30');
    expect(dialog).toHaveTextContent('Asked by Lulu');
    expect(postUrls()).toEqual([]);
  });

  test('the dialog still says "Asked by A member" for a requester with no name, though the cell has no line', async () => {
    mockApi([{ results: [{ ...reservation, requester_name: '' }], next: null }]);
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel reservation' }));

    const dialog = await screen.findByRole('dialog', { name: 'Cancel this reservation?' });
    expect(dialog).toHaveTextContent('Asked by A member');
  });

  test('confirming cancels it once and tells the curator the member was told', async () => {
    mockApi([{ results: [reservation], next: null }]);
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel reservation' }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Cancel reservation' }));

    await waitFor(() => expect(postUrls()).toEqual(['/api/v1/bookings/BKG001/cancel/']));
    expect(await screen.findByText(/the member has been told/)).toBeInTheDocument();
    expect(screen.getByText('Cancelled')).toBeInTheDocument();
    // Settled: nothing left to cancel on the row.
    expect(screen.queryByRole('button', { name: 'Cancel reservation' })).toBeNull();
  });

  test('backing out cancels nothing', async () => {
    mockApi([{ results: [reservation], next: null }]);
    renderPage();
    fireEvent.click(await screen.findByRole('button', { name: 'Cancel reservation' }));
    const dialog = await screen.findByRole('dialog');

    fireEvent.click(within(dialog).getByRole('button', { name: 'Back' }));

    await waitFor(() => expect(screen.queryByRole('dialog')).toBeNull());
    expect(postUrls()).toEqual([]);
    expect(screen.getByText('Confirmed')).toBeInTheDocument();
  });
});

describe('OwnerBookingsPage pagination', () => {
  test('the pager sits in a wide row, so on a phone it is the width of the screen', async () => {
    mockApi([
      { results: [booking()], next: 'http://api.your-domain.test/api/v1/owner-bookings/?page=2' },
    ]);
    renderPage();

    const more = await screen.findByRole('button', { name: 'Load more' });
    expect(more.parentElement).toHaveClass('button-row-wide');
  });

  test('"Load more" appends the next page and keeps the request same-origin', async () => {
    mockApi([
      { results: [booking()], next: 'http://api.your-domain.test/api/v1/owner-bookings/?page=2' },
      { results: [booking({ code: 'BKG002', thing_headline: 'Ladder' })], next: null },
    ]);
    renderPage();
    await screen.findByRole('link', { name: 'Cordless drill' });

    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));

    expect(await screen.findByRole('link', { name: 'Ladder' })).toBeInTheDocument();
    // The first page stays: the pager appends, it doesn't replace.
    expect(screen.getByRole('link', { name: 'Cordless drill' })).toBeInTheDocument();
    // DRF hands back an absolute URL; sending it verbatim would be cross-origin
    // and would drop the auth cookies.
    const [secondUrl] = apiFetch.mock.calls[1];
    expect(secondUrl).toBe('/api/v1/owner-bookings/?page=2');
    // Exhausted, the pager stands down rather than fetching the same page again.
    await waitFor(() => expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull());
  });

  test('no "Load more" when the first page is the only page', async () => {
    mockApi([{ results: [booking()], next: null }]);
    renderPage();
    await screen.findByRole('link', { name: 'Cordless drill' });

    expect(screen.queryByRole('button', { name: 'Load more' })).toBeNull();
  });

  test('a refused second page says so and keeps the first one on screen', async () => {
    // Regression: `!res.ok` had no branch. The button re-enabled, nothing
    // appeared and nothing said why — which reads as a broken app, not a failed
    // request. `mockApi` always answers ok, so this one drives fetch directly.
    apiFetch
      .mockImplementationOnce(() =>
        Promise.resolve({
          ok: true,
          status: 200,
          json: async () => ({
            results: [booking()],
            next: 'http://api.your-domain.test/api/v1/owner-bookings/?page=2',
          }),
        })
      )
      .mockImplementationOnce(() =>
        Promise.resolve({ ok: false, status: 500, json: async () => ({}) })
      );
    renderPage();
    await screen.findByRole('link', { name: 'Cordless drill' });

    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));

    expect(await screen.findByText(/couldn't load more/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Cordless drill' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Load more' })).toBeEnabled();
  });
});

/**
 * On a phone each request is a card instead of a row (`ResponsiveTable`): in a table every column was ~100px wide, the status labels were cut
 * off and the ✓ ⊗ buttons sat off the screen. The decisions are buttons with their
 * words on them now, and they must do exactly what the icons do — so these tests
 * press them and read the same requests the table's tests read.
 */
describe('OwnerBookingsPage on a phone', () => {
  let media;
  beforeEach(() => {
    media = mockMatchMedia({ [PHONE]: true });
  });
  afterEach(() => media.restore());

  test('a request is a card holding the thing, who asked, when, both labels and both decisions', async () => {
    // The verb's label is there because this table mixes verbs.
    mockApi([
      {
        results: [
          booking({ requester_name: 'Lele' }),
          booking({
            code: 'BKG002',
            thing_type: 'GIFT_THING',
            thing_headline: 'Tent',
            start_date: null,
            end_date: null,
          }),
        ],
        next: null,
      },
    ]);
    renderPage();

    const list = await screen.findByRole('list', { name: 'Requests waiting for your answer' });
    expect(screen.queryByRole('table')).toBeNull();
    const [card] = within(list).getAllByRole('listitem');
    expect(within(card).getByRole('link', { name: 'Cordless drill' })).toHaveAttribute(
      'href',
      '/things/THG001'
    );
    expect(within(card).getByText('Lele')).toBeInTheDocument();
    expect(within(card).getByText('Requested 01/08/2026')).toBeInTheDocument();
    expect(within(card).getByText('01/09/2025 — 08/09/2025')).toBeInTheDocument();
    // Who comes before When, as the two columns do.
    expect(
      within(card)
        .getByText('Lele')
        .compareDocumentPosition(within(card).getByText('Requested 01/08/2026')) &
        Node.DOCUMENT_POSITION_FOLLOWING
    ).toBeTruthy();
    expect(within(card).getByText('Lend')).toBeInTheDocument();
    expect(within(card).getByText('Pending')).toBeInTheDocument();
    expect(within(card).getByRole('button', { name: 'Confirm this request' })).toBeVisible();
    expect(within(card).getByRole('button', { name: 'Decline this request' })).toBeVisible();
  });

  test('both decisions sit in a wide row, so each is the width of the screen', async () => {
    mockApi([{ results: [booking()], next: null }]);
    renderPage();

    const confirm = await screen.findByRole('button', { name: 'Confirm this request' });
    expect(confirm.parentElement).toHaveClass('button-row-wide');
    expect(screen.getByRole('button', { name: 'Decline this request' }).parentElement).toBe(
      confirm.parentElement
    );
  });

  test('confirming a loan sends the same request the tick sends, and the card settles', async () => {
    mockApi([{ results: [booking()], next: null }]);
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm this request' }));

    await waitFor(() => expect(postUrls()).toEqual(['/api/v1/bookings/BKG001/accept/']));
    expect(await screen.findByText('Confirmed')).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Confirm this request' })).toBeNull();
  });

  test('declining sends the same request the cross sends', async () => {
    mockApi([{ results: [booking()], next: null }]);
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Decline this request' }));

    await waitFor(() => expect(postUrls()).toEqual(['/api/v1/bookings/BKG001/reject/']));
    expect(await screen.findByText('Rejected')).toBeInTheDocument();
  });

  test('a settled request is still a card, with no decisions', async () => {
    mockApi([{ results: [booking({ status: 'ACCEPTED' })], next: null }]);
    renderPage();

    const list = await screen.findByRole('list', { name: 'Requests you have already answered' });
    expect(within(list).getByRole('link', { name: 'Cordless drill' })).toBeInTheDocument();
    expect(within(list).queryByRole('button')).toBeNull();
  });

  test('a coming reservation offers to cancel, and asks first, as the table does', async () => {
    mockApi([
      {
        results: [
          booking({
            thing_type: 'RESERVE_THING',
            thing_headline: 'Laser cutter',
            status: 'ACCEPTED',
            start_date: '2099-01-10',
            end_date: '2099-01-11',
            start_time: '10:00:00',
            end_time: '11:30:00',
          }),
        ],
        next: null,
      },
    ]);
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Cancel reservation' }));

    expect(await screen.findByRole('dialog')).toBeInTheDocument();
    expect(postUrls()).toEqual([]);
  });

  test('the cards have no axe violations', async () => {
    mockApi([
      { results: [booking(), booking({ code: 'BKG002', status: 'REJECTED' })], next: null },
    ]);
    const { container } = renderPage();
    await screen.findByRole('list', { name: 'Requests waiting for your answer' });

    await settle(apiFetch);
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

/**
 * The verb's label ("Rental", "Reservation"…) over the state in the status cell tells
 * rows apart only when a table mixes verbs: many collections hold
 * one verb, and the label repeated the same word in every row. It is decided per table
 * — "waiting for your answer" and "already answered" — from that table's own rows, and
 * again whenever more rows are loaded. The state label is not part of it.
 */
describe('OwnerBookingsPage — the verb’s label only where a table mixes verbs', () => {
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
  const WAITING = 'Requests waiting for your answer';
  const ANSWERED = 'Requests you have already answered';
  const inTable = (name) => within(screen.getByRole('table', { name }));
  const page = (...results) => mockApi([{ results, next: null }]);

  test('a table of one verb has no label on any row, and every row still has its state', async () => {
    page(rental('B1'), rental('B2'));
    renderPage();

    await screen.findByText('Drill B1');
    expect(screen.queryByText('Rental')).toBeNull();
    expect(screen.getAllByText('Pending')).toHaveLength(2);
  });

  test('a table that mixes verbs gives every row its verb', async () => {
    page(rental('B1'), gift('B2'));
    renderPage();

    await screen.findByText('Drill B1');
    const [, first, second] = within(screen.getByRole('table', { name: WAITING })).getAllByRole(
      'row'
    );
    expect(within(first).getByText('Rental')).toBeInTheDocument();
    expect(within(second).getByText('Gift')).toBeInTheDocument();
  });

  test('the two tables decide apart: one verb waiting, a mix already answered', async () => {
    page(rental('B1'), rental('B2'), rental('B3', 'ACCEPTED'), gift('B4', 'REJECTED'));
    renderPage();

    await screen.findByText('Drill B1');
    expect(inTable(WAITING).queryByText('Rental')).toBeNull();
    expect(inTable(ANSWERED).getByText('Rental')).toBeInTheDocument();
    expect(inTable(ANSWERED).getByText('Gift')).toBeInTheDocument();
  });

  test('and the other way round: a mix waiting, one verb already answered', async () => {
    page(rental('B1'), gift('B2'), rental('B3', 'ACCEPTED'), rental('B4', 'REJECTED'));
    renderPage();

    await screen.findByText('Drill B1');
    expect(inTable(WAITING).getByText('Rental')).toBeInTheDocument();
    expect(inTable(WAITING).getByText('Gift')).toBeInTheDocument();
    expect(inTable(ANSWERED).queryByText('Rental')).toBeNull();
  });

  test('loading more rows of another verb puts the label back on the whole table', async () => {
    mockApi([
      {
        results: [rental('B1'), rental('B2')],
        next: 'http://testserver/api/v1/owner-bookings/?page=2',
      },
      { results: [gift('B3')], next: null },
    ]);
    renderPage();
    await screen.findByText('Drill B1');
    expect(screen.queryByText('Rental')).toBeNull();

    fireEvent.click(screen.getByRole('button', { name: 'Load more' }));

    await screen.findByText('Tent B3');
    expect(screen.getAllByText('Rental')).toHaveLength(2);
    expect(screen.getByText('Gift')).toBeInTheDocument();
  });

  describe('on a phone, where each request is a card', () => {
    let media;
    beforeEach(() => {
      media = mockMatchMedia({ [PHONE]: true });
    });
    afterEach(() => media.restore());

    test('the cards of a table of one verb have no label; those of a mix have it', async () => {
      page(rental('B1'), rental('B2'), rental('B3', 'ACCEPTED'), gift('B4', 'REJECTED'));
      renderPage();

      const waiting = await screen.findByRole('list', { name: WAITING });
      const answered = screen.getByRole('list', { name: ANSWERED });
      expect(within(waiting).queryByText('Rental')).toBeNull();
      expect(within(waiting).getAllByText('Pending')).toHaveLength(2);
      expect(within(answered).getByText('Rental')).toBeInTheDocument();
      expect(within(answered).getByText('Gift')).toBeInTheDocument();
    });
  });
});

// The thing's name is a bold link: one rule in App.css for the
// text links inside the component's own class, `.responsive-table` — see
// `test/tableLinkWeight.test.jsx`. These pin that this page's links are inside it, in
// the table and in the cards.
describe('OwnerBookingsPage — the bold links of the table', () => {
  const SELECTOR = ".responsive-table a:not([class*='hds-button'])";

  test('the thing’s link is inside the component’s class, in the table', async () => {
    mockApi([
      {
        results: [
          booking(),
          booking({ code: 'BKG002', status: 'ACCEPTED', thing_headline: 'Tent' }),
        ],
        next: null,
      },
    ]);
    renderPage();

    await screen.findByText('Cordless drill');
    for (const name of ['Cordless drill', 'Tent']) {
      expect(screen.getByRole('link', { name }).matches(SELECTOR)).toBe(true);
    }
  });

  test('and in the cards of a phone, where the decisions are buttons the rule does not reach', async () => {
    const media = mockMatchMedia({ [PHONE]: true });
    try {
      mockApi([{ results: [booking()], next: null }]);
      renderPage();

      const link = await screen.findByRole('link', { name: 'Cordless drill' });
      expect(link.matches(SELECTOR)).toBe(true);
      expect(screen.getByRole('button', { name: 'Confirm this request' }).matches('a')).toBe(false);
    } finally {
      media.restore();
    }
  });
});

// The request email already carries the requester's address to
// every manager of the thing and the API sends it in `requester_email`; the page
// is the other place a manager looks for it, so it sits under the name as a link
// they can write from. Table and phone card are painted from the same cell, so one
// test each says it.
describe('OwnerBookingsPage — the requester’s address under the name', () => {
  const asked = (over = {}) => booking({ requester_email: 'lele@your-domain.test', ...over });

  test('in the table it is a mailto link right under the name', async () => {
    mockApi([{ results: [asked()], next: null }]);
    renderPage();

    const link = await screen.findByRole('link', { name: 'lele@your-domain.test' });
    expect(link).toHaveAttribute('href', 'mailto:lele@your-domain.test');
    expect(
      within(screen.getAllByRole('table')[0]).getByRole('link', { name: 'lele@your-domain.test' })
    ).toBe(link);
    // Its own line, directly under the name's.
    expect(link.closest('p').previousElementSibling.textContent).toBe('Lele');
    // Nothing after it in the Who cell: the request date is in When.
    expect(link.closest('p').nextElementSibling).toBeNull();
  });

  test('on a phone it is in the card, the same link', async () => {
    const media = mockMatchMedia({ [PHONE]: true });
    try {
      mockApi([{ results: [asked()], next: null }]);
      renderPage();

      const list = await screen.findByRole('list', { name: 'Requests waiting for your answer' });
      const [card] = within(list).getAllByRole('listitem');
      const link = within(card).getByRole('link', { name: 'lele@your-domain.test' });
      expect(link).toHaveAttribute('href', 'mailto:lele@your-domain.test');
      expect(link.closest('p').previousElementSibling.textContent).toBe('Lele');
      expect(screen.queryByRole('table')).toBeNull();
    } finally {
      media.restore();
    }
  });

  test('each row has its own requester’s address, settled requests included', async () => {
    mockApi([
      {
        results: [
          asked(),
          asked({
            code: 'BKG002',
            status: 'ACCEPTED',
            requester_name: 'Lili',
            requester_email: 'lili@your-domain.test',
          }),
        ],
        next: null,
      },
    ]);
    renderPage();

    expect(await screen.findByRole('link', { name: 'lele@your-domain.test' })).toHaveAttribute(
      'href',
      'mailto:lele@your-domain.test'
    );
    expect(screen.getByRole('link', { name: 'lili@your-domain.test' })).toHaveAttribute(
      'href',
      'mailto:lili@your-domain.test'
    );
  });

  test('a requester with no name has no name line: the cell opens with the address, and no "A member"', async () => {
    mockApi([{ results: [asked({ requester_name: '' })], next: null }]);
    renderPage();

    const link = await screen.findByRole('link', { name: 'lele@your-domain.test' });
    const who = link.closest('.table-cell-lines');
    expect(who.firstElementChild).toBe(link.closest('p'));
    expect(who).not.toHaveTextContent('A member');
    expect(who).not.toHaveTextContent('Asked by');
    expect([...who.querySelectorAll('p')].some((p) => p.textContent.trim() === '')).toBe(false);
  });

  test.each([
    ['empty', ''],
    ['absent', undefined],
    ['null', null],
  ])(
    'with the address %s the line is not painted, and the rest of the cell is',
    async (_, value) => {
      mockApi([{ results: [booking({ requester_email: value })], next: null }]);
      renderPage();

      expect(await screen.findByText('Lele')).toBeInTheDocument();
      expect(document.querySelector('a[href^="mailto:"]')).toBeNull();
      expect(screen.getByText('Requested 01/08/2026')).toBeInTheDocument();
    }
  );
});

/**
 * "Remind them to return it": a loan whose return date has passed and which has not
 * been lent again since carries one more action — which of the rows is the
 * server's call (`can_remind_return`), never the page's. It goes once a day per
 * booking, so after a press the action waits for tomorrow and the row says when.
 */
describe('OwnerBookingsPage — reminding a late return', () => {
  const ACTION = { name: 'Remind them to return it' };
  const ON_LOAN = 'On loan now';
  const ENDPOINT = '/api/v1/bookings/LATE01/remind-return/';
  const late = (over = {}) =>
    booking({
      code: 'LATE01',
      status: 'ACCEPTED',
      thing_headline: 'Drill',
      end_date: '2026-10-05',
      can_remind_return: true,
      return_reminded_at: null,
      ...over,
    });
  const page = (...results) => mockApi([{ results, next: null }], undefined);

  // The browser's today, fixed: the page compares the day a reminder went with it.
  // Only `Date` is faked, so testing-library's polling keeps its real timers.
  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-10-07T12:00:00'));
  });
  afterEach(() => vi.useRealTimers());

  const rowOf = (headline) =>
    within(screen.getByRole('table', { name: ON_LOAN }))
      .getAllByRole('row')
      .find((r) => within(r).queryByText(headline));

  test('the action is on the rows the server marks and on no other', async () => {
    page(
      late(),
      booking({
        code: 'DONE01',
        status: 'ACCEPTED',
        thing_headline: 'Ladder',
        can_remind_return: false,
      }),
      // A payload from before the field existed says nothing: no action.
      booking({ code: 'OLD001', status: 'ACCEPTED', thing_headline: 'Tent' })
    );
    renderPage();

    await screen.findByText('Drill');
    expect(screen.getAllByRole('button', ACTION)).toHaveLength(1);
    expect(within(rowOf('Drill')).getByRole('button', ACTION)).toBeInTheDocument();
    // The two without the flag are settled rows, in the answered table.
    const answered = within(
      screen.getByRole('table', { name: 'Requests you have already answered' })
    );
    expect(answered.getByText('Ladder')).toBeInTheDocument();
    expect(answered.getByText('Tent')).toBeInTheDocument();
    expect(answered.queryByRole('button', ACTION)).toBeNull();
  });

  // The reminder goes out with the presser's address as Reply-To — the one place a
  // manager's address reaches a borrower — so the page says it before the press.
  const NOTICE = en.ownerBookings.remindReturnNotice;

  test('the page says the borrower will see your address, above the table, before any press', async () => {
    page(late());
    renderPage();

    await screen.findByText('Drill');
    const notice = screen.getByText(NOTICE);
    const table = screen.getByRole('table', { name: ON_LOAN });
    expect(notice.compareDocumentPosition(table) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(postUrls()).toEqual([]);
  });

  test('with nothing to remind, there is nothing to say about it', async () => {
    page(
      booking({
        code: 'DONE01',
        status: 'ACCEPTED',
        thing_headline: 'Ladder',
        can_remind_return: false,
      })
    );
    renderPage();

    await screen.findByText('Ladder');
    expect(screen.queryByText(NOTICE)).toBeNull();
  });

  test('pressing it posts once, says so in a live region that was already there, and waits for tomorrow', async () => {
    page(late());
    renderPage();
    await screen.findByText('Drill');
    const row = rowOf('Drill');
    // The region is in the page before the message: a live region announces
    // only what lands in one that already existed.
    const region = within(row).getByRole('status');
    expect(region).toBeEmptyDOMElement();

    fireEvent.click(within(row).getByRole('button', ACTION));

    await waitFor(() => expect(postUrls()).toEqual([ENDPOINT]));
    await waitFor(() => expect(region).toHaveTextContent('Reminder sent.'));
    expect(within(row).getByText('Reminded on 07/10/2026')).toBeInTheDocument();
    expect(within(row).getByRole('button', ACTION)).toBeDisabled();
  });

  test('what a press says, and the greying, belong to the row that was pressed', async () => {
    page(late(), late({ code: 'LATE02', thing_headline: 'Saw' }));
    renderPage();
    await screen.findByText('Drill');
    const [drill, saw] = [rowOf('Drill'), rowOf('Saw')];

    fireEvent.click(within(drill).getByRole('button', ACTION));

    await waitFor(() =>
      expect(within(drill).getByRole('status')).toHaveTextContent('Reminder sent.')
    );
    expect(within(saw).getByRole('status')).toBeEmptyDOMElement();
    expect(within(saw).getByRole('button', ACTION)).toBeEnabled();
    expect(within(saw).queryByText(/Reminded on/)).toBeNull();
  });

  test('a reminder that went today keeps the action off until tomorrow', async () => {
    page(late({ return_reminded_at: '2026-10-07T09:30:00' }));
    renderPage();

    await screen.findByText('Drill');
    const row = rowOf('Drill');
    expect(within(row).getByText('Reminded on 07/10/2026')).toBeInTheDocument();
    expect(within(row).getByRole('button', ACTION)).toBeDisabled();
  });

  test('one from yesterday is only a date: the action is back', async () => {
    page(late({ return_reminded_at: '2026-10-06T09:30:00' }));
    renderPage();

    await screen.findByText('Drill');
    const row = rowOf('Drill');
    expect(within(row).getByText('Reminded on 06/10/2026')).toBeInTheDocument();
    expect(within(row).getByRole('button', ACTION)).toBeEnabled();
  });

  test('a loan nobody has reminded about says nothing of it', async () => {
    page(late());
    renderPage();

    await screen.findByText('Drill');
    expect(screen.queryByText(/Reminded on/)).toBeNull();
    expect(screen.queryByText('Reminder sent.')).toBeNull();
  });

  test('the server saying it was already reminded today is worded by requestErrors, and nothing is marked', async () => {
    mockApi([{ results: [late()], next: null }], {
      postOk: false,
      postStatus: 429,
      postBody: { error: 'English from the server', code: 'already_reminded_today' },
    });
    renderPage();
    await screen.findByText('Drill');
    const row = rowOf('Drill');

    fireEvent.click(within(row).getByRole('button', ACTION));

    expect(await screen.findByText("You've already reminded them today.")).toBeInTheDocument();
    expect(screen.queryByText('English from the server')).toBeNull();
    expect(screen.queryByText('Reminder sent.')).toBeNull();
    expect(screen.queryByText(/Reminded on/)).toBeNull();
    expect(within(row).getByRole('button', ACTION)).toBeEnabled();
  });

  test('the server saying the loan is no longer overdue is worded by requestErrors', async () => {
    mockApi([{ results: [late()], next: null }], {
      postOk: false,
      postStatus: 400,
      postBody: { error: 'English from the server', code: 'not_awaiting_return' },
    });
    renderPage();
    await screen.findByText('Drill');
    const row = rowOf('Drill');

    fireEvent.click(within(row).getByRole('button', ACTION));

    expect(
      await screen.findByText("This isn't waiting to be returned any more.")
    ).toBeInTheDocument();
    expect(screen.queryByText('English from the server')).toBeNull();
    expect(screen.queryByText('Reminder sent.')).toBeNull();
  });

  test.each([
    ['a refusal with no code', 403, { error: 'Not authorized' }],
    ['the hourly limit, which has no code to read', 429, { detail: 'Too many requests.' }],
    ['a code this client does not know', 400, { error: 'x', code: 'something_new' }],
    ['a body that is not JSON', 502, null],
  ])('%s is the page’s own generic line', async (_name, postStatus, postBody) => {
    apiFetch.mockImplementation((url, opts) =>
      opts?.method === 'POST'
        ? Promise.resolve({
            ok: false,
            status: postStatus,
            json: postBody
              ? async () => postBody
              : async () => Promise.reject(new Error('no json')),
          })
        : Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ results: [late()], next: null }),
          })
    );
    renderPage();
    await screen.findByText('Drill');
    const row = rowOf('Drill');

    fireEvent.click(within(row).getByRole('button', ACTION));

    expect(await screen.findByText(/Couldn't answer that request/i)).toBeInTheDocument();
    expect(screen.queryByText('Reminder sent.')).toBeNull();
    expect(screen.queryByText(/Reminded on/)).toBeNull();
  });

  test('a dropped connection is said as such, and the action stays', async () => {
    apiFetch.mockImplementation((url, opts) =>
      opts?.method === 'POST'
        ? Promise.reject(new TypeError('Failed to fetch'))
        : Promise.resolve({
            ok: true,
            status: 200,
            json: async () => ({ results: [late()], next: null }),
          })
    );
    renderPage();
    await screen.findByText('Drill');
    const row = rowOf('Drill');

    fireEvent.click(within(row).getByRole('button', ACTION));

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
    expect(within(row).getByRole('button', ACTION)).toBeEnabled();
  });

  test('the table has no axe violations with the action on a row', async () => {
    page(
      late(),
      late({ code: 'LATE02', thing_headline: 'Saw', return_reminded_at: '2026-10-07T09:30:00' })
    );
    const { container } = renderPage();
    await screen.findByText('Drill');

    await settle(apiFetch);
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });

  describe('on a phone', () => {
    let media;
    beforeEach(() => {
      media = mockMatchMedia({ [PHONE]: true });
    });
    afterEach(() => media.restore());

    test('the card has the action as a button with its words, in a wide row', async () => {
      page(late(), booking({ code: 'DONE01', status: 'ACCEPTED', thing_headline: 'Ladder' }));
      renderPage();

      const list = await screen.findByRole('list', { name: ON_LOAN });
      const [drill] = within(list).getAllByRole('listitem');
      const button = within(drill).getByRole('button', ACTION);
      expect(button).toBeVisible();
      expect(button.parentElement).toHaveClass('button-row-wide');
      const answered = screen.getByRole('list', { name: 'Requests you have already answered' });
      expect(within(answered).queryByRole('button', ACTION)).toBeNull();
    });

    test('it sends the same request the table’s icon sends, and the card says so', async () => {
      page(late());
      renderPage();
      const card = (await screen.findAllByRole('listitem'))[0];
      const region = within(card).getByRole('status');

      fireEvent.click(within(card).getByRole('button', ACTION));

      await waitFor(() => expect(postUrls()).toEqual([ENDPOINT]));
      await waitFor(() => expect(region).toHaveTextContent('Reminder sent.'));
      expect(within(card).getByText('Reminded on 07/10/2026')).toBeInTheDocument();
      expect(within(card).getByRole('button', ACTION)).toBeDisabled();
    });

    test('a card whose reminder went today has the action off', async () => {
      page(late({ return_reminded_at: '2026-10-07T09:30:00' }));
      renderPage();

      const card = (await screen.findAllByRole('listitem'))[0];
      expect(within(card).getByText('Reminded on 07/10/2026')).toBeInTheDocument();
      expect(within(card).getByRole('button', ACTION)).toBeDisabled();
    });

    test('the cards have no axe violations with the action', async () => {
      page(late());
      const { container } = renderPage();
      await screen.findByRole('list', { name: ON_LOAN });

      await settle(apiFetch);
      expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
    });
  });
});

describe('OwnerBookingsPage — the contact phone under the address', () => {
  const asked = (over = {}) =>
    booking({
      requester_email: 'lele@your-domain.test',
      thing_type: 'RESERVE_THING',
      status: 'ACCEPTED',
      contact_phone: '+34 (600) 123-456',
      ...over,
    });

  test('the link dials only the digits and the plus, and shows the number as it was typed', async () => {
    mockApi([{ results: [asked()], next: null }]);
    renderPage();

    const link = await screen.findByRole('link', { name: '+34 (600) 123-456' });
    expect(link).toHaveAttribute('href', 'tel:+34600123456');
    // Its own line, right under the address.
    expect(link.closest('p').previousElementSibling).toHaveTextContent('lele@your-domain.test');
  });

  test('on a phone the card carries it too', async () => {
    const media = mockMatchMedia({ [PHONE]: true });
    try {
      mockApi([{ results: [asked({ status: 'PENDING' })], next: null }]);
      renderPage();

      const list = await screen.findByRole('list', { name: 'Requests waiting for your answer' });
      const [card] = within(list).getAllByRole('listitem');
      expect(within(card).getByRole('link', { name: '+34 (600) 123-456' })).toHaveAttribute(
        'href',
        'tel:+34600123456'
      );
    } finally {
      media.restore();
    }
  });

  test.each([
    ['empty', ''],
    ['absent', undefined],
    ['null', null],
  ])('with the number %s there is no tel link', async (_, value) => {
    mockApi([{ results: [asked({ contact_phone: value })], next: null }]);
    renderPage();

    expect(await screen.findByText('Lele')).toBeInTheDocument();
    expect(document.querySelector('a[href^="tel:"]')).toBeNull();
    expect(screen.getByRole('link', { name: 'lele@your-domain.test' })).toBeInTheDocument();
  });

  test('axe finds nothing wrong with a row that carries it', async () => {
    mockApi([{ results: [asked()], next: null }]);
    const { container } = renderPage();
    await screen.findByRole('link', { name: '+34 (600) 123-456' });

    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('OwnerBookingsPage — a request for several', () => {
  test('names the thing with how many', async () => {
    mockApi([
      {
        results: [
          booking({ quantity: 4 }),
          booking({ code: 'BKG002', thing_headline: 'Tent', thing_code: 'THG002' }),
        ],
        next: null,
      },
    ]);
    renderPage();

    expect(await screen.findAllByText('4 × Cordless drill')).not.toHaveLength(0);
    expect(screen.getAllByText('Tent')).not.toHaveLength(0);
    expect(screen.queryByText('4 × Tent')).toBeNull();
  });

  test('and on a phone’s card', async () => {
    mockMatchMedia(PHONE);
    mockApi([{ results: [booking({ quantity: 2 })], next: null }]);
    renderPage();

    expect(await screen.findByText('2 × Cordless drill')).toBeInTheDocument();
  });
});

// The loans that are out right now have a table of their own, first on the page, and
// there whoever manages them says one came back. The browser's today is fixed at the 7th
// of October 2026; the window is 90 days after a return date.
describe('OwnerBookingsPage — "On loan now"', () => {
  const ON_LOAN = 'On loan now';
  const ANSWERED = 'Requests you have already answered';
  const MARK = { name: 'Mark as returned' };
  const REMIND = { name: 'Remind them to return it' };

  beforeEach(() => {
    vi.useFakeTimers({ toFake: ['Date'] });
    vi.setSystemTime(new Date('2026-10-07T12:00:00'));
  });
  afterEach(() => vi.useRealTimers());

  const out = (over = {}) =>
    booking({
      code: 'OUT001',
      status: 'ACCEPTED',
      thing_headline: 'Drill',
      start_date: '2026-10-01',
      end_date: '2026-10-12',
      can_mark_returned: true,
      can_remind_return: false,
      returned_at: null,
      ...over,
    });
  const page = (...results) => mockApi([{ results, next: null }]);
  const withPost = (results, postBody, extra = {}) =>
    mockApi([{ results, next: null }], { postBody, ...extra });
  const onLoanTable = () => screen.getByRole('table', { name: ON_LOAN });
  const answeredTable = () => screen.getByRole('table', { name: ANSWERED });
  const headings = () => screen.getAllByRole('heading', { level: 2 }).map((h) => h.textContent);

  test('a confirmed loan or rental that has started and was not marked is out; every other row is not', async () => {
    page(
      out({ code: 'A', thing_headline: 'Drill' }),
      out({ code: 'B', thing_headline: 'Saw', thing_type: 'RENT_THING' }),
      out({ code: 'C', thing_headline: 'Starts today', start_date: '2026-10-07' }),
      out({
        code: 'D',
        thing_headline: 'Future',
        start_date: '2026-10-08',
        end_date: '2026-10-15',
      }),
      out({ code: 'E', thing_headline: 'Back', returned_at: '2026-10-05T10:00:00Z' }),
      out({ code: 'F', thing_headline: 'Space', thing_type: 'RESERVE_THING' }),
      out({ code: 'G', thing_headline: 'Present', thing_type: 'GIFT_THING' }),
      out({ code: 'H', thing_headline: 'Dropped', status: 'CANCELLED' }),
      out({ code: 'I', thing_headline: 'Asked', status: 'PENDING' })
    );
    renderPage();

    await screen.findByText('Drill');
    const inside = within(onLoanTable());
    for (const name of ['Drill', 'Saw', 'Starts today']) {
      expect(inside.getByText(name)).toBeInTheDocument();
    }
    for (const name of ['Future', 'Back', 'Space', 'Present', 'Dropped', 'Asked']) {
      expect(inside.queryByText(name)).toBeNull();
    }
    // And they are not in the other tables either: each row is in one place.
    const answered = within(answeredTable());
    for (const name of ['Drill', 'Saw', 'Starts today']) {
      expect(answered.queryByText(name)).toBeNull();
    }
    for (const name of ['Future', 'Back', 'Space', 'Present', 'Dropped']) {
      expect(answered.getByText(name)).toBeInTheDocument();
    }
  });

  test('90 days after the return date is the last day it stays; one more and it is a settled row', async () => {
    page(
      out({
        code: 'A',
        thing_headline: 'Last day',
        start_date: '2026-06-01',
        end_date: '2026-07-09',
      }),
      out({
        code: 'B',
        thing_headline: 'Forgotten',
        start_date: '2026-06-01',
        end_date: '2026-07-08',
      })
    );
    renderPage();

    await screen.findByText('Last day');
    expect(within(onLoanTable()).getByText('Last day')).toBeInTheDocument();
    expect(within(onLoanTable()).queryByText('Forgotten')).toBeNull();
    expect(within(answeredTable()).getByText('Forgotten')).toBeInTheDocument();
  });

  test('it is the first table of the page, and there is none when nothing is out', async () => {
    page(out(), booking({ code: 'ASK001', thing_headline: 'Ladder' }));
    renderPage();
    await screen.findByText('Drill');
    expect(headings().slice(0, 2)).toEqual([ON_LOAN, 'Waiting on you']);
  });

  test('with nothing out there is no such table and no empty heading', async () => {
    page(booking({ code: 'ASK001', thing_headline: 'Ladder' }));
    renderPage();

    await screen.findByText('Ladder');
    expect(screen.queryByRole('heading', { name: ON_LOAN })).toBeNull();
    expect(screen.queryByRole('table', { name: ON_LOAN })).toBeNull();
  });

  test('the row says it is overdue only when its return date has passed', async () => {
    page(
      out({ code: 'A', thing_headline: 'Late', end_date: '2026-10-05' }),
      out({ code: 'B', thing_headline: 'On time', end_date: '2026-10-07' })
    );
    renderPage();

    await screen.findByText('Late');
    const rows = within(onLoanTable()).getAllByRole('row');
    const row = (name) => rows.find((r) => within(r).queryByText(name));
    expect(within(row('Late')).getByText('Overdue')).toBeInTheDocument();
    expect(within(row('Late')).getByText('Confirmed')).toBeInTheDocument();
    expect(within(row('On time')).queryByText('Overdue')).toBeNull();
  });

  test('the actions are the ones the server allows, each on its own flag', async () => {
    page(
      out({ code: 'A', thing_headline: 'Both', can_remind_return: true, end_date: '2026-10-05' }),
      out({ code: 'B', thing_headline: 'Only mark' }),
      out({ code: 'C', thing_headline: 'Neither', can_mark_returned: false })
    );
    renderPage();

    await screen.findByText('Both');
    const rows = within(onLoanTable()).getAllByRole('row');
    const row = (name) => rows.find((r) => within(r).queryByText(name));
    expect(within(row('Both')).getByRole('button', MARK)).toBeInTheDocument();
    expect(within(row('Both')).getByRole('button', REMIND)).toBeInTheDocument();
    expect(within(row('Only mark')).getByRole('button', MARK)).toBeInTheDocument();
    expect(within(row('Only mark')).queryByRole('button', REMIND)).toBeNull();
    expect(within(row('Neither')).queryByRole('button', MARK)).toBeNull();
    expect(within(row('Neither')).queryByRole('button', REMIND)).toBeNull();
  });

  test('marking it posts once and moves the row to the answered table with the day it came back', async () => {
    withPost([out()], { returned_at: '2026-10-07T10:00:00Z', end_date: '2026-10-07' });
    renderPage();
    await screen.findByText('Drill');

    fireEvent.click(within(onLoanTable()).getByRole('button', MARK));

    await waitFor(() => expect(postUrls()).toEqual(['/api/v1/bookings/OUT001/returned/']));
    await waitFor(() => expect(screen.queryByRole('table', { name: ON_LOAN })).toBeNull());
    const row = within(answeredTable());
    expect(row.getByText('Drill')).toBeInTheDocument();
    expect(row.getByText('Returned on 07/10/2026')).toBeInTheDocument();
    // It was due on the 12th and came back on the 7th: the row shows the shorter loan.
    expect(row.getByText('01/10/2026 — 07/10/2026')).toBeInTheDocument();
    expect(row.queryByRole('button', MARK)).toBeNull();
    expect(row.queryByText('Overdue')).toBeNull();
  });

  test('the toast says it came back too, since the row has left the table the press was in', async () => {
    withPost([out()], { returned_at: '2026-10-07T10:00:00Z', end_date: '2026-10-07' });
    renderPage();
    await screen.findByText('Drill');

    fireEvent.click(within(onLoanTable()).getByRole('button', MARK));

    // The row's own line and the toast: two places, so a screen reader hears it.
    await waitFor(() => expect(screen.getAllByText('Returned on 07/10/2026')).toHaveLength(2));
  });

  test('a refusal is worded in the reader’s language and leaves the row where it was', async () => {
    withPost([out()], { error: 'x', code: 'not_on_loan' }, { postOk: false, postStatus: 400 });
    renderPage();
    await screen.findByText('Drill');

    fireEvent.click(within(onLoanTable()).getByRole('button', MARK));

    expect(await screen.findByText(en.requestErrors.not_on_loan)).toBeInTheDocument();
    expect(within(onLoanTable()).getByText('Drill')).toBeInTheDocument();
    expect(within(onLoanTable()).getByRole('button', MARK)).toBeEnabled();
  });

  test('a refusal with no code is the page’s own line', async () => {
    withPost([out()], {}, { postOk: false, postStatus: 500 });
    renderPage();
    await screen.findByText('Drill');

    fireEvent.click(within(onLoanTable()).getByRole('button', MARK));

    expect(await screen.findByText(en.ownerBookings.errorActing)).toBeInTheDocument();
  });

  test('a dropped connection is said as such and the row stays', async () => {
    mockApi([{ results: [out()], next: null }]);
    const answer = apiFetch.getMockImplementation();
    apiFetch.mockImplementation((url, opts) =>
      opts?.method === 'POST' ? Promise.reject(new TypeError('offline')) : answer(url, opts)
    );
    renderPage();
    await screen.findByText('Drill');

    fireEvent.click(within(onLoanTable()).getByRole('button', MARK));

    expect(await screen.findByText(en.common.connectionError)).toBeInTheDocument();
    expect(within(onLoanTable()).getByText('Drill')).toBeInTheDocument();
  });

  describe('what a reminder says now that it lends the loan again', () => {
    const late = () =>
      out({ end_date: '2026-10-05', can_remind_return: true, can_mark_returned: true });
    const press = async (body) => {
      withPost([late()], body);
      renderPage();
      await screen.findByText('Drill');
      const row = within(onLoanTable());
      fireEvent.click(row.getByRole('button', REMIND));
      await waitFor(() => expect(postUrls()).toEqual(['/api/v1/bookings/OUT001/remind-return/']));
      return row;
    };

    test('with the new date when it was extended', async () => {
      const row = await press({ status: 'ok', extended_to: '2026-10-14', cut_short: false });
      expect(
        await row.findByText("Reminder sent. It's now due back on 14/10/2026.")
      ).toBeInTheDocument();
      // The row shows the loan as it now is: no longer overdue.
      expect(row.getByText('01/10/2026 — 14/10/2026')).toBeInTheDocument();
      expect(row.queryByText('Overdue')).toBeNull();
    });

    test('and says it was cut short when someone else has it from then', async () => {
      const row = await press({ status: 'ok', extended_to: '2026-10-10', cut_short: true });
      expect(
        await row.findByText(
          'Reminder sent. It could only be extended to 10/10/2026: someone else has it from then.'
        )
      ).toBeInTheDocument();
    });

    test('and is the plain "Reminder sent." when nothing could be extended', async () => {
      const row = await press({ status: 'ok', extended_to: null, cut_short: true });
      expect(await row.findByText('Reminder sent.')).toBeInTheDocument();
      expect(row.getByText('01/10/2026 — 05/10/2026')).toBeInTheDocument();
      expect(row.getByText('Overdue')).toBeInTheDocument();
    });

    test('and an answer with no body at all is still a sent reminder', async () => {
      const row = await press(undefined);
      expect(await row.findByText('Reminder sent.')).toBeInTheDocument();
    });
  });

  describe('on a phone, where each loan is a card', () => {
    let media;
    beforeEach(() => {
      media = mockMatchMedia({ [PHONE]: true });
    });
    afterEach(() => media.restore());

    test('both actions are buttons with their words in one wide row, and marking posts the same request', async () => {
      withPost([out({ can_remind_return: true, end_date: '2026-10-05' })], {
        returned_at: '2026-10-07T10:00:00Z',
        end_date: '2026-10-05',
      });
      renderPage();
      const list = await screen.findByRole('list', { name: ON_LOAN });
      const [card] = within(list).getAllByRole('listitem');
      const mark = within(card).getByRole('button', MARK);
      expect(mark).toBeVisible();
      expect(mark.parentElement).toHaveClass('button-row-wide');
      expect(within(card).getByRole('button', REMIND).parentElement).toBe(mark.parentElement);

      fireEvent.click(mark);

      await waitFor(() => expect(postUrls()).toEqual(['/api/v1/bookings/OUT001/returned/']));
      await waitFor(() => expect(screen.queryByRole('list', { name: ON_LOAN })).toBeNull());
      expect(
        within(screen.getByRole('list', { name: ANSWERED })).getByText('Returned on 07/10/2026')
      ).toBeInTheDocument();
    });

    test('the cards have no axe violations', async () => {
      page(out({ can_remind_return: true, end_date: '2026-10-05' }));
      const { container } = renderPage();
      await screen.findByRole('list', { name: ON_LOAN });

      await settle(apiFetch);
      expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
    });
  });

  test('the table has no axe violations with both actions on a row', async () => {
    page(out({ can_remind_return: true, end_date: '2026-10-05' }));
    const { container } = renderPage();
    await screen.findByText('Drill');

    await settle(apiFetch);
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});

describe('OwnerBookingsPage — the contact details a library asked the borrower for', () => {
  const DETAILS = {
    full_name: 'Laura Pérez Gómez',
    address: 'C/ de la Fusteria 12, 3r 2a\n08003 Barcelona',
    phone: '+34 600 000 000',
    identity_document: '12345678Z',
  };
  const loan = (over = {}) =>
    booking({
      code: 'LC0001',
      status: 'PENDING',
      thing_headline: 'Ladder',
      requester_email: 'lele@your-domain.test',
      lending_contact: DETAILS,
      ...over,
    });
  const lines = (scope) => [
    scope.getByText('Laura Pérez Gómez'),
    scope.getByText(/^C\/ de la Fusteria 12, 3r 2a/),
    scope.getByText('+34 600 000 000'),
    scope.getByText('12345678Z'),
  ];

  test('the four lines sit under the address, the address with its own line breaks', async () => {
    mockApi([{ results: [loan()], next: null }]);
    renderPage();

    const [name, address, phone, document] = lines(within(await screen.findByRole('table')));
    expect(address).toHaveClass('table-cell-line--pre-line');
    expect(address).toHaveTextContent('08003 Barcelona');
    const email = screen.getByRole('link', { name: 'lele@your-domain.test' }).closest('p');
    expect(email.nextElementSibling).toBe(name);
    expect([name, address, phone, document].map((p) => p.tagName)).toEqual(['P', 'P', 'P', 'P']);
  });

  test('the four go bare, with no "Full name:", "Address:", "Phone:" or "Identity document:" in front', async () => {
    mockApi([{ results: [loan()], next: null }]);
    renderPage();

    const [name, address, phone, document] = lines(within(await screen.findByRole('table')));
    expect(name.textContent).toBe('Laura Pérez Gómez');
    expect(address.textContent).toBe('C/ de la Fusteria 12, 3r 2a\n08003 Barcelona');
    expect(phone.textContent).toBe('+34 600 000 000');
    expect(document.textContent).toBe('12345678Z');
    expect(screen.getByRole('table')).not.toHaveTextContent(
      /Full name|Address:|Phone:|Identity document/
    );
  });

  test('a request with none (or an older payload) shows no such lines', async () => {
    mockApi([
      {
        results: [
          loan({ lending_contact: null }),
          loan({ code: 'LC0002', lending_contact: undefined }),
        ],
        next: null,
      },
    ]);
    renderPage();

    await screen.findAllByText('Ladder');
    expect(screen.queryByText('12345678Z')).toBeNull();
    expect(screen.queryByText('Laura Pérez Gómez')).toBeNull();
  });

  test('on a phone the card carries them too', async () => {
    const media = mockMatchMedia({ [PHONE]: true });
    try {
      mockApi([{ results: [loan()], next: null }]);
      renderPage();
      const [card] = within(await screen.findByRole('list')).getAllByRole('listitem');
      lines(within(card));
    } finally {
      media.restore();
    }
  });

  test('the table has no axe violations with them', async () => {
    mockApi([{ results: [loan()], next: null }]);
    const { container } = renderPage();
    await screen.findByText('Laura Pérez Gómez');

    await settle(apiFetch);
    expect(await axe(container, { rules: { region: { enabled: false } } })).toHaveNoViolations();
  });
});
