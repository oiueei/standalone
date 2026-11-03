import { render, screen, waitFor, act } from '@testing-library/react';
import { vi, describe, test, expect, beforeEach, afterEach } from 'vitest';
import { settle, switchLanguage } from './settle';

// This file is about what a deployment with no forms of its own hosted elsewhere shows
// — the app's own contact page, `VITE_FEEDBACK_URL`, the server's request address. A
// core test cannot assume what `deployment/` holds, so the
// `externalForms` a deployment may have are switched off here by stubbing the helper
// that reads them; `externalForms.test.jsx` pins them on, with the module mocked.
vi.mock('../utils/externalForms', () => ({ externalFormUrl: () => null }));
// The pages a deployment may send "Request access" to (`requestAccessPaths`) are switched
// off the same way: this file pins what the standalone shows, whatever `deployment/` holds.
vi.mock('../deployment', async (orig) => ({ ...(await orig()), requestAccessPaths: {} }));

/**
 * `App.jsx` — the frame every page renders inside: the skip link, the focus and
 * scroll reset on navigation, and `html[lang]`.
 *
 * Its routes are covered elsewhere (`deployment.test.jsx` pins that a
 * deployment's own route mounts above the catch-all and that unknown paths still
 * reach the 404). What was unguarded is the pair of effects around them, both of
 * which carry a written rationale and neither of which any test exercised — so
 * the rationale was the only thing keeping them true.
 *
 * The one that is easiest to "fix" into a bug is the initial mount: focusing
 * `<main>` on load looks like the obviously complete version of a focus reset,
 * and it would make the skip link — which precedes `<main>` — unreachable by the
 * first forward Tab, quietly deleting the affordance for exactly the users it
 * exists for.
 */

// App's mount effect primes the CSRF cookie against the real network, and jsdom
// has no scrollTo. Both inert; the scrollTo spy is also an assertion target.
globalThis.fetch = vi.fn(() =>
  Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve({}) })
);
window.scrollTo = vi.fn();

beforeEach(() => {
  localStorage.clear();
  vi.clearAllMocks();
  vi.resetModules();
  window.history.pushState({}, '', '/legal');
});

afterEach(() => {
  window.history.pushState({}, '', '/');
});

/** Navigate the way a real click does: push the entry, then let the router hear
 *  about it. `pushState` alone changes the URL without notifying BrowserRouter. */
function navigateTo(path) {
  window.history.pushState({}, '', path);
  // The router re-renders on the event: inside `act`, as a click would be.
  act(() => {
    window.dispatchEvent(new PopStateEvent('popstate'));
  });
}

/** Navigate to the contact page and wait until it has finished mounting: the pages are
 *  lazy chunks, and one that finishes loading after the test has ended is reported as
 *  an update outside `act`. Its heading is the page's own, and `settle` lets the
 *  request it makes on arrival land too. */
async function navigateToContact() {
  navigateTo('/contact');
  await screen.findByRole('heading', { level: 1, name: 'Contact us' });
  await settle(globalThis.fetch);
}

describe('the skip link', () => {
  test('is in the document, before main, pointing at it', async () => {
    const { default: App } = await import('../App');
    const { container } = render(<App />);

    const skip = container.querySelector('a.skip-link');
    expect(skip).not.toBeNull();
    expect(skip.getAttribute('href')).toBe('#main');

    // Order is the whole mechanism: a skip link after the content it skips is
    // decoration. DOCUMENT_POSITION_FOLLOWING = main comes after the link.
    const main = container.querySelector('#main');
    expect(skip.compareDocumentPosition(main) & Node.DOCUMENT_POSITION_FOLLOWING).toBeTruthy();
  });

  test('survives the first load with focus untouched, so it is the first tab stop', async () => {
    const { default: App } = await import('../App');
    const { container } = render(<App />);

    await waitFor(() => expect(container.querySelector('#main')).not.toBeNull());

    // Nothing has stolen focus into the page: the next Tab reaches the skip
    // link. If a focus reset ever runs on mount, this is the test that says so.
    expect(document.activeElement).not.toBe(container.querySelector('#main'));
    expect(window.scrollTo).not.toHaveBeenCalled();
  });
});

describe('navigating to another page', () => {
  test('moves focus into main and scrolls back to the top', async () => {
    const { default: App } = await import('../App');
    const { container } = render(<App />);

    const main = container.querySelector('#main');
    await waitFor(() => expect(main).not.toBeNull());

    await navigateToContact();

    // Both halves matter to a keyboard or screen-reader user: focus lands on the
    // new page's content rather than wherever the previous page left it, and the
    // viewport is not still parked halfway down the page they came from.
    await waitFor(() => expect(document.activeElement).toBe(main));
    expect(window.scrollTo).toHaveBeenCalledWith({ top: 0, left: 0, behavior: 'instant' });
  });

  test('focuses main without scrolling it into view: the jump to the top is the only scroll', async () => {
    const { default: App } = await import('../App');
    const { container } = render(<App />);

    const main = container.querySelector('#main');
    await waitFor(() => expect(main).not.toBeNull());
    const focus = vi.spyOn(main, 'focus');

    await navigateToContact();

    await waitFor(() => expect(focus).toHaveBeenCalledWith({ preventScroll: true }));
    // `html` smooths scrolling for the footer's anchor; a page change must jump.
    expect(window.scrollTo).toHaveBeenLastCalledWith({ top: 0, left: 0, behavior: 'instant' });
  });

  test('renders the page that was navigated to', async () => {
    // Guards the navigation helper itself: a focus assertion would also pass on
    // a router that never heard the popstate and re-rendered nothing.
    const { default: App } = await import('../App');
    render(<App />);

    await waitFor(() => expect(document.title).toMatch(/legal|OIUEEI/i));

    await navigateToContact();

    await waitFor(() => expect(document.title).toMatch(/contact|contacto|contacte/i));
  });
});

describe('the account own saved language', () => {
  test('is applied once at boot, ahead of any page', async () => {
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ language: 'ca' }) })
    );
    const { default: App } = await import('../App');
    const { default: i18n } = await import('../i18n');
    render(<App />);

    await waitFor(() => expect(i18n.language).toBe('ca'));
  });

  test('an unsupported code is ignored, not applied', async () => {
    // Asserting on `i18n.language` alone is not enough here: 'fr' is not in
    // `supportedLngs`, so `changeLanguage('fr')` would itself fall through
    // `fallbackLng.default` back to 'en' — indistinguishable from the guard
    // never firing at all if the baseline is already 'en' (found in review,
    // 2026-09-15). Spying on the call itself is what actually pins the guard.
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: true, status: 200, json: () => Promise.resolve({ language: 'fr' }) })
    );
    const { default: App } = await import('../App');
    const { default: i18n } = await import('../i18n');
    const spy = vi.spyOn(i18n, 'changeLanguage');
    render(<App />);

    // The page of the address is a lazy chunk: let it arrive, then give the
    // language check a moment to (not) happen.
    await screen.findByRole('heading', { level: 1 });
    await settle(globalThis.fetch);
    expect(spy).not.toHaveBeenCalled();
    spy.mockRestore();
  });

  test('a signed-out visitor (401) leaves the language untouched', async () => {
    // A plain fetch, not apiFetch: a 401 here must never trigger apiFetch's
    // refresh-then-redirect-to-/login dance (services/api.js) — this call
    // warms the CSRF cookie for a visitor who may not have an account at all.
    // `globalThis.fetch` is spied on directly, so a stray `apiFetch` call
    // (which itself calls `fetch`) would still show up as extra calls here.
    globalThis.fetch = vi.fn(() =>
      Promise.resolve({ ok: false, status: 401, json: () => Promise.resolve({}) })
    );
    const { default: App } = await import('../App');
    const { default: i18n } = await import('../i18n');
    const before = i18n.language;
    render(<App />);

    await screen.findByRole('heading', { level: 1 });
    await settle(globalThis.fetch);
    expect(i18n.language).toBe(before);
    expect(globalThis.fetch).toHaveBeenCalledTimes(1);
  });
});

describe('html[lang]', () => {
  test('follows the interface language, on load and on every change', async () => {
    const { default: App } = await import('../App');
    const { default: i18n } = await import('../i18n');
    render(<App />);

    await waitFor(() => expect(document.documentElement.lang).toBe(i18n.language));

    // The attribute is what tells a screen reader which pronunciation to use and
    // a translator which language it is reading; the picker changes the strings
    // whether or not anyone updates it.
    await switchLanguage(i18n, 'es');
    await waitFor(() => expect(document.documentElement.lang).toBe('es'));

    await switchLanguage(i18n, 'en');
    await waitFor(() => expect(document.documentElement.lang).toBe('en'));
  });
});

describe('the way to a human is reached from one place on the front door', () => {
  test('/login has no link to /contact in its content; the site footer has the one', async () => {
    // "Trouble signing in? Tell us…" closed the page until it was taken out
    // (2026-10-04): "Contact us" is the footer's third door on every page. Rendered
    // whole — App, so the footer is there — because the page alone cannot say how
    // many links the user sees.
    const { default: App } = await import('../App');
    render(<App />);
    navigateTo('/login');
    await screen.findByRole('button', { name: 'Sign in' });

    const links = [...document.querySelectorAll('a[href="/contact"]')];
    expect(links).toHaveLength(1);
    expect(links[0].closest('footer')).not.toBeNull();
    expect(links[0]).toHaveTextContent('Contact us');
    expect(screen.queryByRole('link', { name: /Trouble signing in/i })).toBeNull();
  });
});

describe('the legal notice is reached from one place on the front door', () => {
  test('/login links /legal exactly once, from the site footer', async () => {
    // The door once carried its own "Legal notice & privacy" link as well as the
    // footer's (since removed). Rendered whole — App, so the footer
    // is there — because the page alone cannot say how many links the user sees.
    const { default: App } = await import('../App');
    render(<App />);
    navigateTo('/login');
    await screen.findByRole('button', { name: 'Sign in' });

    const links = document.querySelectorAll('a[href="/legal"]');
    expect(links).toHaveLength(1);
    expect(links[0].closest('footer')).not.toBeNull();
  });
});
