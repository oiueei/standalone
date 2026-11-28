import { readFileSync } from 'node:fs';
import { render, screen, waitFor, within, fireEvent } from '@testing-library/react';
import { axe, toHaveNoViolations } from 'jest-axe';
import { MemoryRouter, Routes, Route, useLocation } from 'react-router';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import en from '../i18n/locales/en.json';

expect.extend(toHaveNoViolations);

// What a deployment that hides nothing, or something, answers on `/auth/me/`.
// A core test cannot assume what `deployment/` hosts elsewhere, so the forms a
// deployment may host are switched off, as the other pages that carry the notice do.
vi.mock('../utils/externalForms', () => ({ externalFormUrl: () => null }));
// The pages a deployment may send "Request access" to (`requestAccessPaths`) are switched
// off the same way: this file pins what the standalone shows, whatever `deployment/` holds.
vi.mock('../deployment', async (orig) => ({ ...(await orig()), requestAccessPaths: {} }));

let capabilities;
globalThis.fetch = vi.fn(() =>
  Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ capabilities }) })
);

import NewCollectionPage from './NewCollectionPage';
import { settle } from '../test/settle';

const OPEN = {
  collection_modes: ['PROPRIETARY', 'COMMUNITY'],
  collection_kinds: ['STALL', 'LIBRARY', 'SHED'],
  thing_types: [],
  request_url: null,
};

beforeEach(() => {
  vi.resetModules();
  localStorage.clear();
  // One cached `/auth/me/` per account; a fresh code per test keeps them apart.
  localStorage.setItem('userCode', `U${Math.random()}`);
  capabilities = OPEN;
  globalThis.fetch.mockClear();
});

const FormProbe = () => <p data-testid="form-state">{JSON.stringify(useLocation().state)}</p>;

const renderPage = (entry = '/new') =>
  render(
    <MemoryRouter initialEntries={[entry]}>
      <Routes>
        <Route path="/new" element={<NewCollectionPage />} />
        <Route path="/:kind/new" element={<FormProbe />} />
      </Routes>
    </MemoryRouter>
  );

const cards = () => screen.getAllByRole('listitem');

describe('the three cards', () => {
  test('are a stall, a library and a shed, in that order, each with what it is for', async () => {
    renderPage();
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());

    expect(cards()).toHaveLength(3);
    const names = cards().map((card) => within(card).getByRole('link').textContent);
    expect(names).toEqual([en.kinds.STALL.long, en.kinds.LIBRARY.long, en.kinds.SHED.long]);
    expect(within(cards()[0]).getByText(en.kinds.STALL.what)).toBeInTheDocument();
    expect(within(cards()[1]).getByText(en.kinds.LIBRARY.what)).toBeInTheDocument();
    expect(within(cards()[2]).getByText(en.kinds.SHED.what)).toBeInTheDocument();
  });

  test('a card has no heading of its own: its text and a button named after the kind', async () => {
    renderPage();
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());

    expect(screen.queryByRole('heading', { level: 2 })).toBeNull();
    expect(document.querySelector('.kind-card-title')).toBeNull();
    for (const [index, kind] of ['STALL', 'LIBRARY', 'SHED'].entries()) {
      const card = cards()[index];
      expect(within(card).getByText(en.kinds[kind].what)).toHaveClass('kind-card-what');
      expect(within(card).getByRole('link', { name: en.kinds[kind].long })).toHaveAttribute(
        'href',
        `/${kind.toLowerCase()}/new`
      );
    }
  });

  test('the text of a card is bold and the title rule is gone from the stylesheet', () => {
    const css = readFileSync('src/App.css', 'utf8');
    const what = /\.kind-card-what\s*\{([^}]*)\}/.exec(css);
    expect(what?.[1]).toMatch(/font-weight:\s*700/);
    expect(css).not.toContain('.kind-card-title');
  });

  test('the page is titled "Create collection" and the tab says so', async () => {
    renderPage();

    expect(
      await screen.findByRole('heading', { level: 1, name: en.createCollection.pageTitle })
    ).toBeInTheDocument();
    await waitFor(() => expect(document.title).toBe(en.titles.newCollection));
  });

  test('each button goes to its own form, and there is one button per card', async () => {
    renderPage();
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());

    const hrefs = cards().map((card) => {
      const links = within(card).getAllByRole('link');
      expect(links).toHaveLength(1);
      return [links[0].textContent, links[0].getAttribute('href')];
    });
    expect(hrefs).toEqual([
      [en.kinds.STALL.long, '/stall/new'],
      [en.kinds.LIBRARY.long, '/library/new'],
      [en.kinds.SHED.long, '/shed/new'],
    ]);
  });

  test('has no accessibility violations, heading order included', async () => {
    const { container } = renderPage();
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());

    await settle(globalThis.fetch);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('the kind is for good, and the page says so', () => {
  test('it is said above the cards', async () => {
    renderPage();
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());

    expect(screen.getByText(en.kinds.chooseIntro)).toBeInTheDocument();
    expect(en.kinds.chooseIntro).toMatch(/can't be changed/);
  });

  test('it is said too when the cards have no button for the deployment', async () => {
    capabilities = {
      collection_modes: ['PROPRIETARY'],
      collection_kinds: ['STALL'],
      thing_types: ['GIFT_THING', 'SELL_THING'],
      request_url: null,
    };
    renderPage();
    await settle(globalThis.fetch);

    expect(screen.getByText(en.kinds.chooseIntro)).toBeInTheDocument();
    expect(screen.queryByRole('link', { name: en.kinds.LIBRARY.long })).toBeNull();
  });
});

describe('the way back', () => {
  const back = { backPath: '/welcome', backLabel: 'Welcome' };
  const from = { pathname: '/new', state: back };

  test('without a state the arrow goes home', async () => {
    renderPage();
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());

    const arrow = screen.getByRole('link', { name: new RegExp(en.common.home) });
    expect(arrow).toHaveAttribute('href', '/');
  });

  test('the arrow follows the state of whoever opened the page', async () => {
    renderPage(from);
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());

    const arrow = screen.getByRole('link', { name: /Welcome/ });
    expect(arrow).toHaveAttribute('href', '/welcome');
  });

  test('a kind button hands the same state on to its form', async () => {
    renderPage(from);
    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());

    fireEvent.click(within(cards()[1]).getByRole('link'));

    expect(await screen.findByTestId('form-state')).toHaveTextContent(JSON.stringify(back));
  });
});

describe('a deployment that gives out only some kinds', () => {
  const ONLY_STALL = {
    collection_modes: ['PROPRIETARY'],
    collection_kinds: ['STALL'],
    thing_types: ['GIFT_THING', 'SELL_THING'],
    request_url: 'https://example.test/ask/',
  };

  test('the others keep their card but lose the button, and say where to ask', async () => {
    capabilities = ONLY_STALL;
    renderPage();

    await waitFor(() =>
      expect(within(cards()[1]).queryByRole('link', { name: en.kinds.LIBRARY.long })).toBeNull()
    );
    expect(within(cards()[0]).getByRole('link', { name: en.kinds.STALL.long })).toHaveAttribute(
      'href',
      '/stall/new'
    );
    for (const index of [1, 2]) {
      const card = cards()[index];
      expect(within(card).getByText(en.kinds[index === 1 ? 'LIBRARY' : 'SHED'].what)).toBeVisible();
      const ask = await within(card).findByRole('link', { name: /request access/i });
      expect(ask).toHaveAttribute('href', 'https://example.test/ask/');
      expect(card).toHaveTextContent(/need approval/i);
    }
    expect(screen.getAllByRole('link', { name: /request access/i })).toHaveLength(2);
  });

  test('with nowhere to ask it says the kind is not available, and offers no button', async () => {
    capabilities = { ...ONLY_STALL, request_url: null };
    renderPage();

    await waitFor(() => expect(cards()[1]).toHaveTextContent(/not available/i));
    expect(within(cards()[1]).queryByRole('link')).toBeNull();
    expect(within(cards()[2]).queryByRole('link')).toBeNull();
    expect(within(cards()[0]).getByRole('link')).toBeInTheDocument();
  });

  test('has no accessibility violations either', async () => {
    capabilities = ONLY_STALL;
    const { container } = renderPage();
    await waitFor(() => expect(cards()[2]).toHaveTextContent(/need approval/i));

    await settle(globalThis.fetch);
    expect(await axe(container)).toHaveNoViolations();
  });
});

describe('when the answer is not known', () => {
  test('every card offers its button: the server is the gate', async () => {
    globalThis.fetch.mockImplementationOnce(() => Promise.reject(new Error('offline')));
    renderPage();

    await waitFor(() => expect(globalThis.fetch).toHaveBeenCalled());
    expect(cards().flatMap((card) => within(card).getAllByRole('link'))).toHaveLength(3);
  });
});

// A deployment may give a withheld kind a page of its own to ask on
// (`deployment/requestAccessPaths`); the module is mocked, upstream's map is empty.
describe('a deployment with a page to ask on for what it withholds', () => {
  afterEach(() => vi.doUnmock('../deployment'));

  async function renderWith(paths, request_url = 'https://example.test/ask/') {
    vi.resetModules();
    vi.doMock('../deployment', () => ({
      deploymentRoutes: [],
      popInPath: null,
      aboutPath: null,
      faqPath: null,
      externalForms: null,
      deploymentI18n: {},
      requestAccessPaths: paths,
    }));
    capabilities = {
      collection_modes: ['PROPRIETARY'],
      collection_kinds: ['STALL'],
      thing_types: ['GIFT_THING', 'SELL_THING'],
      request_url,
    };
    const { default: Page } = await import('./NewCollectionPage');
    render(
      <MemoryRouter initialEntries={['/new']}>
        <Routes>
          <Route path="/new" element={<Page />} />
          <Route path="/access/:need" element={<p data-testid="access" />} />
        </Routes>
      </MemoryRouter>
    );
    await screen.findAllByRole('listitem');
  }

  const requestLink = async (cardIndex) =>
    within((await screen.findAllByRole('listitem'))[cardIndex]).findByRole('link', {
      name: /Request access/,
    });

  test('the library’s button goes to its page and the shed’s to its own, in the same tab', async () => {
    await renderWith({ LIBRARY: '/access/library', SHED: '/access/shed' });

    const library = await requestLink(1);
    expect(library).toHaveAttribute('href', '/access/library');
    expect(library).not.toHaveAttribute('target');
    const shed = await requestLink(2);
    expect(shed).toHaveAttribute('href', '/access/shed');
    expect(shed).not.toHaveAttribute('target');
  });

  test('a normal click on the library’s button navigates inside the app', async () => {
    await renderWith({ LIBRARY: '/access/library', SHED: '/access/shed' });

    fireEvent.click(await requestLink(1));

    expect(await screen.findByTestId('access')).toBeInTheDocument();
  });

  test('a kind with no page of its own keeps the address it always had, in a new tab', async () => {
    await renderWith({ LIBRARY: '/access/library' });

    const shed = await requestLink(2);
    expect(shed).toHaveAttribute('href', 'https://example.test/ask/');
    expect(shed).toHaveAttribute('target', '_blank');
  });
});
