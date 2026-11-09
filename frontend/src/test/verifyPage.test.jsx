import { render, screen, act, waitFor } from '@testing-library/react';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { StrictMode, useEffect } from 'react';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import VerifyPage from '../pages/VerifyPage';

// `useNavigate` gives a new function whenever the address moves (it is built from the
// location); this wrapper gives one on every render, which is the same property without
// depending on how a given router version memoises it.
vi.mock('react-router', async (orig) => {
  const actual = await orig();
  return {
    ...actual,
    useNavigate: () => {
      const navigate = actual.useNavigate();
      return (...args) => navigate(...args);
    },
  };
});
import i18n from '../i18n';
import { switchLanguage } from './settle';

// VerifyPage talks to the backend via raw `fetch` (not the apiFetch wrapper), so
// we drive both legs of the auto-commit (GET preview, POST commit) from here.
// The `requires_confirmation → POST` auto-commit and its
// `committedRef` StrictMode guard had zero behavioural coverage — the smoke
// test mocks fetch to 400, so this path never executed.

const CODE = 'RSVPTEST123';

function mockResponse(body, ok = true, status = 200) {
  return { ok, status, json: () => Promise.resolve(body) };
}

function renderVerify(wrapInStrictMode = false) {
  const tree = (
    <MemoryRouter initialEntries={[`/verify/${CODE}`]}>
      <Routes>
        <Route path="/verify/:code" element={<VerifyPage />} />
        {/* catch-all so the login/invite/user navigations don't crash */}
        <Route path="*" element={<div data-testid="navigated" />} />
      </Routes>
    </MemoryRouter>
  );
  return render(wrapInStrictMode ? <StrictMode>{tree}</StrictMode> : tree);
}

const postCalls = (mock) => mock.mock.calls.filter(([, opts]) => opts?.method === 'POST');
const getCalls = (mock) => mock.mock.calls.filter(([, opts]) => !opts?.method);

describe('VerifyPage auto-commit', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('commits a booking ACCEPT with a single POST when GET requires confirmation', async () => {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({ action: 'BOOKING_ACCEPT' }))
        : Promise.resolve(mockResponse({ requires_confirmation: true }))
    );

    renderVerify();

    expect(await screen.findByText('The request has been confirmed!')).toBeInTheDocument();
    expect(screen.getByText('Confirmed!')).toBeInTheDocument();

    // One preview GET + exactly one committing POST — nothing more.
    expect(getCalls(globalThis.fetch)).toHaveLength(1);
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
    expect(globalThis.fetch.mock.calls[1][0]).toBe(`/api/v1/auth/verify/${CODE}/`);
  });

  test('commits a booking REJECT and shows the rejected screen', async () => {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({ action: 'BOOKING_REJECT' }))
        : Promise.resolve(mockResponse({ requires_confirmation: true }))
    );

    renderVerify();

    expect(await screen.findByText('The request has been declined.')).toBeInTheDocument();
    expect(screen.getByText('Rejected')).toBeInTheDocument();
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
  });

  test('treats an unknown commit action as an invalid/expired link', async () => {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({ action: 'SOMETHING_ELSE' }))
        : Promise.resolve(mockResponse({ requires_confirmation: true }))
    );

    renderVerify();

    expect(await screen.findByText('Invalid or expired link.')).toBeInTheDocument();
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
  });

  test('the way out of a failed link sits in a wide row, so on a phone it is the width of the screen', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(mockResponse({ error: 'expired' }, false, 400)));

    renderVerify();

    const exit = await screen.findByRole('link', { name: 'Go to login' });
    expect(exit.parentElement).toHaveClass('button-row-wide');
  });

  test('never commits when the GET preview is non-OK (expired link)', async () => {
    globalThis.fetch = vi.fn(() => Promise.resolve(mockResponse({ error: 'expired' }, false, 400)));

    renderVerify();

    expect(await screen.findByText('Invalid or expired link.')).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1); // the GET only — no POST
    expect(postCalls(globalThis.fetch)).toHaveLength(0);
  });

  test('never commits when the GET request throws (offline)', async () => {
    globalThis.fetch = vi.fn(() => Promise.reject(new Error('network down')));

    renderVerify();

    expect(await screen.findByText('Connection error.')).toBeInTheDocument();
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
    expect(postCalls(globalThis.fetch)).toHaveLength(0);
  });

  test('StrictMode double-invoke fires the committing POST exactly once', async () => {
    // StrictMode (dev build) mounts → runs the effect twice. committedRef must
    // keep the irreversible booking-decision POST to a single fire even though
    // the effect runs twice; the link itself is asked for once (`redeemedRef`).
    // Method-keyed mock so the assertion is robust to the async interleaving.
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse({ action: 'BOOKING_ACCEPT' }))
        : Promise.resolve(mockResponse({ requires_confirmation: true }))
    );

    renderVerify(true);

    expect(await screen.findByText('The request has been confirmed!')).toBeInTheDocument();
    // The preview GET and the commit POST each went out exactly once.
    expect(getCalls(globalThis.fetch)).toHaveLength(1);
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
  });
});

/**
 * Every refusal this page can meet consumes its RSVP — the booking is already
 * decided, the suggestion is already answered — except one. An approval the
 * deployment's daily invitation cap or the group's member ceiling turns down
 * leaves the proposal pending and both links alive **on purpose**: "not now",
 * so the owner can answer tomorrow. The page showed that as "Invalid or expired
 * link", which is the one thing it is not, and the owner it was telling to stop
 * clicking had no other route back to the decision.
 *
 * `retryable` is the server's word for which of the two this is (it is not
 * inferable from the status: a full collection and a settled suggestion both
 * answer 400), so both halves are pinned here — the one that survives and the
 * one that really is over.
 */
describe('a refusal the link survives', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  const previewApprove = { requires_confirmation: true, action: 'PROPOSAL_APPROVE' };

  function mockRefusal(body, status) {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse(body, false, status))
        : Promise.resolve(mockResponse(previewApprove))
    );
  }

  test('shows the server’s reason and says the link still works', async () => {
    mockRefusal(
      { error: 'Daily invitation limit reached. Try again tomorrow.', retryable: true },
      429
    );

    renderVerify();

    expect(
      await screen.findByText('Daily invitation limit reached. Try again tomorrow.')
    ).toBeInTheDocument();
    // Not "your link died": the owner is meant to come back to this same one.
    expect(screen.getByText(/this link still works/i)).toBeInTheDocument();
    expect(screen.queryByText('Invalid or expired link.')).toBeNull();
    expect(screen.queryByText(/ask the person who invited you/i)).toBeNull();
  });

  test('a full group is a reason too, not an expiry, on the same 400 as a dead link', async () => {
    mockRefusal(
      { error: 'This collection has reached its limit of 2 guests.', retryable: true },
      400
    );

    renderVerify();

    expect(
      await screen.findByText('This collection has reached its limit of 2 guests.')
    ).toBeInTheDocument();
    expect(screen.getByText(/this link still works/i)).toBeInTheDocument();
  });

  test('a suggestion that is genuinely over is still called a dead link', async () => {
    // Same 400, same shape, no `retryable`: this RSVP was consumed and the
    // decision already stands, so the old copy is the right one — and keeping
    // it right is what stops "the link still works" from being said always.
    mockRefusal({ error: 'This suggestion is no longer pending' }, 400);

    renderVerify();

    expect(await screen.findByText('Invalid or expired link.')).toBeInTheDocument();
    expect(screen.getByText(/ask the person who invited you/i)).toBeInTheDocument();
    expect(screen.queryByText(/this link still works/i)).toBeNull();
  });
});

/**
 * An approval turned down because the suggested person was already invited by email.
 * Unlike the daily cap or a full group it is not "not now": the block lasts a year, the
 * suggestion stays pending for a curator to decline, and the page must neither say the
 * link "still works, try again later" nor talk about asking whoever invited you.
 */
describe('an approval refused because the person was already invited', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(async () => {
    const { default: i18n } = await import('../i18n');
    await switchLanguage(i18n, 'en');
    localStorage.removeItem('i18nextLng');
  });

  function mockRefusal() {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(
            mockResponse(
              {
                error: 'This person has already been invited. They can join with the share link.',
                code: 'invite_already_asked',
              },
              false,
              400
            )
          )
        : Promise.resolve(mockResponse({ requires_confirmation: true, action: 'PROPOSAL_APPROVE' }))
    );
  }

  test.each([
    [
      'en',
      "This person has already had an invitation and can't get another by email. Send them the invitation link yourself.",
    ],
    [
      'es',
      'Esta persona ya recibió una invitación y no se le puede enviar otra por correo. Mándale tú el enlace de invitación.',
    ],
    [
      'ca',
      "Aquesta persona ja va rebre una invitació i no se n'hi pot enviar una altra per correu. Envia-li tu l'enllaç d'invitació.",
    ],
  ])('says it in %s, with no help line under it', async (language, sentence) => {
    const { default: i18n } = await import('../i18n');
    await switchLanguage(i18n, language);
    mockRefusal();

    renderVerify();

    expect(await screen.findByText(sentence)).toBeInTheDocument();
    expect(screen.queryByText(/This person has already been invited/)).toBeNull();
    for (const help of [i18n.t('verify.refusalHelp'), i18n.t('verify.expiredHelp')]) {
      expect(screen.queryByText(help)).toBeNull();
    }
    expect(screen.queryByText(/this link still works/i)).toBeNull();
  });
});

/**
 * The account's saved language is applied on sign-in, the way its theme and koro
 * already are. The one effect that applies it (`App.jsx`) runs
 * once, when the app mounts — and opening a magic link mounts the app *before*
 * there is a session, so its `/auth/me/` is a 401 and applies nothing. A person with
 * "English" saved, opening the link on a phone, got the app in the browser's
 * Spanish and kept it until a reload.
 */
describe('a magic link applies the saved language of the account', () => {
  const USER = { code: 'USR003', name: 'Lulu', email: 'lulu@your-domain.test' };

  // What language the page the person lands on is first painted in.
  const seen = { language: undefined };
  // `seen` is written by an effect, which runs AFTER the commit that paints "landed":
  // `findByText('landed')` can resolve first, and on a loaded machine (the whole suite
  // with coverage) it does, so reading `seen` straight after it read `undefined`.
  // Wait for the effect to have run — and only for that: the value is asserted after
  // this, not inside the wait, or a language that changes late would pass as good.
  const landed = async () => {
    await screen.findByText('landed');
    await waitFor(() => expect(seen.language).not.toBeUndefined());
  };
  function Landing() {
    useEffect(() => {
      seen.language = i18n.language;
    }, []);
    return <p>landed</p>;
  }

  function renderMagicLink(language) {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(
        mockResponse({ action: 'MAGIC_LINK', landing: 'home', user: { ...USER, language } })
      )
    );
    return render(
      <MemoryRouter initialEntries={[`/verify/${CODE}`]}>
        <Routes>
          <Route path="/verify/:code" element={<VerifyPage />} />
          <Route path="*" element={<Landing />} />
        </Routes>
      </MemoryRouter>
    );
  }

  beforeEach(async () => {
    localStorage.clear();
    seen.language = undefined;
    await switchLanguage(i18n, 'es');
    localStorage.clear();
  });
  afterEach(async () => {
    await switchLanguage(i18n, 'en');
    localStorage.removeItem('i18nextLng');
  });

  test('a saved language is in force before the person lands, and persists like the profile’s', async () => {
    renderMagicLink('ca');

    await landed();
    expect(seen.language).toBe('ca');
    expect(i18n.language).toBe('ca');
    // Kept for the next visit exactly as the profile page's own Select keeps it.
    expect(localStorage.getItem('i18nextLng')).toBe('ca');
  });

  test.each([
    ['empty ("Automatic")', ''],
    ['one this app does not speak', 'fr'],
    ['absent', undefined],
  ])('%s leaves the language alone', async (_what, language) => {
    renderMagicLink(language);

    await landed();
    expect(seen.language).toBe('es');
    expect(i18n.language).toBe('es');
  });

  test('the single-use link is redeemed once, even though signing in changes the language', async () => {
    // Changing the language gives `useTranslation` a new `t`; when the effect that
    // redeems the link depended on `t` it ran again, found the link spent and
    // showed an error to someone who had just signed in (and, with a server that
    // keeps saying yes, would never stop). The second call is answered as the
    // real server would: spent.
    let calls = 0;
    globalThis.fetch = vi.fn(() => {
      calls += 1;
      return Promise.resolve(
        calls === 1
          ? mockResponse({
              action: 'MAGIC_LINK',
              landing: 'home',
              user: { ...USER, language: 'ca' },
            })
          : mockResponse({ error: 'Invalid or expired link' }, false, 400)
      );
    });
    render(
      <MemoryRouter initialEntries={[`/verify/${CODE}`]}>
        <Routes>
          <Route path="/verify/:code" element={<VerifyPage />} />
          <Route path="*" element={<Landing />} />
        </Routes>
      </MemoryRouter>
    );

    await screen.findByText('landed');
    expect(getCalls(globalThis.fetch)).toHaveLength(1);
    expect(screen.queryByText('Invalid or expired link.')).toBeNull();
  });

  test('a language that cannot be loaded does not fail the sign-in', async () => {
    const change = vi.spyOn(i18n, 'changeLanguage').mockRejectedValueOnce(new Error('chunk 404'));
    renderMagicLink('ca');

    await screen.findByText('landed');
    expect(localStorage.getItem('userCode')).toBe('USR003');
    change.mockRestore();
  });
});

/**
 * A co-curator demoted after the email pressed "Confirm" on the old link.
 * The server refuses it, correctly, burns the link and leaves the request
 * pending — with a 403 that now carries `no_longer_manages`. The page used to say
 * "Invalid or expired link. If your link has expired, ask the person who invited
 * you…", which talks about invitations and is no use to a manager who just lost
 * the role. With the code it says why, and has no invitation help line to add.
 */
describe('a decision link its holder no longer manages', () => {
  beforeEach(() => {
    localStorage.clear();
  });
  afterEach(async () => {
    const { default: i18n } = await import('../i18n');
    await switchLanguage(i18n, 'en');
    localStorage.removeItem('i18nextLng');
  });

  function mockRefusal(body) {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse(body, false, 403))
        : Promise.resolve(mockResponse({ requires_confirmation: true }))
    );
  }

  test('says they no longer run the thing, with no invitation advice', async () => {
    mockRefusal({ error: 'Not authorized', code: 'no_longer_manages' });

    renderVerify();

    expect(
      await screen.findByText(
        'You no longer run this thing, so this link can no longer decide the request.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByText('Invalid or expired link.')).toBeNull();
    expect(screen.queryByText(/ask the person who invited you/i)).toBeNull();
    expect(screen.queryByText(/this link still works/i)).toBeNull();
  });

  test('without the code a 403 is as it was: an invalid or expired link', async () => {
    // A server that does not send the code yet, or a 403 for another reason.
    mockRefusal({ error: 'Not authorized' });

    renderVerify();

    expect(await screen.findByText('Invalid or expired link.')).toBeInTheDocument();
    expect(screen.getByText(/ask the person who invited you/i)).toBeInTheDocument();
  });

  test.each([
    [
      'es',
      'Ya no gestionas esta cosa, así que este enlace ya no sirve para decidir la solicitud.',
      /pide a quien te invitó/i,
    ],
    [
      'ca',
      'Ja no gestiones aquesta cosa, així que aquest enllaç ja no serveix per decidir la sol·licitud.',
      /demana a qui t'ha convidat/i,
    ],
  ])('says it in %s, again with no invitation advice', async (language, sentence, advice) => {
    const { default: i18n } = await import('../i18n');
    await switchLanguage(i18n, language);
    mockRefusal({ error: 'Not authorized', code: 'no_longer_manages' });

    renderVerify();

    expect(await screen.findByText(sentence)).toBeInTheDocument();
    expect(screen.queryByText(advice)).toBeNull();
  });
});

/**
 * Approving a suggestion is the third irreversible act on this page, and the
 * only one whose consequence lands on somebody who does not yet know they were
 * suggested: it mails a stranger an invitation. It rides the same auto-commit
 * as a booking decision — and therefore the same `committedRef` — so it owes
 * the same two guarantees, and nothing checked that it kept them.
 */
describe('the owner answering a member’s suggestion', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  const approvePreview = { requires_confirmation: true, action: 'PROPOSAL_APPROVE' };
  const approved = {
    action: 'PROPOSAL_APPROVE',
    message: 'Invitation sent',
    email: 'lolo1@your-domain.test',
    collection_headline: 'Toy library',
  };

  function mockDecision(body) {
    globalThis.fetch = vi.fn((url, opts = {}) =>
      opts.method === 'POST'
        ? Promise.resolve(mockResponse(body))
        : Promise.resolve(mockResponse(approvePreview))
    );
  }

  test('approving names the address that was just invited', async () => {
    mockDecision(approved);

    renderVerify();

    // Naming them is the point: the owner is being told who they let into the
    // group, not merely that something happened. A confirmation that said
    // "done" would leave them unable to spot the wrong address.
    expect(await screen.findByText(/lolo1@your-domain\.test/)).toBeInTheDocument();
    expect(screen.getByText('Confirmed!')).toBeInTheDocument();
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
  });

  test('declining says the suggested person was never contacted', async () => {
    // The reassurance is the message: saying no must not read as if a stranger
    // had already been emailed and then un-emailed.
    mockDecision({ action: 'PROPOSAL_REJECT', message: 'Suggestion declined' });

    renderVerify();

    expect(await screen.findByText(/never contacted/i)).toBeInTheDocument();
    expect(screen.getByText('Declined')).toBeInTheDocument();
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
  });

  test('StrictMode’s double mount never mails the invitation twice', async () => {
    // The booking decision has this test; approving needs its own, because what
    // a second commit costs here is a second email to somebody outside the app.
    mockDecision(approved);

    renderVerify(true);

    expect(await screen.findByText(/lolo1@your-domain\.test/)).toBeInTheDocument();
    expect(getCalls(globalThis.fetch)).toHaveLength(1); // the effect ran twice, the link was asked once
    expect(postCalls(globalThis.fetch)).toHaveLength(1);
  });
});

describe('declining an invitation from the email', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  test('is decided by the GET alone, and says the owner was told', async () => {
    // Unlike a booking, declining an invitation authorises nothing and takes
    // nothing away from anyone else, so it is safe on GET — which is exactly
    // why the page must not fire a commit of its own after it.
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(mockResponse({ action: 'COLLECTION_REJECT', message: 'Invitation declined' }))
    );

    renderVerify();

    expect(
      await screen.findByText('Invitation declined. The owner of the group has been told.')
    ).toBeInTheDocument();
    expect(screen.getByText('Declined')).toBeInTheDocument();
    expect(postCalls(globalThis.fetch)).toHaveLength(0);
  });
});

/**
 * The most-travelled path in the product — every sign-in goes through it — and
 * it had no test at all. Two separate things happen here: the session is
 * written into this browser, and the **server** decides where the person lands
 * (`landing`). It used to be decided in the page from `seenWelcome`, which
 * logout wipes, so every re-login looked like a first visit; the fix moved the
 * decision to the server and this is what keeps it there.
 */
describe('where a magic link lands', () => {
  const USER = {
    code: 'USR002',
    name: 'Lele',
    email: 'lele@your-domain.test',
    theeeme_colors: {
      color_01: 'bus',
      color_02: 'white',
      color_03: 'engel',
      color_04: 'black',
      color_05: 'black',
      color_06: 'white',
    },
    koro: 'beat',
  };

  function Landing() {
    const { pathname } = useLocation();
    return <p>{`landed on ${pathname}`}</p>;
  }

  function renderMagicLink(body) {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(mockResponse({ action: 'MAGIC_LINK', user: USER, ...body }))
    );
    return render(
      <MemoryRouter initialEntries={[`/verify/${CODE}`]}>
        <Routes>
          <Route path="/verify/:code" element={<VerifyPage />} />
          <Route path="*" element={<Landing />} />
        </Routes>
      </MemoryRouter>
    );
  }

  beforeEach(() => {
    localStorage.clear();
  });

  test('writes the session and drops an invited member on the collection', async () => {
    renderMagicLink({
      landing: 'collection',
      collection: 'COL001',
      invited_collection: 'COL001',
    });

    expect(await screen.findByText('landed on /collections/COL001')).toBeInTheDocument();
    expect(localStorage.getItem('userCode')).toBe('USR002');
    // The palette is not the account's any more: nothing of it is kept.
    expect(localStorage.getItem('theeemeColors')).toBeNull();
    expect(localStorage.getItem('koro')).toBeNull();
  });

  test('a returning member with one group lands on it', async () => {
    // Same landing, no invitation payload: the server sends a lone-collection
    // user straight to it.
    renderMagicLink({ landing: 'collection', collection: 'COL001' });

    expect(await screen.findByText('landed on /collections/COL001')).toBeInTheDocument();
  });

  test('a join that came from a "Reserve" click lands back on that thing', async () => {
    // The server sends `thing` when the join carried a thing code and it is
    // still a live thing in the collection — the visitor came to reserve it,
    // so drop them on it, not the grid.
    renderMagicLink({
      landing: 'collection',
      collection: 'COL001',
      invited_collection: 'COL001',
      thing: 'THG001',
    });

    expect(
      await screen.findByText('landed on /collections/COL001/things/THG001')
    ).toBeInTheDocument();
  });

  test('anyone else goes home', async () => {
    renderMagicLink({ landing: 'home' });

    expect(await screen.findByText('landed on /')).toBeInTheDocument();
  });

  test('a login that remembers where it was going lands on that page', async () => {
    // The session ran out on a thing; the server kept the path and sends it back
    // as `landing: "path"`, outranking the lone-collection landing.
    renderMagicLink({ landing: 'path', path: '/collections/COL001/things/THG001' });

    expect(
      await screen.findByText('landed on /collections/COL001/things/THG001')
    ).toBeInTheDocument();
    expect(localStorage.getItem('userCode')).toBe('USR002');
  });

  test.each(['//evil.com', 'https://evil.com', '/login', undefined])(
    'a path that is not somewhere to return to falls back to home (%s)',
    async (path) => {
      // The server checks it first; the page checks again because it is fed to
      // the router, and a value that fails goes home rather than anywhere odd.
      renderMagicLink({ landing: 'path', path });

      expect(await screen.findByText('landed on /')).toBeInTheDocument();
    }
  );

  /* There is no `landing: "welcome"` case: the server stopped answering it
     — someone who comes in by an open door lands where anyone
     with the same groups would — and a landing this page does not know goes home
     through the same `else` as `home`. */
});

describe('a stalled network', () => {
  beforeEach(() => {
    localStorage.clear();
  });

  afterEach(() => {
    vi.useRealTimers();
  });

  test('gives up after 15s instead of saying "Verifying…" forever', async () => {
    // The dead end this closes: a request that never answers used to leave the
    // page on its loading screen with no error, no way out and nothing to read.
    vi.useFakeTimers();
    globalThis.fetch = vi.fn(() => new Promise(() => {})); // never settles

    renderVerify();
    expect(screen.getByText('Verifying…')).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(15000);
    });

    expect(screen.getByText('Connection error.')).toBeInTheDocument();
    expect(screen.getByText('Oops')).toBeInTheDocument();
  });

  test('a screen waiting for the person is not replaced by an error 15s later', async () => {
    /* Asserted on the delete confirmation, and not on a success screen, because
       a success screen shadows the error one in the render order and would
       have passed with both guards (the `settled` flag and its `clearTimeout`)
       torn out — a green test proving nothing.

       Here it is visible, and it is the screen where a slow read is the
       *correct* behaviour: this one asks somebody to weigh deleting their
       account. A stale timer would take the question away mid-thought and
       replace it with a connection error for a connection that answered fine. */
    vi.useFakeTimers();
    globalThis.fetch = vi.fn(() =>
      Promise.resolve(
        mockResponse({
          action: 'ACCOUNT_DELETE',
          requires_confirmation: true,
          name: 'Lele',
          email: 'lele@your-domain.test',
          collections: 2,
          things: 5,
        })
      )
    );

    renderVerify();
    await act(async () => {}); // let the preview GET settle

    expect(screen.getByText('Delete your account?')).toBeInTheDocument();

    await act(async () => {
      vi.advanceTimersByTime(15000);
    });

    expect(screen.getByText('Delete your account?')).toBeInTheDocument();
    expect(screen.getByRole('button', { name: 'Delete my account forever' })).toBeInTheDocument();
    expect(screen.queryByText('Connection error.')).toBeNull();
  });
});

describe('a magic link is redeemed once, however the router moves under the page', () => {
  // Signing in navigates to the collection, whose page is a lazy chunk: while it loads
  // the verify page is still mounted and the address has already changed, which gives
  // `useNavigate` a new identity. An effect that depends on it ran again and asked for
  // the link a second time, spent, and painted "invalid or expired" for an instant.
  // `Routes` keeps the location it was given, so the page stays up as it does while the
  // chunk loads, and it renders again when the router's location moves under it.
  const STAYED = { pathname: `/verify/${CODE}`, search: '', hash: '', state: null, key: 'k' };

  test('after a sign-in that navigates, the link was asked for once and no error shows', async () => {
    localStorage.clear();
    // The first answer signs in; a link is single-use, so any later one finds it spent.
    let asked = 0;
    globalThis.fetch = vi.fn(() => {
      asked += 1;
      return Promise.resolve(
        asked === 1
          ? mockResponse({
              action: 'MAGIC_LINK',
              user: { code: 'USR002', name: 'Lele', email: 'lele@your-domain.test' },
              landing: 'collection',
              collection: 'COL001',
              collection_kind: 'LIBRARY',
            })
          : mockResponse({ error: 'spent' }, false, 400)
      );
    });
    render(
      <MemoryRouter initialEntries={[`/verify/${CODE}`]}>
        <Routes location={STAYED}>
          <Route path="/verify/:code" element={<VerifyPage />} />
        </Routes>
        <Landing />
      </MemoryRouter>
    );

    expect(await screen.findByText('landed on /library/COL001')).toBeInTheDocument();
    // Let whatever the navigation re-ran settle.
    await act(async () => {
      await new Promise((r) => setTimeout(r, 50));
    });

    expect(getCalls(globalThis.fetch)).toHaveLength(1);
    expect(screen.queryByText(/invalid or expired/i)).toBeNull();
  });
});

function Landing() {
  const { pathname } = useLocation();
  return <p>{`landed on ${pathname}`}</p>;
}
