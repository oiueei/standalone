import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router-dom';
import { vi, describe, test, expect, beforeEach } from 'vitest';

// ── jsdom shims ────────────────────────────────────────────────────────
// PageLayout / RouteFocusReset and friends call scrollTo; HDS reads clipboard.
window.scrollTo = vi.fn();

// ── Mock apiFetch (the components fetch the calendar, POST requests, etc.) ─
// The factory cannot reference module-scope vars (it is hoisted), so it ships a
// permissive default; each test refines behaviour through setApi() below.
vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import { apiFetch, extractApiError } from '../services/api';
import ThingLinkbox from '../components/ThingLinkbox';
import ThingPage from '../pages/ThingPage';

function mockResponse(data, ok = true, status = ok ? 200 : 400) {
  return { ok, status, json: () => Promise.resolve(data) };
}

// Route apiFetch by URL. `thing` feeds the ThingPage detail fetch; `calendar`
// feeds the owner bookings fetch; `responses` feeds the wish answers fetch.
// `request`/`activate`/`booking` override a single route outright, for the
// failure branches that need a status code or a throw.
function setApi({
  thing = {}, calendar = [], responses = [], requestOk = true,
  request = null, activate = null, booking = null,
} = {}) {
  apiFetch.mockImplementation((url) => {
    if (/\/things\/[^/]+\/calendar\//.test(url)) return Promise.resolve(mockResponse(calendar));
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
    if (/\/things\/[^/]+\/transfers\//.test(url)) return Promise.resolve(mockResponse({ total_transfers: 0, transfers: [] }));
    if (/\/things\/[^/]+\/responses\//.test(url)) return Promise.resolve(mockResponse({ results: responses }));
    if (/\/wish-responses\/[^/]+\/accept\//.test(url)) return Promise.resolve(mockResponse({ status: 'ACCEPTED' }));
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
  localStorage.setItem('theeemeColors', JSON.stringify({
    color_01: 'bus', color_02: 'suomenlinna-light', color_03: 'copper',
    color_04: 'black', color_05: 'white', color_06: 'white',
  }));
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

  // Date-based (LEND/RENT) and SWAP navigate to RequestThingPage instead
  // of POSTing — these need a follow-up form (dates / swap items).
  test.each([
    ['LEND_THING', 'Borrow'],
    ['RENT_THING', 'Rent'],
    ['SWAP_THING', 'Swap'],
  ])('%s navigates to the request page', async (type, label) => {
    const thing = makeThing({ type, fee: type === 'RENT_THING' ? '5' : null });
    renderLinkbox({ thing, userCode: 'GUEST1' });

    fireEvent.click(screen.getByRole('button', { name: label }));

    await waitFor(() => expect(screen.getByTestId('navigated')).toBeInTheDocument());
    expect(apiFetch).not.toHaveBeenCalledWith(
      '/api/v1/things/THG001/request/',
      expect.anything()
    );
  });

  // NOTE: SHARE_THING is NOT in `needsPage` (only date-based LEND/RENT and SWAP
  // are), so the SHARE hold POSTs directly here — it does NOT navigate to
  // RequestThingPage. This contradicts frontend/CLAUDE.md ("LEND/RENT/SHARE …
  // navigate"), but matches the code today. Locked as-is; not a fix.
  test('SHARE_THING holds via direct POST (does not navigate)', async () => {
    const thing = makeThing({ type: 'SHARE_THING' });
    renderLinkbox({ thing, userCode: 'GUEST1' });

    fireEvent.click(screen.getByRole('button', { name: 'Take' }));

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith(
        '/api/v1/things/THG001/request/',
        expect.objectContaining({ method: 'POST' })
      );
    });
    expect(screen.queryByTestId('navigated')).toBeNull();
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
// ThingLinkbox — swap minimum-items gate
// ════════════════════════════════════════════════════════════════════════
describe('ThingLinkbox — swap minimum gate', () => {
  test('below the minimum disables the button, labels the gap, and shows the notification', () => {
    const thing = makeThing({
      type: 'SWAP_THING',
      collection_swap_minimum_items: 3,
      my_swap_count_in_collection: 1,
    });
    renderLinkbox({ thing, userCode: 'GUEST1' });

    // The disabled button now states the gap (P1-2) instead of the action verb,
    // and the detailed notification still appears below it.
    expect(screen.getByRole('button', { name: 'Need 2 more items' })).toBeDisabled();
    expect(screen.getByText('Upload more items first')).toBeInTheDocument();
  });

  test('at the minimum enables the button and hides the notification', () => {
    const thing = makeThing({
      type: 'SWAP_THING',
      collection_swap_minimum_items: 3,
      my_swap_count_in_collection: 3,
    });
    renderLinkbox({ thing, userCode: 'GUEST1' });

    expect(screen.getByRole('button', { name: 'Swap' })).toBeEnabled();
    expect(screen.queryByText('Upload more items first')).toBeNull();
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

    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reactivate' })).toBeNull();
    expect(screen.queryByRole('button', { name: 'Confirm hold' })).toBeNull();
  });

  test('INACTIVE shows Reactivate + Edit + Delete', () => {
    const thing = makeThing({ status: 'INACTIVE' });
    renderLinkbox({ thing, userCode: 'OWNER1' });

    expect(screen.getByRole('button', { name: 'Reactivate' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });

  test('TAKEN shows Confirm hold + Cancel hold + Edit', async () => {
    const thing = makeThing({ status: 'TAKEN' });
    renderLinkbox({ thing, userCode: 'OWNER1' });

    expect(await screen.findByRole('button', { name: 'Confirm hold' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel hold' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
  });

  // The pending booking arrives from the /calendar/ fetch (date-based type).
  test('ACTIVE date-based with a pending booking shows Confirm/Cancel hold', async () => {
    const thing = makeThing({ type: 'LEND_THING', status: 'ACTIVE' });
    setApi({ calendar: [{ code: 'BK1', status: 'PENDING', end_date: '2099-12-31' }] });
    renderLinkbox({ thing, userCode: 'OWNER1' });

    expect(await screen.findByRole('button', { name: 'Confirm hold' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel hold' })).toBeInTheDocument();
    // The Delete button is suppressed while a pending hold exists.
    expect(screen.queryByRole('button', { name: 'Delete' })).toBeNull();
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

  test('SWAP navigates to the request page', async () => {
    localStorage.setItem('userCode', 'GUEST1');
    setApi({ thing: makeThing({ type: 'SWAP_THING', owner: 'OWNER1' }) });
    renderThingPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Swap' }));

    await waitFor(() => expect(screen.getByTestId('navigated')).toBeInTheDocument());
  });
});

describe('ThingPage — owner button matrix', () => {
  test('ACTIVE shows Edit + Delete, no Reactivate', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    setApi({ thing: makeThing({ status: 'ACTIVE', owner: 'OWNER1' }) });
    renderThingPage();

    expect(await screen.findByRole('button', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
    expect(screen.queryByRole('button', { name: 'Reactivate' })).toBeNull();
  });

  test('INACTIVE shows Reactivate + Edit + Delete', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    setApi({ thing: makeThing({ status: 'INACTIVE', owner: 'OWNER1' }) });
    renderThingPage();

    expect(await screen.findByRole('button', { name: 'Reactivate' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete' })).toBeInTheDocument();
  });

  test('TAKEN shows Confirm hold + Cancel hold + Edit', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    setApi({ thing: makeThing({ status: 'TAKEN', owner: 'OWNER1' }) });
    renderThingPage();

    expect(await screen.findByRole('button', { name: 'Confirm hold' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Cancel hold' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Edit' })).toBeInTheDocument();
  });
});

describe('ThingPage — wish branch', () => {
  test('non-owner sees the answer menu and no reservation button', async () => {
    localStorage.setItem('userCode', 'GUEST1');
    setApi({ thing: makeThing({ type: 'WISH_THING', owner: 'OWNER1' }) });
    renderThingPage();

    // The RespondMenu ("Contestar") one-shot Select renders its placeholder.
    expect(await screen.findByText('Choose how to help')).toBeInTheDocument();
    // No Hold/action reservation button for a wish.
    expect(screen.queryByRole('button', { name: 'Claim' })).toBeNull();
  });

  test('creator sees the answers section, an accept control, and resolve', async () => {
    localStorage.setItem('userCode', 'OWNER1');
    setApi({
      thing: makeThing({ type: 'WISH_THING', owner: 'OWNER1', status: 'ACTIVE' }),
      responses: [{ code: 'RSP001', responder_name: 'Bob', kind: 'KNOW_WHERE', status: 'PENDING', message: 'I know where' }],
    });
    renderThingPage();

    expect(await screen.findByText('Answers')).toBeInTheDocument();
    expect(await screen.findByRole('button', { name: 'Accept' })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Mark as resolved' })).toBeInTheDocument();
  });
});

// ════════════════════════════════════════════════════════════════════════
// ThingPage — anonymous visitor (login-to-act, JoinPage pattern)
// An anonymous visitor on a PUBLIC collection sees the action buttons (like
// ThingLinkbox's loginToAct mode); each click routes to /collections/:code/join
// instead of showing the old inline JoinToAct email box.
// ════════════════════════════════════════════════════════════════════════
describe('ThingPage — anonymous login-to-act', () => {
  test('non-wish shows the reserve button and routes the click to the join page', async () => {
    localStorage.removeItem('userCode');
    setApi({ thing: makeThing({ type: 'GIFT_THING', owner: 'OWNER1', collection_code: 'PUB001' }) });
    renderThingPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Claim' }));

    await waitFor(() => expect(screen.getByTestId('navigated')).toBeInTheDocument());
    // The anonymous click only navigates — it never fires a direct hold POST.
    expect(apiFetch).not.toHaveBeenCalledWith(
      '/api/v1/things/THG001/request/',
      expect.anything()
    );
    // The old inline JoinToAct email box is gone (replaced by the routing button).
    expect(screen.queryByText('Join to take part')).toBeNull();
  });

  test('wish shows an Answer button that routes to the join page', async () => {
    localStorage.removeItem('userCode');
    setApi({ thing: makeThing({ type: 'WISH_THING', owner: 'OWNER1', collection_code: 'PUB001' }) });
    renderThingPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Answer' }));

    await waitFor(() => expect(screen.getByTestId('navigated')).toBeInTheDocument());
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

    expect(await screen.findByText('Hold requested — you’ll hear back soon.')).toBeInTheDocument();
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
  function renderOwner(thing, api = {}) {
    const onUpdateThing = vi.fn();
    setApi({ calendar: [{ code: 'BK1', status: 'PENDING', end_date: '2099-12-31' }], ...api });
    renderLinkbox({ thing, userCode: 'OWNER1', onUpdateThing });
    return onUpdateThing;
  }

  // GIFT/SELL (bookingKeepsStatus false): the thing is gone once given.
  test('accepting a gift retires the thing', async () => {
    const onUpdateThing = renderOwner(makeThing({ type: 'GIFT_THING', status: 'TAKEN' }));

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm hold' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/bookings/BK1/accept/', { method: 'POST' })
    );
    expect(onUpdateThing).toHaveBeenCalledWith('THG001', {
      status: 'INACTIVE',
      pending_booking: null,
    });
    expect(await screen.findByText('Hold confirmed.')).toBeInTheDocument();
  });

  test('rejecting a gift puts it back on offer', async () => {
    const onUpdateThing = renderOwner(makeThing({ type: 'GIFT_THING', status: 'TAKEN' }));

    fireEvent.click(await screen.findByRole('button', { name: 'Cancel hold' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/bookings/BK1/reject/', { method: 'POST' })
    );
    expect(onUpdateThing).toHaveBeenCalledWith('THG001', { status: 'ACTIVE', pending_booking: null });
    expect(await screen.findByText('Hold cancelled.')).toBeInTheDocument();
  });

  // LEND/RENT (bookingKeepsStatus true): the thing keeps circulating, so a
  // decision may only move which request is waiting — never the status.
  test.each([
    ['accepting', 'Confirm hold', 'accept'],
    ['rejecting', 'Cancel hold', 'reject'],
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

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm hold' }));

    await waitFor(() =>
      expect(onUpdateThing).toHaveBeenCalledWith('THG001', { pending_booking: 'BK2' })
    );

    // The buttons now act on the second request, with no reload in between.
    fireEvent.click(screen.getByRole('button', { name: 'Cancel hold' }));

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

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm hold' }));

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/bookings/BKNOW/accept/', { method: 'POST' })
    );
  });

  test.each([
    ['confirm', 'Confirm hold', 'Error confirming hold.'],
    ['cancel', 'Cancel hold', 'Error cancelling hold.'],
  ])('a failed %s says which way it failed and leaves the thing alone', async (_n, label, message) => {
    const onUpdateThing = renderOwner(makeThing({ type: 'GIFT_THING', status: 'TAKEN' }), {
      booking: () => Promise.resolve(mockResponse({}, false)),
    });

    fireEvent.click(await screen.findByRole('button', { name: label }));

    expect(await screen.findByText(message)).toBeInTheDocument();
    expect(onUpdateThing).not.toHaveBeenCalled();
  });

  test('a dropped connection while deciding is reported', async () => {
    renderOwner(makeThing({ type: 'GIFT_THING', status: 'TAKEN' }), {
      booking: () => Promise.reject(new Error('network down')),
    });

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm hold' }));

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
