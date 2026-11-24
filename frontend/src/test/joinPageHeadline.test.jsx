import { render, screen, waitFor, fireEvent, act } from '@testing-library/react';
import { MemoryRouter, Routes, Route } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';

vi.mock('../services/api', () => ({
  apiFetch: vi.fn(),
  getCsrfToken: () => 'tok',
}));

import i18n from 'i18next';
import { apiFetch } from '../services/api';
import JoinPage from '../pages/JoinPage';

// JoinPage is where an anonymous visitor is asked for their email — the first
// screen of the viral funnel. It used to take the collection's name only from
// navigation state, which just one caller passes (ThingLinkbox). ThingPage's
// reserve button, a refresh and a shared /join URL all arrived with
// nothing, so the page asked a stranger to join "Collection".
function renderJoin(state, search = '') {
  return render(
    <MemoryRouter initialEntries={[{ pathname: '/collections/PUB001/join', search, state }]}>
      <Routes>
        <Route path="/collections/:code/join" element={<JoinPage />} />
      </Routes>
    </MemoryRouter>
  );
}

describe('JoinPage — the collection is named', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  test('names the collection when arriving cold, with no navigation state', async () => {
    apiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          code: 'PUB001',
          headline: 'Tool Library',
          mode: 'PROPRIETARY',
          allowed_thing_types: ['LEND_THING'],
        }),
    });

    renderJoin(undefined);

    // The named variant of the body copy — the sentence that asks for the email —
    // with the verbs the collection endpoint gave: a lending library says "borrow",
    // not the four verbs every collection used to promise.
    expect(await screen.findByText(/^Join to borrow in Tool Library\./)).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalledWith('/api/v1/collections/PUB001/', expect.anything());
  });

  test('resolves a headline written once per language into the reader own language', async () => {
    apiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          code: 'PUB001',
          headline: JSON.stringify({ en: 'Tool Library', es: 'Biblioteca de herramientas' }),
          mode: 'PROPRIETARY',
          allowed_thing_types: ['LEND_THING'],
        }),
    });

    renderJoin(undefined);

    // The test i18n runs in English, so the raw map must never reach the screen.
    expect(await screen.findByText(/^Join to borrow in Tool Library\./)).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\{"en"/);
  });

  // `useCollectionLanguage` switches this page to the group's own language once the
  // collection has loaded — which is after the name arrived. The name used to be
  // resolved at that moment and kept as words, so the title stayed in the language
  // before the switch. It has to follow the page into the new one.
  test('the name follows the page into another language after it has loaded', async () => {
    i18n.addResourceBundle('ca', 'translation', { common: { done: 'Fet' } });
    apiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          code: 'PUB001',
          headline: JSON.stringify({ en: 'Tool Library', ca: "Biblioteca d'eines" }),
          mode: 'PROPRIETARY',
          allowed_thing_types: ['LEND_THING'],
        }),
    });

    try {
      renderJoin(undefined);
      expect(
        await screen.findByRole('heading', { level: 1, name: 'Join Tool Library' })
      ).toBeInTheDocument();

      await act(() => i18n.changeLanguage('ca'));

      expect(
        await screen.findByRole('heading', { level: 1, name: "Join Biblioteca d'eines" })
      ).toBeInTheDocument();
    } finally {
      await act(() => i18n.changeLanguage('en'));
      i18n.removeResourceBundle('ca', 'translation');
    }
  });

  test('a collection it cannot read leaves the generic copy, not a broken name', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 404 });

    renderJoin(undefined);

    // The page waits for the collection's answer before it paints: wait for the copy.
    expect(await screen.findByText(/Join to request, reserve/)).toBeInTheDocument();
    expect(apiFetch).toHaveBeenCalled();
  });

  test('a ?thing= from a "Reserve" click rides into the join request', async () => {
    apiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ code: 'PUB001', headline: 'Tool Library' }),
    });
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: 'sent' }),
    });

    renderJoin(undefined, '?thing=THG001');

    fireEvent.change(await screen.findByLabelText(/Email/), {
      target: { value: 'lele2@your-domain.test' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send me a magic link' }));

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    const body = JSON.parse(globalThis.fetch.mock.calls[0][1].body);
    expect(body.collection_code).toBe('PUB001');
    expect(body.thing_code).toBe('THG001');
  });

  test('no ?thing= means no thing_code in the request', async () => {
    apiFetch.mockResolvedValue({
      ok: true,
      json: () => Promise.resolve({ code: 'PUB001', headline: 'Tool Library' }),
    });
    globalThis.fetch = vi.fn().mockResolvedValue({
      ok: true,
      status: 200,
      json: async () => ({ message: 'sent' }),
    });

    renderJoin(undefined);

    fireEvent.change(await screen.findByLabelText(/Email/), {
      target: { value: 'lele2@your-domain.test' },
    });
    fireEvent.click(screen.getByRole('button', { name: 'Send me a magic link' }));

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    const body = JSON.parse(globalThis.fetch.mock.calls[0][1].body);
    expect(body).not.toHaveProperty('thing_code');
  });
});

/**
 * "Join {collection}": the title says which group the stranger is
 * about to join, the way `/share/:token` already does — it used to be "Join to
 * take part" with the name only in the text below and in the way back. The words
 * are the share page's own (`share.pageTitleNamed`, `titles.shareNamed`); until
 * the name is known the title of always.
 */
describe('JoinPage — the title names the collection', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  const collectionNamed = (headline) =>
    apiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          code: 'PUB001',
          headline,
          mode: 'PROPRIETARY',
          allowed_thing_types: ['LEND_THING'],
        }),
    });

  test('with the collection loaded, the h1 and the tab both say "Join {name}"', async () => {
    collectionNamed('Tool Library');

    renderJoin(undefined);

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Join Tool Library' })
    ).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe('Join Tool Library — OIUEEI'));
    expect(screen.queryByRole('heading', { level: 1, name: 'Join to take part' })).toBeNull();
  });

  test('a headline written once per language is read in the reader’s own', async () => {
    collectionNamed(JSON.stringify({ en: 'Tool Library', es: 'Biblioteca de herramientas' }));

    renderJoin(undefined);

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Join Tool Library' })
    ).toBeInTheDocument();
    expect(document.body.textContent).not.toMatch(/\{"en"/);
  });

  test('the tab names the collection from the first paint; the page waits for the colours', () => {
    // The collection call never answers: nothing but the state can have named it.
    apiFetch.mockReturnValue(new Promise(() => {}));

    renderJoin({ collectionHeadline: 'Tool Library' });

    // The tab does not wait. The page does: it is the group's door and wears the
    // group's colours, so no hero is painted in the app's palette meanwhile.
    expect(document.title).toBe('Join Tool Library — OIUEEI');
    expect(screen.queryByRole('heading', { level: 1 })).not.toBeInTheDocument();
  });

  test('a collection it cannot read still shows the page, with the name the card handed over', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 403 });

    renderJoin({ collectionHeadline: 'Tool Library' });

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Join Tool Library' })
    ).toBeInTheDocument();
  });

  test('without a name — a collection it cannot read — it is the title of always', async () => {
    apiFetch.mockResolvedValue({ ok: false, status: 404 });

    renderJoin(undefined);

    expect(
      await screen.findByRole('heading', { level: 1, name: 'Join to take part' })
    ).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe('Join to take part — OIUEEI'));
  });
});

/**
 * The door looks like the page it leads to: a collection's image is its logo here
 * exactly as in its own hero — an ordinary `<img class="hero-logo" alt="">` after the
 * way back and before the title, in a `form-hero--collection` hero — and never the
 * full-bleed `HeroPhoto` composition (`form-hero--photo`) this page used to paint. The
 * image comes from the collection endpoint the page already calls, which gives
 * `thumbnail_url` to an anonymous reader of a PUBLIC collection.
 */
describe('JoinPage — the hero carries the collection’s image as its logo', () => {
  const LOGO = 'https://bucket.your-domain.test/oiueei/collections/cover.jpg';

  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
  });
  afterEach(() => vi.restoreAllMocks());

  const collectionWith = (thumbnail_url) =>
    apiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          code: 'PUB001',
          headline: 'Tool Library',
          mode: 'PROPRIETARY',
          allowed_thing_types: ['LEND_THING'],
          thumbnail_url,
        }),
    });

  test('with an image, the hero shows it as a decorative logo between the way back and the title', async () => {
    collectionWith(LOGO);

    const { container } = renderJoin(undefined);

    await screen.findByText(/^Join to borrow in Tool Library\./);
    const logo = container.querySelector('img.hero-logo');
    expect(logo).toHaveAttribute('src', LOGO);
    // Decorative: the <h1> already names the collection.
    expect(logo).toHaveAttribute('alt', '');
    const hero = container.querySelector('.form-hero');
    expect(hero).toHaveClass('form-hero--collection');
    expect(hero).not.toHaveClass('form-hero--photo');
    // Not the photo composition: no wedge, no full-bleed picture.
    expect(container.querySelector('.hero-photo-wrap, .hero-photo')).toBeNull();
    // After the way back and before the title, in the hero's content column.
    const back = container.querySelector('.form-hero-content .back-link');
    const title = screen.getByRole('heading', { level: 1, name: 'Join Tool Library' });
    expect(logo.parentElement).toBe(back.parentElement);
    expect(back.compareDocumentPosition(logo) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
    expect(logo.compareDocumentPosition(title) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test('without one, the hero is the same collection hero with no image at all', async () => {
    collectionWith('');

    const { container } = renderJoin(undefined);

    await screen.findByText(/^Join to borrow in Tool Library\./);
    expect(container.querySelector('img')).toBeNull();
    expect(container.querySelector('.form-hero')).toHaveClass('form-hero--collection');
    expect(container.querySelector('.form-hero')).not.toHaveClass('form-hero--photo');
  });
});

/**
 * The page's email serves a new address, an account that exists and a member
 * alike, so it is the only action: a reader with no session gets no "Sign in" icon in
 * the corner and no link to /login anywhere. With a session the account menu is as
 * on every other page.
 */
describe('JoinPage — the email is the only way in', () => {
  beforeEach(() => {
    localStorage.clear();
    vi.clearAllMocks();
    apiFetch.mockResolvedValue({
      ok: true,
      json: () =>
        Promise.resolve({
          code: 'PUB001',
          headline: 'Tool Library',
          mode: 'PROPRIETARY',
          allowed_thing_types: ['LEND_THING'],
        }),
    });
  });
  afterEach(() => vi.restoreAllMocks());

  test('with no session there is no link to /login on the page', async () => {
    const { container } = renderJoin(undefined, '?thing=THG001');

    await screen.findByText(/^Join to borrow in Tool Library\./);
    expect(container.querySelector('a[href^="/login"]')).toBeNull();
    expect(container.querySelector('.hero-corners a')).toBeNull();
    expect(screen.queryByRole('link', { name: /sign in/i })).toBeNull();
  });

  test('with a session the account menu is in the corner', async () => {
    localStorage.setItem('userCode', 'VISITOR1');
    const { container } = renderJoin(undefined);

    await screen.findByText(/^Join to borrow in Tool Library\./);
    expect(container.querySelector('.hero-corners')).toContainElement(
      screen.getByRole('button', { name: /your account/i })
    );
  });
});
