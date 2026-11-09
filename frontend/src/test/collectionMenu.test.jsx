import { render, screen, fireEvent, waitFor, within } from '@testing-library/react';
import { press, settle } from './settle';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  ),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

// `downloadBlob` is imperative DOM (object URL, anchor, click) with no return
// value, so the only honest assertion is on the call itself: did the click
// hand the browser the file, and under which name. `filenameFromResponse`
// stays real — it is half of what these tests pin.
vi.mock('../utils/downloadBlob', async (importOriginal) => ({
  ...(await importOriginal()),
  default: vi.fn(),
}));

// These pin the entries the product itself puts in the menu; a deployment that has a
// guide for whoever runs a group adds one more (pinned in `curatorGuide.test.jsx`).
vi.mock('../deployment', async (orig) => ({ ...(await orig()), curatorGuidePath: null }));

import en from '../i18n/locales/en.json';
import { apiFetch } from '../services/api';
import downloadBlob from '../utils/downloadBlob';
import CollectionPage from '../pages/CollectionPage';
import declarePalette from './declarePalette';

const LEND_THING = {
  code: 'THG001',
  type: 'LEND_THING',
  headline: 'Drill',
  description: '',
  status: 'ACTIVE',
  owner: 'ABC123',
  owner_name: 'Owner',
  fee: null,
  availability: '',
  location: '',
  condition: '',
  thumbnail_url: '',
  gallery: [],
  gallery_urls: [],
  available_today: null,
  next_available: null,
  tags: [],
  collection_tags: [],
  pending_questions: 0,
  my_pending_booking: null,
  pending_booking: null,
  bookings: [],
  created: '2026-09-01T10:00:00Z',
};

// The founder-curator shape; every test overrides what it needs.
const COLLECTION = {
  code: 'COL001',
  headline: 'Tool library',
  description: '',
  status: 'ACTIVE',
  visibility: 'PRIVATE',
  mode: 'PROPRIETARY',
  owner: 'ABC123',
  owner_name: 'Owner',
  is_curator: true,
  is_member: false,
  thumbnail_url: '',
  tags: [],
  things: [LEND_THING],
  invites: [],
  is_paused: false,
  allowed_thing_types: ['LEND_THING'],
};

// A calendar-export response the way the endpoint really answers: the count
// in `X-Calendar-Events`, the filename in `Content-Disposition`, the .ics as
// a blob. A Map stands in for Headers — `.get` with exact casing is all the
// code ever reads.
const calendarResponse = ({ count = '3', cancelled, filename = 'COL001-cal.ics' } = {}) => ({
  ok: true,
  status: 200,
  headers: new Map([
    ['X-Calendar-Events', count],
    // Absent unless a test names it — the SPA must read a missing header as 0.
    ...(cancelled === undefined ? [] : [['X-Calendar-Cancelled', cancelled]]),
    ['Content-Disposition', `attachment; filename="${filename}"`],
  ]),
  blob: () => Promise.resolve(new Blob(['BEGIN:VCALENDAR'], { type: 'text/calendar' })),
});

// The JSON export's name comes from the server's Content-Disposition; the
// stats CSV has never had one, so its name is built client-side.
const statsResponse = () => ({
  ok: true,
  status: 200,
  blob: () => Promise.resolve(new Blob(['metric,value\n'], { type: 'text/csv' })),
});

const exportResponse = ({
  ok = true,
  status = 200,
  filename = 'oiueei-COL001-2026-08-21.json',
} = {}) => ({
  ok,
  status,
  headers: new Map(ok ? [['Content-Disposition', `attachment; filename="${filename}"`]] : []),
  blob: () => Promise.resolve(new Blob(['{}'], { type: 'application/json' })),
});

// What an endpoint answers: a response, or a function that returns one (or a
// promise of one) at each call — which is how a test makes the same download
// fail the first time and work the second, or hold it in flight.
const answer = (given, fallback) =>
  Promise.resolve(typeof given === 'function' ? given() : (given ?? fallback()));

/** The first response for the first call, the next for the next… the last for every one after. */
const sequence = (...responses) => {
  let call = 0;
  return () => responses[Math.min(call++, responses.length - 1)];
};

function setApi(collection, { calendar, stats, collectionExport } = {}) {
  apiFetch.mockImplementation((url) => {
    if (url.includes('/inbox/')) {
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
    }
    if (url === '/api/v1/collections/COL001/calendar-export/') {
      return answer(calendar, calendarResponse);
    }
    if (url === '/api/v1/collections/COL001/stats/') {
      return answer(stats, statsResponse);
    }
    if (url === '/api/v1/collections/COL001/export/') {
      return answer(collectionExport, exportResponse);
    }
    return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(collection) });
  });
}

function renderCollection(collection, responses) {
  setApi(collection, responses);
  return renderPage();
}

/** For tests that need their own fetch mock: they set it, then render. */
function renderPage() {
  return render(
    <MemoryRouter initialEntries={['/collections/COL001']}>
      <Routes>
        <Route path="/collections/:code" element={<CollectionPage />} />
        {/* A collection that names its kind is moved to its own address. */}
        <Route path="/:kind/:code" element={<CollectionPage />} />
      </Routes>
    </MemoryRouter>
  );
}

const TRIGGER = 'Collection options';
/** The open panel, or null when it is closed. "Add thing" is also a button in the
 * hero row now, so a link of that name no longer tells the two apart. */
const panel = () => document.getElementById('collection-menu-panel');
const CALENDAR = 'Download the calendar (ICS)';

/** The menu's trigger, then the panel open — every test below starts here. */
async function openMenu() {
  await press(await screen.findByRole('button', { name: TRIGGER }));
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
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
});

/**
 * The collection's own options, one click from its page:
 * "Add thing", "Manage members" and the three downloads left the hero row
 * (which keeps "Add thing" and "Invite your people") and the settings page's foot, and
 * live in this menu instead — a fourth icon in the hero's corner, curators
 * only. These tests pin the menu's own decisions:
 *
 * - WHO sees it: `is_curator` only — a member or an anonymous reader gets no
 *   trigger at all, so no entry either.
 * - The calendar entry additionally needs the group to hold date-based
 *   things: a library and a shed always do, a stall only when one of its
 *   things is a loan, a rental or a reservation (one that a migrated mixed
 *   collection kept).
 * - What a click does: each download's request, filename and outcome message
 *   (stats and JSON moved from `EditCollectionPage` as they were), the panel
 *   closing, and the focus landing back on the trigger — the pressed button
 *   disappears with the panel, and the focus would fall to <body>.
 */
describe('the collection menu in the CollectionPage hero corner', () => {
  test.each([
    ['a network', { mode: 'NETWORK' }],
    ['a collection that is not a network', {}],
  ])('a curator of %s finds their organisation in the menu', async (_, extra) => {
    renderCollection({ ...COLLECTION, ...extra });
    await openMenu();

    expect(within(panel()).getByRole('link', { name: en.organisation.menuEntry })).toHaveAttribute(
      'href',
      '/collections/COL001/organisation'
    );
  });

  test('a curator gets the trigger; the panel holds both links and the three downloads', async () => {
    renderCollection(COLLECTION);
    await openMenu();

    expect(within(panel()).getByRole('link', { name: 'Add thing' })).toHaveAttribute(
      'href',
      '/collections/COL001/add'
    );
    expect(screen.getByRole('link', { name: 'Manage members' })).toHaveAttribute(
      'href',
      '/collections/COL001/invites'
    );
    expect(screen.getByRole('button', { name: CALENDAR })).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Download the stats (CSV)' })).toBeInTheDocument();
    expect(
      screen.getByRole('button', { name: 'Download the whole collection (JSON)' })
    ).toBeInTheDocument();
  });

  test('the trigger draws the document-group icon, hidden from assistive tech', async () => {
    renderCollection(COLLECTION);
    const trigger = await screen.findByRole('button', { name: TRIGGER });

    // HDS names each icon's <svg> after itself (`document-group`, `menu-dots`)
    // even when `aria-hidden` keeps it out of the accessibility tree, so that
    // label is how a test tells one icon from another in jsdom.
    const icon = trigger.querySelector('svg');
    expect(icon).toHaveAttribute('aria-label', 'document-group');
    // HDS hides a bare icon by default, so this pins the outcome (the glyph is
    // never read out beside the button's own name), not the explicit prop.
    expect(icon).toHaveAttribute('aria-hidden', 'true');
    // The button's own name is still the one `aria-label`, not the icon's.
    expect(trigger).toHaveAccessibleName(TRIGGER);
  });

  test('"Add several at once (CSV)" follows "Add thing" in the panel, and goes to its own page', async () => {
    renderCollection(COLLECTION);
    await openMenu();

    const entries = within(panel())
      .getAllByRole('link')
      .map((link) => [link.textContent, link.getAttribute('href')]);
    expect(entries).toEqual([
      ['Add thing', '/collections/COL001/add'],
      // A page of its own, no longer a section of /add.
      ['Add several at once (CSV)', '/collections/COL001/import'],
      ['Manage members', '/collections/COL001/invites'],
      // The curator's own page in the group, in every collection.
      [en.organisation.menuEntry, '/collections/COL001/organisation'],
      // …and so is the CSV of invitations, a page of its own.
      ['Invite many at once (CSV)', '/collections/COL001/invites/import'],
    ]);
  });

  test('"Invite many at once (CSV)" follows the members and organisation entries, and is nowhere else', async () => {
    renderCollection(COLLECTION);
    await openMenu();

    const names = within(panel())
      .getAllByRole('link')
      .map((link) => link.textContent);
    expect(names.indexOf(en.organisation.menuEntry)).toBe(names.indexOf('Manage members') + 1);
    expect(names.indexOf('Invite many at once (CSV)')).toBe(names.indexOf('Manage members') + 2);
    expect(
      within(panel()).getAllByRole('link', { name: 'Invite many at once (CSV)' })
    ).toHaveLength(1);
  });

  test('choosing the CSV entry closes the panel', async () => {
    renderCollection(COLLECTION);
    await openMenu();
    // jsdom would try to follow the anchor's href and say it cannot.
    const noNavigation = (event) => event.preventDefault();
    document.addEventListener('click', noNavigation);
    try {
      fireEvent.click(within(panel()).getByRole('link', { name: 'Add several at once (CSV)' }));
    } finally {
      document.removeEventListener('click', noNavigation);
    }

    expect(panel()).toBeNull();
  });

  test('a co-curator (not the founder) gets it too', async () => {
    renderCollection({
      ...COLLECTION,
      owner: 'OTHER1',
      owner_name: 'Founder',
      co_owners: [{ code: 'OTHER1', name: 'Founder Co' }],
    });

    expect(await screen.findByRole('button', { name: TRIGGER })).toBeInTheDocument();
  });

  test('a curator of a GIFT/SELL-only collection gets the menu, but no calendar entry', async () => {
    renderCollection({
      ...COLLECTION,
      allowed_thing_types: ['GIFT_THING', 'SELL_THING'],
      things: [{ ...LEND_THING, type: 'GIFT_THING', headline: 'Board game' }],
    });

    await screen.findByText('Board game');
    await openMenu();

    expect(screen.queryByRole('button', { name: CALENDAR })).not.toBeInTheDocument();
    // The two downloads that do not depend on dates stay.
    expect(screen.getByRole('button', { name: 'Download the stats (CSV)' })).toBeInTheDocument();
  });

  test('a signed-in reader who is neither a curator nor a member gets no menu, even with date-based things', async () => {
    // A PUBLIC group is readable by anyone: being signed in is not being in it. The
    // member's menu (below) is theirs only because it holds what is theirs.
    renderCollection({
      ...COLLECTION,
      owner: 'OTHER1',
      owner_name: 'Owner',
      is_curator: false,
      is_member: false,
      mode: 'COMMUNITY',
      visibility: 'PUBLIC',
    });

    await screen.findByText('Drill');
    expect(screen.queryByRole('button', { name: TRIGGER })).not.toBeInTheDocument();
  });

  test('an anonymous reader gets no menu', async () => {
    localStorage.removeItem('userCode');
    // The server computes `is_curator` per reader — a stranger on a PUBLIC
    // collection is not one, so the payload it gets is not one either.
    renderCollection({ ...COLLECTION, visibility: 'PUBLIC', is_curator: false });

    await screen.findByText('Drill');
    expect(screen.queryByRole('button', { name: TRIGGER })).not.toBeInTheDocument();
  });

  test('a library with nothing in it yet still offers the calendar entry', async () => {
    renderCollection({
      ...COLLECTION,
      kind: 'LIBRARY',
      allowed_thing_types: ['LEND_THING', 'RENT_THING'],
      things: [],
    });

    await openMenu();
    expect(screen.getByRole('button', { name: CALENDAR })).toBeInTheDocument();
  });

  test('a stall with only gifts and sales offers no calendar entry', async () => {
    renderCollection({
      ...COLLECTION,
      kind: 'STALL',
      allowed_thing_types: ['GIFT_THING', 'SELL_THING'],
      things: [{ ...LEND_THING, type: 'SELL_THING', headline: 'Record' }],
    });

    await screen.findByText('Record');
    await openMenu();
    expect(screen.queryByRole('button', { name: CALENDAR })).not.toBeInTheDocument();
  });

  test('a stall that kept a loan from before the kinds offers the calendar entry', async () => {
    renderCollection({
      ...COLLECTION,
      kind: 'STALL',
      allowed_thing_types: ['GIFT_THING', 'SELL_THING'],
      things: [LEND_THING],
    });

    await screen.findByText('Drill');
    await openMenu();
    expect(screen.getByRole('button', { name: CALENDAR })).toBeInTheDocument();
  });

  test('an old collection with no allowlist: a RENT thing offers the calendar entry', async () => {
    renderCollection({
      ...COLLECTION,
      allowed_thing_types: [],
      things: [{ ...LEND_THING, type: 'RENT_THING', headline: 'Projector' }],
    });

    await openMenu();
    expect(screen.getByRole('button', { name: CALENDAR })).toBeInTheDocument();
  });

  test('no allowlist and nothing date-based offers no calendar entry either', async () => {
    renderCollection({
      ...COLLECTION,
      allowed_thing_types: [],
      things: [{ ...LEND_THING, type: 'SELL_THING', headline: 'Record' }],
    });

    await screen.findByText('Record');
    await openMenu();
    expect(screen.queryByRole('button', { name: CALENDAR })).not.toBeInTheDocument();
  });

  test('the calendar entry POSTs the export and saves the file under the server-set name', async () => {
    renderCollection(COLLECTION, {
      calendar: calendarResponse({ count: '3', filename: 'COL001-cal.ics' }),
    });
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: CALENDAR }));

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/collections/COL001/calendar-export/', {
        method: 'POST',
      });
      expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'COL001-cal.ics');
    });
    expect(await screen.findByText('3 events — check your downloads.')).toBeInTheDocument();
  });

  test('one event is “1 event”, not “1 events”', async () => {
    renderCollection(COLLECTION, { calendar: calendarResponse({ count: '1', cancelled: '0' }) });
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: CALENDAR }));

    expect(await screen.findByText('1 event — check your downloads.')).toBeInTheDocument();
  });

  test('a zero calendar count downloads nothing and says why', async () => {
    renderCollection(COLLECTION, { calendar: calendarResponse({ count: '0', cancelled: '0' }) });
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: CALENDAR }));

    expect(await screen.findByText('Nothing coming up in the calendar.')).toBeInTheDocument();
    expect(downloadBlob).not.toHaveBeenCalled();
  });

  test('cancellations alone are still downloaded — importing them is what clears the calendar', async () => {
    renderCollection(COLLECTION, { calendar: calendarResponse({ count: '0', cancelled: '2' }) });
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: CALENDAR }));

    expect(
      await screen.findByText(
        'Nothing coming up, but 2 cancelled reservations — import the file so your calendar can drop them.'
      )
    ).toBeInTheDocument();
    expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'COL001-cal.ics');
  });

  test('confirmed and cancelled together: both are said, in one message', async () => {
    renderCollection(COLLECTION, { calendar: calendarResponse({ count: '3', cancelled: '1' }) });
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: CALENDAR }));

    expect(
      await screen.findByText(
        '3 events — check your downloads. It includes 1 cancelled reservation, marked so your calendar can drop it.'
      )
    ).toBeInTheDocument();
    expect(downloadBlob).toHaveBeenCalledTimes(1);
  });

  test.each([
    ['429', 'Too many attempts — please wait a moment and try again.'],
    ['500', "Couldn't build the calendar file. Please try again in a moment."],
  ])(
    'a calendar export refused with %s says its own message and downloads nothing',
    async (status, message) => {
      renderCollection(COLLECTION, {
        calendar: { ok: false, status: Number(status), headers: new Map() },
      });
      await openMenu();

      fireEvent.click(screen.getByRole('button', { name: CALENDAR }));

      expect(await screen.findByText(message)).toBeInTheDocument();
      expect(downloadBlob).not.toHaveBeenCalled();
    }
  );

  test('a calendar export request that never arrives says the connection one', async () => {
    apiFetch.mockImplementation((url) => {
      if (url.includes('/inbox/')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
      }
      if (url === '/api/v1/collections/COL001/calendar-export/') {
        return Promise.reject(new TypeError('Failed to fetch'));
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(COLLECTION) });
    });
    renderPage();
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: CALENDAR }));

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
    expect(downloadBlob).not.toHaveBeenCalled();
  });

  test('the stats entry GETs the CSV and names the file after the collection', async () => {
    renderCollection(COLLECTION, { stats: statsResponse() });
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: 'Download the stats (CSV)' }));

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/collections/COL001/stats/');
      expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'COL001-stats.csv');
    });
  });

  test('a failed stats download says so', async () => {
    renderCollection(COLLECTION, {
      stats: { ok: false, status: 500, blob: () => Promise.resolve(new Blob(['x'])) },
    });
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: 'Download the stats (CSV)' }));

    expect(await screen.findByText("Couldn't download the stats.")).toBeInTheDocument();
  });

  test('the JSON entry GETs the export and saves it under the server-set name', async () => {
    renderCollection(COLLECTION, {
      collectionExport: exportResponse({ filename: 'oiueei-COL001-2026-08-21.json' }),
    });
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: 'Download the whole collection (JSON)' }));

    await waitFor(() => {
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/collections/COL001/export/');
      expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'oiueei-COL001-2026-08-21.json');
    });
  });

  test.each([
    ['429', 'Too many attempts — please wait a moment and try again.'],
    ['500', "Couldn't build the export. Please try again in a moment."],
  ])('a JSON export refused with %s says its own message', async (status, message) => {
    renderCollection(COLLECTION, {
      collectionExport: exportResponse({ ok: false, status: Number(status) }),
    });
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: 'Download the whole collection (JSON)' }));

    expect(await screen.findByText(message)).toBeInTheDocument();
  });

  test('a JSON export request that never arrives says the connection one', async () => {
    apiFetch.mockImplementation((url) => {
      if (url.includes('/inbox/')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
      }
      if (url === '/api/v1/collections/COL001/export/') {
        return Promise.reject(new TypeError('Failed to fetch'));
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(COLLECTION) });
    });
    renderPage();
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: 'Download the whole collection (JSON)' }));

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
  });

  test('starting a download drops the message of the previous one, and it does not come back', async () => {
    // One message at a time: a finished "3 events" beside a half-done stats
    // file would read as both having completed. The stats response is held in
    // flight so the test sees both moments — the old message gone while the new
    // download runs, and still gone once it lands (a status zone that merely
    // hid the old message during the download would show it again at the end).
    let release;
    renderCollection(COLLECTION, {
      stats: () =>
        new Promise((resolve) => {
          release = () => resolve(statsResponse());
        }),
    });
    await openMenu();
    fireEvent.click(screen.getByRole('button', { name: CALENDAR }));
    expect(await screen.findByText('3 events — check your downloads.')).toBeInTheDocument();

    await press(screen.getByRole('button', { name: TRIGGER }));
    fireEvent.click(screen.getByRole('button', { name: 'Download the stats (CSV)' }));

    expect(await screen.findByText('Preparing the file…')).toBeInTheDocument();
    expect(screen.queryByText('3 events — check your downloads.')).toBeNull();

    release();
    await waitFor(() =>
      expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'COL001-stats.csv')
    );
    await waitFor(() => expect(screen.queryByText('Preparing the file…')).toBeNull());
    expect(screen.queryByText('3 events — check your downloads.')).toBeNull();
  });

  test('a stats error is gone once the next stats download succeeds', async () => {
    renderCollection(COLLECTION, {
      stats: sequence(
        { ok: false, status: 500, blob: () => Promise.resolve(new Blob(['x'])) },
        statsResponse()
      ),
    });
    await openMenu();
    fireEvent.click(screen.getByRole('button', { name: 'Download the stats (CSV)' }));
    expect(await screen.findByText("Couldn't download the stats.")).toBeInTheDocument();

    await press(screen.getByRole('button', { name: TRIGGER }));
    fireEvent.click(screen.getByRole('button', { name: 'Download the stats (CSV)' }));

    await waitFor(() =>
      expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'COL001-stats.csv')
    );
    await waitFor(() => expect(screen.queryByText("Couldn't download the stats.")).toBeNull());
  });

  test('a JSON export error is gone once the next export succeeds', async () => {
    renderCollection(COLLECTION, {
      collectionExport: sequence(exportResponse({ ok: false, status: 500 }), exportResponse()),
    });
    await openMenu();
    fireEvent.click(screen.getByRole('button', { name: 'Download the whole collection (JSON)' }));
    expect(
      await screen.findByText("Couldn't build the export. Please try again in a moment.")
    ).toBeInTheDocument();

    await press(screen.getByRole('button', { name: TRIGGER }));
    fireEvent.click(screen.getByRole('button', { name: 'Download the whole collection (JSON)' }));

    await waitFor(() =>
      expect(downloadBlob).toHaveBeenCalledWith(expect.any(Blob), 'oiueei-COL001-2026-08-21.json')
    );
    await waitFor(() =>
      expect(
        screen.queryByText("Couldn't build the export. Please try again in a moment.")
      ).toBeNull()
    );
  });

  test('while a download runs, the status zone says the file is being prepared', async () => {
    let release;
    apiFetch.mockImplementation((url) => {
      if (url.includes('/inbox/')) {
        return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve([]) });
      }
      if (url === '/api/v1/collections/COL001/stats/') {
        return new Promise((resolve) => {
          release = () => resolve(statsResponse());
        });
      }
      return Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(COLLECTION) });
    });
    renderPage();
    await openMenu();

    fireEvent.click(screen.getByRole('button', { name: 'Download the stats (CSV)' }));

    expect(await screen.findByText('Preparing the file…')).toBeInTheDocument();
    // And its menu entry is disabled until it lands.
    await press(screen.getByRole('button', { name: TRIGGER }));
    expect(screen.getByRole('button', { name: 'Download the stats (CSV)' })).toBeDisabled();

    release();
    await waitFor(() => expect(screen.queryByText('Preparing the file…')).toBeNull());
  });

  test('Escape closes the panel and returns focus to the trigger', async () => {
    renderCollection(COLLECTION);
    await openMenu();
    const trigger = screen.getByRole('button', { name: TRIGGER });

    fireEvent.keyDown(document, { key: 'Escape' });

    expect(panel()).toBeNull();
    expect(trigger).toHaveFocus();
  });

  test('a download closes the panel and returns focus to the trigger', async () => {
    renderCollection(COLLECTION);
    await openMenu();
    const trigger = screen.getByRole('button', { name: TRIGGER });

    await press(screen.getByRole('button', { name: 'Download the stats (CSV)' }));

    // The panel is gone at once (the file keeps fetching underneath)…
    expect(panel()).toBeNull();
    // …and the focus did not fall to <body> with the button that held it.
    expect(trigger).toHaveFocus();
  });

  // A plain click on one of the links leaves the page, which unmounts the menu
  // whether or not the link closes it — a test with a plain click would pass
  // for the wrong reason. A modified click (a new tab) is the case that stays
  // on the page, and the one where the panel would otherwise be left open.
  test.each([
    'Add thing',
    'Add several at once (CSV)',
    'Manage members',
    'Invite many at once (CSV)',
  ])('a click on "%s" that opens a new tab still closes the panel', async (name) => {
    renderCollection(COLLECTION);
    await openMenu();
    // jsdom would try to follow the anchor's href and say it cannot.
    const noNavigation = (event) => event.preventDefault();
    document.addEventListener('click', noNavigation);
    try {
      fireEvent.click(within(panel()).getByRole('link', { name }), { ctrlKey: true });
    } finally {
      document.removeEventListener('click', noNavigation);
    }

    expect(panel()).toBeNull();
    // Still on the collection's page, trigger folded.
    expect(screen.getByRole('button', { name: TRIGGER })).toHaveAttribute('aria-expanded', 'false');
  });

  test('opening the account menu closes the collection menu — it is a click outside', async () => {
    renderCollection(COLLECTION);
    await openMenu();

    const accountTrigger = screen.getByRole('button', { name: 'Your account' });
    fireEvent.pointerDown(accountTrigger);
    fireEvent.click(accountTrigger);

    expect(panel()).toBeNull();
    expect(screen.getByRole('link', { name: 'My profile' })).toBeInTheDocument();
  });
});

/**
 * The same menu for a member: the corner icon in the same
 * place, with what is theirs — the group's welcome document (a link that opens in
 * a new tab, first), "Mute the summaries" / "Get the summaries again" (only where the
 * group sends one) and, under a divider, "Leave the group". The three things were
 * scattered: leaving only in "My groups" on the profile, the summary switch only
 * in the footer of the email, the document a loose link in the hero.
 */
describe('the collection menu for a member', () => {
  const DOC = 'https://bucket.your-domain.test/oiueei/documents/welcome.pdf';
  const MEMBER = {
    ...COLLECTION,
    owner: 'OTHER1',
    owner_name: 'Owner',
    is_curator: false,
    is_member: true,
    digest_frequency: 'WEEKLY',
    is_digest_muted: false,
    welcome_doc_url: DOC,
  };
  const DIGEST_URL = '/api/v1/collections/COL001/digest/';
  const MUTE = 'Mute the summaries';
  const UNMUTE = 'Get the summaries again';
  const LEAVE = 'Leave the group';
  const DOC_NAME = /welcome document \(PDF\)/;

  /** Records where the leave link went, and what it handed over. */
  function LeaveProbe() {
    const { state } = useLocation();
    return <div data-testid="leave-page">{state?.headline}</div>;
  }

  // The collection endpoint as `setApi` answers it, with the digest POST decided
  // by the test: a response (or a function returning one) — by default it does what
  // the server does and answers `{muted}` for what it was sent.
  function renderMember(collection, { digest } = {}) {
    setApi(collection);
    const base = apiFetch.getMockImplementation();
    apiFetch.mockImplementation((url, options) =>
      url === DIGEST_URL
        ? answer(digest, () => ({
            ok: true,
            status: 200,
            json: () => Promise.resolve({ muted: JSON.parse(options.body).muted }),
          }))
        : base(url, options)
    );
    return render(
      <MemoryRouter initialEntries={['/collections/COL001']}>
        <Routes>
          <Route path="/collections/:code" element={<CollectionPage />} />
          <Route path="/collections/:code/leave" element={<LeaveProbe />} />
        </Routes>
      </MemoryRouter>
    );
  }
  const digestPosts = () =>
    apiFetch.mock.calls.filter(([url, o]) => url === DIGEST_URL && o?.method === 'POST');
  const entries = () => [...panel().querySelectorAll('a, button')].map((e) => e.textContent.trim());

  test('a member gets the trigger, and the panel holds the document, the summary switch and leaving — nothing of a curator’s', async () => {
    renderMember(MEMBER);
    await openMenu();

    expect(entries()).toEqual(["The group's welcome document (PDF)", MUTE, LEAVE]);
    // A divider sits between what the group gives them and leaving it.
    const divider = panel().querySelector('.collection-menu-divider');
    expect(divider).not.toBeNull();
    expect(
      divider.compareDocumentPosition(within(panel()).getByRole('link', { name: LEAVE }))
    ).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    for (const curators of [
      'Add thing',
      'Add several at once (CSV)',
      'Manage members',
      'Invite many at once (CSV)',
    ]) {
      expect(within(panel()).queryByRole('link', { name: curators })).toBeNull();
    }
    expect(within(panel()).queryByRole('button', { name: /Download/ })).toBeNull();
  });

  test('the document opens in a new tab and says so to a screen reader', async () => {
    renderMember(MEMBER);
    await openMenu();

    const link = within(panel()).getByRole('link', { name: DOC_NAME });
    expect(link).toHaveAttribute('href', DOC);
    expect(link).toHaveAttribute('target', '_blank');
    expect(link).toHaveAttribute('rel', expect.stringContaining('noopener'));
    // The visible words first, then the sentence — the way "Ideas and bugs" says it.
    expect(link).toHaveAccessibleName("The group's welcome document (PDF). Opens in a new tab.");
  });

  test('the hero no longer carries the document: it is in the menu only', async () => {
    const { container } = renderMember(MEMBER);
    await screen.findByText('Drill');

    // Closed: no link to it anywhere on the page…
    expect(container.querySelector(`a[href="${DOC}"]`)).toBeNull();
    await openMenu();
    // …open: one, inside the panel.
    const links = container.querySelectorAll(`a[href="${DOC}"]`);
    expect(links).toHaveLength(1);
    expect(panel()).toContainElement(links[0]);
    expect(container.querySelector('.form-hero .invite-nudge')).toBeNull();
  });

  test('without a document there is no entry for it', async () => {
    renderMember({ ...MEMBER, welcome_doc_url: '' });
    await openMenu();

    expect(entries()).toEqual([MUTE, LEAVE]);
  });

  test('a group that sends no summary offers nothing to mute', async () => {
    renderMember({ ...MEMBER, digest_frequency: 'NONE' });
    await openMenu();

    expect(entries()).toEqual(["The group's welcome document (PDF)", LEAVE]);
  });

  test('with neither, "Leave the group" is the only entry and there is no divider above it', async () => {
    renderMember({ ...MEMBER, welcome_doc_url: '', digest_frequency: 'NONE' });
    await openMenu();

    expect(entries()).toEqual([LEAVE]);
    expect(panel().querySelector('.collection-menu-divider')).toBeNull();
  });

  test('muting POSTs { muted: true }, says so, and the entry now offers to turn it back on', async () => {
    renderMember(MEMBER);
    await openMenu();

    fireEvent.click(within(panel()).getByRole('button', { name: MUTE }));

    expect(
      await screen.findByText("Done: you won't get this group's summaries any more.")
    ).toBeInTheDocument();
    expect(digestPosts()).toHaveLength(1);
    expect(JSON.parse(digestPosts()[0][1].body)).toEqual({ muted: true });
    // It closed the panel and left the focus on the trigger, like a download.
    expect(panel()).toBeNull();
    expect(screen.getByRole('button', { name: TRIGGER })).toHaveFocus();

    await openMenu();
    expect(within(panel()).getByRole('button', { name: UNMUTE })).toBeInTheDocument();
    expect(within(panel()).queryByRole('button', { name: MUTE })).toBeNull();
  });

  test('turning it back on POSTs { muted: false } and says so', async () => {
    renderMember({ ...MEMBER, is_digest_muted: true });
    await openMenu();

    fireEvent.click(within(panel()).getByRole('button', { name: UNMUTE }));

    expect(
      await screen.findByText("Done: you'll get this group's summaries again.")
    ).toBeInTheDocument();
    expect(JSON.parse(digestPosts()[0][1].body)).toEqual({ muted: false });
    await openMenu();
    expect(within(panel()).getByRole('button', { name: MUTE })).toBeInTheDocument();
  });

  // The team's switch is in the same menu, but `is_member` is false for it, so the
  // member's block (and its status zone) is not rendered: the answer has its own
  // place under the team's row.
  const FOUNDER = { ...COLLECTION, digest_frequency: 'WEEKLY', is_digest_muted: false };
  const CO_CURATOR = {
    ...FOUNDER,
    owner: 'OTHER1',
    owner_name: 'Owner',
    co_owners: [{ code: 'ABC123', name: 'Me' }],
  };

  test.each([
    ['the founder', FOUNDER],
    ['a co-curator', CO_CURATOR],
  ])('%s who mutes the summary is told it worked', async (_who, view) => {
    renderMember(view);
    await openMenu();

    fireEvent.click(within(panel()).getByRole('button', { name: MUTE }));

    expect(
      await screen.findByText("Done: you won't get this group's summaries any more.")
    ).toBeInTheDocument();
    expect(JSON.parse(digestPosts()[0][1].body)).toEqual({ muted: true });
  });

  test.each([
    ['the founder', FOUNDER],
    ['a co-curator', CO_CURATOR],
  ])('%s whose mute fails is told it did not', async (_who, view) => {
    renderMember(view, {
      digest: () => ({ ok: false, status: 500, json: () => Promise.resolve({}) }),
    });
    await openMenu();

    fireEvent.click(within(panel()).getByRole('button', { name: MUTE }));

    expect(
      await screen.findByText("We couldn't change that. Please try again.")
    ).toBeInTheDocument();
  });

  test.each([
    [
      'the server refuses',
      () => ({ ok: false, status: 500, json: () => Promise.resolve({}) }),
      "We couldn't change that. Please try again.",
    ],
    [
      'the hourly limit is hit',
      () => ({ ok: false, status: 429, json: () => Promise.resolve({}) }),
      'Too many attempts — please wait a moment and try again.',
    ],
    [
      'the request never arrives',
      () => Promise.reject(new TypeError('Failed to fetch')),
      'Connection error.',
    ],
  ])('when %s it says so and the entry stays as it was', async (_what, digest, message) => {
    renderMember(MEMBER, { digest });
    await openMenu();

    fireEvent.click(within(panel()).getByRole('button', { name: MUTE }));

    expect(await screen.findByText(message)).toBeInTheDocument();
    await openMenu();
    expect(within(panel()).getByRole('button', { name: MUTE })).toBeInTheDocument();
    expect(within(panel()).queryByRole('button', { name: UNMUTE })).toBeNull();
  });

  test('no POST happens until it is pressed', async () => {
    renderMember(MEMBER);
    await openMenu();

    expect(digestPosts()).toHaveLength(0);
  });

  test('"Leave the group" goes to the leave page with the group’s name', async () => {
    renderMember(MEMBER);
    await openMenu();

    fireEvent.click(within(panel()).getByRole('link', { name: LEAVE }));

    expect(await screen.findByTestId('leave-page')).toHaveTextContent('Tool library');
  });

  test('a curator keeps their own menu, with the document first when there is one — and no leaving', async () => {
    renderCollection({ ...COLLECTION, welcome_doc_url: DOC, digest_frequency: 'WEEKLY' });
    await openMenu();

    expect(entries().slice(0, 6)).toEqual([
      "The group's welcome document (PDF)",
      'Add thing',
      'Add several at once (CSV)',
      'Manage members',
      en.organisation.menuEntry,
      'Invite many at once (CSV)',
    ]);
    expect(within(panel()).queryByRole('link', { name: LEAVE })).toBeNull();
  });

  test('a curator can silence the summary they now receive: it is the last entry, after a divider', async () => {
    renderMember({ ...COLLECTION, digest_frequency: 'WEEKLY' });
    await openMenu();

    expect(entries().at(-1)).toBe(MUTE);
    expect(panel().querySelectorAll('.collection-menu-divider').length).toBeGreaterThan(0);
  });

  test.each([
    ['the founder', COLLECTION],
    [
      'a co-curator',
      { ...COLLECTION, owner: 'OTHER1', co_owners: [{ code: 'ABC123', name: 'Me' }] },
    ],
  ])(
    'a group with no weekly summary still offers %s the switch: the sign-ups email reaches them anyway',
    async (_who, view) => {
      renderMember({ ...view, digest_frequency: 'NONE' });
      await openMenu();

      expect(entries().at(-1)).toBe(MUTE);
    }
  );

  test('a member of that same group is offered nothing to mute: they get no summary at all', async () => {
    renderMember({ ...MEMBER, digest_frequency: 'NONE', welcome_doc_url: '' });
    await openMenu();

    expect(within(panel()).queryByRole('button', { name: MUTE })).toBeNull();
    expect(within(panel()).queryByRole('button', { name: UNMUTE })).toBeNull();
  });

  test('a curator silences it: the POST goes, the entry flips, and a muted one offers the way back', async () => {
    renderMember({ ...COLLECTION, digest_frequency: 'WEEKLY' });
    await openMenu();

    fireEvent.click(within(panel()).getByRole('button', { name: MUTE }));

    await waitFor(() => expect(digestPosts()).toHaveLength(1));
    expect(JSON.parse(digestPosts()[0][1].body)).toEqual({ muted: true });
    await openMenu();
    expect(within(panel()).getByRole('button', { name: UNMUTE })).toBeInTheDocument();
  });

  test('a curator who had muted it is offered to turn it back on', async () => {
    renderMember({ ...COLLECTION, digest_frequency: 'WEEKLY', is_digest_muted: true });
    await openMenu();

    expect(within(panel()).getByRole('button', { name: UNMUTE })).toBeInTheDocument();
    expect(within(panel()).queryByRole('button', { name: MUTE })).toBeNull();
  });

  test('a curator without a document has the menu it always had', async () => {
    renderCollection({ ...COLLECTION, welcome_doc_url: '' });
    await openMenu();

    expect(entries()[0]).toBe('Add thing');
    expect(within(panel()).queryByRole('link', { name: DOC_NAME })).toBeNull();
  });

  test('in a public group the corner reads account · collection menu · share, for a member too', async () => {
    const { container } = renderMember({ ...MEMBER, visibility: 'PUBLIC' });
    await screen.findByText('Drill');

    const account = screen.getByRole('button', { name: 'Your account' });
    const menu = screen.getByRole('button', { name: TRIGGER });
    const share = container.querySelector('.hero-corners .share-menu');
    expect(share).not.toBeNull();
    expect(account.compareDocumentPosition(menu)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
    expect(menu.compareDocumentPosition(share)).toBe(Node.DOCUMENT_POSITION_FOLLOWING);
  });

  test('no member of that group, no menu: a reader who is signed in but outside gets none', async () => {
    renderMember({ ...MEMBER, is_member: false, visibility: 'PUBLIC' });

    await screen.findByText('Drill');
    expect(screen.queryByRole('button', { name: TRIGGER })).not.toBeInTheDocument();
  });

  test('a reader with no session gets none either, whatever the payload says', async () => {
    localStorage.removeItem('userCode');
    renderMember({ ...MEMBER, visibility: 'PUBLIC' });

    await screen.findByText('Drill');
    expect(screen.queryByRole('button', { name: TRIGGER })).not.toBeInTheDocument();
  });
});

/**
 * "Requests to me" moved here from the account menu on the collection's page:
 * the first entry of the menu — a curator's and a member's — for
 * whoever receives requests, with a divider under it, and out of the account menu.
 * Everywhere else the account menu keeps it. The question is asked as it always was:
 * when the panel opens, and no answer means no link.
 */
describe('the collection menu — "Requests to me"', () => {
  const MEMBER = {
    ...COLLECTION,
    owner: 'OTHER1',
    owner_name: 'Owner',
    is_curator: false,
    is_member: true,
    digest_frequency: 'NONE',
    welcome_doc_url: '',
  };
  const REQUESTS = 'Requests to me';

  /** The page, with `GET /auth/me/` answering what the test says (or failing). */
  function renderReceiving(collection, me) {
    setApi(collection);
    const base = apiFetch.getMockImplementation();
    apiFetch.mockImplementation((url, options) =>
      url === '/api/v1/auth/me/'
        ? answer(me, () => ({
            ok: true,
            status: 200,
            json: () => Promise.resolve({ receives_requests: false }),
          }))
        : base(url, options)
    );
    return renderPage();
  }
  const receives = (value) => ({
    ok: true,
    status: 200,
    json: () => Promise.resolve({ receives_requests: value }),
  });
  const entries = () => [...panel().querySelectorAll('a, button')].map((e) => e.textContent.trim());
  const meCalls = () => apiFetch.mock.calls.filter(([url]) => url === '/api/v1/auth/me/');

  test('a curator who receives requests has it first, with a divider under it', async () => {
    renderReceiving(COLLECTION, receives(true));
    await openMenu();

    await waitFor(() => expect(entries()[0]).toBe(REQUESTS));
    expect(within(panel()).getByRole('link', { name: REQUESTS })).toHaveAttribute(
      'href',
      '/owner-bookings'
    );
    // A divider directly under it, before the rest of the menu.
    const first = panel().firstElementChild;
    expect(first).toHaveTextContent(REQUESTS);
    expect(first.nextElementSibling).toHaveClass('collection-menu-divider');
    expect(entries().slice(1, 6)).toEqual([
      'Add thing',
      'Add several at once (CSV)',
      'Manage members',
      en.organisation.menuEntry,
      'Invite many at once (CSV)',
    ]);
  });

  test('a member who receives requests has it first too', async () => {
    renderReceiving(MEMBER, receives(true));
    await openMenu();

    await waitFor(() => expect(entries()[0]).toBe(REQUESTS));
    expect(panel().firstElementChild.nextElementSibling).toHaveClass('collection-menu-divider');
    expect(entries()).toContain('Leave the group');
  });

  test('somebody who receives none has the menu as it was, with no stray divider', async () => {
    renderReceiving(COLLECTION, receives(false));
    await openMenu();
    await waitFor(() => expect(meCalls().length).toBeGreaterThan(0));

    expect(within(panel()).queryByRole('link', { name: REQUESTS })).toBeNull();
    expect(entries()[0]).toBe('Add thing');
    expect(panel().firstElementChild).toHaveTextContent('Add thing');
  });

  test.each([
    ['an error status', { ok: false, status: 500, json: () => Promise.resolve({}) }],
    ['a request that never arrives', () => Promise.reject(new TypeError('Failed to fetch'))],
  ])('with %s there is no link: guessing would put a dead page in the menu', async (_what, me) => {
    renderReceiving(COLLECTION, me);
    await openMenu();
    await waitFor(() => expect(meCalls().length).toBeGreaterThan(0));

    expect(within(panel()).queryByRole('link', { name: REQUESTS })).toBeNull();
  });

  test('the server is asked when the panel opens, not before, and again each time', async () => {
    renderReceiving(COLLECTION, receives(true));
    await screen.findByText('Drill');
    expect(meCalls()).toHaveLength(0);

    await openMenu();
    await waitFor(() => expect(meCalls()).toHaveLength(1));
    fireEvent.keyDown(document, { key: 'Escape' });
    await openMenu();

    await waitFor(() => expect(meCalls()).toHaveLength(2));
  });

  test('on the collection page the account menu no longer offers it; the collection menu does', async () => {
    renderReceiving(COLLECTION, receives(true));
    await openMenu();
    await waitFor(() => expect(entries()[0]).toBe(REQUESTS));
    // Close this one, open the account menu (a click outside closes it).
    const accountTrigger = screen.getByRole('button', { name: 'Your account' });
    fireEvent.pointerDown(accountTrigger);
    await press(accountTrigger);

    expect(screen.getByRole('link', { name: 'My requests' })).toBeInTheDocument();
    await settle(apiFetch);
    expect(screen.queryByRole('link', { name: REQUESTS })).not.toBeInTheDocument();
  });

  test('a signed-in reader with no collection menu on that page keeps it in the account menu', async () => {
    // Neither curator nor member of a public group: no collection menu, so the link
    // must not vanish from both.
    renderReceiving(
      { ...MEMBER, is_member: false, visibility: 'PUBLIC', mode: 'COMMUNITY' },
      receives(true)
    );
    await screen.findByText('Drill');
    fireEvent.click(screen.getByRole('button', { name: 'Your account' }));

    expect(await screen.findByRole('link', { name: REQUESTS })).toHaveAttribute(
      'href',
      '/owner-bookings'
    );
  });
});
