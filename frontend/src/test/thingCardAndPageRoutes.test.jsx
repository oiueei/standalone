import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { vi, describe, test, expect, beforeEach } from 'vitest';

/**
 * Where the thing card and the thing page send people, what deciding a hold does from the
 * page, and how the page fails. `thingBooking.test.jsx` pins that each button EXISTS for the
 * right viewer and that a hold is requested; what it leaves is the wiring behind the others:
 * a click on Delete carries the way back to the next page in navigation state (that page has
 * no other way to know where "Cancel" goes), a date-based verb goes to the request page rather
 * than posting, an anonymous click goes to the join page, and the same owner buttons on
 * `ThingPage` — a second copy of the card's — actually call the endpoints.
 */

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  extractApiError: vi.fn(() => Promise.resolve('')),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import en from '../i18n/locales/en.json';
import { apiFetch } from '../services/api';
import { settle } from './settle';
import ThingLinkbox from '../components/ThingLinkbox';
import ThingPage from '../pages/ThingPage';
import declarePalette from './declarePalette';

const respond = (body, status = 200) =>
  Promise.resolve({ ok: status < 400, status, json: () => Promise.resolve(body) });

// Route apiFetch by URL. `thing` feeds the ThingPage detail fetch; `calendar` the owner's
// bookings; `booking` / `activate` override those single POSTs (a promise that never settles
// holds the in-flight state).
function setApi({
  thing = {},
  thingStatus = 200,
  calendar = [],
  booking = null,
  activate = null,
} = {}) {
  apiFetch.mockImplementation((url) => {
    if (/\/things\/[^/]+\/calendar\//.test(url)) return respond(calendar);
    if (/\/things\/[^/]+\/activate\//.test(url)) return activate ? activate() : respond({});
    if (/\/bookings\/[^/]+\/(accept|reject)\//.test(url)) return booking ? booking() : respond({});
    if (/\/things\/[^/]+\/faq\//.test(url)) return respond({ results: [] });
    if (/\/things\/[^/]+\/transfers\//.test(url)) return respond({ total_transfers: 0 });
    if (/\/things\/[^/]+\/request\//.test(url)) return respond({});
    if (/\/things\/[^/]+\//.test(url)) return respond(thing, thingStatus);
    return respond({});
  });
}

const makeThing = (overrides = {}) => ({
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
});

// Where a navigation ended, and the state it carried.
function Arrived() {
  const { pathname, search, state } = useLocation();
  return <output data-testid="arrived">{JSON.stringify({ at: pathname + search, state })}</output>;
}
const arrived = async () => JSON.parse((await screen.findByTestId('arrived')).textContent);

const renderCard = (props) =>
  render(
    <MemoryRouter initialEntries={['/']}>
      <Routes>
        <Route path="/" element={<ThingLinkbox onUpdateThing={() => {}} {...props} />} />
        <Route path="*" element={<Arrived />} />
      </Routes>
    </MemoryRouter>
  );

const renderPage = (entry = '/things/THG001') =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/things/:thingCode" element={<ThingPage />} />
        <Route path="/collections/:code/things/:thingCode" element={<ThingPage />} />
        <Route path="*" element={<Arrived />} />
      </Routes>
    </MemoryRouter>
  );

const postsTo = (pattern) =>
  apiFetch.mock.calls.filter(([url, options]) => pattern.test(url) && options?.method === 'POST');

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'OWNER1');
  vi.clearAllMocks();
  setApi();
});

// ════════════════════════════════════════════════════════════════════════
// The card
// ════════════════════════════════════════════════════════════════════════
describe('ThingLinkbox — Delete hands the next page the way back', () => {
  // DeleteThingPage's Cancel, and its own "back" after deleting, go where `backPath` says;
  // with no state it has nowhere to send anybody.
  test.each([
    ['ACTIVE', 'ACTIVE'],
    ['INACTIVE', 'INACTIVE'],
  ])('a %s thing, from inside a collection', async (status) => {
    renderCard({
      thing: makeThing({ status }),
      userCode: 'OWNER1',
      collectionCode: 'COL001',
      collectionHeadline: 'Kitchen',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    expect(await arrived()).toEqual({
      at: '/collections/COL001/things/THG001/delete',
      state: { backPath: '/collections/COL001', backLabel: 'Kitchen' },
    });
  });

  test('from the home dashboard (no collection) the way back is Home', async () => {
    renderCard({ thing: makeThing({ status: 'ACTIVE' }), userCode: 'OWNER1' });

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    expect(await arrived()).toEqual({
      at: '/things/THG001/delete',
      state: { backPath: '/', backLabel: en.common.home },
    });
  });

  test('a collection whose name is not known yet is still called "Collection"', async () => {
    renderCard({
      thing: makeThing({ status: 'ACTIVE' }),
      userCode: 'OWNER1',
      collectionCode: 'COL001',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    expect((await arrived()).state).toEqual({
      backPath: '/collections/COL001',
      backLabel: en.common.collection,
    });
  });

  test("the collection's owner can delete a member's contribution — and only that", async () => {
    // COMMUNITY: the thing is somebody else's, so the owner matrix is not theirs to see.
    renderCard({
      thing: makeThing({ owner: 'MEMBER9', status: 'ACTIVE' }),
      userCode: 'OWNER1',
      collectionOwner: 'OWNER1',
      collectionCode: 'COL001',
      collectionHeadline: 'Kitchen',
    });

    expect(screen.queryByRole('link', { name: 'Edit' })).not.toBeInTheDocument();
    fireEvent.click(screen.getByRole('button', { name: 'Delete' }));

    expect(await arrived()).toEqual({
      at: '/collections/COL001/things/THG001/delete',
      state: { backPath: '/collections/COL001', backLabel: 'Kitchen' },
    });
  });
});

describe('ThingLinkbox — the other viewers’ clicks', () => {
  test('a date-based verb opens the request page, not a direct hold', async () => {
    renderCard({
      thing: makeThing({ type: 'LEND_THING', owner: 'OTHER1' }),
      userCode: 'GUEST1',
      collectionCode: 'COL001',
      collectionHeadline: 'Kitchen',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Borrow' }));

    expect(await arrived()).toEqual({
      at: '/collections/COL001/things/THG001/request',
      state: { backPath: '/collections/COL001', backLabel: 'Kitchen' },
    });
    expect(postsTo(/\/request\//)).toHaveLength(0);
  });

  test('without a collection the request page’s way back is Home', async () => {
    renderCard({ thing: makeThing({ type: 'RENT_THING', owner: 'OTHER1' }), userCode: 'GUEST1' });

    fireEvent.click(screen.getByRole('button', { name: 'Rent' }));

    expect(await arrived()).toEqual({
      at: '/things/THG001/request',
      state: { backPath: '/', backLabel: en.common.home },
    });
  });

  test('an anonymous reader is sent to join, carrying the thing and the group’s name', async () => {
    localStorage.removeItem('userCode');
    renderCard({
      thing: makeThing({ owner: 'OTHER1' }),
      userCode: null,
      loginToAct: true,
      collectionCode: 'PUB001',
      collectionHeadline: 'Kitchen',
    });

    fireEvent.click(screen.getByRole('button', { name: 'Claim' }));

    expect(await arrived()).toEqual({
      at: '/collections/PUB001/join?thing=THG001',
      // The join page names the group from this; a refreshed URL falls back to fetching it.
      state: { collectionHeadline: 'Kitchen' },
    });
    expect(postsTo(/\/request\//)).toHaveLength(0);
  });

  test('a failed hold shows why, and the message can be dismissed', async () => {
    apiFetch.mockImplementation((url) =>
      /\/request\//.test(url) ? respond({}, 500) : respond({ results: [] })
    );
    renderCard({ thing: makeThing({ owner: 'OTHER1' }), userCode: 'GUEST1' });

    fireEvent.click(screen.getByRole('button', { name: 'Claim' }));
    const close = await screen.findByRole('button', { name: en.common.close });

    fireEvent.click(close);

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: en.common.close })).not.toBeInTheDocument()
    );
  });
});

describe('ThingLinkbox — photos', () => {
  const carousel = () => screen.queryByRole('group', { name: en.thingPage.galleryLabel });

  test('several photos are browsable in the card, each click still going to the thing', () => {
    renderCard({
      thing: makeThing({ thumbnail_url: 'cover.jpg', gallery_urls: ['g1.jpg', 'g2.jpg'] }),
      userCode: 'GUEST1',
      collectionCode: 'COL001',
    });

    expect(carousel()).toBeInTheDocument();
    expect(screen.getByRole('button', { name: en.thingPage.galleryNext })).toBeInTheDocument();
  });

  test('one photo is a plain image that is not a second stop to the same place', () => {
    renderCard({
      thing: makeThing({ thumbnail_url: 'cover.jpg' }),
      userCode: 'GUEST1',
      collectionCode: 'COL001',
    });

    expect(carousel()).not.toBeInTheDocument();
    // The headline is the real link; the photo's own one steps out of the tab order and the
    // accessibility tree, and its alt empties with it (announced once, by the headline).
    const photo = document.querySelector('img[src="cover.jpg"]');
    expect(photo).toHaveAttribute('alt', '');
    expect(photo.closest('a')).toHaveAttribute('tabindex', '-1');
    expect(photo.closest('a')).toHaveAttribute('aria-hidden', 'true');
    expect(photo.closest('a')).toHaveAttribute('href', '/collections/COL001/things/THG001');
  });

  test('no photo, no frame', () => {
    renderCard({ thing: makeThing(), userCode: 'GUEST1' });

    expect(carousel()).not.toBeInTheDocument();
    expect(document.querySelector('.thing-card img')).toBeNull();
  });
});

// ════════════════════════════════════════════════════════════════════════
// The page
// ════════════════════════════════════════════════════════════════════════
describe('ThingPage — how it fails to load', () => {
  test.each([
    [403, en.thingPage.noPermission],
    [404, en.thingPage.notFound],
    [500, en.thingPage.errorLoading],
  ])('a %i says why, with a way home', async (status, message) => {
    setApi({ thing: {}, thingStatus: status });

    renderPage();

    expect(await screen.findByText(message)).toBeInTheDocument();
    // The hero's back link; a 403 has a second Home, the button below the message.
    expect(screen.getAllByRole('link', { name: en.common.home })[0]).toHaveAttribute('href', '/');
  });

  test('a 403 is a notice titled for the reader, not an "Error"', async () => {
    setApi({ thing: {}, thingStatus: 403 });

    renderPage();

    expect(
      await screen.findByRole('heading', { level: 1, name: "You can't see this thing" })
    ).toBeInTheDocument();
    expect(screen.getByText(en.common.notice)).toBeInTheDocument();
    expect(screen.queryByText(en.common.error)).not.toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe(en.titles.thingDefault));
  });

  test.each([404, 500])('a %i is still an "Error"', async (status) => {
    setApi({ thing: {}, thingStatus: status });

    renderPage();

    expect(
      await screen.findByRole('heading', { level: 1, name: en.common.error })
    ).toBeInTheDocument();
    expect(screen.queryByText("You can't see this thing")).not.toBeInTheDocument();
  });

  describe('a refusal leaves a way out', () => {
    const THEEEME = {
      color_01: 'bus',
      color_02: 'white',
      color_03: 'bus-light',
      color_04: 'black',
      color_06: 'white',
    };
    const wayOut = (container) => container.querySelector('.button-row-wide a');

    test('with a session it is a secondary button to Home', async () => {
      declarePalette(THEEEME);
      setApi({ thing: {}, thingStatus: 403 });
      const { container } = renderPage();
      await screen.findByText(en.thingPage.noPermission);

      const link = wayOut(container);
      expect(link).toHaveTextContent(en.common.home);
      expect(link).toHaveAttribute('href', '/');
      expect(link.className).toMatch(/hds-button/);
      expect(link.style.getPropertyValue('--background-color')).toBe('var(--color-white)');
      expect(link.style.getPropertyValue('--border-color')).toBe('var(--color-bus)');
      expect(screen.queryByRole('link', { name: en.login.signIn })).toBeNull();
    });

    test('without one it is a primary Sign in that brings them back to this thing', async () => {
      localStorage.removeItem('userCode');
      declarePalette(THEEEME);
      setApi({ thing: {}, thingStatus: 403 });
      const { container } = renderPage('/collections/COL001/things/THG001');
      await screen.findByText(en.thingPage.noPermission);

      const link = wayOut(container);
      expect(link).toHaveTextContent(en.login.signIn);
      expect(link).toHaveAttribute('href', '/login?next=%2Fcollections%2FCOL001%2Fthings%2FTHG001');
      expect(link.style.getPropertyValue('--background-color')).toBe('var(--color-bus)');
    });

    test.each([[404], [500]])(
      'a %i has no such row: access is not what is wrong',
      async (status) => {
        setApi({ thing: {}, thingStatus: status });
        const { container } = renderPage();
        await screen.findByRole('heading', { level: 1 });

        expect(wayOut(container)).toBeNull();
      }
    );
  });

  test('a request that never arrives says the connection is down', async () => {
    apiFetch.mockImplementation((url) =>
      /\/things\/[^/]+\/$/.test(url) ? Promise.reject(new Error('offline')) : respond({})
    );

    renderPage();

    expect(await screen.findByText(en.common.connectionError)).toBeInTheDocument();
  });
});

describe('ThingPage — Delete hands the next page the way back', () => {
  test.each([['ACTIVE'], ['INACTIVE']])(
    'a %s thing on the standalone route goes back to its collection',
    async (status) => {
      setApi({
        thing: makeThing({
          status,
          collection_code: 'COL001',
          collection_headline: 'Kitchen',
        }),
      });
      renderPage('/things/THG001');

      fireEvent.click(await screen.findByRole('button', { name: 'Delete' }));

      expect(await arrived()).toEqual({
        at: '/things/THG001/delete',
        state: { backPath: '/collections/COL001', backLabel: 'Kitchen' },
      });
    }
  );

  test('inside a collection the delete page keeps that context', async () => {
    setApi({ thing: makeThing({ collection_code: 'COL001', collection_headline: 'Kitchen' }) });
    renderPage('/collections/COL001/things/THG001');

    fireEvent.click(await screen.findByRole('button', { name: 'Delete' }));

    expect(await arrived()).toEqual({
      at: '/collections/COL001/things/THG001/delete',
      state: { backPath: '/collections/COL001', backLabel: 'Kitchen' },
    });
  });

  test("the collection's owner deleting a member's contribution is offered only that", async () => {
    setApi({
      thing: makeThing({
        owner: 'MEMBER9',
        collection_owner: 'OWNER1',
        collection_code: 'COL001',
        collection_headline: 'Kitchen',
      }),
    });
    renderPage('/things/THG001');

    const remove = await screen.findByRole('button', { name: 'Delete' });
    expect(screen.queryByRole('link', { name: 'Edit' })).not.toBeInTheDocument();
    fireEvent.click(remove);

    expect(await arrived()).toEqual({
      at: '/things/THG001/delete',
      state: { backPath: '/collections/COL001', backLabel: 'Kitchen' },
    });
  });
});

describe('ThingPage — the buttons of a date-based thing act on the pending hold', () => {
  const pendingLoan = () => {
    setApi({
      thing: makeThing({ type: 'LEND_THING', status: 'ACTIVE' }),
      calendar: [{ code: 'BK1', status: 'PENDING', end_date: '2099-12-31' }],
    });
  };

  test('Confirm request accepts that booking', async () => {
    pendingLoan();
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Confirm request' }));

    await waitFor(() => expect(postsTo(/\/bookings\/BK1\/accept\//)).toHaveLength(1));
    expect(postsTo(/\/reject\//)).toHaveLength(0);
  });

  test('Decline request rejects it, and says so while it does', async () => {
    let release;
    setApi({
      thing: makeThing({ type: 'LEND_THING', status: 'ACTIVE' }),
      calendar: [{ code: 'BK1', status: 'PENDING', end_date: '2099-12-31' }],
      booking: () => new Promise((resolve) => (release = resolve)),
    });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: 'Decline request' }));

    // In flight: the label says what is happening and neither button can be pressed again.
    // It is the manager *declining* a request, in the words es/ca already used
    // ("Rechazando..."); "Cancelling..." said it was the requester withdrawing one.
    const cancelling = await screen.findByRole('button', { name: 'Declining...' });
    expect(cancelling).toBeDisabled();
    expect(screen.getByRole('button', { name: 'Confirm request' })).toBeDisabled();
    expect(postsTo(/\/bookings\/BK1\/reject\//)).toHaveLength(1);
    // Let the held request answer inside `act`, so the page's reply lands in the test.
    release(await respond({}));
    await settle(apiFetch);
  });
});

describe('ThingPage — a requested gift or sale', () => {
  test('Decline request puts the request back to the requester, rejecting that booking', async () => {
    setApi({
      thing: makeThing({ type: 'GIFT_THING', status: 'TAKEN' }),
      calendar: [{ code: 'BK2', status: 'PENDING', requester_name: 'Guest One' }],
    });
    renderPage();
    // The buttons are there at once (the thing is TAKEN); which booking they act on arrives
    // with the calendar. Pressed before that they would answer for nobody.
    await screen.findByText(/Guest One/);

    fireEvent.click(screen.getByRole('button', { name: 'Decline request' }));

    await waitFor(() => expect(postsTo(/\/bookings\/BK2\/reject\//)).toHaveLength(1));
    expect(postsTo(/\/accept\//)).toHaveLength(0);
  });
});

describe('ThingPage — the rest of the owner’s and the guest’s buttons', () => {
  test('Reactivate says so while it works, and cannot be pressed twice', async () => {
    let release;
    setApi({
      thing: makeThing({ status: 'INACTIVE' }),
      activate: () => new Promise((resolve) => (release = resolve)),
    });
    renderPage();

    fireEvent.click(await screen.findByRole('button', { name: en.thingCard.reactivate }));

    const working = await screen.findByRole('button', { name: en.thingCard.reactivating });
    expect(working).toBeDisabled();
    expect(postsTo(/\/activate\//)).toHaveLength(1);
    // Let the held request answer inside `act`, so the page's reply lands in the test.
    release(await respond({}));
    await settle(apiFetch);
  });

  test('a guest’s date-based verb opens the request page with the way back to this thing', async () => {
    localStorage.setItem('userCode', 'GUEST1');
    setApi({
      thing: makeThing({ type: 'LEND_THING', owner: 'OTHER1', headline: 'Ladder' }),
    });
    renderPage('/collections/COL001/things/THG001');

    fireEvent.click(await screen.findByRole('button', { name: 'Borrow' }));

    expect(await arrived()).toEqual({
      at: '/collections/COL001/things/THG001/request',
      state: { backPath: '/collections/COL001/things/THG001', backLabel: 'Ladder' },
    });
    expect(postsTo(/\/request\//)).toHaveLength(0);
  });

  test('a failed hold’s message can be dismissed', async () => {
    localStorage.setItem('userCode', 'GUEST1');
    setApi({ thing: makeThing({ owner: 'OTHER1' }) });
    renderPage();
    const claim = await screen.findByRole('button', { name: 'Claim' });
    apiFetch.mockImplementation((url) =>
      /\/request\//.test(url) ? respond({}, 500) : respond({ results: [] })
    );

    fireEvent.click(claim);
    fireEvent.click(await screen.findByRole('button', { name: en.common.close }));

    await waitFor(() =>
      expect(screen.queryByRole('button', { name: en.common.close })).not.toBeInTheDocument()
    );
  });
});

describe('ThingPage — photos', () => {
  test('several photos are browsable', async () => {
    setApi({ thing: makeThing({ thumbnail_url: 'cover.jpg', gallery_urls: ['g1.jpg'] }) });
    renderPage();

    expect(
      await screen.findByRole('group', { name: en.thingPage.galleryLabel })
    ).toBeInTheDocument();
  });

  test('one photo is a plain image named by the thing', async () => {
    setApi({ thing: makeThing({ thumbnail_url: 'cover.jpg' }) });
    renderPage();

    expect(await screen.findByRole('img', { name: 'Test Thing' })).toHaveAttribute(
      'src',
      'cover.jpg'
    );
    expect(
      screen.queryByRole('group', { name: en.thingPage.galleryLabel })
    ).not.toBeInTheDocument();
  });
});
