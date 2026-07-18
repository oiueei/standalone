# React testing reference (OIUEEI)

Stack: vitest · @testing-library/react · jest-axe · i18n mock with the real
`en.json`. Network is mocked at the boundary: `globalThis.fetch = vi.fn(...)`.
That seam is the repo convention — keep it, and make the mocked responses
**real contracts** (copy the DRF serializer's actual JSON, don't invent a
convenient shape; a field the serializer doesn't send is a test that passes
against a backend that doesn't exist).

## The four states rule

A component that fetches has at least four states, and "with data" is the
least interesting one. Test all that exist:

1. **Loading** — what renders before the promise resolves.
2. **Empty** — `results: []` (the empty-state copy + its CTA link).
3. **Error** — non-OK response (the inline error + Retry, not a blank page)
   and network throw (`fetch.mockRejectedValue(new TypeError())` — the offline
   banner path).
4. **Data** — and here assert *exclusions* too (the INACTIVE thing absent,
   the owner-only button absent for a guest).

```jsx
test('a failed section shows Retry instead of an endless spinner', async () => {
  globalThis.fetch = vi.fn(() => Promise.resolve(mockResponse({}, false, 500)));
  renderPage();
  expect(await screen.findByText("Couldn't load this section")).toBeInTheDocument();
  expect(screen.getByRole('button', { name: 'Retry' })).toBeInTheDocument();
});
```

## Interactions

- Prefer `userEvent` for new tests involving typing, tabbing, or hover — it
  fires the real event sequence. `fireEvent.click` remains fine for a plain
  click. (Don't retrofit the existing suite for style points.)
- Assert what the interaction DID: the POST body
  (`JSON.parse(post[1].body)`), the optimistic UI change, the navigation
  target — not merely "the handler didn't crash" (smell #1).
- One-shot guards matter: a double-click on an irreversible button must fire
  ONE request (count `fetch.mock.calls`).

## Hooks

Test through a minimal consumer component (or `renderHook`):
- **Cleanup**: unmount mid-fetch and assert no state update happened after
  (the AbortController pattern — `signal.aborted` guards; the console must
  stay free of act() warnings).
- **Race**: resolve fetch A *after* fetch B (two `Promise` handles you settle
  manually) and assert B's data wins — the stale-response bug this repo
  actually had in `CollectionPage`.
- **Re-render identity**: a callback returned by the hook that feeds an
  effect dependency must be stable (`expect(fn1).toBe(fn2)` across renders).

## Queries = accessibility (AA)

Query by **role and accessible name** — `getByRole('button', { name: … })`,
`getByLabelText` — never by class or test-id when a role exists. If the test
can't find it by role, users of assistive tech can't either: fix the
component, not the query. Every new page joins `smoke.test.jsx`
(`smokeAndAxe`) so jest-axe scans it; interactive states with dialogs/menus
open get axe'd in `a11yInteractive.test.jsx`.

## Repo gotchas (learned the hard way)

- React puts a textarea's value in its `textContent`: scope copy assertions
  with `{ ignore: 'script, style, textarea' }` or `getByText` will match the
  input box and pass in false.
- HDS `required` appends `*` to labels → match with regex: `getByLabelText(/Email/)`.
- HDS `Select` needs `language="en"`; its `onChange` receives arrays.
  `ToggleButton.onChange` receives the CURRENT value (negate it).
- StrictMode double-invokes effects in dev: guards (`committedRef`) get a
  dedicated test wrapping the render in `<StrictMode>`.
- i18n: the mock loads the real `en.json`, so assert real copy strings; new
  keys go to all three locales or `i18nParity.test.js` fails the suite.

## Coverage ratchet

`vite.config.js` holds the floors; CI runs `npm run test:coverage`. New code
that drops a metric below the ratchet needs better tests — never a lower
ratchet. When a strengthening session raises real coverage by ≥2-3 points,
raise the ratchet to lock the gain (leave the usual v8 wobble margin).
