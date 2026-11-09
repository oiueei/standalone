import { render, screen, waitFor, fireEvent } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

window.scrollTo = vi.fn();

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(() =>
    Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({}) })
  ),
  getCsrfToken: vi.fn(() => 'mock-csrf'),
}));

import i18n from '../i18n';
import { switchLanguage } from './settle';
import { apiFetch } from '../services/api';
import CollectionPage from '../pages/CollectionPage';
import HomePage from '../pages/HomePage';
import InboxNotifications from '../components/InboxNotifications';

const REQUEST_NOTIFICATION = {
  code: 'NOT001',
  type: 'BOOKING_REQUESTED',
  payload: {
    thing_headline: 'The drill',
    requester_name: 'Lele',
    booking_code: 'BKG001',
    thing_code: 'THG001',
    collection_code: 'COL001',
  },
  created: '2026-07-13T10:00:00Z',
};

// A notification from another collection: Home shows it, COL001's page must not.
const ELSEWHERE_NOTIFICATION = {
  code: 'NOT002',
  type: 'FAQ_QUESTION',
  payload: {
    thing_headline: 'A ladder',
    questioner_name: 'Lili',
    thing_code: 'THG009',
    collection_code: 'COL009',
  },
  created: '2026-07-13T09:00:00Z',
};

const COLLECTION = {
  code: 'COL001',
  headline: 'Toy library',
  description: 'Shared toys',
  status: 'ACTIVE',
  visibility: 'PRIVATE',
  mode: 'PROPRIETARY',
  owner: 'ABC123',
  owner_name: 'Test User',
  is_curator: true,
  thumbnail_url: '',
  tags: [],
  things: [],
  invites: [],
  is_paused: false,
  allowed_thing_types: [],
};

const USER = { code: 'ABC123', name: 'Test User', email: 'lala2@your-domain.test', koro: 'basic' };

const ok = (body) => Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve(body) });

/** Route by URL like the real API does — the inbox filter is the point of the test. */
function setApi() {
  apiFetch.mockImplementation((url) => {
    if (url.startsWith('/api/v1/inbox/?collection=')) return ok([REQUEST_NOTIFICATION]);
    if (url.startsWith('/api/v1/inbox/')) return ok([REQUEST_NOTIFICATION, ELSEWHERE_NOTIFICATION]);
    if (url.startsWith('/api/v1/auth/me/')) return ok(USER);
    if (url.startsWith('/api/v1/collections/COL001/')) return ok(COLLECTION);
    if (url.startsWith('/api/v1/collections/')) return ok({ results: [] });
    return ok([]);
  });
}

beforeEach(() => {
  localStorage.clear();
  localStorage.setItem('userCode', 'ABC123');
  vi.clearAllMocks();
  setApi();
});

const renderCollection = () =>
  render(
    <MemoryRouter initialEntries={['/collections/COL001']}>
      <Routes>
        <Route path="/collections/:code" element={<CollectionPage />} />
      </Routes>
    </MemoryRouter>
  );

describe('InboxNotifications', () => {
  test("the owner sees the collection's own notifications on its page", async () => {
    renderCollection();

    expect(await screen.findByText(/The drill/)).toBeInTheDocument();
    // Scoped: it asked the API for this collection only.
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/inbox/?collection=COL001', expect.anything());
    // And the request deep-links the thing, so the owner can go and answer it.
    expect(screen.getByRole('link', { name: /view/i })).toHaveAttribute(
      'href',
      '/collections/COL001/things/THG001'
    );
  });

  test('a guest gets no inbox on the collection page', async () => {
    localStorage.setItem('userCode', 'GUEST1');
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) return ok([]);
      if (url.startsWith('/api/v1/collections/COL001/')) {
        return ok({ ...COLLECTION, is_curator: false });
      }
      if (url.startsWith('/api/v1/collections/')) return ok({ results: [] });
      return ok([]);
    });
    renderCollection();

    await screen.findByText('Toy library');
    expect(screen.queryByText(/The drill/)).not.toBeInTheDocument();
    expect(apiFetch).not.toHaveBeenCalledWith(
      expect.stringContaining('/api/v1/inbox/'),
      expect.anything()
    );
  });

  test('Home still shows every notification, whatever collection it came from', async () => {
    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    await waitFor(() => {
      expect(screen.getByText(/The drill/)).toBeInTheDocument();
      expect(screen.getByText(/A ladder/)).toBeInTheDocument();
    });
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/inbox/', expect.anything());
  });
});

/**
 * Every type the backend writes must SAY something.
 *
 * These four had no `case` in notificationLabel/notificationBody, so they fell
 * through to the BROADCAST default and rendered a card headed " — {headline}"
 * with an empty body. The decline was the worst of them: its payload carries
 * `owner_name`, so it drew a blank message apparently *from the owner*.
 *
 * The assertion that matters is the negative one — the body is not empty and is
 * not broadcast copy. Adding a Type to core/models/notification.py without a
 * matching case fails here rather than shipping a silent card.
 */
describe('InboxNotifications — every type says something', () => {
  const CASES = [
    {
      what: 'a member leaving the group tells the owner who left',
      notification: {
        code: 'NOTA01',
        type: 'MEMBER_LEFT',
        payload: {
          collection_headline: 'Toy library',
          member_name: 'Lulu',
          collection_code: 'COL001',
        },
        created: '2026-08-06T10:00:00Z',
      },
      says: [/Lulu/, /Toy library/],
      links: '/collections/COL001/invites',
    },
    {
      what: 'a member joined: names them and the group, and links to the group',
      notification: {
        code: 'NOTJ01',
        type: 'MEMBER_JOINED',
        payload: {
          collection_headline: 'Toy library',
          member_name: 'Lulu',
          collection_code: 'COL001',
        },
        created: '2026-10-19T10:00:00Z',
      },
      says: [/Someone joined/, /Lulu joined Toy library\./],
      links: '/collections/COL001/invites',
    },
    {
      what: 'a member who joined with only an address is named by it',
      notification: {
        code: 'NOTJ03',
        type: 'MEMBER_JOINED',
        payload: {
          collection_headline: 'Toy library',
          member_name: '',
          member_email: 'lulu@your-domain.test',
          collection_code: 'COL001',
        },
        created: '2026-10-19T10:00:00Z',
      },
      says: [/lulu@your-domain\.test joined Toy library\./],
      links: '/collections/COL001/invites',
    },
    {
      what: 'a member who left with only an address is named by it',
      notification: {
        code: 'NOTL03',
        type: 'MEMBER_LEFT',
        payload: {
          collection_headline: 'Toy library',
          member_name: '',
          member_email: 'lulu@your-domain.test',
          collection_code: 'COL001',
        },
        created: '2026-10-19T10:00:00Z',
      },
      says: [/lulu@your-domain\.test/, /Toy library/],
      links: '/collections/COL001/invites',
    },
    {
      what: 'a member who was removed with only an address is named by it',
      notification: {
        code: 'NOTL04',
        type: 'MEMBER_LEFT',
        payload: {
          collection_headline: 'Toy library',
          member_name: '',
          member_email: 'lulu@your-domain.test',
          removed_by_name: 'Lele',
          collection_code: 'COL001',
        },
        created: '2026-10-19T10:00:00Z',
      },
      says: [/Lele removed lulu@your-domain\.test from “Toy library”/],
      links: '/collections/COL001/invites',
    },
    {
      what: 'a member who set no name and gave no address is "a member"',
      notification: {
        code: 'NOTJ02',
        type: 'MEMBER_JOINED',
        payload: { collection_headline: 'Toy library', member_name: '', collection_code: 'COL001' },
        created: '2026-10-19T10:00:00Z',
      },
      says: [/A member joined Toy library\./i],
      links: '/collections/COL001/invites',
    },
    {
      what: 'a pending recommendation names the member, the guest and whose call it is',
      notification: {
        code: 'NOTA02',
        type: 'INVITE_PROPOSED',
        payload: {
          collection_headline: 'Toy library',
          collection_code: 'COL001',
          proposer_name: 'Lele',
          email: 'lolo1@your-domain.test',
          note: 'my downstairs neighbour',
        },
        created: '2026-08-06T10:00:00Z',
      },
      says: [/Lele/, /lolo1@your-domain\.test/, /your call/i],
      // The guest list is where the owner actually answers it.
      links: '/collections/COL001/invites',
    },
    {
      what: 'an approved recommendation tells the proposer their guest is in',
      notification: {
        code: 'NOTA03',
        type: 'INVITE_PROPOSAL_APPROVED',
        payload: {
          collection_headline: 'Toy library',
          collection_code: 'COL001',
          email: 'lolo1@your-domain.test',
          approved: true,
        },
        created: '2026-08-06T10:00:00Z',
      },
      says: [/lolo1@your-domain\.test/, /Toy library/],
      links: '/collections/COL001',
    },
    {
      what: 'a declined recommendation says no reason travelled with it',
      notification: {
        code: 'NOTA04',
        type: 'INVITE_PROPOSAL_DECLINED',
        payload: {
          collection_headline: 'Toy library',
          collection_code: 'COL001',
          owner_name: 'Lili',
          email: 'lolo1@your-domain.test',
        },
        created: '2026-08-06T10:00:00Z',
      },
      says: [/lolo1@your-domain\.test/, /nobody was contacted/i, /haven't been told why/i],
      links: '/collections/COL001',
    },
    {
      // The backend sends NO email for this (a deliberate v1 simplification),
      // so this card is the whole notice. It used to fall through to the broadcast
      // default and render blank.
      what: 'a promotion to co-curator says what the member can now do',
      notification: {
        code: 'NOTA06',
        type: 'PROMOTED_CO_OWNER',
        payload: { collection_headline: 'Toy library', collection_code: 'COL001' },
        created: '2026-08-06T10:00:00Z',
      },
      says: [/you help run this group now/i, /Toy library/, /founder can delete/i],
      links: '/collections/COL001',
    },
    {
      what: 'a promotion in a network says they run their own things, not the whole group',
      notification: {
        code: 'NOTA12',
        type: 'PROMOTED_CO_OWNER',
        payload: { collection_headline: 'Toy network', collection_code: 'COL001', network: true },
        created: '2026-08-06T10:00:00Z',
      },
      says: [
        /message the group, add your own things/i,
        /Toy network/,
        /founder keeps the settings/i,
      ],
      links: '/collections/COL001',
    },
    {
      what: 'a demotion says the member is a regular member again',
      notification: {
        code: 'NOTA07',
        type: 'DEMOTED_CO_OWNER',
        payload: { collection_headline: 'Toy library', collection_code: 'COL001' },
        created: '2026-08-06T10:00:00Z',
      },
      says: [/you no longer help run this group/i, /regular member/i, /Toy library/],
      links: '/collections/COL001',
    },
    {
      what: 'a thing hidden by the founder of a network says who hid it and that it is still yours',
      notification: {
        code: 'NOTA10',
        type: 'THING_HIDDEN',
        payload: {
          thing_headline: 'A mitre saw',
          founder_name: 'Lala',
          thing_code: 'THG010',
          collection_code: 'COL001',
        },
        created: '2026-09-29T09:00:00Z',
      },
      says: [/your thing was hidden/i, /Lala hid A mitre saw/i, /still yours/i],
      links: '/collections/COL001/things/THG010',
      linkName: /view thing/i,
    },
    {
      what: 'a demotion in a network says how many of their things were deleted',
      notification: {
        code: 'NOTA11',
        type: 'DEMOTED_CO_OWNER',
        payload: {
          collection_headline: 'Toy library',
          collection_code: 'COL001',
          things_deleted: 3,
        },
        created: '2026-08-06T10:00:00Z',
      },
      says: [/Your 3 things there were deleted/i],
      links: '/collections/COL001',
    },
    {
      what: 'a demotion in a network with one thing deleted says it without the number',
      notification: {
        code: 'NOTA12',
        type: 'DEMOTED_CO_OWNER',
        payload: {
          collection_headline: 'Toy library',
          collection_code: 'COL001',
          things_deleted: 1,
        },
        created: '2026-08-06T10:00:00Z',
      },
      says: [/Your thing there was deleted\./i],
      links: '/collections/COL001',
    },
    {
      // The team-side record of a decision (2026-09-29): whoever made the call
      // reads their own trace, not a report of themselves in the third person.
      what: 'a decision you made yourself is your own trace, naming who asked',
      notification: {
        code: 'NOTA09',
        type: 'BOOKING_DECIDED',
        payload: {
          thing_headline: 'A mitre saw',
          requester_name: 'Lulu',
          decider_name: 'Lala',
          accepted: true,
          by_you: true,
          booking_code: 'BKG009',
          thing_code: 'THG009',
          collection_code: 'COL001',
          start_date: '2026-10-01',
          end_date: '2026-10-04',
        },
        created: '2026-09-29T09:00:00Z',
      },
      says: [/You confirmed Lulu's request/i, /A mitre saw/],
      label: /Request confirmed/i,
      links: '/collections/COL001/things/THG009',
      linkName: /view thing/i,
    },
    {
      // The other two corners of the by_you × accepted square: the bodies are
      // four keys and only two were pinned, so a crossed wire between the two
      // first-person ones (or the two third-person ones) shipped invisibly.
      what: 'a rejection you made yourself is your own trace, naming who asked',
      notification: {
        code: 'NOTA11',
        type: 'BOOKING_DECIDED',
        payload: {
          thing_headline: 'A mitre saw',
          requester_name: 'Lulu',
          decider_name: 'Lala',
          accepted: false,
          by_you: true,
          booking_code: 'BKG011',
          thing_code: 'THG011',
          collection_code: 'COL001',
          start_date: '2026-10-01',
          end_date: '2026-10-04',
        },
        created: '2026-09-29T09:00:00Z',
      },
      says: [/You declined Lulu's request/i, /A mitre saw/],
      label: /Request declined/i,
      links: '/collections/COL001/things/THG011',
      linkName: /view thing/i,
    },
    {
      what: "a teammate's acceptance names them, and says it was a yes",
      notification: {
        code: 'NOTA12',
        type: 'BOOKING_DECIDED',
        payload: {
          thing_headline: 'A board game',
          requester_name: 'Lolo',
          decider_name: 'Lala',
          accepted: true,
          by_you: false,
          booking_code: 'BKG012',
          thing_code: 'THG012',
          collection_code: 'COL001',
        },
        created: '2026-09-29T09:00:00Z',
      },
      says: [/Lala confirmed Lolo's request/i, /A board game/],
      label: /Request confirmed/i,
      links: '/collections/COL001/things/THG012',
      linkName: /view thing/i,
    },
    {
      what: "a teammate's decision names them, and whether it was a yes",
      notification: {
        code: 'NOTA10',
        type: 'BOOKING_DECIDED',
        payload: {
          thing_headline: 'A board game',
          requester_name: 'Lolo',
          decider_name: 'Lala',
          accepted: false,
          by_you: false,
          booking_code: 'BKG010',
          thing_code: 'THG010',
          collection_code: 'COL001',
        },
        created: '2026-09-29T09:00:00Z',
      },
      says: [/Lala declined Lolo's request/i, /A board game/],
      label: /Request declined/i,
      links: '/collections/COL001/things/THG010',
      linkName: /view thing/i,
    },
    {
      // Its link read "I can help!" — the retired WISH_THING call-for-help CTA —
      // under every group message, whatever the curator had written.
      what: 'a group message carries its text and a link that says where it goes',
      notification: {
        code: 'NOTA08',
        type: 'BROADCAST',
        payload: {
          collection_headline: 'Toy library',
          collection_code: 'COL001',
          owner_name: 'Lili',
          message: 'The workshop is shut on Monday',
        },
        created: '2026-08-06T10:00:00Z',
      },
      says: [/Lili/, /The workshop is shut on Monday/],
      links: '/collections/COL001',
      rejects: /I can help/i,
    },
  ];

  test.each(CASES)('$what', async ({ notification, says, links, rejects, linkName, label }) => {
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) return ok([notification]);
      if (url.startsWith('/api/v1/auth/me/')) return ok(USER);
      if (url.startsWith('/api/v1/collections/')) return ok({ results: [] });
      return ok([]);
    });

    const { container } = render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    for (const phrase of says) {
      expect(await screen.findByText(phrase, { exact: false })).toBeInTheDocument();
    }
    // Only the four BOOKING_DECIDED rows carry one: their label is a separate
    // key from the body and says which way the decision went.
    if (label) expect(await screen.findByText(label)).toBeInTheDocument();
    // Not the broadcast fallback: that renders an empty body and a bare " — ".
    expect(container.textContent).not.toMatch(/\s—\s*Toy library\s*$/);
    expect(container.textContent).not.toMatch(/\{\{\w+\}\}/);
    expect(
      screen.getByRole('link', { name: linkName || /decide now|open the group|see the members/i })
    ).toHaveAttribute('href', links);
    if (rejects) expect(container.textContent).not.toMatch(rejects);
  });

  test('a recommendation approved before the dedicated type existed still reads right', async () => {
    // Legacy row: INVITE_PROPOSED carrying `approved: true`. Without the
    // back-compatibility branch it would read as a request to decide — telling
    // the proposer to go and approve their own recommendation.
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/'))
        return ok([
          {
            code: 'NOTA05',
            type: 'INVITE_PROPOSED',
            payload: {
              collection_headline: 'Toy library',
              collection_code: 'COL001',
              email: 'lolo1@your-domain.test',
              approved: true,
            },
            created: '2026-08-06T10:00:00Z',
          },
        ]);
      if (url.startsWith('/api/v1/auth/me/')) return ok(USER);
      if (url.startsWith('/api/v1/collections/')) return ok({ results: [] });
      return ok([]);
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    expect(await screen.findByText(/recommendation went through/i)).toBeInTheDocument();
    expect(screen.getByRole('link', { name: /open the group/i })).toHaveAttribute(
      'href',
      '/collections/COL001'
    );
  });
});

/**
 * Dismissing — the one thing the inbox does that no test ever did.
 *
 * `dismiss()` drops the row from state optimistically and then DELETEs it. If
 * the DELETE stops being sent, nothing looks broken: the card vanishes on
 * click, exactly as it should, and comes back on the next load — for ever. The
 * member can never clear their inbox and has no way to tell why.
 *
 * Rendered directly rather than through a page: the dismiss and its failure
 * path belong to this component, and `onNetworkError` is a prop only a direct
 * render can observe (Home turns it into an offline banner).
 */
describe('InboxNotifications — dismissing', () => {
  const renderInbox = (onNetworkError) =>
    render(
      <MemoryRouter>
        <InboxNotifications onNetworkError={onNetworkError} />
      </MemoryRouter>
    );

  test('dismissing removes the card and tells the server which one', async () => {
    renderInbox();
    await screen.findByText(/The drill/);

    fireEvent.click(screen.getAllByRole('button', { name: 'Dismiss' })[0]);

    await waitFor(() =>
      expect(apiFetch).toHaveBeenCalledWith('/api/v1/inbox/NOT001/', { method: 'DELETE' })
    );
    expect(screen.queryByText(/The drill/)).not.toBeInTheDocument();
  });

  test('dismissing one leaves the others standing', async () => {
    // The filter is by code. A predicate that matched too widely would empty
    // the whole inbox on one click, and the rows are gone server-side too.
    renderInbox();
    await screen.findByText(/A ladder/);

    fireEvent.click(screen.getAllByRole('button', { name: 'Dismiss' })[0]);

    const deletes = () => apiFetch.mock.calls.filter(([, o]) => o?.method === 'DELETE');
    await waitFor(() => expect(deletes()).toHaveLength(1));
    // Exactly one row was dropped, and it was the one clicked.
    expect(deletes()[0][0]).toBe('/api/v1/inbox/NOT001/');
    expect(screen.getByText(/A ladder/)).toBeInTheDocument();
    expect(screen.queryByText(/The drill/)).not.toBeInTheDocument();
  });

  test('a dropped connection while dismissing is reported, not swallowed', async () => {
    const onNetworkError = vi.fn();
    apiFetch.mockImplementation((url, opts) => {
      if (opts?.method === 'DELETE') return Promise.reject(new TypeError('Failed to fetch'));
      if (url.startsWith('/api/v1/inbox/')) return ok([REQUEST_NOTIFICATION]);
      return ok([]);
    });
    renderInbox(onNetworkError);
    await screen.findByText(/The drill/);

    fireEvent.click(screen.getByRole('button', { name: 'Dismiss' }));

    await waitFor(() => expect(onNetworkError).toHaveBeenCalled());
  });
});

/**
 * The backend sends the bare `name`, never `display_name`, because the
 * fallback in `display_name` is the person's email address and the reader of an
 * inbox card is a co-member who is not entitled to it. So a person who never
 * filled in their profile arrives here as `''`.
 *
 * Every one of these strings interpolates the name mid-sentence, so an empty one
 * is not a cosmetic problem: the card reads " has replied to your question
 * about:" — a message from nobody. `localizedPayload` substitutes the same
 * stand-in `ThingLinkbox` has always used, and this is what pins it.
 *
 * The backend half lives in `core/tests/integration/test_member_name_privacy.py`.
 */
describe('InboxNotifications — a person with no name still has a subject', () => {
  const renderInbox = () =>
    render(
      <MemoryRouter>
        <InboxNotifications />
      </MemoryRouter>
    );

  const NAMELESS_CASES = [
    {
      what: 'an answer from an owner who never set a name',
      notification: {
        code: 'NON001',
        type: 'FAQ_ANSWERED',
        payload: { thing_headline: 'The drill', owner_name: '', thing_code: 'THG001' },
        created: '2026-08-25T10:00:00Z',
      },
    },
    {
      what: 'a question from an asker who never set a name',
      notification: {
        code: 'NON002',
        type: 'FAQ_QUESTION',
        payload: { thing_headline: 'The drill', questioner_name: '', thing_code: 'THG001' },
        created: '2026-08-25T10:00:00Z',
      },
    },
    {
      what: 'a hold accepted by an owner who never set a name',
      notification: {
        code: 'NON003',
        type: 'BOOKING_ACCEPTED',
        payload: { thing_headline: 'The drill', owner_name: '', thing_code: 'THG001' },
        created: '2026-08-25T10:00:00Z',
      },
    },
  ];

  test('a pending invitation from an owner who never set a name still names somebody', async () => {
    // Not an inbox notification — HomePage renders these from
    // `/api/v1/my-invitations/`, whose `owner_name` follows the same rule (the
    // reader is only invited so far, so the API withholds the owner's address).
    // It sits here because it is the same concern and the same page.
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/my-invitations/'))
        return ok([
          {
            accept_code: 'tok-accept',
            reject_code: 'tok-reject',
            collection_code: 'COL001',
            collection_headline: 'Toy library',
            owner_name: '',
          },
        ]);
      if (url.startsWith('/api/v1/inbox/')) return ok([]);
      if (url.startsWith('/api/v1/auth/me/')) return ok(USER);
      if (url.startsWith('/api/v1/collections/')) return ok({ results: [] });
      return ok([]);
    });

    render(
      <MemoryRouter>
        <HomePage />
      </MemoryRouter>
    );

    expect(await screen.findByText(/A member has invited you/)).toBeInTheDocument();
    expect(screen.queryByText(/@/)).not.toBeInTheDocument();
  });

  test.each(NAMELESS_CASES)('$what still names somebody', async ({ notification }) => {
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) return ok([notification]);
      if (url.startsWith('/api/v1/auth/me/')) return ok(USER);
      return ok([]);
    });

    renderInbox();

    // The stand-in, not a blank — and above all not an email address.
    expect(await screen.findByText(/A member/)).toBeInTheDocument();
    expect(screen.queryByText(/@/)).not.toBeInTheDocument();
  });
});

/**
 * A request or reservation notice says when: under the body and its link, two quiet
 * lines — when the event the notice records happened (`created`, the
 * notification's own stamp: for a cancellation that is the cancellation's
 * moment, which is the fact being reported) and, when the payload carries
 * dates, when the booking runs, read from the payload's booking fields by
 * `formatBookingWhen` — the same formatter the booking tables use, so an
 * hourly slot reads identically here and in My requests. An undated notice (a
 * gift or sale — or a row written before its type carried dates) shows only
 * the registration line: the when it happened is knowable, the when it runs
 * is not.
 *
 * The registered stamp renders in the reader's own timezone, so its expected
 * string is built from the same instant locally — never a hardcoded offset
 * that only holds where the suite happens to run. The formatter's timezone
 * behaviour itself is pinned separately by rental.test.js under a stubbed TZ.
 */
describe('InboxNotifications — a request or reservation notice says when', () => {
  const localStamp = (iso) => {
    const d = new Date(iso);
    const pad = (n) => String(n).padStart(2, '0');
    return `${pad(d.getDate())}/${pad(d.getMonth() + 1)}/${d.getFullYear()} ${pad(
      d.getHours()
    )}:${pad(d.getMinutes())}`;
  };

  const renderInbox = (notifications) => {
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) return ok(notifications);
      return ok([]);
    });
    return render(
      <MemoryRouter>
        <InboxNotifications />
      </MemoryRouter>
    );
  };

  // The backend's own shapes: an hourly slot carries start/end time and its
  // `end_date` is only the free-again marker; a day reservation carries no
  // times and its `end_date` is start + duration, so the last *inclusive* day
  // is one earlier (formatBookingWhen's RESERVE_THING branch).
  const MADE_HOURLY = {
    code: 'NOTR01',
    type: 'RESERVATION_MADE',
    payload: {
      requester_name: 'Lele',
      thing_headline: 'The meeting room',
      thing_code: 'THG001',
      collection_code: 'COL001',
      start_date: '2026-09-29',
      end_date: '2026-09-30',
      start_time: '10:00',
      end_time: '12:00',
    },
    created: '2026-09-28T13:11:00Z',
  };

  const MADE_BY_DAYS = {
    code: 'NOTR02',
    type: 'RESERVATION_MADE',
    payload: {
      requester_name: 'Lili',
      thing_headline: 'The workshop',
      thing_code: 'THG002',
      collection_code: 'COL001',
      start_date: '2026-10-03',
      end_date: '2026-10-06',
      start_time: null,
      end_time: null,
    },
    created: '2026-09-28T09:05:00Z',
  };

  const CANCELLED = {
    code: 'NOTR03',
    type: 'RESERVATION_CANCELLED',
    payload: {
      other_name: 'Lolo',
      thing_headline: 'The meeting room',
      thing_code: 'THG001',
      collection_code: 'COL001',
      start_date: '2026-09-29',
      end_date: '2026-09-30',
      start_time: '10:00',
      end_time: '12:00',
    },
    // The cancellation's own moment — not the reservation's.
    created: '2026-09-28T16:40:00Z',
  };

  test('an hourly reservation shows both lines, the stamp local and the slot exact', async () => {
    renderInbox([MADE_HOURLY]);

    expect(
      await screen.findByText(`Registered: ${localStamp('2026-09-28T13:11:00Z')}`)
    ).toBeInTheDocument();
    expect(screen.getByText('Reserved for: 29/09/2026, 10:00–12:00')).toBeInTheDocument();
  });

  test('a day reservation shows the span inclusive of its last day', async () => {
    renderInbox([MADE_BY_DAYS]);

    expect(
      await screen.findByText(`Registered: ${localStamp('2026-09-28T09:05:00Z')}`)
    ).toBeInTheDocument();
    expect(screen.getByText('Reserved for: 03/10/2026 — 05/10/2026')).toBeInTheDocument();
  });

  test('a cancellation shows both lines, its registered stamp being its own moment', async () => {
    renderInbox([CANCELLED]);

    expect(
      await screen.findByText(`Registered: ${localStamp('2026-09-28T16:40:00Z')}`)
    ).toBeInTheDocument();
    expect(screen.getByText('Reserved for: 29/09/2026, 10:00–12:00')).toBeInTheDocument();
    // Not the reservation's original stamp posing as the cancellation's.
    expect(
      screen.queryByText(`Registered: ${localStamp('2026-09-28T13:11:00Z')}`)
    ).not.toBeInTheDocument();
  });

  test('no other type of notice grows the two lines', async () => {
    renderInbox([ELSEWHERE_NOTIFICATION]);

    expect(await screen.findByText(/A ladder/)).toBeInTheDocument();
    expect(screen.queryByText(/^Registered: /)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Reserved for: /)).not.toBeInTheDocument();
  });

  test('a loan request shows both lines, the slot pickup to return', async () => {
    renderInbox([
      {
        code: 'NOTR05',
        type: 'BOOKING_REQUESTED',
        payload: {
          requester_name: 'Lulu',
          thing_headline: 'A mitre saw',
          booking_code: 'BKG005',
          thing_code: 'THG005',
          collection_code: 'COL001',
          start_date: '2026-10-01',
          end_date: '2026-10-04',
        },
        created: '2026-09-29T06:38:00Z',
      },
    ]);

    expect(
      await screen.findByText(`Registered: ${localStamp('2026-09-29T06:38:00Z')}`)
    ).toBeInTheDocument();
    expect(screen.getByText('Requested dates: 01/10/2026 — 04/10/2026')).toBeInTheDocument();
    // A loan is not a reservation: the reservation wording is for RESERVE_THING.
    expect(screen.queryByText(/^Reserved for: /)).not.toBeInTheDocument();
  });

  test('an accepted loan shows both lines, the slot pickup to return', async () => {
    renderInbox([
      {
        code: 'NOTR07',
        type: 'BOOKING_ACCEPTED',
        payload: {
          owner_name: 'Lala',
          thing_headline: 'A mitre saw',
          booking_code: 'BKG007',
          thing_code: 'THG007',
          collection_code: 'COL001',
          start_date: '2026-10-01',
          end_date: '2026-10-04',
        },
        created: '2026-09-29T08:12:00Z',
      },
    ]);

    expect(
      await screen.findByText(`Registered: ${localStamp('2026-09-29T08:12:00Z')}`)
    ).toBeInTheDocument();
    expect(screen.getByText('Requested dates: 01/10/2026 — 04/10/2026')).toBeInTheDocument();
    // A loan is not a reservation: the reservation wording is for RESERVE_THING.
    expect(screen.queryByText(/^Reserved for: /)).not.toBeInTheDocument();
  });

  test('a loan for a single day shows that day once, in any notice about it', async () => {
    // "Fecha y horario de reserva: 13/10/2026 — 13/10/2026" on a loan.
    const loanFor = (type, extra = {}) => ({
      code: `NOT-${type}`,
      type,
      payload: {
        requester_name: 'Lulu',
        owner_name: 'Lala',
        decider_name: 'Lele',
        accepted: true,
        thing_headline: `A mitre saw ${type}`,
        booking_code: 'BKG020',
        thing_code: 'THG020',
        collection_code: 'COL001',
        start_date: '2026-10-13',
        end_date: '2026-10-13',
        ...extra,
      },
      created: '2026-10-02T11:00:00Z',
    });
    renderInbox([
      loanFor('BOOKING_REQUESTED'),
      loanFor('BOOKING_ACCEPTED'),
      loanFor('BOOKING_DECIDED'),
    ]);

    await screen.findAllByText('Requested dates: 13/10/2026');
    expect(screen.getAllByText('Requested dates: 13/10/2026')).toHaveLength(3);
    expect(screen.queryByText(/13\/10\/2026 — 13\/10\/2026/)).not.toBeInTheDocument();
  });

  test('a rejected gift shows the registration line but nothing to schedule', async () => {
    renderInbox([
      {
        code: 'NOTR08',
        type: 'BOOKING_REJECTED',
        payload: {
          owner_name: 'Lala',
          thing_headline: 'A board game',
          booking_code: 'BKG008',
          thing_code: 'THG008',
          collection_code: 'COL001',
        },
        created: '2026-09-29T08:12:00Z',
      },
    ]);

    expect(
      await screen.findByText(`Registered: ${localStamp('2026-09-29T08:12:00Z')}`)
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Reserved for: /)).not.toBeInTheDocument();
    expect(screen.queryByText(/^Requested dates: /)).not.toBeInTheDocument();
  });

  test('a request without dates (a gift, or one from before) shows only the registration line', async () => {
    // The rule changed on 2026-09-29: registration is knowable for every
    // request notice even when the run dates are not, so the gift keeps the
    // first line — it grew none at all before.
    renderInbox([
      {
        code: 'NOTR06',
        type: 'BOOKING_REQUESTED',
        payload: {
          requester_name: 'Lulu',
          thing_headline: 'A board game',
          booking_code: 'BKG006',
          thing_code: 'THG006',
          collection_code: 'COL001',
        },
        created: '2026-09-29T06:38:00Z',
      },
    ]);

    expect(
      await screen.findByText(`Registered: ${localStamp('2026-09-29T06:38:00Z')}`)
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Reserved for: /)).not.toBeInTheDocument();
  });

  test('a reservation payload without dates shows the stamp but no schedule line', async () => {
    renderInbox([
      {
        code: 'NOTR04',
        type: 'RESERVATION_MADE',
        payload: {
          requester_name: 'Lulu',
          thing_headline: 'The meeting room',
          thing_code: 'THG001',
          collection_code: 'COL001',
        },
        created: '2026-09-28T13:11:00Z',
      },
    ]);

    expect(
      await screen.findByText(`Registered: ${localStamp('2026-09-28T13:11:00Z')}`)
    ).toBeInTheDocument();
    expect(screen.queryByText(/^Reserved for: /)).not.toBeInTheDocument();
  });
});

/**
 * Whoever cancelled a reservation keeps an in-app record of their own:
 * the reservation's whole story lives in the inbox, and the
 * canceller's copy used to stop at the email confirmation. Their record is in
 * the first person — and names whose reservation it was when it wasn't theirs.
 */
describe('InboxNotifications — whoever cancelled keeps their own record', () => {
  const renderInbox = (notifications) => {
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) return ok(notifications);
      return ok([]);
    });
    return render(
      <MemoryRouter>
        <InboxNotifications />
      </MemoryRouter>
    );
  };

  const BASE_PAYLOAD = {
    thing_headline: 'The meeting room',
    other_name: 'Lolo',
    thing_code: 'THG001',
    collection_code: 'COL001',
    start_date: '2026-09-29',
    end_date: '2026-09-30',
    start_time: '10:00',
    end_time: '12:00',
  };

  test('a member who cancelled their own reservation reads it in the first person', async () => {
    renderInbox([
      {
        code: 'NOTR11',
        type: 'RESERVATION_CANCELLED',
        payload: { ...BASE_PAYLOAD, by_you: true },
        created: '2026-09-29T10:30:00Z',
      },
    ]);

    expect(
      await screen.findByText(/You cancelled your reservation of The meeting room/)
    ).toBeInTheDocument();
    // Not the third-person copy, and not their own name posing as somebody else's.
    expect(screen.queryByText(/Lolo/)).not.toBeInTheDocument();
  });

  test("a curator who cancelled somebody else's is told whose it was", async () => {
    renderInbox([
      {
        code: 'NOTR12',
        type: 'RESERVATION_CANCELLED',
        payload: { ...BASE_PAYLOAD, by_you: true, member_name: 'Lele' },
        created: '2026-09-29T10:30:00Z',
      },
    ]);

    expect(
      await screen.findByText(/You cancelled Lele's reservation of The meeting room/)
    ).toBeInTheDocument();
  });

  test("an unnamed member's reservation still reads as somebody else's", async () => {
    // The backend sends '' when the reservation's owner never set a name.
    renderInbox([
      {
        code: 'NOTR13',
        type: 'RESERVATION_CANCELLED',
        payload: { ...BASE_PAYLOAD, by_you: true, member_name: '' },
        created: '2026-09-29T10:30:00Z',
      },
    ]);

    expect(
      await screen.findByText(/You cancelled a member's reservation of The meeting room/)
    ).toBeInTheDocument();
    expect(screen.queryByText(/your reservation/)).not.toBeInTheDocument();
  });
});

// Leaving a group deletes the leaver's things there; the founder's notice says how many.
describe('InboxNotifications — a member leaving says how many of their things went', () => {
  const renderInbox = (notifications) => {
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) return ok(notifications);
      return ok([]);
    });
    return render(
      <MemoryRouter>
        <InboxNotifications />
      </MemoryRouter>
    );
  };

  const left = (extra) => ({
    code: 'NOTL01',
    type: 'MEMBER_LEFT',
    payload: {
      collection_headline: 'Toy library',
      member_name: 'Lulu',
      collection_code: 'COL001',
      ...extra,
    },
    created: '2026-10-16T10:00:00Z',
  });

  test('one thing is said in the singular', async () => {
    renderInbox([left({ things_deleted: 1 })]);

    expect(
      await screen.findByText(
        'Lulu has left “Toy library”. Their thing in it was deleted with them.'
      )
    ).toBeInTheDocument();
  });

  test('several are counted', async () => {
    renderInbox([left({ things_deleted: 3 })]);

    expect(
      await screen.findByText(
        'Lulu has left “Toy library”. Their 3 things in it were deleted with them.'
      )
    ).toBeInTheDocument();
  });

  test.each([
    ['none', { things_deleted: 0 }],
    ['a notice written before the count existed', {}],
  ])('with %s only who left is said', async (_case, extra) => {
    renderInbox([left(extra)]);

    expect(await screen.findByText('Lulu has left “Toy library”.')).toBeInTheDocument();
    expect(screen.queryByText(/deleted with them/)).not.toBeInTheDocument();
  });

  test('a removal says who removed whom, and keeps the count of things', async () => {
    renderInbox([left({ removed_by_name: 'Lele', things_deleted: 2 })]);

    expect(
      await screen.findByText(
        'Lele removed Lulu from “Toy library”. Their 2 things in it were deleted with them.'
      )
    ).toBeInTheDocument();
    expect(screen.queryByText(/has left/)).not.toBeInTheDocument();
  });

  test('a removal is labelled as one, and a member leaving of their own accord is not', async () => {
    const { unmount } = renderInbox([left({ removed_by_name: 'Lele' })]);
    expect(await screen.findByText('Someone was removed from the group')).toBeInTheDocument();
    expect(screen.queryByText('Someone left the group')).not.toBeInTheDocument();
    unmount();

    renderInbox([left()]);
    expect(await screen.findByText('Someone left the group')).toBeInTheDocument();
    expect(screen.queryByText('Someone was removed from the group')).not.toBeInTheDocument();
  });

  test('a removal by someone with no name says "A member" and is still a removal', async () => {
    renderInbox([left({ removed_by_name: '', things_deleted: 0 })]);

    expect(
      await screen.findByText('A member removed Lulu from “Toy library”.')
    ).toBeInTheDocument();
  });
});

// A notice about the group's own page must not link to the page it is on, and a
// roster change opens the roster.
describe('InboxNotifications — where a notice links', () => {
  const notice = (type, payload = {}) => ({
    code: `NOT_${type}`,
    type,
    payload: {
      collection_headline: 'Toy library',
      collection_code: 'COL001',
      collection_kind: 'LIBRARY',
      member_name: 'Lulu',
      owner_name: 'Lili',
      message: 'Shut on Monday',
      ...payload,
    },
    created: '2026-10-20T10:00:00Z',
  });

  const renderInbox = (notifications, collection) => {
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) return ok(notifications);
      return ok([]);
    });
    return render(
      <MemoryRouter>
        <InboxNotifications collection={collection} />
      </MemoryRouter>
    );
  };

  test.each(['MEMBER_JOINED', 'MEMBER_LEFT'])(
    '%s links to the members, on Home and inside the collection',
    async (type) => {
      const { unmount } = renderInbox([notice(type)]);
      const home = await screen.findByRole('link', { name: 'See the members' });
      expect(home).toHaveAttribute('href', '/library/COL001/invites');
      unmount();

      renderInbox([notice(type)], 'COL001');
      const inside = await screen.findByRole('link', { name: 'See the members' });
      expect(inside).toHaveAttribute('href', '/library/COL001/invites');
    }
  );

  test.each(['BROADCAST', 'PROMOTED_CO_OWNER'])(
    'inside the collection a %s has no link to its own page; on Home it has',
    async (type) => {
      const { unmount } = renderInbox([notice(type)], 'COL001');
      await screen.findByText(/Toy library/);
      expect(screen.queryByRole('link', { name: 'Open the group' })).not.toBeInTheDocument();
      // The X stays.
      expect(screen.getByRole('button', { name: 'Dismiss' })).toBeInTheDocument();
      unmount();

      renderInbox([notice(type)]);
      expect(await screen.findByRole('link', { name: 'Open the group' })).toHaveAttribute(
        'href',
        '/library/COL001'
      );
    }
  );

  test('inside the collection a notice about a thing still links to it', async () => {
    renderInbox(
      [notice('FAQ_QUESTION', { thing_code: 'THG001', thing_headline: 'The drill' })],
      'COL001'
    );

    expect(await screen.findByRole('link', { name: /view/i })).toHaveAttribute(
      'href',
      '/library/COL001/things/THG001'
    );
  });
});

/**
 * The stand-in for a person with no name is written in lower case where the name
 * falls in the middle of a sentence ("…the reservation of a member") and with a
 * capital where it opens one ("A member joined…"). Which one a key needs depends on
 * the language's own word order, so each row says where the name falls in the three.
 */
describe('InboxNotifications — "a member" in the middle of a sentence', () => {
  const base = { collection_headline: 'Toy library', collection_code: 'COL001' };
  const CASES = [
    {
      what: 'COLLECTION_DELETED (the owner follows "by")',
      type: 'COLLECTION_DELETED',
      payload: { ...base, owner_name: '' },
      says: {
        en: 'has been deleted by a member.',
        es: 'ha sido eliminada por un miembro.',
        ca: 'ha estat eliminada per un membre.',
      },
    },
    {
      what: 'COLLECTION_REVOKED (follows "by" in English, opens the sentence in es/ca)',
      type: 'COLLECTION_REVOKED',
      payload: { ...base, owner_name: '' },
      says: {
        en: 'by a member.',
        es: 'Un miembro te ha eliminado de',
        ca: "Un membre t'ha eliminat de",
      },
    },
    {
      what: 'BOOKING_DECIDED, mine (the requester is the object)',
      type: 'BOOKING_DECIDED',
      payload: { thing_headline: 'The drill', requester_name: '', by_you: true, accepted: true },
      says: {
        en: "You confirmed a member's request for The drill.",
        es: 'Has confirmado la solicitud de un miembro de The drill.',
        ca: 'Has confirmat la sol·licitud de The drill feta per un membre.',
      },
    },
    {
      what: "BOOKING_DECIDED, a teammate's (the decider opens, the requester follows)",
      type: 'BOOKING_DECIDED',
      payload: {
        thing_headline: 'The drill',
        requester_name: '',
        decider_name: '',
        accepted: false,
      },
      says: {
        en: "A member declined a member's request for The drill.",
        es: 'Un miembro ha rechazado la solicitud de un miembro de The drill.',
        ca: 'Un membre ha rebutjat la sol·licitud de The drill feta per un membre.',
      },
    },
    {
      what: 'MEMBER_LEFT after a removal (the remover opens, the removed follows)',
      type: 'MEMBER_LEFT',
      payload: { ...base, member_name: '', removed_by_name: '' },
      says: {
        en: 'A member removed a member from “Toy library”.',
        es: 'Un miembro ha sacado a un miembro de “Toy library”.',
        ca: 'Un membre ha tret un membre de “Toy library”.',
      },
    },
    {
      what: 'RESERVATION_CANCELLED by you, somebody else’s (the member is the object)',
      type: 'RESERVATION_CANCELLED',
      payload: { thing_headline: 'The room', by_you: true, member_name: '' },
      says: {
        en: "You cancelled a member's reservation of The room.",
        es: 'Has cancelado la reserva de un miembro de The room.',
        ca: 'Has cancel·lat la reserva de The room feta per un membre.',
      },
    },
  ];

  const renderInbox = () =>
    render(
      <MemoryRouter>
        <InboxNotifications />
      </MemoryRouter>
    );

  afterEach(async () => {
    await switchLanguage(i18n, 'en');
  });

  describe.each(['en', 'es', 'ca'])('in %s', (lang) => {
    test.each(CASES)('$what', async ({ type, payload, says }) => {
      await switchLanguage(i18n, lang);
      apiFetch.mockImplementation((url) =>
        url.startsWith('/api/v1/inbox/')
          ? ok([{ code: 'NOTX01', type, payload, created: '2026-10-20T10:00:00Z' }])
          : ok([])
      );

      renderInbox();

      // A regex, not `exact: false`: that one ignores case, which is the point here.
      const phrase = new RegExp(says[lang].replace(/[.*+?^${}()|[\]\\]/g, '\\$&'));
      expect(await screen.findByText(phrase)).toBeInTheDocument();
    });
  });

  test.each([
    ['accepted by you', { by_you: true, accepted: true }],
    ['rejected by you', { by_you: true, accepted: false }],
    ['accepted by a teammate', { decider_name: '', accepted: true }],
    ['rejected by a teammate', { decider_name: '', accepted: false }],
  ])(
    'in Catalan a decision %s names the requester after "per", never "de un membre"',
    async (_what, extra) => {
      await switchLanguage(i18n, 'ca');
      apiFetch.mockImplementation((url) =>
        url.startsWith('/api/v1/inbox/')
          ? ok([
              {
                code: 'NOTX03',
                type: 'BOOKING_DECIDED',
                payload: { thing_headline: 'El trepant', requester_name: '', ...extra },
                created: '2026-10-20T10:00:00Z',
              },
            ])
          : ok([])
      );

      renderInbox();

      expect(
        await screen.findByText(/sol·licitud de El trepant feta per un membre\./)
      ).toBeInTheDocument();
      expect(screen.queryByText(/de un membre/)).not.toBeInTheDocument();
    }
  );

  test('in Catalan a name after "per" needs no elision, whichever letter it starts with', async () => {
    await switchLanguage(i18n, 'ca');
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/inbox/')
        ? ok([
            {
              code: 'NOTX04',
              type: 'RESERVATION_CANCELLED',
              payload: { thing_headline: 'La sala', by_you: true, member_name: 'Anna' },
              created: '2026-10-20T10:00:00Z',
            },
          ])
        : ok([])
    );

    renderInbox();

    expect(
      await screen.findByText('Has cancel·lat la reserva de La sala feta per Anna.')
    ).toBeInTheDocument();
  });

  test('a name that opens the sentence keeps its capital', async () => {
    apiFetch.mockImplementation((url) =>
      url.startsWith('/api/v1/inbox/')
        ? ok([
            {
              code: 'NOTX02',
              type: 'FAQ_ANSWERED',
              payload: { thing_headline: 'The drill', owner_name: '' },
              created: '2026-10-20T10:00:00Z',
            },
          ])
        : ok([])
    );

    renderInbox();

    expect(
      await screen.findByText('A member answered your question about The drill.')
    ).toBeInTheDocument();
  });
});

describe('InboxNotifications — a request for several names how many', () => {
  const renderInbox = (notifications) => {
    apiFetch.mockImplementation((url) => {
      if (url.startsWith('/api/v1/inbox/')) return ok(notifications);
      return ok([]);
    });
    return render(
      <MemoryRouter>
        <InboxNotifications />
      </MemoryRouter>
    );
  };

  const notice = (type, extra = {}, payload = {}) => ({
    code: 'NOTQ01',
    type,
    payload: {
      thing_headline: 'Arduino kit',
      requester_name: 'Lele',
      owner_name: 'Lala',
      decider_name: 'Lila',
      accepted: true,
      booking_code: 'BKG001',
      thing_code: 'THG001',
      collection_code: 'COL001',
      start_date: '2026-09-01',
      end_date: '2026-09-08',
      ...payload,
    },
    created: '2026-08-01T10:00:00Z',
    ...extra,
  });

  test.each([
    ['BOOKING_REQUESTED', 'Lele requested 4 × Arduino kit.'],
    ['BOOKING_ACCEPTED', 'Lala confirmed your request for 4 × Arduino kit.'],
    ['BOOKING_REJECTED', null],
    ['BOOKING_DECIDED', null],
  ])('%s with a quantity says "4 × Arduino kit"', async (type, exact) => {
    renderInbox([notice(type, {}, { quantity: 4 })]);

    expect(await screen.findByText(/4 × Arduino kit/)).toBeInTheDocument();
    if (exact) expect(screen.getByText(exact)).toBeInTheDocument();
  });

  test.each([
    ['without a quantity', {}],
    ['with a quantity of one', { quantity: 1 }],
  ])('%s it is the name as it was', async (_, extra) => {
    renderInbox([notice('BOOKING_REQUESTED', {}, extra)]);

    expect(await screen.findByText('Lele requested Arduino kit.')).toBeInTheDocument();
    expect(screen.queryByText(/×/)).toBeNull();
  });
});
