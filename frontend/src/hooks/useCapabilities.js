import { useEffect, useState } from 'react';
import { apiFetch } from '../services/api';

/**
 * What this deployment lets the signed-in account create — the `capabilities`
 * block on `GET /auth/me/` (see `core/services/creator_policy.py`).
 *
 * Upstream OIUEEI answers "everything, and nowhere to ask", so every consumer
 * of this hook renders exactly what it rendered before the endpoint carried the
 * field. It matters on a deployment that withholds something: the forms stop
 * offering what the API would refuse, instead of letting someone fill a form in
 * and meet a 403 at the end of it.
 *
 * **Null until known, and null on failure.** Callers treat null as "no
 * restriction" and show the full catalogue — the same fail-open reasoning the
 * whole file rests on: this is a courtesy to the user, never the gate. The gate
 * is the server, which refuses regardless of what the browser managed to fetch.
 */

// One request per signed-in account, shared by every page that asks. The four
// forms that consume `loadCapabilities` are otherwise four extra calls to an
// endpoint the app already hits on load; `loadUserLanguage` (below) shares the
// same cached fetch rather than opening a fifth. Keyed by user so it cannot
// outlive a logout and answer for whoever signs in next.
//
// **Two callers, two answers to a dead session.** `loadUserLanguage` runs on
// public pages and must never redirect an anonymous-looking visitor, so it
// asks with `optionalAuth`. `loadCapabilities` only runs behind `RequireAuth`,
// where a dead session *should* land on `/login` — and on `CreateCollectionPage`
// this is the only authenticated call before submit, so when it too asked with
// `optionalAuth` a >7-day-stale session rendered the form and lost whatever was
// typed at the POST instead (found in review, 2026-09-15; fixed 2026-09-18).
// So each caller states its mode: a strict caller shares a strict or a
// successful request freely, and after an optional one's failure it asks again
// strictly, which is what lets `apiFetch` redirect.
let cached = { userCode: null, promise: null, optionalAuth: false };

function fetchMe(userCode, optionalAuth) {
  const promise = apiFetch('/api/v1/auth/me/', optionalAuth ? { optionalAuth: true } : {})
    .then((res) => {
      if (res.ok) return res.json();
      // With `optionalAuth`, `apiFetch` already tried refreshing and it still
      // came back 401 — the same definitive "session is dead" signal that,
      // without `optionalAuth`, would itself have cleared `userCode` and
      // redirected. Clearing it here too means `RequireAuth`'s own fast path
      // (a plain `localStorage.getItem('userCode')` check, evaluated once at
      // mount) catches it honestly on whichever protected page is opened
      // next, rather than every later collection/thing page failing open
      // silently forever and repeating the failed refresh attempt on each
      // one — a real cost against `/auth/refresh/`'s 10/minute-per-IP limit
      // (found in review, 2026-09-15). A non-401 failure (offline, 500)
      // leaves `userCode` alone: nothing there says the session is dead.
      if (res.status === 401) localStorage.removeItem('userCode');
      return Promise.reject(new Error(`me ${res.status}`));
    })
    .catch(() => {
      // A request that never got an answer is **not** cached. Failing open is
      // deliberate (the server is the gate), but *remembering* the failure is
      // not: one offline blip on the first form of a session would otherwise
      // keep every later form offering what this deployment refuses, for the
      // rest of that session, and send the user to a 403 at the end of a form
      // they had no reason to distrust. Guarded on identity so a retry already
      // in flight for the same account is never discarded.
      if (cached.promise === promise)
        cached = { userCode: null, promise: null, optionalAuth: false };
      return null;
    });

  cached = { userCode, promise, optionalAuth };
  return promise;
}

function loadMe({ optionalAuth }) {
  const userCode = localStorage.getItem('userCode');
  if (cached.promise && cached.userCode === userCode) {
    if (!optionalAuth && cached.optionalAuth) {
      // An optional request's failure never redirected; a strict caller
      // doesn't settle for it. A success is shared as it is.
      return cached.promise.then((data) => data ?? fetchMe(userCode, false));
    }
    return cached.promise;
  }
  return fetchMe(userCode, optionalAuth);
}

export function loadCapabilities() {
  // An answer without the field is still an answer — an older or narrower
  // backend saying "no restrictions" — so it caches like any other.
  return loadMe({ optionalAuth: false }).then((data) => data?.capabilities ?? null);
}

/**
 * The signed-in account's own, deliberately-saved UI language (`EditProfilePage`),
 * or `''` for a signed-out visitor, one with no preference of their own, or a
 * failed request — every one of those means "no preference", the same fail-open
 * shape as `loadCapabilities`. This is the top tier of the hierarchy
 * `useCollectionLanguage` applies: a real preference here always wins over a
 * collection's own language, which in turn only ever wins over the plain
 * browser default.
 *
 * **Checks for `userCode` before ever calling `loadMe()`, and asks it with
 * `optionalAuth`.** `useCollectionLanguage` is this module's one caller reached
 * from genuinely public pages — `CollectionPage`, `JoinPage`, `SharePage`, an
 * anonymous `ThingPage` — where `apiFetch`'s 401-then-refresh-then-redirect-to-
 * login dance (`services/api.js`) must never fire. The `userCode` check alone
 * caught a never-signed-in visitor, but not one whose `access_token`/
 * `refresh_token` cookies (1h/7d, `core/views/auth.py`) had simply expired
 * while `userCode` — which never expires on its own — stayed in `localStorage`
 * (both found in review, 2026-09-15). With `optionalAuth` a failed request
 * comes back as a response to inspect, never a redirect, and `loadMe()` clears
 * `userCode` itself on a definitive 401, so the next protected page's
 * `RequireAuth` still catches a dead session honestly. `loadCapabilities` asks
 * strictly instead (see the cache note above), so the pages behind
 * `RequireAuth` that rely on it still redirect a dead session.
 */
export function loadUserLanguage() {
  if (!localStorage.getItem('userCode')) return Promise.resolve('');
  return loadMe({ optionalAuth: true }).then((data) => data?.language ?? '');
}

/**
 * The signed-in account's own record as `/auth/me/` answers it, from the same shared
 * fetch as the two above, or `null` for no session, a failed request or no answer.
 * Whoever reads it paints nothing extra until it comes back: a missing answer is "ask
 * nothing", never a half-drawn control.
 */
export function loadMeProfile() {
  if (!localStorage.getItem('userCode')) return Promise.resolve(null);
  return loadMe({ optionalAuth: false });
}

/**
 * Drops the shared `/auth/me/` cache so the next `loadCapabilities()` /
 * `loadUserLanguage()` call re-fetches instead of serving a stale answer.
 *
 * `capabilities` never changes from inside the SPA, but `language` does — one
 * click away in `EditProfilePage` — and that page neither reads nor updates
 * this module's cache when it saves. Without this, a member who opens a
 * Catalan collection (caching `language: ''`), switches their profile to
 * Spanish, and clicks straight back into the group would see it flip back to
 * Catalan: the cached empty answer overriding a preference saved seconds
 * earlier, self-healing only on a full reload (found in review, 2026-09-15).
 */
export function invalidateMe() {
  cached = { userCode: null, promise: null, optionalAuth: false };
}

/**
 * `useCapabilities` and whether the question has been answered. `settled` turns
 * true once the request is over, answer or failure, so a caller that must not
 * decide on the `null` of "still asking" (a form that would be swapped for a notice
 * after the person has started typing) can wait, and still fail open on the `null`
 * of a failure.
 */
export function useCapabilitiesSettled() {
  const [state, setState] = useState({ capabilities: null, settled: false });

  useEffect(() => {
    let alive = true;
    loadCapabilities().then((value) => {
      if (alive) setState({ capabilities: value, settled: true });
    });
    return () => {
      alive = false;
    };
  }, []);

  return state;
}

export default function useCapabilities() {
  return useCapabilitiesSettled().capabilities;
}

/**
 * Whether a form should offer `value` for `kind` — the filter behind every
 * shortened option list.
 *
 * Unknown capabilities offer everything: this is the fail-open half described
 * above, and it is also what makes the whole file a no-op upstream.
 *
 * `current` — the value being edited — is always offered even when the policy
 * no longer allows it. Someone editing a collection opened before this
 * deployment narrowed must still see which mode it is in, and saving it
 * unchanged has to keep working: the server only judges a *change*, so a form
 * that hid the current answer would show a wrong one and then submit it.
 */
export function isOfferable(capabilities, kind, value, current = null) {
  const allowed = capabilities?.[kind];
  if (!allowed) return true;
  return allowed.includes(value) || value === current;
}
