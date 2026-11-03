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
  start_date: '2026-09-01',
  end_date: '2026-09-08',
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

    await screen.findByText('Asked by Lele');

    expect(screen.getAllByRole('button', { name: /decline|reject/i }).length).toBeGreaterThan(0);
    expect(screen.queryByRole('button', { name: /confirm|accept/i })).not.toBeInTheDocument();
  });

  test('a request the reader decides offers both answers', async () => {
    mockApi([{ results: [booking({ can_decide: true })], next: null }]);
    renderPage();

    await screen.findByText('Asked by Lele');

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
    expect(await screen.findByText('Asked by Lele')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Cordless drill' })).toHaveAttribute(
      'href',
      '/things/THG001'
    );
    expect(screen.getByRole('heading', { name: 'Waiting on you' })).toBeInTheDocument();
    expect(screen.getByRole('heading', { name: 'Past requests' })).toBeInTheDocument();
  });

  test('the thing and its group are one column; who asked, when and the note are the next', async () => {
    // The first column used to hold six lines. "Thing" is the link
    // and the group it is in; "Who and when" is who asked, the request date, the
    // dates (or "No dates") and, for a reservation, the project note.
    mockApi([
      {
        results: [
          booking({
            thing_type: 'RESERVE_THING',
            collection_headline: 'Tool library',
            collection_code: 'COL001',
            project_note: 'Painting the hall',
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
    expect(headers).toEqual(['Thing', 'Who and when', 'Status', 'Actions']);

    const [thing, whoWhen] = within(
      screen.getByRole('link', { name: 'Cordless drill' }).closest('tr')
    ).getAllByRole('cell');
    expect(within(thing).getByRole('link', { name: 'Cordless drill' })).toBeInTheDocument();
    expect(thing).toHaveTextContent('Tool library');
    expect(thing).not.toHaveTextContent(/Asked by/);
    expect(whoWhen).toHaveTextContent('Asked by Lele');
    expect(whoWhen).toHaveTextContent(/Requested/);
    expect(whoWhen).toHaveTextContent('01/09/2026');
    // The project note is in this cell too, not in the first.
    expect(whoWhen).toHaveTextContent('Painting the hall');
    expect(thing).not.toHaveTextContent('Painting the hall');
  });

  test('the lines of a cell touch: they carry the shared class and no margin of their own', async () => {
    mockApi([{ results: [booking({ collection_headline: 'Tool library' })], next: null }]);
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
    expect(within(card).getByText('Asked by Lele')).toBeInTheDocument();
    expect(within(card).getByText('Requested 01/08/2026')).toBeInTheDocument();
    expect(within(card).getByText('01/09/2026 — 08/09/2026')).toBeInTheDocument();
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
// is the other place a manager looks for it, so it sits under "Asked by …" as a link
// they can write from. Table and phone card are painted from the same cell, so one
// test each says it.
describe('OwnerBookingsPage — the requester’s address under the name', () => {
  const asked = (over = {}) => booking({ requester_email: 'lele@your-domain.test', ...over });

  test('in the table it is a mailto link right under "Asked by …"', async () => {
    mockApi([{ results: [asked()], next: null }]);
    renderPage();

    const link = await screen.findByRole('link', { name: 'lele@your-domain.test' });
    expect(link).toHaveAttribute('href', 'mailto:lele@your-domain.test');
    expect(
      within(screen.getAllByRole('table')[0]).getByRole('link', { name: 'lele@your-domain.test' })
    ).toBe(link);
    // Its own line, directly under the name's.
    expect(link.closest('p').previousElementSibling).toHaveTextContent('Asked by Lele');
    expect(link.closest('p').nextElementSibling).toHaveTextContent('Requested 01/08/2026');
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
      expect(link.closest('p').previousElementSibling).toHaveTextContent('Asked by Lele');
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

  test('a requester with no name is still "A member" and still has the address to write to', async () => {
    mockApi([{ results: [asked({ requester_name: '' })], next: null }]);
    renderPage();

    expect(await screen.findByText('Asked by A member')).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'lele@your-domain.test' })).toBeInTheDocument();
    // …and the address does not take the name's place.
    expect(screen.queryByText('Asked by lele@your-domain.test')).toBeNull();
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

      expect(await screen.findByText('Asked by Lele')).toBeInTheDocument();
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
  const ANSWERED = 'Requests you have already answered';
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
    within(screen.getByRole('table', { name: ANSWERED }))
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
    expect(within(rowOf('Ladder')).queryByRole('button', ACTION)).toBeNull();
    expect(within(rowOf('Tent')).queryByRole('button', ACTION)).toBeNull();
  });

  // The reminder goes out with the presser's address as Reply-To — the one place a
  // manager's address reaches a borrower — so the page says it before the press.
  const NOTICE = en.ownerBookings.remindReturnNotice;

  test('the page says the borrower will see your address, above the table, before any press', async () => {
    page(late());
    renderPage();

    await screen.findByText('Drill');
    const notice = screen.getByText(NOTICE);
    const table = screen.getByRole('table', { name: ANSWERED });
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

      const list = await screen.findByRole('list', { name: ANSWERED });
      const [drill, ladder] = within(list).getAllByRole('listitem');
      const button = within(drill).getByRole('button', ACTION);
      expect(button).toBeVisible();
      expect(button.parentElement).toHaveClass('button-row-wide');
      expect(within(ladder).queryByRole('button', ACTION)).toBeNull();
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
      await screen.findByRole('list', { name: ANSWERED });

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

    expect(await screen.findByText('Asked by Lele')).toBeInTheDocument();
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
