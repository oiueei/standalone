import { render, screen } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch } from '../services/api';
import ThingPage from '../pages/ThingPage';

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });

const THING = {
  code: 'THG001',
  headline: 'A cordless drill',
  description: '',
  type: 'LEND_THING',
  status: 'ACTIVE',
  owner: 'OWN001',
  owner_name: 'Lili',
  created: '2026-07-01T10:00:00Z',
  thumbnail_url: '',
  gallery_urls: [],
  tags: [],
  collection_code: 'COL001',
};

const journey = (autoClosed) => ({
  total_transfers: 1,
  unique_homes: 2,
  current_holder: null,
  current_holder_name: null,
  original_owner: 'OWN001',
  original_owner_name: 'Lili',
  transfers: [
    {
      code: 'TRF001',
      from_user: 'OWN001',
      to_user: 'BOR001',
      from_user_name: 'Lili',
      to_user_name: 'Lele',
      lent_date: '2026-07-20',
      returned_date: '2026-07-27',
      auto_closed: autoClosed,
    },
  ],
});

const setApi = (autoClosed) => {
  apiFetch.mockImplementation((url) => {
    if (url.includes('/transfers/')) return ok(journey(autoClosed));
    if (url.includes('/faq/')) return ok({ results: [] });
    if (url.includes('/calendar/')) return ok([]);
    if (url.includes('/things/')) return ok(THING);
    return ok({});
  });
};

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'SOMEBODY');
  vi.clearAllMocks();
});

const renderThing = () =>
  render(
    <MemoryRouter initialEntries={['/things/THG001']}>
      <Routes>
        <Route path="/things/:thingCode" element={<ThingPage />} />
      </Routes>
    </MemoryRouter>
  );

/**
 * The journey must not narrate a handover nobody witnessed.
 *
 * `close_transfers` stamps a return date once the booking's end_date passes —
 * whether or not the thing came back. Printing that as "Returned on {date}"
 * made the product's most human surface ("this item has travelled to 4 homes")
 * tell a story it has no evidence for.
 */
describe('Journey timeline', () => {
  test('an inferred close reads as a due date, not a return', async () => {
    setApi(true);
    renderThing();

    expect(await screen.findByText(/Due back on/)).toBeInTheDocument();
    expect(screen.queryByText(/Returned on/)).not.toBeInTheDocument();
  });

  test('a genuine handover still reads as a return', async () => {
    setApi(false);
    renderThing();

    expect(await screen.findByText(/Returned on/)).toBeInTheDocument();
    expect(screen.queryByText(/Due back on/)).not.toBeInTheDocument();
  });
});

/**
 * An empty name in the journey means two different things.
 *
 * For a signed-in reader it is a deleted account — the hop stays, the name goes
 * (right to erasure) — and "Former member" is the truth. For a signed-out one
 * the API withheld *every* name, because a thing in a PUBLIC collection is
 * readable with no account and a group's membership is not for the open web.
 * Reusing "Former member" there would tell a stranger that everyone who has
 * held this thing has left, which is a claim about real people they have no way
 * to check.
 */
describe('Journey names, signed out', () => {
  const anonymousJourney = {
    ...journey(false),
    original_owner_name: null,
    transfers: [{ ...journey(false).transfers[0], from_user_name: '', to_user_name: '' }],
  };

  const setAnonymousApi = () => {
    apiFetch.mockImplementation((url) => {
      if (url.includes('/transfers/')) return ok(anonymousJourney);
      if (url.includes('/faq/')) return ok({ results: [] });
      if (url.includes('/calendar/')) return ok([]);
      if (url.includes('/things/')) return ok(THING);
      return ok({});
    });
  };

  test('withheld names read as a neutral member, never as former ones', async () => {
    localStorage.clear(); // no userCode: an anonymous reader of a public collection
    setAnonymousApi();
    renderThing();

    // The journey is still told — it is only the people who are anonymous.
    const hop = await screen.findByText(/A member/);
    expect(screen.queryByText(/Former member/)).not.toBeInTheDocument();
    // Scoped to the hop: the *thing owner's* name is still shown elsewhere on
    // the page, and deliberately so — they chose to publish. It is the members
    // the thing passed through who did not.
    expect(hop.textContent).not.toMatch(/Lili|Lele/);
  });

  test('a signed-in reader still gets "Former member" for a deleted account', async () => {
    setAnonymousApi(); // same empty names, but this reader has an account
    localStorage.setItem('userCode', 'SOMEBODY');
    renderThing();

    expect(await screen.findByText(/Former member/)).toBeInTheDocument();
  });
});

/**
 * With several identical units several people may hold one at once, so the server
 * names no current holder and the page has no "Currently with" line; with one unit
 * it is there as ever.
 */
describe('Journey — who has it now', () => {
  const withHolder = (name) => {
    apiFetch.mockImplementation((url) => {
      if (url.includes('/transfers/')) {
        return ok({
          ...journey(false),
          current_holder: name ? 'BOR001' : null,
          current_holder_name: name,
        });
      }
      if (url.includes('/faq/')) return ok({ results: [] });
      if (url.includes('/calendar/')) return ok([]);
      if (url.includes('/things/')) return ok(THING);
      return ok({});
    });
  };

  test('names the current holder when the server does', async () => {
    withHolder('Lele');
    renderThing();

    expect(await screen.findByText('Currently with Lele')).toBeInTheDocument();
  });

  test('has no such line when the server sends none', async () => {
    withHolder(null);
    renderThing();

    await screen.findByText(/Returned on/);
    expect(screen.queryByText(/Currently with/)).not.toBeInTheDocument();
  });
});

/**
 * The owner's list of a thing's bookings says how many of it a request holds.
 */
describe('The thing page — a request for several in the owner’s list', () => {
  test('names the thing with how many, before who and when', async () => {
    localStorage.setItem('userCode', 'OWN001');
    apiFetch.mockImplementation((url) => {
      if (url.includes('/transfers/')) return ok({ ...journey(false), total_transfers: 0 });
      if (url.includes('/faq/')) return ok({ results: [] });
      if (url.includes('/calendar/')) {
        return ok([
          {
            code: 'BKG001',
            status: 'ACCEPTED',
            requester_name: 'Lele',
            quantity: 4,
            created: '2026-07-20T10:00:00Z',
            start_date: '2099-10-05',
            end_date: '2099-10-06',
          },
        ]);
      }
      if (url.includes('/things/')) return ok({ ...THING, can_manage: true, units: 6 });
      return ok({});
    });
    renderThing();

    expect(await screen.findByText(/4 × A cordless drill\. Lele\./)).toBeInTheDocument();
  });
});
