import { render, renderHook, act, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// ── jsdom shims ────────────────────────────────────────────────────────
// PageLayout / RouteFocusReset and friends call scrollTo; HDS reads clipboard.
window.scrollTo = vi.fn();

// ── Mock apiFetch (the components fetch the calendar, POST requests, etc.) ─
// The factory cannot reference module-scope vars (it is hoisted), so it ships a
// permissive default; each test refines behaviour through setApi() below.
vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  ),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch, extractApiError } from '../services/api';
import ThingLinkbox from '../components/ThingLinkbox';
import ThingPage from '../pages/ThingPage';
import useThingBooking from '../hooks/useThingBooking';
import declarePalette from './declarePalette';
import { settle } from './settle';

function mockResponse(data, ok = true, status = ok ? 200 : 400) {
  return { ok, status, json: () => Promise.resolve(data) };
}

// A calendar answer the test lets through when it chooses, so what the page does
// before the calendar arrives is checked with the answer provably still missing.
function heldCalendar() {
  let release;
  const calendarGate = new Promise((resolve) => {
    release = resolve;
  });
  return { calendarGate, release };
}

// Route apiFetch by URL. `thing` feeds the ThingPage detail fetch; `calendar`
// feeds the owner bookings fetch; `calendarGate` (see `heldCalendar`) holds its
// answer back until the test lets it through.
// `request`/`activate`/`booking` override a single route outright, for the
// failure branches that need a status code or a throw.
function setApi({
  thing = {},
  calendar = [],
  responses = [],
  requestOk = true,
  request = null,
  activate = null,
  booking = null,
  calendarGate = null,
} = {}) {
  apiFetch.mockImplementation((url) => {
    if (/\/things\/[^/]+\/calendar\//.test(url)) {
      const answer = mockResponse(calendar);
      return calendarGate ? calendarGate.then(() => answer) : Promise.resolve(answer);
    }
    if (/\/things\/[^/]+\/request\//.test(url)) {
      return request ? request() : Promise.resolve(mockResponse({}, requestOk));
    }
    if (/\/things\/[^/]+\/activate\//.test(url)) {
      return activate ? activate() : Promise.resolve(mockResponse({}));
    }
    if (/\/bookings\/[^/]+\/(accept|reject)\//.test(url)) {
      return booking ? booking() : Promise.resolve(mockResponse({}));
    }
    if (/\/things\/[^/]+\/faq\//.test(url)) return Promise.resolve(mockResponse({ results: [] }));
    if (/\/things\/[^/]+\/transfers\//.test(url))
      return Promise.resolve(mockResponse({ total_transfers: 0, transfers: [] }));
    if (/\/things\/[^/]+\/responses\//.test(url))
      return Promise.resolve(mockResponse({ results: responses }));
    if (/\/things\/[^/]+\/resolve\//.test(url)) return Promise.resolve(mockResponse({}));
    if (/\/things\/[^/]+\//.test(url)) return Promise.resolve(mockResponse(thing));
    return Promise.resolve(mockResponse({}));
  });
}

function makeThing(overrides = {}) {
  return {
    code: 'THG001',
    type: 'GIFT_THING',
    headline: 'Test Thing',
    status: 'ACTIVE',
    owner: 'OWNER1',
    owner_name: 'Owner One',
    thumbnail_url: '',
    gallery_urls: [],
    transfer_count: 0,
    ...overrides,
  };
}

// Render ThingLinkbox in a router whose catch-all surfaces any navigation.
function renderLinkbox(props) {
  return render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<ThingLinkbox onUpdateThing={() => {}} {...props} />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

// Render ThingPage at the standalone /things/:thingCode route.
function renderThingPage() {
  return render(
    <MemoryRouter initialEntries={['/things/THG001']}>
      <Routes>
        <Route path="/things/:thingCode" element={<ThingPage />} />
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'GUEST1');
  declarePalette({
    color_01: 'bus',
    color_02: 'suomenlinna-light',
    color_03: 'copper',
    color_04: 'black',
    color_05: 'white',
    color_06: 'white',
  });
  localStorage.setItem('koro', 'basic');
  vi.clearAllMocks();
  // clearAllMocks keeps implementations, so a test that gives the server a
  // reason to state would otherwise hand it to every test after it.
  extractApiError.mockResolvedValue('');
  setApi();
});

// ════════════════════════════════════════════════════════════════════════
// ThingLinkbox — guest (non-owner) reservation buttons
// ════════════════════════════════════════════════════════════════════════
describe('ThingLinkbox — guest reservation button', () => {
  // GIFT and SELL hold directly: the click POSTs to /request/ and no navigation
  // happens. The button label is the per-type action verb, not the literal "Hold".
  test.each([
    ['GIFT_THING', 'Claim'],
    ['SELL_THING', 'Buy'],
  ])('%s holds via direct POST to /request/', async (type, label) => {
    const thing = makeThing({ type, fee: type === 'SELL_THING' ? '5' : null });
    renderLinkbox({ thing, userCode: 'GUEST1' });

    fireEvent.click(screen.getByRole('button', { name: label }));

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/things/THG001/request/',
        expect.objectContaining({ method: 'POST' })
      );
    });
    expect(screen.queryByTestId('navigated')).toBeNull();
  });

  // Date-based (LEND/RENT) navigates to RequestThingPage instead of POSTing —
  // it needs a follow-up form (the dates).
  test.each([
    ['LEND_THING', 'Borrow'],
    ['RENT_THING', 'Rent'],
  ])('%s navigates to the request page', async (type, label) => {
    const thing = makeThing({ type, fee: type === 'RENT_THING' ? '5' : null });
    renderLinkbox({ thing, userCode: 'GUEST1' });

    fireEvent.click(screen.getByRole('button', { name: label }));

    await waitFor(() => expect(screen.getByTestId('navigated')).toBeInTheDocument());
    expect(apiFetch).not.toHaveBeenCalledWith('/api/v1/things/THG001/request/', expect.anything());
  });

  // An endless GIFT/SELL keeps circulating (bookingKeepsStatus) but has no
  // dates/items to pick, so its hold POSTs directly — it must NOT navigate to an
  // empty RequestThingPage. Regression guard: `is_endless` must stay out of
  // `needsPage` and behave identically on the card and the detail page.
  test('endless GIFT holds via direct POST (does not navigate)', async () => {
    const thing = makeThing({ type: 'GIFT_THING', is_endless: true });
    renderLinkbox({ thing, userCode: 'GUEST1' });

    fireEvent.click(screen.getByRole('button', { name: 'Claim' }));

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/things/THG001/request/',
        expect.objectContaining({ method: 'POST' })
      );
    });
    expect(screen.queryByTestId('navigated')).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════
// ThingLinkbox — status / pause gating
// ════════════════════════════════════════════════════════════════════════
describe('ThingLinkbox — status and pause gating', () => {
  // A TAKEN thing is disabled for everyone, but the label is audience-specific:
  // only the viewer holding the pending booking (my_pending_booking / local
  // `requested`) sees "Waiting for confirmation"; everyone else sees "Not
  // available", so the disabled button explains itself.
  test('TAKEN shows "Not available" to a non-requester and disables the button', () => {
    const thing = makeThing({ status: 'TAKEN' });
    renderLinkbox({ thing, userCode: 'GUEST1' });

    const btn = screen.getByRole('button', { name: 'Not available' });
    expect(btn).toBeDisabled();
  });

  test('TAKEN shows "Waiting for confirmation" to the requester (my_pending_booking)', () => {
    const thing = makeThing({ status: 'TAKEN', my_pending_booking: 'BK9' });
    renderLinkbox({ thing, userCode: 'GUEST1' });

    const btn = screen.getByRole('button', { name: 'Waiting for confirmation' });
    expect(btn).toBeDisabled();
  });

  test('isPaused disables the hold button and labels it "Paused"', () => {
    const thing = makeThing({ type: 'GIFT_THING' });
    renderLinkbox({ thing, userCode: 'GUEST1', isPaused: true });

    const btn = screen.getByRole('button', { name: 'Paused' });
    expect(btn).toBeDisabled();
  });
});

// ════════════════════════════════════════════════════════════════════════
// ThingLinkbox — owner button matrix
// ════════════════════════════════════════════════════════════════════════
describe('ThingLinkbox — owner button matrix', () => {
  // NOTE: the ACTIVE secondary button is labelled "Delete" (common.delete) and
  // navigates to DeleteThingPage. frontend/CLAUDE.md calls it "Hide", but the
  // code renders "Delete". Locked to the actual label.
  test('ACTIVE (no pending) shows Edit + Delete, no Reactivate/Confirm', () => {
    const thing = makeThing({ status: 'ACTIVE' });
    renderLinkbox({ thing, userCode: 'OWNER1' });

    expect(screen.getByRole('link', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reactivate' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Confirm request' })).toBeNull();
  });

  test('INACTIVE shows Reactivate + Edit + Delete', () => {
    const thing = makeThing({ status: 'INACTIVE' });
    renderLinkbox({ thing, userCode: 'OWNER1' });

    expect(screen.getByRole('button', { name: 'Reactivate' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });

  test('TAKEN shows Confirm request + Decline request + Edit', async () => {
    const thing = makeThing({ status: 'TAKEN' });
    renderLinkbox({ thing, userCode: 'OWNER1' });

    expect(await screen.findByRole('button', { name: 'Confirm request' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Decline request' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Edit' })).toBeInTheDocument();
  });

  // The pending booking arrives from the /calendar/ fetch (date-based type).
  test('ACTIVE date-based with a pending booking shows Confirm/Decline request', async () => {
    const thing = makeThing({ type: 'LEND_THING', status: 'ACTIVE' });
    setApi({ calendar: [{ code: 'BK1', status: 'PENDING', end_date: '2099-12-31' }] });
    renderLinkbox({ thing, userCode: 'OWNER1' });

    expect(await screen.findByRole('button', { name: 'Confirm request' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Decline request' })).toBeInTheDocument();
    // The Delete button is suppressed while a pending hold exists.
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
  });

  test('a co-curator (can_manage, not owner) gets the owner matrix, not the hold button', () => {
    // A PROPRIETARY collection's curator runs its catalogue — the backend says
    // so via `thing.can_manage`, and the card keys off that, not `owner`.
    const thing = makeThing({ status: 'ACTIVE', owner: 'OWNER1', can_manage: true });
    renderLinkbox({ thing, userCode: 'CURATOR2' });

    expect(screen.getByRole('link', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Claim' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Hold' })).toBeNull();
  });

  test('a plain member (can_manage false) still sees the hold button, not the matrix', () => {
    const thing = makeThing({ status: 'ACTIVE', owner: 'OWNER1', can_manage: false });
    renderLinkbox({ thing, userCode: 'MEMBER3' });

    expect(screen.queryByRole('link', { name: 'Edit' })).toBeNull();
    expect(screen.getByRole('button', { name: /Claim|Hold/ })).toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════
// ThingPage — duplicated booking/owner logic (must match ThingLinkbox)
// ════════════════════════════════════════════════════════════════════════
describe('ThingPage — guest reservation', () => {
  test('GIFT holds via direct POST to /request/', async () => {
    localStorage.setItem('userCode', 'GUEST1');
    setApi({ thing: makeThing({ type: 'GIFT_THING', owner: 'OWNER1' }) });
    renderThingPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Claim' }));

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/things/THG001/request/',
        expect.objectContaining({ method: 'POST' })
      );
    });
  });
});

describe('ThingPage — owner button matrix', () => {
  test('ACTIVE shows Edit + Delete, no Reactivate', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    setApi({ thing: makeThing({ status: 'ACTIVE', owner: 'OWNER1' }) });
    renderThingPage();

    expect(await screen.findByRole('link', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reactivate' })).toBeNull();
  });

  test('INACTIVE shows Reactivate + Edit + Delete', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    setApi({ thing: makeThing({ status: 'INACTIVE', owner: 'OWNER1' }) });
    renderThingPage();

    expect(await screen.findByRole('button', { name: 'Reactivate' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });

  test('TAKEN shows Confirm request + Decline request + Edit', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    setApi({ thing: makeThing({ status: 'TAKEN', owner: 'OWNER1' }) });
    renderThingPage();

    expect(await screen.findByRole('button', { name: 'Confirm request' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Decline request' })).toBeInTheDocument();
    expect(screen.getByRole('link', { name: 'Edit' })).toBeInTheDocument();
  });

  test('TAKEN decides the booking the thing names, before the calendar has answered', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    const { calendarGate, release } = heldCalendar();
    setApi({
      thing: makeThing({ status: 'TAKEN', owner: 'OWNER1', pending_booking: 'BK1' }),
      calendarGate,
    });
    renderThingPage();

    const decline = await screen.findByRole('button', { name: 'Decline request' });
    expect(decline).toBeEnabled();
    fireEvent.click(decline);

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/bookings/BK1/reject/', { method: 'POST' })
    );
    release();
    await settle(apiFetch);
  });
});

// ════════════════════════════════════════════════════════════════════════
// ThingPage — the decision about a request sits in the hero
// Whoever runs the thing sees "Confirm request" (primary) and "Decline request"
// (secondary) as the first thing under the way back, in a wide row; Edit and
// Delete stay in the content. A member's "Reserve" stays in the content too: they
// are meant to read the whole page before they ask.
// ════════════════════════════════════════════════════════════════════════
describe('ThingPage — the decision about a request sits in the hero', () => {
  const PENDING = [
    { code: 'BK1', status: 'PENDING', requester_name: 'Lele', end_date: '2099-12-31' },
  ];
  const heroRow = (container) => container.querySelector('.form-hero .hero-actions');
  const content = (container) => container.querySelector('.page-container');
  const labels = (el) => [...el.children].map((c) => c.textContent.trim());
  const PRIMARY = 'var(--color-bus)';
  const SECONDARY = 'var(--color-white)';

  test('a loan with a request waiting: Confirm (primary) and Decline (secondary), in a wide row in the hero', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    setApi({
      thing: makeThing({ type: 'LEND_THING', status: 'ACTIVE', owner: 'OWNER1' }),
      calendar: PENDING,
    });
    const { container } = renderThingPage();

    const confirm = await screen.findByRole('button', { name: 'Confirm request' });
    const decline = screen.getByRole('button', { name: 'Decline request' });

    const row = heroRow(container);
    expect(row).toHaveClass('button-row-wide');
    expect(labels(row)).toEqual(['Confirm request', 'Decline request']);
    expect(confirm.style.getPropertyValue('--background-color')).toBe(PRIMARY);
    expect(decline.style.getPropertyValue('--background-color')).toBe(SECONDARY);
    // Nothing is painted twice, and what is not a decision stays where it was.
    expect(screen.getAllByRole('button', { name: 'Confirm request' })).toHaveLength(1);
    expect(screen.getAllByRole('button', { name: 'Decline request' })).toHaveLength(1);
    expect(content(container)).not.toContainElement(confirm);
    expect(content(container)).toContainElement(screen.getByRole('link', { name: 'Edit' }));
    // Delete is not offered while a request is waiting — in the hero or anywhere.
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
  });

  test('a taken gift: its transfer confirm and Decline are in the hero, and the confirm opens there', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    setApi({
      thing: makeThing({ status: 'TAKEN', owner: 'OWNER1', pending_booking: 'BK1' }),
      calendar: PENDING,
    });
    const { container } = renderThingPage();

    const confirm = await screen.findByRole('button', { name: 'Confirm request' });
    const row = heroRow(container);
    expect(labels(row)).toEqual(['Confirm request', 'Decline request']);
    expect(confirm.style.getPropertyValue('--background-color')).toBe(PRIMARY);
    expect(
      screen
        .getByRole('button', { name: 'Decline request' })
        .style.getPropertyValue('--background-color')
    ).toBe(SECONDARY);
    expect(content(container)).toContainElement(screen.getByRole('link', { name: 'Edit' }));

    fireEvent.click(confirm);

    // The panel is a sibling of the trigger, so it opens inside the row — the
    // stylesheet then gives it a line of its own — and never in the content.
    const panel = (await screen.findByText(/transfers the item/i)).closest('.thing-report-confirm');
    expect(row).toContainElement(panel);
    expect(content(container).querySelector('.thing-report-confirm')).toBeNull();
    expect(screen.getAllByRole('button', { name: 'Confirm request' })).toHaveLength(1);
  });

  test.each([
    ['a loan with no request waiting', { type: 'LEND_THING', status: 'ACTIVE' }],
    ['a gift nobody has asked for', { type: 'GIFT_THING', status: 'ACTIVE' }],
    ['a hidden thing', { type: 'GIFT_THING', status: 'INACTIVE' }],
  ])('%s: the hero has no buttons', async (_what, over) => {
    localStorage.setItem('userCode', 'OWNER1');
    setApi({ thing: makeThing({ ...over, owner: 'OWNER1' }) });
    const { container } = renderThingPage();

    await screen.findByRole('link', { name: 'Edit' });

    expect(heroRow(container)).toBeNull();
    expect(container.querySelector('.hero-actions')).toBeNull();
  });

  test('a member keeps "Claim" in the content: they read the page before they ask', async () => {
    localStorage.setItem('userCode', 'GUEST1');
    setApi({ thing: makeThing({ type: 'GIFT_THING', status: 'ACTIVE', owner: 'OWNER1' }) });
    const { container } = renderThingPage();

    const claim = await screen.findByRole('button', { name: 'Claim' });

    expect(content(container)).toContainElement(claim);
    expect(container.querySelector('.hero-actions')).toBeNull();
    expect(container.querySelector('.form-hero')).not.toContainElement(claim);
  });
});

describe('ThingPage — a co-curator demoted since the page loaded', () => {
  test('pressing Confirm request says why, reloads the thing, and the controls that are no longer theirs go', async () => {
    localStorage.setItem('userCode', 'CURATOR1');
    // A loan, not a gift: accepting a gift asks to confirm the handover first.
    const asCurator = makeThing({
      type: 'LEND_THING',
      status: 'ACTIVE',
      owner: 'OWNER1',
      can_manage: true,
    });
    const demoted = { ...asCurator, can_manage: false };
    let reads = 0;
    apiFetch.mockImplementation((url) => {
      if (/\/things\/[^/]+\/calendar\//.test(url)) {
        return Promise.resolve(
          mockResponse([{ code: 'BK1', status: 'PENDING', end_date: '2099-12-31' }])
        );
      }
      if (/\/bookings\/[^/]+\/accept\//.test(url)) {
        return Promise.resolve(mockResponse({}, false, 403));
      }
      if (/\/things\/[^/]+\/(faq|transfers|responses)\//.test(url)) {
        return Promise.resolve(mockResponse({ results: [], transfers: [], total_transfers: 0 }));
      }
      if (/\/things\/THG001\/(\?.*)?$/.test(url)) {
        reads += 1;
        return Promise.resolve(mockResponse(reads === 1 ? asCurator : demoted));
      }
      return Promise.resolve(mockResponse({}));
    });
    renderThingPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm request' }));

    expect(
      await screen.findByText(
        "You can no longer decide this request. We've reloaded it so you can see where it stands."
      )
    ).toBeInTheDocument();
    expect(reads).toBe(2);
    await waitFor(() =>
      expect(screen.queryByRole('button', { name: 'Confirm request' })).not.toBeInTheDocument()
    );
    expect(screen.queryByRole('button', { name: 'Decline request' })).not.toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════
// ThingPage — anonymous visitor (login-to-act, JoinPage pattern)
// An anonymous visitor on a PUBLIC collection sees the action buttons (like
// ThingLinkbox's loginToAct mode); each click routes to /collections/:code/join
// instead of showing the old inline JoinToAct email box.
// ════════════════════════════════════════════════════════════════════════
describe('ThingPage — anonymous login-to-act', () => {
  function NavSnapshot() {
    const { pathname, search } = useLocation();
    return <div data-testid="nav">{pathname + search}</div>;
  }

  function renderThingPageWithNav() {
    return render(
      <MemoryRouter initialEntries={['/things/THG001']}>
        <Routes>
          <Route path="/things/:thingCode" element={<ThingPage />} />
          <Route path="*" element={<NavSnapshot />} />
        </Routes>
      </MemoryRouter>
    );
  }

  test('shows the reserve button and routes the click to the join page, carrying ?thing=', async () => {
    localStorage.removeItem('userCode');
    setApi({
      thing: makeThing({ type: 'GIFT_THING', owner: 'OWNER1', collection_code: 'PUB001' }),
    });
    renderThingPageWithNav();

    fireEvent.click(await screen.findByRole('button', { name: 'Claim' }));

    // Lands on the collection's join page, with the thing it was trying to
    // reserve in the query string so the magic link comes back to it.
    expect(await screen.findByTestId('nav')).toHaveTextContent(
      '/collections/PUB001/join?thing=THG001'
    );
    // The anonymous click only navigates — it never fires a direct hold POST.
    expect(apiFetch).not.toHaveBeenCalledWith('/api/v1/things/THG001/request/', expect.anything());
    // The old inline JoinToAct email box is gone (replaced by the routing button).
    expect(screen.queryByText('Join to take part')).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════
// useThingBooking — handleRequest, and how a refused hold reaches the user
// A hold that silently does nothing is the worst outcome here: the guest walks
// away thinking they asked. Every branch has to say something.
// ════════════════════════════════════════════════════════════════════════
describe('useThingBooking — a guest asks for a hold', () => {
  const claim = (props = {}) => {
    renderLinkbox({ thing: makeThing({ type: 'GIFT_THING' }), userCode: 'GUEST1', ...props });
    fireEvent.click(screen.getByRole('button', { name: 'Claim' }));
  };

  test('a hold that lands confirms it', async () => {
    claim();

    expect(await screen.findByText("Request sent — you'll hear back soon.")).toBeInTheDocument();
  });

  // A thing can live in several collections, and only the requester knows which
  // one they were looking at — it decides where the owner's notification lands.
  test('the request carries the collection the requester was browsing', async () => {
    claim({ collectionCode: 'COL001' });

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/things/THG001/request/', {
        method: 'POST',
        body: JSON.stringify({ collection_code: 'COL001' }),
      })
    );
  });

  // Nothing to send when there is no collection context (the standalone
  // /things/:code view) — the backend falls back to its own approximation.
  test('a card with no collection context sends none', async () => {
    claim();

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/things/THG001/request/', {
        method: 'POST',
        body: JSON.stringify({}),
      })
    );
  });

  test('a rate limit asks the guest to wait', async () => {
    setApi({ request: () => Promise.resolve(mockResponse({}, false, 429)) });
    claim();

    expect(
      await screen.findByText('Too many attempts — please wait a moment and try again.')
    ).toBeInTheDocument();
  });

  test('a 400 surfaces the reason the server gave', async () => {
    extractApiError.mockResolvedValue('You already hold this item.');
    setApi({ request: () => Promise.resolve(mockResponse({}, false, 400)) });
    claim();

    expect(await screen.findByText('You already hold this item.')).toBeInTheDocument();
  });

  test('a 400 with no usable body falls back to our own copy', async () => {
    extractApiError.mockResolvedValue(null);
    setApi({ request: () => Promise.resolve(mockResponse({}, false, 400)) });
    claim();

    expect(await screen.findByText('Invalid request.')).toBeInTheDocument();
  });

  test('a server error is reported as one', async () => {
    setApi({ request: () => Promise.resolve(mockResponse({}, false, 500)) });
    claim();

    expect(await screen.findByText('Error sending request.')).toBeInTheDocument();
  });

  test('a dropped connection is reported', async () => {
    setApi({ request: () => Promise.reject(new Error('network down')) });
    claim();

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════
// useThingBooking — handleBookingAction: what a decision does to the thing
// The patch differs by type (bookingKeepsStatus), which is the whole reason the
// option exists — a rental keeps circulating, a gift does not.
// ════════════════════════════════════════════════════════════════════════
describe('useThingBooking — the owner decides a hold', () => {
  const GIFT_ASKED = makeThing({ type: 'GIFT_THING', status: 'TAKEN', pending_booking: 'BK1' });

  function renderOwner(thing, api = {}) {
    const onUpdateThing = vi.fn();
    setApi({ calendar: [{ code: 'BK1', status: 'PENDING', end_date: '2099-12-31' }], ...api });
    renderLinkbox({ thing, userCode: 'OWNER1', onUpdateThing });
    return onUpdateThing;
  }

  // The calendar is held back in these: the booking to answer is the one the thing
  // names, so a decision never waits for it. It is let through at the end only so
  // its answer lands inside the test.
  // GIFT/SELL (bookingKeepsStatus false): the thing is gone once given.
  test('accepting a gift retires the thing', async () => {
    const { calendarGate, release } = heldCalendar();
    const onUpdateThing = renderOwner(GIFT_ASKED, { calendarGate });

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm request' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/bookings/BK1/accept/', { method: 'POST' })
    );
    expect(onUpdateThing).toHaveBeenCalledWith('THG001', {
      status: 'INACTIVE',
      pending_booking: null,
    });
    expect(await screen.findByText('Request confirmed.')).toBeInTheDocument();
    release();
    await settle(apiFetch);
  });

  test('rejecting a gift puts it back on offer', async () => {
    const { calendarGate, release } = heldCalendar();
    const onUpdateThing = renderOwner(GIFT_ASKED, { calendarGate });

    fireEvent.click(await screen.findByRole('button', { name: 'Decline request' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/bookings/BK1/reject/', { method: 'POST' })
    );
    expect(onUpdateThing).toHaveBeenCalledWith('THG001', {
      status: 'ACTIVE',
      pending_booking: null,
    });
    expect(await screen.findByText('Request declined.')).toBeInTheDocument();
    release();
    await settle(apiFetch);
  });

  // A payload that does not carry `pending_booking` is the only way to have buttons
  // and no code: they wait for the calendar, and a press never reaches
  // `/bookings/null/`.
  test('with no code in the thing the buttons wait for the calendar and never act on nobody', async () => {
    const { calendarGate, release } = heldCalendar();
    renderOwner(makeThing({ type: 'GIFT_THING', status: 'TAKEN' }), { calendarGate });

    const confirm = await screen.findByRole('button', { name: 'Confirm request' });
    const decline = screen.getByRole('button', { name: 'Decline request' });
    expect(confirm).toBeDisabled();
    expect(decline).toBeDisabled();
    fireEvent.click(confirm);
    fireEvent.click(decline);
    expect(apiFetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/bookings/'),
      expect.anything()
    );

    release();
    await waitFor(() => expect(confirm).toBeEnabled());
    fireEvent.click(confirm);

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/bookings/BK1/accept/', { method: 'POST' })
    );
    const urls = apiFetch.mock.calls.map(([url]) => url);
    expect(urls.some((url) => url.includes('/bookings/null/'))).toBe(false);
    await settle(apiFetch);
  });

  test('the booking the calendar names wins over the one the thing carried', async () => {
    renderOwner(GIFT_ASKED, { calendar: [{ code: 'BK2', status: 'PENDING' }] });
    await screen.findByRole('button', { name: 'Decline request' });
    await settle(apiFetch);

    fireEvent.click(screen.getByRole('button', { name: 'Decline request' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/bookings/BK2/reject/', { method: 'POST' })
    );
    expect(apiFetch).not.toHaveBeenCalledWith('/api/v1/bookings/BK1/reject/', {
      method: 'POST',
    });
  });

  test('the handler itself does nothing when there is nobody to answer', async () => {
    setApi({});
    const { result } = renderHook(() => useThingBooking(makeThing({ status: 'TAKEN' })));

    await act(async () => {
      await result.current.handleBookingAction('accept');
    });

    expect(apiFetch).not.toHaveBeenCalled();
    expect(result.current.bookingAction).toBeNull();
  });

  // LEND/RENT (bookingKeepsStatus true): the thing keeps circulating, so a
  // decision may only move which request is waiting — never the status.
  test.each([
    ['accepting', 'Confirm request', 'accept'],
    ['rejecting', 'Decline request', 'reject'],
  ])('%s a rental leaves the thing active', async (_name, label, action) => {
    const onUpdateThing = renderOwner(makeThing({ type: 'LEND_THING', status: 'ACTIVE' }));

    fireEvent.click(await screen.findByRole('button', { name: label }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith(`/api/v1/bookings/BK1/${action}/`, { method: 'POST' })
    );
    // No `status` key at all — an exact match is the point of the assertion.
    expect(onUpdateThing).toHaveBeenCalledWith('THG001', { pending_booking: null });
  });

  test('deciding one request advances to the next one waiting', async () => {
    const onUpdateThing = renderOwner(makeThing({ type: 'LEND_THING', status: 'ACTIVE' }), {
      calendar: [
        { code: 'BK1', status: 'PENDING', end_date: '2099-12-31' },
        { code: 'BK2', status: 'PENDING', end_date: '2099-12-31' },
      ],
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm request' }));

    await waitFor(() =>
      expect(onUpdateThing).toHaveBeenCalledWith('THG001', { pending_booking: 'BK2' })
    );

    // The buttons now act on the second request, with no reload in between.
    fireEvent.click(screen.getByRole('button', { name: 'Decline request' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/bookings/BK2/reject/', { method: 'POST' })
    );
  });

  // The calendar returns past bookings too; a finished one must not become the
  // request the owner's buttons are pointed at.
  test('a booking that already ended is not the one decided', async () => {
    renderOwner(makeThing({ type: 'LEND_THING', status: 'ACTIVE' }), {
      calendar: [
        { code: 'BKOLD', status: 'PENDING', end_date: '2020-01-01' },
        { code: 'BKNOW', status: 'PENDING', end_date: '2099-12-31' },
      ],
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm request' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/bookings/BKNOW/accept/', { method: 'POST' })
    );
  });

  test.each([
    ['confirm', 'Confirm request', 'Error confirming the request.'],
    ['decline', 'Decline request', 'Error declining the request.'],
  ])(
    'a failed %s says which way it failed and leaves the thing alone',
    async (_n, label, message) => {
      const onUpdateThing = renderOwner(makeThing({ type: 'GIFT_THING', status: 'TAKEN' }), {
        booking: () => Promise.resolve(mockResponse({}, false)),
      });

      fireEvent.click(await screen.findByRole('button', { name: label }));

      expect(await screen.findByText(message)).toBeInTheDocument();
      expect(onUpdateThing).not.toHaveBeenCalled();
    }
  );

  // A co-curator demoted in another tab kept the card's "Confirm
  // hold / Decline request" on screen; pressing one, the server refused (correctly)
  // and the page said only "Error confirming the request." — no why, no way forward.
  // A 403 now says why and reloads the thing, so what is no longer theirs goes.
  const NO_LONGER =
    "You can no longer decide this request. We've reloaded it so you can see where it stands.";

  test.each([
    ['confirm', 'Confirm request'],
    ['decline', 'Decline request'],
  ])('a refused %s (403) says why and reloads the thing', async (_n, label) => {
    const demoted = makeThing({ type: 'GIFT_THING', status: 'TAKEN', can_manage: false });
    const onUpdateThing = renderOwner(makeThing({ type: 'GIFT_THING', status: 'TAKEN' }), {
      thing: demoted,
      booking: () => Promise.resolve(mockResponse({}, false, 403)),
    });

    fireEvent.click(await screen.findByRole('button', { name: label }));

    expect(await screen.findByText(NO_LONGER)).toBeInTheDocument();
    expect(screen.queryByText(/^Error (confirming|declining) hold\.$/)).not.toBeInTheDocument();
    // The thing was asked for again, and what came back replaces the card's copy.
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/things/THG001/');
    expect(onUpdateThing).toHaveBeenCalledWith('THG001', demoted);
  });

  test('any other refusal keeps the generic message and does not reload', async () => {
    const onUpdateThing = renderOwner(makeThing({ type: 'GIFT_THING', status: 'TAKEN' }), {
      booking: () => Promise.resolve(mockResponse({}, false, 500)),
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm request' }));

    expect(await screen.findByText('Error confirming the request.')).toBeInTheDocument();
    expect(screen.queryByText(NO_LONGER)).not.toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalledWith('/api/v1/things/THG001/');
    expect(onUpdateThing).not.toHaveBeenCalled();
  });

  test('if the thing cannot be reloaded the generic message stands: "reloaded" would be untrue', async () => {
    const onUpdateThing = vi.fn();
    apiFetch.mockImplementation((url) => {
      if (/\/things\/[^/]+\/calendar\//.test(url)) {
        return Promise.resolve(
          mockResponse([{ code: 'BK1', status: 'PENDING', end_date: '2099-12-31' }])
        );
      }
      if (/\/bookings\/[^/]+\/accept\//.test(url)) {
        return Promise.resolve(mockResponse({}, false, 403));
      }
      return Promise.resolve(mockResponse({}, false, 500));
    });
    renderLinkbox({
      thing: makeThing({ type: 'GIFT_THING', status: 'TAKEN' }),
      userCode: 'OWNER1',
      onUpdateThing,
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm request' }));

    expect(await screen.findByText('Error confirming the request.')).toBeInTheDocument();
    expect(screen.queryByText(NO_LONGER)).not.toBeInTheDocument();
    expect(onUpdateThing).not.toHaveBeenCalled();
  });

  test('a dropped connection while deciding is reported', async () => {
    renderOwner(makeThing({ type: 'GIFT_THING', status: 'TAKEN' }), {
      booking: () => Promise.reject(new Error('network down')),
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm request' }));

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════
// useThingBooking — handleActivate
// ════════════════════════════════════════════════════════════════════════
describe('useThingBooking — reactivating a thing', () => {
  test('reactivating puts it back and clears the deal it was in', async () => {
    const onUpdateThing = vi.fn();
    renderLinkbox({ thing: makeThing({ status: 'INACTIVE' }), userCode: 'OWNER1', onUpdateThing });

    fireEvent.click(screen.getByRole('button', { name: 'Reactivate' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/things/THG001/activate/', { method: 'POST' })
    );
    expect(onUpdateThing).toHaveBeenCalledWith('THG001', { status: 'ACTIVE', deal: [] });
  });

  test('a failed reactivate is reported and leaves the thing inactive', async () => {
    const onUpdateThing = vi.fn();
    setApi({ activate: () => Promise.resolve(mockResponse({}, false)) });
    renderLinkbox({ thing: makeThing({ status: 'INACTIVE' }), userCode: 'OWNER1', onUpdateThing });

    fireEvent.click(screen.getByRole('button', { name: 'Reactivate' }));

    expect(await screen.findByText('Error reactivating thing.')).toBeInTheDocument();
    expect(onUpdateThing).not.toHaveBeenCalled();
  });
});
