# OIUEEI Views Documentation

This document describes the behaviour, endpoints, permissions, and business logic for each view in the OIUEEI application.

---

## Auth Views (`core/views/auth.py`)

### RequestLinkView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/auth/request-link/` |
| **Permission** | `AllowAny` |
| **Rate limit** | 5 requests/minute per IP **and** 5 requests/hour per account (the requested email, lowercased — `email_ratelimit_key`) so one mailbox can't be flooded from rotating IPs. |

Requests a magic link for passwordless authentication.

**Request body:**
```json
{ "email": "lala@your-domain.test", "next": "/collections/AbC123/things/XyZ789" }
```

`next` is optional: the same-site path the person was heading for when their session ran out (the SPA's `apiFetch` and `RequireAuth` put it in `/login?next=…`, `LoginPage` forwards it). It goes through `core.utils.safe_next_path` — the single door, whitelist-based: starts with `/`, not `//`, ≤256 characters, no `..`, not `/` alone, not one of the SPA's own doors (`login`, `logout`, `verify`, `rsvp`, `magic-link`). It is read straight from the body, **not** through `RequestLinkSerializer`, so **a bad `next` is dropped without a word and the response does not change** — a 400 would tell a caller which requests carried a bad one for no reason.

**Behaviour:**
1. Validates email via `RequestLinkSerializer`.
2. Looks up user by email (lowercased). Returns 200 with unified message regardless of whether email exists (anti-enumeration).
3. If user found: creates an RSVP with action `MAGIC_LINK` and sends magic link email via `send_magic_link_email()`. A valid `next` is stored on the RSVP (`context["next"]`), server-side on purpose: the link is often opened in another browser (webmail, the phone's mail app) that shares no storage with the one that showed `/login`. An unregistered address with a `next` creates nothing, like without one.
4. Logs request to `security` logger with IP.

**Anti-enumeration, and the timing delta that remains.** The response body is identical either way — with or without a `next`, valid or not (`test_landing.py` compares `response.content`) — and the SMTP send is dispatched to a daemon thread in production (`EMAIL_SEND_ASYNC`) so the slow part can't be timed — that was L10. What it did not close: the `RSVP.objects.create()` INSERT (and the thread spawn itself) run **only** on the registered path, so a registered address still answers marginally faster-to-measure than an unregistered one. Carrying `next` adds nothing to it: same INSERT, one more value in a column it already wrote. This is **known and accepted**, not an oversight. Equalising it would mean writing the RSVP from inside the daemon thread and spawning that thread on both paths — a DB write with no connection cleanup, and a failed INSERT downgraded from a 500 to a silent no-email — to hide a sub-millisecond difference that the rate limits (5/min per IP, 5/hour per email) already cap sampling of far below the point where it could be averaged out of network noise.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Always (unified message for anti-enumeration) |
| 429 | Rate limited |

---

### VerifyLinkView

| | |
|---|---|
| **Endpoint** | `GET` / `POST /api/v1/auth/verify/{token}/` (also aliased at `/api/v1/rsvp/{token}/`) |
| **Permission** | `AllowAny`. **`authentication_classes = []`** — the ~134-bit URL token is the bearer credential, so no authenticator runs; this also keeps `POST` clear of DRF's `SessionAuthentication` CSRF gate (no handler reads `request.user`). |
| **Rate limit** | 10 requests/minute per IP (GET and POST keyed separately) |

The URL segment is the RSVP's high-entropy `token` (≈134 bits), not the 6-char PK — the PK can no longer resolve an RSVP.

**GET vs POST — `BOOKING_ACCEPT`/`BOOKING_REJECT` require a POST to commit.** These two decisions are irreversible and authenticate no one, so a bare GET must never fire them — an email link-scanner or a page prefetch/refresh could otherwise auto-decide a hold. For those actions **GET only previews** (`200 {"action", "requires_confirmation": true, "thing_headline"}` — no mutation, RSVP not consumed); the frontend `VerifyPage` then **auto-fires the committing POST from JS** on load (one click for the manager — opening the link — with no second on-page button). This keeps the anti-prefetch guarantee: a scanner/prefetch does a bare GET, runs no JS, and so never reaches the committing POST. The login/invite actions (`MAGIC_LINK`, `COLLECTION_INVITE`, `COLLECTION_REJECT`) still resolve on GET — a scanner that consumes one only forces a fresh link; it decides nothing on the user's behalf.

Routes to the appropriate handler based on `rsvp.action`:

| Action | Handler | Commit verb | Description |
|--------|---------|-------------|-------------|
| `MAGIC_LINK` | `_handle_magic_link` | GET | Authenticates user, sets auth cookies, and returns the `landing` contract below |
| `COLLECTION_INVITE` | `_handle_collection_invite` | GET | Adds user to collection invites M2M, sets auth cookies, deletes sibling `COLLECTION_REJECT` RSVP. Returns `landing: "collection"` + `collection` + `invited_collection` (or `landing: "home"` if the collection was deleted meanwhile) |
| `COLLECTION_REJECT` | `_handle_collection_reject` | GET | Notifies collection owner of rejection, deletes sibling `COLLECTION_INVITE` RSVP, no JWT |
| `BOOKING_ACCEPT` | `_handle_booking_accept` | **POST** | Accepts booking via `finalize_booking_decision()`, signed by whoever the link was minted to (GET previews only) |
| `BOOKING_REJECT` | `_handle_booking_reject` | **POST** | Rejects booking via `finalize_booking_decision()`, signed by whoever the link was minted to (GET previews only) |
| `PROPOSAL_APPROVE` | `_handle_proposal_approve` | **POST** | **Re-checks at the click that whoever the link was minted to still runs the group** (`collection.is_curator(rsvp.user_code_id)`; a recommendation is mailed to every curator with their own pair, and the link outlives the role): if not, the pressed RSVP is burnt, a `security` warning is written and the answer is **403 `{"error": "Not authorized", "code": "no_longer_manages"}`** — the same code `VerifyPage` already words for a booking link — while the suggestion stays pending for whoever still decides. Then sends the real invitation, behind the **same** quota + member-ceiling guard as the in-app approval (`invitation_service.proposal_approval_blocked` — the link is not a way around either; a refusal leaves both links alive so the owner can answer tomorrow, and carries `retryable: true` to say so — a full collection and a settled suggestion both answer 400, so the SPA cannot tell "not now" from "gone" without it. **The exception is `invite_already_asked`**: the person was already invited by email, the block lasts a year, so it carries no `retryable` and `VerifyPage` shows the reason in the reader's language with no help line; the suggestion stays pending for a curator to decline. `_helpers.approval_refusal_response` is the one place that decides). If another invitation gets in between that check and the send, `InvitationAlreadyAsked` is caught on both routes and answered with the same refusal; the decision's reservation went with the transaction, so the suggestion is still pending and the link alive. GET previews only `{action, requires_confirmation}` — approving **mails a third party**, so a link scanner must never fire it, and the preview carries **none of the proposal's details** (the address, the note, the proposer's name whose display fallback is *their* email): a GET is what a link scanner issues, and the person suggested does not know they were. The SPA auto-commits with a POST and reads the invited address from that response |
| `PROPOSAL_REJECT` | `_handle_proposal_reject` | **POST** | Declines, after the same authority re-check as the approval (403 `no_longer_manages` and a burnt link for a curator who no longer runs the group). Every curator's links and notices die with the decision, either way |
| `ACCOUNT_DELETE` | `_handle_account_delete` | **POST** | Erases the account via `account_service.delete_account()` (GET previews only: name, email, owned collection/thing counts). Unlike bookings, the frontend **never auto-commits** this preview — the person must press the explicit on-page confirm button. The commit response also clears the auth cookies (the session died with the account); the RSVP itself cascades away with the user row |

**Post-login landing (`landing`).** The successful-login response carries where the SPA should send the user — `"collection"` (plus `collection`, the code), `"path"` (plus `path`, a same-site route) or `"home"`. It used to be decided in the browser from the `seenWelcome` localStorage key, but logout clears that key, so every re-login looked like a first visit and dropped returning users on `/welcome`. The rules, in order:

1. The RSVP carries a `target_code` — a share-token or public-collection join — ⇒ **that collection** (they joined it precisely to get there). **The join is made here, at the click, not when the address was typed**: `JoinView` only writes `join_source` (and, for a share link, the `share_token` it used) on the RSVP's `context`, and `_join_when_pressed` checks the join is **still allowed** before it calls `_join_collection` — by share link, the collection is ACTIVE *and its `share_token` is still the one the link was sent with* (a curator who rotated or revoked it withdrew exactly that invitation); by public collection, it is ACTIVE *and* PUBLIC. If it is no longer allowed **nobody is joined and the link carries no collection**: rule 3 below answers, instead of a landing that would 403. A `target_code` with **no** `join_source` (a link sent before this change — they live 24 h — or one a deployment's own door stamped) is not a pending join: it only lands, as it always did. `invited_collection` is still returned alongside `collection` for compatibility (an older SPA read the landing collection from it). If that RSVP's `context` also carries a `thing_code` (the visitor clicked "Reserve" on one thing, `JoinView` stashed it) **and** that is still a non-INACTIVE thing in the collection, the response adds **`thing`** so the SPA lands on `/{kind}/{code}/things/{thing}` instead of the index. A thing hidden or moved out between the join and the click drops silently to the collection landing.
2. Otherwise a link that **remembers where the person was going** — `context["next"]`, stamped by `RequestLinkView` — ⇒ **`"path"`** plus `path`, that route. It outranks the single-collection rule: the email they came from (a "Ver anuncio", a "Ver y responder", the viral "Empieza aquí", the weekly digest) named a page, and the session ran out on it. The value is **validated again here** (`safe_next_path`) although it comes from our own table: a `context` written by another route must not be able to send a session anywhere. It is read before the RSVP is deleted, like `context_thing`. **A link born at an open door (`RSVP.origin == POPIN`) never follows one**: whoever walks in that way has no session that ran out on a page, and a `next` written there by another route must not steer them. `LOGIN` and a legacy blank `origin` do follow it. Rule 1 still wins over it (only `JoinView` sets a `target_code`, and never on a `LOGIN` RSVP — the order just makes that plain).
3. Otherwise ⇒ their **one real ACTIVE collection** — owned or invited, a co-curator being always in `invites` too — when they have exactly one, else **home**. **"Real" leaves out the demonstration collections** (`is_onboarding=True`, the ones an open door joins people to), and an INACTIVE one does not count: somebody who peeked at the demo and then founded or joined a group of their own goes to that group; somebody who only has the demo, or has two or more real groups, goes home. It is the same answer for a `/popin` link as for a `/login` one. `_solo_collection()` stops the query at two rows and returns `(code, kind)`; every response that lands the SPA on a collection (`landing: "collection"`, the `COLLECTION_INVITE` one too) carries **`collection_kind`** beside `collection`, since the app's address is `/{kind}/{code}`.

`RSVP.origin` is stamped `LOGIN` by `RequestLinkView` and `POPIN` by `JoinView`; it is blank on every other action. The `seenWelcome` localStorage flag this replaced is gone entirely — the collection welcome box it also fed was removed in 2026-09. **There is no `"welcome"` landing any more** (it was what a targetless `POPIN` link answered, for a deployment's own "what this is" page): the rule above answers an open door's visitor from the groups they actually have, so `LANDING_WELCOME` and the SPA's branch for it are gone.

**Common behaviour (`_resolve_rsvp` → `_dispatch`):**
1. Looks up RSVP by `token` (the high-entropy URL token, not the PK). Returns 401 if not found.
2. Checks `rsvp.is_valid()` (per-action expiry — magic 24h / booking 72h / invite ~30 days, see the RSVP model). Deletes and returns 401 if expired.
3. GET previews a confirm-required action (`_preview`, no mutation); otherwise (and always on POST) delegates to the action handler.
4. On commit, the RSVP is deleted after use (one-time use).

**Internal helpers:**
- `_join_collection(collection, user, source)` — the single funnel of every join (the four doors). **When `user` is the collection's founder it is a no-op** (no `invites` row, no event, no counter, no document): the founder is an FK, never a member, and the caller still lands them on the collection, which the owner can always read. On a **new** membership only it counts the member, logs the `MEMBER_JOINED` event, **leaves an in-app `MEMBER_JOINED` notice for each curator** (founder + co-curators, never the one joining; `_tell_the_team_of_a_join`, whose payload carries `member_email` only when the member has no name; joining is never blocked or approved, the team is only told) and sends the welcome document. The daily email summary of the same sign-ups is `send_join_summaries`.
- `_join_when_pressed(rsvp, user)` — Rule 1 of the landing, and the half of a join that moved here from `JoinView`: returns the collection a `MAGIC_LINK` takes the person to, joining them to it first (`_join_collection`, so the `MEMBER_JOINED` event with its `source` and the welcome PDF happen **now**, once) when the RSVP is a pending join that is still allowed — see rule 1 above for what "allowed" means for each door — or `None`.
- `_authenticate_user(request, rsvp)` — Shared by `MAGIC_LINK` and `COLLECTION_INVITE` handlers. Validates user, calls `update_last_activity()`, mints a JWT. Returns `(user, refresh, user_data)` tuple or `Response` on failure. Auth tokens are set as HttpOnly cookies via `_set_auth_cookies()`. Auth is JWT-cookie-only — it deliberately does **not** open a Django session (no `login()`); the admin site has its own session, so a shadow session would be needless attack surface.
- `_handle_booking_action(request, rsvp, accepted)` — Shared by `BOOKING_ACCEPT` and `BOOKING_REJECT` handlers. Looks up booking, validates via `is_valid()`, then **re-checks the authority of whoever the link was minted to, at the click**: `rsvp.user_code_id == booking.owner_code_id or thing.can_manage(rsvp.user_code_id)`. A hold request is emailed to every manager of the thing with **their own** RSVP pair (`RSVP.create_booking_pair(booking, manager)`), and the link outlives the role that earned it (72 h) — a co-curator demoted or removed after the email, a collection turned COMMUNITY, or the thing moved out of it, must not decide with the old link. A failed check burns that RSVP, writes a `security` warning and answers **403 `{"error": "Not authorized", "code": "no_longer_manages"}`** — the English sentence is unchanged for a client that knows nothing more, and the code lets `VerifyPage` say "You no longer run this thing, so this link can no longer decide the request" instead of its `invalidOrExpired` screen, whose help line sends a lapsed manager to ask "whoever invited you". The owner always passes. Then calls `finalize_booking_decision(decided_by=rsvp.user_code)` — **the decision is signed by whoever pressed**, so the requester's notice names them (and they get no `BOOKING_DECIDED` of their own: it goes to the rest of the team) — sends the decision email, and deletes every RSVP for the booking (all managers', not only the sibling).

**MAGIC_LINK response (200):**
```json
{
  "action": "MAGIC_LINK",
  "user": { ... },
  "invited_collection": "<collection_code>"
}
```
Auth tokens (`access_token`, `refresh_token`) are set as HttpOnly cookies via `_set_auth_cookies()`. `invited_collection` is present **only** when the RSVP carried a `target_code` **and the person was joined to it, or already was** — i.e. the magic link came from a join (private share token or PUBLIC login-to-act code) that was still allowed at the click. The SPA then drops the user straight onto that collection rather than the default landing (home, or their single collection). A plain `/login` magic link has no `target_code`, so the field is omitted. A `thing` key rides alongside when the join came from a "Reserve" click on a specific thing (see the landing rules above).

**A response that lands on a collection** (`MAGIC_LINK` with a target or one real group, `COLLECTION_INVITE`) carries **`collection_kind`** next to `collection`: the app's address for it is `/{kind}/{code}`. `ThingSerializer`, `BookingPeriodSerializer` (so `/owner-bookings`), the inbox's notices, `SharePreviewView` and `ShareJoinView` carry the kind wherever they carry a collection code, for the same reason.

**COLLECTION_INVITE response (200):**
```json
{
  "action": "COLLECTION_INVITE",
  "user": { ... },
  "invited_collection": "<collection_code>"
}
```
Auth tokens are set as HttpOnly cookies via `_set_auth_cookies()`.

**COLLECTION_REJECT response (200):**
```json
{
  "action": "COLLECTION_REJECT",
  "message": "Invitation declined"
}
```

**BOOKING_ACCEPT response (200):**
```json
{
  "action": "BOOKING_ACCEPT",
  "message": "Booking accepted",
  "thing_headline": "...",
  "start_date": "...",
  "end_date": "..."
}
```

---

### JoinView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/auth/join/` |
| **Permission** | `AllowAny` |
| **Rate limit** | 5 requests/minute per IP **and** 5/hour per account (email), plus the per-collection daily join cap (below) |

How a visitor who was pointed at a collection asks to join it and gets a magic link
back. **Nothing is joined here — the click joins**: the address is only typed, and it may be somebody else's, so joining on submit put a stranger into a group they had never heard of (and mailed them its welcome document) because someone else typed their email. An emailed invitation has always joined at the click (`_handle_collection_invite`); this door now does too. Two doors reach it, and both are somebody choosing to let a specific
person in: an owner's `share_token` (the `/share/{token}` link they handed out)
and a PUBLIC collection's `collection_code` (login-to-act).

It was `POST /auth/pop-in/` until v0.12.0, when the open demo door left the
standalone. `RSVP.Origin.POPIN` keeps its name — see the model for why.

**Request body:**
```json
{ "email": "lala@your-domain.test", "share_token": "<optional 22-char token>", "collection_code": "<optional PUBLIC collection code>", "thing_code": "<optional — the thing the visitor tried to reserve>" }
```

**Behaviour:**
1. Validates email via `RequestLinkSerializer`.
2. **Resolves the target first** (`_resolve_target`): a `share_token` naming an ACTIVE collection, else a `collection_code` naming a **PUBLIC, ACTIVE** one. A code is never a way into a PRIVATE collection, and an unknown/revoked/INACTIVE one is silently ignored.
3. **With no target, nothing is created** — no `User`, no RSVP, no email — and the same 200 is returned. Ordering matters here and is the point: `get_or_create` used to run *first*, so a POST carrying only an email minted a real account that joined nothing, which on any deployment without onboarding collections was an open registration door on an otherwise invite-only product.
4. `get_or_create` user by email. **No `language` is ever taken from the request** — a newly created user's `language` stays blank, so `resolve_email_language` falls through to the joined collection's own language for every email to them, including this first one. This used to accept the visitor's current UI language and stamp it onto the new user permanently, which then outranked the collection's own language for every future email to that member, with no way back short of a profile edit.
5. **Does not add them to the collection.** The account (step 4) exists with **no membership at all** until the click — the RSVP needs a user. What it does is stamp the collection as the RSVP `target_code` **and write into the RSVP's `context` what the click needs to decide**: `join_source` (`SHARE` or `PUBLIC`, the value the `MEMBER_JOINED` event will carry) and, for a share link, the **`share_token` that was used**. Verifying the link then goes through `VerifyLinkView._join_when_pressed`, which checks the join is still allowed (a rotated or revoked token, a collection made private or inactive in between → nobody is joined and the landing follows the general rule) and joins through `_join_collection`, so first-join side effects — `MEMBER_JOINED`, the welcome PDF — fire exactly once, **at the click**. The response, the per-collection daily cap (`COLLECTION_JOINS_PER_DAY`, charged when the mail is sent, since it protects the sending) and a **signed-in** reader's own join (`CollectionJoinView`, `ShareJoinView`: there the person pressing is the person joining) are all unchanged.
6. Creates the `MAGIC_LINK` RSVP (`origin=POPIN`) and sends the magic link, **whose subject names the joined collection** (`"Hello, welcome to '{headline}' - OIUEEI!"`) and whose language follows the collection's. An optional **`thing_code`** in the body — the thing the visitor clicked "Reserve" on — is written to the RSVP's `context` when it names a non-INACTIVE thing that actually lives in the joined collection (anything else is dropped), so the magic link returns them to that thing rather than the collection index.
7. Logs to the `security` logger with IP, whether the user is new, and which collection — or that nothing was created.

**The per-collection daily cap (`COLLECTION_JOINS_PER_DAY`).** Neither door here
is a secret — a PUBLIC collection's code is printed in its own URL and a share
token exists to be passed around — so anyone may ask this deployment to mail a
magic link to any address they type. That is a relay pointed at the operator's
sending domain, and the two rate limits above do not reach it: they cap how often
**one IP** asks and how often **one victim** is mailed, not many IPs each mailing
a different stranger once, which is the shape of the abuse. `INVITE_EMAILS_PER_DAY`
did not cover it either — that counts what an *account* sends through the owner's
invite routes, and this door has no account behind it.

So `join_quota_exhausted()` is checked **after** the target resolves and
**before** anything is created; `consume_join_quota()` charges one after the send
is dispatched. It is keyed per collection, never per deployment: a single global
counter would let anyone shut joining off for every group on the instance by
spending it on one. **Somebody already in the group is outside the cap**: the founder, a
co-curator (always in `invites`) or a member is neither refused nor charged, because the cap
stops mail to strangers and they are only coming back in (an expired session lands them on
`/join`); the 5/h per address limit still bounds them, and their response is the same
unified one. The lookup (`JoinView._is_inside`) creates nothing. A refusal creates nothing, sends nothing, returns the
**unified response** — telling the visitor "over its limit" would confirm the
code names a real, joinable collection — and writes a `security` warning, the
same shape as the capacity alarms, where the tripwire reports to whoever set it
and never to whoever tripped it. Off by default; see
[`join_quota`](../services/CLAUDE.md).

**The unified response is the anti-enumeration guarantee.** The refusal and the
success are byte-for-byte identical, which is what stops the endpoint answering
"does this address / token / collection code exist?". `test_join_hardening.py`
compares whole responses rather than a message, so a field added to one path and
not the other fails there — and it now does the same for the quota refusal.

**It is a guarantee about the *body*, not the clock.** Since the no-target path
was made to create nothing, it also returns without the writes the joining path
does — so the two differ in *duration* even though they are identical in
content. What keeps the spaces unwalkable is therefore not constant time but
their size and the rate limits: a 22-character share token, a 6-character code
(36⁶ ≈ 2.2 × 10⁹), and 5/min per IP + 5/h per email. Timing is the weaker of the
two properties and always was; the fix that removed the account creation
improved the endpoint and narrowed this claim at the same time. **Don't add
sleeps to "even it out"** — padding to the slow path would slow every real join
for a threat the rate limit already bounds, and padding accurately is a much
harder problem than it looks.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Always (unified message, whether or not anything was created) |
| 400 | Malformed email |
| 429 | Rate limited |

---

### MeView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/auth/me/` |
| **Permission** | `IsAuthenticated` |

Returns the current authenticated user's full profile via `UserSerializer`. Updates `last_activity` on each call.

**Plus `capabilities`** — what this deployment lets that account create:

```json
"capabilities": {
  "collection_modes": ["PROPRIETARY", "COMMUNITY"],
  "collection_kinds": ["STALL", "LIBRARY", "SHED"],
  "thing_types": ["GIFT_THING", "SELL_THING", "RENT_THING", "LEND_THING"],
  "request_url": null
}
```

The standalone answers with everything and a null `request_url` (see [`creator_policy`](../services/CLAUDE.md#creator_policypy--who-may-create-what-on-this-deployment)). It is **not** a `UserSerializer` field: what someone may create belongs to the deployment, not to the person, and that serializer is also what `/users/{code}/` returns about somebody else. It rides here because the SPA calls this endpoint on every app load, and it comes from the **same `capabilities()` call the create endpoints refuse with** — that is what stops the UI offering a control the API would 403. `request_url` is where to ask for what was withheld; null means there is nowhere, which is the difference between "this deployment does not do that" and "ask here".

**Plus `receives_requests`** (2026-10-02) — whether "Requests to me" has anything to show this person: `receives_booking_requests(user)` in `booking_service.py`, true when they **own a thing** (a COMMUNITY member who contributed one gets requests on it) or **founded or co-curate a PROPRIETARY collection**, or **founded a NETWORK** (its founder rejects pending requests as a rescue before owning a thing; a network's co-curators receive only their own things); two `EXISTS` queries. The account menu reads it when it opens, so the browser keeps nothing about it.

---

### LogoutView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/auth/logout/` |
| **Permission** | `AllowAny`, `authentication_classes = []` |

Logs out the current user. Reads the refresh token from the `refresh_token` HttpOnly cookie (scoped to `/api/v1/auth/` so it actually reaches this endpoint — `REFRESH_COOKIE_PATH`), blacklists it so it can't be reused to refresh, and clears both `access_token` and `refresh_token` cookies.

**Authenticates nothing, on purpose — logout must never fail.** It used to be `IsAuthenticated`, which broke it in the two cases that matter most: an **expired access token** 401'd the request, leaving the still-valid (up to 7 days) refresh token unblacklisted; and a cookie-authenticated POST **without an `X-CSRFToken` header** was rejected by `CookieJWTAuthentication.enforce_csrf` with a 403, leaving every cookie alive while the SPA navigated to `/login` anyway — so the session came back to life on the next page load (the reported "logout doesn't log out" bug; `LogoutPage` now also goes through `apiFetch`, which sends the header). With no authenticator the view simply reads the refresh cookie, blacklists it (best-effort — an invalid token is swallowed) and **always** returns 200 with the three cookie-deleting headers. The trade-off is a CSRF-forced logout: a cross-site POST can end a session, never act inside one.

### AccountDeleteRequestView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/auth/delete-account/` |
| **Permission** | `IsAuthenticated` |
| **Rate limit** | 3 requests/hour per user |

Step one of the right-to-erasure flow. Deletes any previous `ACCOUNT_DELETE` RSVP for the account (resend-safe: at most one live link), creates a fresh one (24h expiry) and emails its confirmation link via `send_account_delete_email` (Cat. 1, always delivered, no viral CTA). **Nothing is deleted here** — the deletion commits in `VerifyLinkView._handle_account_delete`, on an explicit POST from the page the link lands on, so a stolen browser session alone can't erase an account (the attacker would also need the mailbox). Returns `200 {"message": "Confirmation email sent"}`.

---

### TokenRefreshView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/auth/refresh/` |
| **Permission** | `AllowAny` |

Rotates auth tokens. Reads the `refresh_token` from the HttpOnly cookie, validates it, generates a new access/refresh token pair, and sets them as HttpOnly cookies on the response.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Tokens rotated successfully |
| 401 | Missing, invalid, or expired refresh token |

---

## Contact View (`core/views/contact.py`)

### ContactView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/contact/` |
| **Permission** | `AllowAny` — anonymous on purpose: the person who most needs the support channel is the one who can't log in |
| **Rate limit** | 5 requests/hour per IP |

Forwards a support/feedback message to the operator's mailbox (`CONTACT_EMAIL` env var, defaulting to `DEFAULT_FROM_EMAIL`) via `send_contact_email`, with the sender's address as `Reply-To` so answering is one click. Body: `{name?, email, message, kind?}` (`ContactSerializer` — SafeHeadline name ≤32, EmailField, SafeText message ≤2000, so HTML/injection is rejected at the boundary; `kind` is `support` (default, the contact page, and what every page sends — the front end sends no `kind` at all) or `collab` (the collaborate page, which left the front end on 2026-10-04: no page sends it, but it is still accepted) and only changes the operator's subject line). Fixed recipient: the form can annoy exactly one mailbox, never relay spam to third parties. Returns `200 {"message": "Message received"}`.

---

## User Views (`core/views/users.py`)

### can_view_user(viewer_user_code, target_user_code)

Helper function. Returns `True` if:
- Viewer is the target (own profile)
- There is a collection both are **inside of** (founder, co-curator or member; a co-curator is always in `invites`)

Anyone who is not in the group opens nobody's general profile through it, a public group's team included (a team is known to its group by that group's page). A person of another group is just as closed. The status of the collection is not looked at. One `EXISTS` query, however many groups (two chained `filter()` calls, so each side joins `invites` on its own). What the other person sees is `UserPublicSerializer` (code, name, headline, about, photo, created) plus `shared_collections`, which lists only the groups both are inside; never language, demographics or email preferences. Pinned in `test_profile_visibility.py`.

This provides IDOR protection — users can only see profiles of people who share a group with them.

### UserDetailView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/users/{user_code}/` |
| **Permission** | `IsAuthenticated` + `can_view_user()` |

Returns user profile. Own profile returns full data (`UserSerializer`), other profiles return public data (`UserPublicSerializer`) plus a `shared_collections` array (collections where both users are connected as owner/invite) with `code`, `headline` and `kind` for each (the app links to `/{kind}/{code}`).

| | |
|---|---|
| **Endpoint** | `PUT /api/v1/users/{user_code}/` |
| **Permission** | `IsAuthenticated` + own profile only |

Updates own profile via `UserUpdateSerializer` (partial update). Accepts optional `name`, `headline`, `about` (Markdown bio, max 2000, HTML rejected), `photo` (storage key), `notify_activity`, and `notify_news` (a body that still names `koro` or `theeeme` has them ignored: the palette is a collection's now). Returns the full `UserSerializer` (including `photo_url`). Returns 403 if attempting to update another user.

---

## Inbox Views (`core/views/inbox.py`)

### InboxView

| | |
|---|---|
| **Endpoints** | `GET /api/v1/inbox/[?collection={code}]`, `DELETE /api/v1/inbox/{code}/` and `DELETE /api/v1/inbox/?group=bookings[&collection={code}]` |
| **Permission** | `IsAuthenticated` |

GET lists the current user's in-app notifications (`code`, `type`, `payload`, `created`). **A payload that names a `collection_code` is served with a `collection_kind` beside it**, added when the list is read — one query for every collection the notices name, however many notices and collections — so notices written before kinds existed link at `/{kind}/{code}` too; nothing is stored in the payload. DELETE dismisses (hard-deletes) one, scoped to the requesting user — a code belonging to someone else 404s. Both URL routes resolve to this one view; each handler takes an optional `code` and returns a clean **405** for the combination it doesn't serve (`GET /inbox/{code}/` and `DELETE /inbox/` with no `group`) rather than a signature-mismatch 500.

**`DELETE /inbox/?group=bookings` (2026-10-02)** dismisses, in one call and with a `204`, the caller's request and reservation notices that are *for the team that manages them* — the set the inbox folds into one summary card once there are more than three of them, whose X used to have only the one-at-a-time delete to call. The set is `InAppNotification.team_booking_notices`: `BOOKING_REQUESTED`, `BOOKING_DECIDED` and `RESERVATION_MADE` (all three only ever go to managers — the requester is excluded from each on purpose) plus the `RESERVATION_CANCELLED` copies that are a manager's (`cancelled_by_owner` is `false`, or `by_you` with a `member_name`, a manager's own record of cancelling somebody else's). **A copy for the person who asked or held the reservation is never in it** (`cancelled_by_owner: true`, or their own `by_you` record with no `member_name`; a cancellation written before the payload said who it was for is left alone): the summary card links to the team's bookings page, which is not theirs. Always scoped to `request.user`; with `collection` only notices whose `payload.collection_code` matches, the same filter as the GET (a `RESERVATION_CANCELLED` payload carries none, so a collection-scoped call never touches it, as the scoped GET never lists it). An unknown `group` is a `400` and deletes nothing. `frontend/src/test/inboxGroupParity.json` holds this rule and the browser's copy of it (`utils/inboxGroups.js`) together.

**`DELETE /inbox/?group=info`** dismisses, the same way (204, the caller's own, `collection` narrowing it), the notices that **only inform**: `InAppNotification.informative_notices`, every type that neither asks its reader for an action (`ACTION_NOTICE_TYPES`: `BOOKING_REQUESTED`, `FAQ_QUESTION`, `INVITE_PROPOSED`, `THING_REPORTED`) nor belongs to the team's booking group above. The inbox folds them into one card once there are more than three. `inboxGroupParity.json` carries both answers per row (`grouped`, `informative`).

**`?collection={code}`** narrows the list to the notifications born in that collection (`payload__collection_code`, a JSONField lookup that works on SQLite and PostgreSQL alike) — no param means today's behaviour, everything. It is what lets a collection's own page show its owner the hold requests for the things that live there, instead of stranding them on Home; the frontend `InboxNotifications` component is the only caller. Payloads written before the key existed carry no collection and so never match a filtered list.

Booking notifications also **clear themselves** once the request they announce is settled — see [`booking_service`](../services/CLAUDE.md#the-request-notifications-lifecycle). Both decision paths (this API's `BookingActionView` and the email/RSVP `VerifyLinkView`) converge on `finalize_booking_decision`, so neither can leave a stale one behind.

---

## Notification Preference Views (`core/views/notifications.py`)

### NotificationsByTokenView

| | |
|---|---|
| **Endpoints** | `GET /api/v1/notifications/token/{token}/` and `PATCH /api/v1/notifications/token/{token}/` |
| **Permission** | `AllowAny` |
| **Rate limits** | GET: 20/min per IP. PATCH: 10/min per IP. |

Unauthenticated endpoint scoped to editing `notify_activity` / `notify_news` on a specific user. The token is a `TimestampSigner` signature over the user's code (salt `notifications-prefs`, ~1-year TTL — no stored column), produced by `core.services.email_service.make_notifications_token()` and resolved by `verify_notifications_token()`; every Cat. 2 / Cat. 3 email footer contains a link of the form `/me/notifications/{token}`.

**Behaviour:**
- Resolves the token via `verify_notifications_token()`. Returns 401 `{ "detail": "Invalid or expired link" }` if invalid.
- On GET: returns `{ notify_activity, notify_news }` for the signed user.
- On PATCH: accepts partial `{ notify_activity?, notify_news? }` via `NotificationPrefsSerializer` and persists the change.
- Token has blast radius limited to these two booleans — it cannot be used to read or modify anything else.

### DigestMuteByTokenView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/digest/mute/{token}/` |
| **Permission** | `AllowAny` — the signed token is the whole credential |
| **Rate limit** | 10 requests/minute per IP |

The one-click unsubscribe at the foot of every digest. The token signs `{user_code}:{collection_code}` under its own salt (`make_digest_mute_token`), so it can't be exchanged for a preferences token; its blast radius is one row in one M2M, which the member can undo from the collection page.

**POST, not GET** — the same anti-prefetch reasoning as the booking decisions in `VerifyLinkView`: a mail client's link scanner issues a bare GET and runs no JS, so it must not be able to unsubscribe someone. The SPA page at `/digest/mute/:token` fires the POST from JS on mount. Answers 401 on an invalid/expired/tampered token, and never reveals whether the member was subscribed.

---

## Thing Views (`core/views/things.py`)

### ThingViewSet

| | |
|---|---|
| **Base** | `ModelViewSet` with `DefaultRouter` |
| **Lookup** | `code` |

| Action | Endpoint | Permission |
|--------|----------|------------|
| `list` | `GET /api/v1/things/` | `IsAuthenticated` |
| `create` | `POST /api/v1/things/` | `IsAuthenticated` — **a thing is created in a collection**: no `collection_code` is a 400 `{"collection_code": ["A thing is created in a collection."]}`, before any other check |
| `retrieve` | `GET /api/v1/things/{code}/` | `AllowAny` + `can_view()` — anonymous-safe: visible when the thing sits in a PUBLIC, ACTIVE collection |
| `update` | `PUT /api/v1/things/{code}/` | `IsAuthenticated` + `IsThingManager` |
| `partial_update` | `PATCH /api/v1/things/{code}/` | `IsAuthenticated` + `IsThingManager` |
| `destroy` | `DELETE /api/v1/things/{code}/` | `IsAuthenticated` + `_can_delete()` — the `THING_REMOVED` event is written by the `Thing` delete receiver (`core/services/deletion_events.py`), not by the view; `perform_destroy` only wraps the delete in `deleting_as(request.user)` so the event names who deleted |
| `activate` | `POST /api/v1/things/{code}/activate/` | `IsAuthenticated` + `IsThingManager` |
| `hide` | `POST /api/v1/things/{code}/hide/` | `IsAuthenticated` + `IsThingManager` |

**`IsThingManager`** (2026-09) is `IsThingOwner` one tier wider: the thing owner, **or a curator of a PROPRIETARY collection it sits in** (`Thing.can_manage`). A PROPRIETARY collection's curators run its whole catalogue. Note `get_object()` fetches the thing with a bare `get_object_or_404` (not the owner-filtered `get_queryset`), so a co-curator reaches a thing they don't own and the permission — not the queryset — is what gates them. **In a NETWORK `can_manage` is the thing's owner alone**: a co-curator edits, hides, activates and decides their own things and nobody else's. The founder's reach is the rescue (`Thing.can_rescue`): reject a pending request (`BookingActionView`, below) and hide (`IsThingManagerOrRescuer`).

**Serializers:**
- Create: `ThingCreateSerializer`
- Update: `ThingUpdateSerializer` (`status` is read-only to prevent direct manipulation, `type` is editable)
- Read: `ThingSerializer`

**Queryset:** Own things only (`Thing.objects.filter(owner=request.user)`), ordered by `-created`.

**Retrieve:** Uses `thing.can_view(user_code)` — owner, or invited to an ACTIVE collection containing the thing (INACTIVE things are only visible to their owner).

**Deployment policy (`CREATOR_POLICY`).** `perform_create` asks whether this deployment offers that verb to this account at all — **403** if not — **unless** it is a member contributing to a COMMUNITY collection they were invited to, of a type its owner allow-listed (`community_contribution_types`; a `CreatorPolicy` gates *initiating*, not *contributing* to a group someone else already vouched for). The collection is resolved before the check now, but a nonexistent or un-addable one still falls through to the **same 403** as no collection at all, so the verb refusal never turns on — or reveals — which collection was named. `perform_update` asks the same, but **only when the type actually changes** (a thing already under a withheld verb stays editable), and the COMMUNITY exception there needs *every* collection the thing sits in to allow the new verb. The standalone's policy allows everything, so none of this does anything upstream. See [`creator_policy`](../services/CLAUDE.md#creator_policypy--who-may-create-what-on-this-deployment).

**Create behaviour:** Optionally accepts `collection_code` in request body. `perform_create` raises DRF exceptions directly (no `{"error": ...}` two-phase protocol): an unknown `collection_code` → **404 NotFound**; a collection the user can't add to → **403 PermissionDenied**; a type/tag rule violation → **400 ValidationError** (field-keyed: `{"type": [...]}` / `{"tags": [...]}`, like `perform_update`). If valid, the thing is automatically added to it. **The verb is the server's**: for someone who may add to the collection, `verb_from_price(collection, fee, type)` gives `Thing.type` from the collection's kind and the price (a stall gives or sells, a library lends or rents out, a shed books) and a `type` the price contradicts is a 400 `{"type": "In a stall the verb follows the price…"}`; `perform_update` does the same when an edit touches the price or the type, except for a thing whose verb is not one of its collection's kind (kept from a mixed collection at the migration). It is only applied after `can_add_thing`, so the 403/404 ordering below still reveals nothing about a private collection's kind. **The collection's verb list** (`Collection.allowed_thing_types`, never empty) is still checked against the derived verb — 400, *"This group doesn't take prices."* for a paid verb in a COMMUNITY group whose members may not set a price. **`RESERVE_THING`** can *only* be created in a shed (`Collection.is_reservations_collection()`) — 400 `{"type": ...}` otherwise. Ordering matters and is deliberate: (1) `thing_type_denial` first (judged on the derived verb), so a deployment that withholds RESERVE answers **403**, not this 400; (2) a **standalone** RESERVE create (no `collection_code`) is the 400 straight away; (3) a *named* collection is resolved first — **404** if it doesn't exist, **403** if the caller can't add to it, and only then the **400** for "not a shed". So that 400 never doubles as a "does this code name a shed?" probe for someone with no standing there. `perform_update` applies the same shed rule when the type changes to/from RESERVE (no 404 concern — the thing's own collections already exist, and the caller is already `IsThingManager`). **Tags**: any `tags` on the thing must belong to the collection's `Collection.tags` vocabulary — returns 400 otherwise (tags require a collection; on update, `ThingUpdateSerializer.validate_tags` checks the union of the thing's collections' tags). Removing a tag from a collection (via `CollectionUpdateSerializer`) cascade-strips it from that collection's things.

**`activate` action:** Sets `status = 'ACTIVE'`. Returns 400 if thing is not INACTIVE.

**`hide` action:** Sets `status = 'INACTIVE'`. A manager of the thing (`Thing.can_manage`) or, in a network, its founder (the rescue) — 403 for everyone else. When the one hiding does not manage the thing and may rescue it, the thing's owner gets a `THING_HIDDEN` notice and email (nothing otherwise: a PROPRIETARY curator hiding another curator's thing tells nobody). Returns 400 if thing is not ACTIVE (cannot hide a TAKEN thing — cancel the hold first).

**`destroy` action (`_can_delete()`):** Permanent deletion (the thing and all related data). Four cases grant permission: (1) the user owns any collection containing the thing (a collection owner can always delete, any mode); (2) the user is a **co-curator of a PROPRIETARY** collection it sits in (2026-09 — that catalogue is the curators' collectively); (3) the user owns the thing and is a **dinamizador of the NETWORK** it sits in — lent or not, since a network's dinamizador runs their own things (never another dinamizador's); (4) the user is the current thing owner AND no `ThingTransfer` records exist (thing has never changed hands). The rule is `Thing.can_delete(user_code)` on the model, shared with the page that warns before deleting. **Deleting is always allowed whatever hangs from the thing — a loan in hand included, never a 409 — but it is not silent**: `perform_destroy` goes through `membership_service.delete_thing`, which reads the live requests (`BookingPeriod.blocking_filter`: pending, or accepted and not over) before the bookings cascade away and, once the transaction commits, emails each requester once (`send_thing_withdrawn_email`), except whoever deleted it. This holds in every mode and for anyone who deletes (owner, co-curator, founder). Leaving, being demoted, deleting a collection and erasing an account keep their own notices. Returns 403 otherwise. **`live_requesters_count`** on the thing's payload is the number of people that deletion would email (`membership_service.people_told_on_delete`, the very list `delete_thing` uses, the reader left out): only for someone who `can_delete` it and only when one thing is read (`None` in a list and for everyone else), and `DeleteThingPage` shows it before the button. The frontend shows the Delete button from `can_manage` (`useThingActions.canDelete`: the collection owner, or whoever manages the thing), not from the transfers.

### ThingBulkCreateView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/things/bulk/` |
| **Permission** | `IsAuthenticated` + `collection.can_add_thing()` |
| **Rate limit** | `10/h` per user |

CSV/ZIP bulk-add (F-9). Each row's verb is derived from the collection's kind and the row's fee exactly as for a single thing (`verb_from_price`); the **`type` column is optional** and a `type` the fee contradicts is a row error. Body is `{"rows": [{type?, headline, description, fee, availability, location, condition, tags, thumbnail, gallery, is_endless}, ...]}` (max 100 rows), parsed and previewed client-side by `BulkAddCsv`. Each row is validated with `ThingBulkRowSerializer` (the project's Safe* fields + a `reject_spreadsheet_formula` CSV-injection guard on free-text fields, including each `tags` entry; `thumbnail` uses `ImageIdField`, path-traversal-safe; `fee` accepts a decimal comma — `LocaleDecimalField` — since a CSV cell has no client `NumberInput` to normalise it first) , `thing_type_denial` (the deployment's `CREATOR_POLICY` — reported as a row error like every other row failure, since the contract here is that one response names every bad row) and `type_validity_error`; `tags` are additionally checked in the view against the target collection's `Collection.tags` vocabulary (mirrors the single-create subset check). **A CSV tag may name a localized vocabulary entry by any of its languages** (`_resolve_tag_aliases`): `{"es": "Crianza", "ca": "Criança"}` in the vocabulary accepts a CSV cell of `Crianza` or `Criança` (case-insensitively) as well as the exact canonical JSON, storing the canonical string either way; a casefolded alias that matches two distinct vocabulary entries is rejected as ambiguous rather than guessed, and an alias matching nothing keeps the existing "not defined by the collection" error. If **any** row fails the request returns `400 {"errors": [{row, errors}]}` and **nothing** is created. On full success every row is created in one `transaction.atomic()` and the response is `201 {"created": N, "codes": [...]}`. **Photos** are importable via the client's ZIP path: `BulkAddCsv` unzips, uploads each image to the bucket through the same ticketed path as every other upload, and sends the resulting storage keys as `thumbnail` (the cover) and `gallery` (the carousel, in the CSV's order, at most 8) — the server only ever receives the validated keys, never the binary. Each photo takes one upload ticket (`UploadTicketView` allows 120 an hour), which is why the client counts the distinct photos of a ZIP before it starts.

---

## Collection Views (`core/views/collections.py`)

### CollectionViewSet

| | |
|---|---|
| **Base** | `ModelViewSet` with `DefaultRouter` |
| **Lookup** | `code` |

| Action | Endpoint | Permission |
|--------|----------|------------|
| `list` | `GET /api/v1/collections/` | `IsAuthenticated` |
| `create` | `POST /api/v1/collections/` | `IsAuthenticated` |
| `retrieve` | `GET /api/v1/collections/{code}/` | `AllowAny` + `can_view()` — anonymous-safe: a PUBLIC, ACTIVE collection is readable without login |
| `update` | `PUT /api/v1/collections/{code}/` | `IsAuthenticated` + `IsCollectionCurator` (owner or co-owner) |
| `partial_update` | `PATCH /api/v1/collections/{code}/` | `IsAuthenticated` + `IsCollectionCurator` (owner or co-owner) |
| `destroy` | `DELETE /api/v1/collections/{code}/` | `IsAuthenticated` + `IsCollectionOwner` — deliberately **not** curator-widened; deleting the collection stays the founding owner's alone. `perform_destroy` deletes the collection and the things that were only in it inside `deleting_as(request.user)`; the things deleted are those with no membership in any other collection (a query of their own: counting through the related manager reuses its filtered join and always said one); the `COLLECTION_DELETED` and one `THING_REMOVED` per deleted thing come from the delete receivers (`core/services/deletion_events.py`), not from the view |

**Serializers:**
- Create: `CollectionCreateSerializer`
- Update: `CollectionUpdateSerializer`
- Read: `CollectionSerializer`

**Queryset:** Owned **or co-owned** collections, ordered by `-created` — `list` is "my collections", and a co-owner's curated group belongs there next to their own rather than only under `InvitedCollectionsView`'s "shared with me". List and retrieve actions use the module-level `_optimise_collection_queryset()` helper for `select_related`/`prefetch_related` optimisation (also reused by `InvitedCollectionsView`).

**Deployment policy (`CREATOR_POLICY`).** `perform_create` refuses a mode this deployment does not hand out with **403**, judging the **PROPRIETARY default** when the body names no mode, **and then the kind** (`collection_kind_denial`: a kind is open when any of its verbs is offered, so a policy that gives GIFT/SELL lets an account open a stall and nothing else; the kind is always present by then, named or deduced). The kind never changes, so creation is its only door. `perform_update` refuses switching an existing collection *into* a withheld mode — only on a real change, so a collection already in one stays editable by its owner. Both are no-ops under the standalone's open policy. See [`creator_policy`](../services/CLAUDE.md#creator_policypy--who-may-create-what-on-this-deployment).

**Retrieve:** Uses `collection.can_view(user_code)` — owner, or invited user if collection is ACTIVE (INACTIVE collections are only visible to their owner). The `CollectionSerializer.things` field excludes INACTIVE things for non-owners.

### CollectionInviteView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/invite/` |
| **Permission** | `IsAuthenticated` + collection curator (owner or co-owner) |
| **Rate limit** | 30 requests/hour per user, plus the shared daily invitation-email quota (below) |

Invites a user to a collection by email. Creates user if they don't exist (`get_or_create`). Returns 400 if the user is already invited (in M2M). **One invitation per person**: an address that this collection's founder or the one inviting has already invited and that has not accepted (`SENT` with the invitation still pending, or `DECLINED`) is refused before anything is created with **400 `invite_already_asked`** ("This person has already been invited. They can join with the share link."), so there is no resend and a blocked address leaves no `User`, RSVP, email or quota spent (`InvitationRecord`, `invitation_service.invitation_blocked`). Someone who accepted once can be invited to another group of the same founder. Joining by the share link or a public collection is never blocked. Creates two RSVPs (`COLLECTION_INVITE` for accept and `COLLECTION_REJECT` for decline) and sends invitation email with both links.

**Daily invitation-email quota (shared with the bulk endpoint).** The per-view rate limits count *requests*, so one bulk request could still fan out 100 emails (5/h × 100 rows ≈ 500 owner-authored emails an hour from one free account — a spam vector riding the platform's sending domain). `INVITE_EMAILS_PER_DAY` counts the invitation *emails* an account sends per day — **operator policy, not a product rule**: it guards a particular deployment's sending reputation, so the standalone ships it **unset (= unlimited)** and each operator sets their own (0 also means unlimited). It is shared between this endpoint and `CollectionBulkInviteView`. Exhausted → **429** `{"error": ...}` before any User/RSVP is created. The counter lives on the shared cache (`invq:{user}:{date}`, ~24h TTL) and follows `RATELIMIT_ENABLE` — off in dev/tests, same switch as the django-ratelimit decorators; its read-then-set shares the DatabaseCache non-atomicity note in `config/settings/base.py`.

**Request body:**
```json
{ "email": "lele@your-domain.test" }
```

| | |
|---|---|
| **Endpoint** | `DELETE /api/v1/collections/{collection_code}/invite/` |
| **Permission** | `IsAuthenticated` + collection curator (owner or co-owner) |

Removes a user from the collection's invite list. **The founder can never be removed**: a `user_code` equal to the collection's `owner` is a 400 `{"error": "The owner can't be removed from their own collection.", "code": "owner_cannot_be_removed"}`, answered **before** `invites` is read, so a stray `invites` row from before the founder was kept out cannot turn this into the deletion of things nobody else may delete. If the invite is still pending (user has not accepted yet), deletes the pending RSVPs instead of removing from M2M, and no revocation email is sent. If the invite was accepted (user is in M2M), ends the membership through `membership_service.end_membership` — which removes the user from `invites` **and `co_owners`** (`co_owners ⊆ invites`) and **deletes every thing they own in this collection**, any status, with `THING_REMOVED` events naming the curator — and sends the revocation email, which lists those things when there were any. When the one removing is **not the founder** (a co-curator), the founder also gets a `MEMBER_LEFT` in-app notice with `removed_by_name` (bare `name`) and `things_deleted` — they did not do it, so they must hear of it; the founder removing someone, the removed user and the co-curator get no such notice. The answer carries `things_deleted`. Those who had a live request or reservation on a deleted thing are emailed once the transaction commits (see `membership_service`). Demoting a co-curator (`CollectionCoOwnerView` DELETE) is not a removal and deletes nothing. **In a NETWORK** cancelling a pending invitation is any dinamizador's (inviting is theirs), but removing an accepted member is **the founder's alone** (403 `network_founder_only`) and is refused with **409 `member_holds_loans`** while the member has a started, unreturned loan, whoever lent it, or **409 `curator_things_lent_out`** while one of a dinamizador's things is out (`membership_service.network_exit_block`); the member's removal also deletes their pickup point.

**Request body:**
```json
{ "user_code": "ABC123" }
```

### CollectionCoOwnerView

| | |
|---|---|
| **Endpoints** | `POST` and `DELETE /api/v1/collections/{collection_code}/co-owners/` |
| **Permission** | `IsAuthenticated` + collection curator, owner or co-owner (`require_collection_curator`) |
| **Rate limit** | POST and DELETE: 30 requests/hour per user (the same decorator keyed to its method — demotion joined promotion's ceiling so a compromised curator can't thrash either). |

Promote or demote a co-curator, **in either mode** (2026-09, co-curators in PROPRIETARY). **Any curator may** — appointing help is part of the founder's reach, which a co-curator now shares over everything except deleting the collection (the CASCADE-delete root, still `IsCollectionOwner`). The accepted trade-off: co-curators can ping-pong demotions, and the founder — an FK, never an `invites` row, so this endpoint structurally cannot demote them (`_get_target` 400s on a non-member) — is the circuit breaker. **In a NETWORK both are the founder's alone** (403 `network_founder_only`: a co-curator who names or demotes would be deciding for the others' things). Demoting a dinamizador **deletes their things and their pickup point**; outside a network demoting deletes their page too (their things stay) — the notice (`DEMOTED_CO_OWNER`) says how many (`things_deleted`) — and waits (409 `curator_things_lent_out`) while one of those things is out; promoting writes the `PROMOTED_CO_OWNER` notice with `network: true`, so the card words the narrower reach of a dinamizador. The ceiling is `Collection.MAX_CO_OWNERS` = 10.

**`POST` behaviour:**
- 403 (`co_owners_denial`) if this deployment's `CREATOR_POLICY` withholds `co_owners_enabled`.
- 400 if `user_code` isn't already in `invites` — promotion only, never a separate invite door (`co_owners ⊆ invites`).
- 400 when the collection already holds `Collection.MAX_CO_OWNERS` (10) co-curators — the abuse bound on one stolen curator credential (every promotion hands over the member list), not the design intent of 1–2. Promoting someone who is *already* a co-curator stays idempotent and never hits the ceiling; a collection holding more than 5 is not broken, it just cannot grow. The 400 is **coded** like a request's refusals: `{"error": "This collection already has the maximum of 10 co-curators", "code": "co_owners_full", "params": {"max": 10}}`, so the SPA says it in the reader's language from `requestErrors.co_owners_full_{one,other}` (`test_refusal_codes.py` reads this file's codes too and fails for one with no translation); the sentence is the fallback for a client that lacks it. Both methods are rate-limited (30/h), and a 429 has no body.
- **The ceiling check and the add are one locked step**, `Collection.promote_co_owner(member)` (2026-09-29): it locks the collection's row (`select_for_update`) and reads the membership test and the `count()` **under** the lock, then adds, returning `Promotion.ADDED`, `ALREADY` or `FULL`. The view only translates: `FULL` → the coded 400 above, `ADDED` → the notification, `ALREADY` → a bare 200. It used to be `count()` then `add()` with nothing between, so promotions running together all read the same count and all added — from 4, four at once ended at 8 — which defeats the one bound that exists for a stolen credential. The race is proved in `test_booking_row_locks.py`, **on PostgreSQL only** (SQLite drops `FOR UPDATE`; it is skipped locally and runs in CI).
- Adds to `co_owners` (idempotent) and, on the first promotion only (`Promotion.ADDED`), creates a `PROMOTED_CO_OWNER` in-app notification for the member. No email — a deliberate v1 simplification.

**`DELETE` behaviour:**
- Same membership validation as POST, **except no `co_owners_denial` check** — the gate is on bringing co-curator status into existence, never on living in it (the same grandfathering `creator_policy` already applies to a mode or a verb). A curator must always be able to demote, even on a deployment that has since disabled the feature.
- Removes from `co_owners` (idempotent, a harmless no-op on a plain member) and, if they were actually a co-owner, creates a `DEMOTED_CO_OWNER` notification **and then takes out of their inbox the team notices of this collection** (`drop_team_notices_of`, 2026-10-02 — see `services/CLAUDE.md` § The team). The member stays in `invites` — demotion removes the admin tier, not the membership. Removing a co-curator from the group (`CollectionInviteView.delete`) ends the role too and does the same; removing a plain member does not.

**Request body:**
```json
{ "user_code": "ABC123" }
```

### CollectionPointView

| | |
|---|---|
| **Endpoint** | `GET` / `PUT /api/v1/collections/{collection_code}/point/` |
| **Permission** | `IsAuthenticated` + collection curator (`require_collection_curator`, the founder included) |
| **Rate limit** | PUT: 30 requests/hour per user |

The page the curator asking has in this group, **in any collection**: name, logo, about and contact; in a **network** also their pickup point and the conditions of their own loans (403 for a member who is not a curator). GET returns it, or the empty fields when there is none yet; PUT upserts it through `NetworkPointWriteSerializer` (the collection's own widths, HTML rejection, localized about and conditions, `closed_dates` parsed as the collection's line). **Outside a network a PUT keeps only `entity_name`, `logo`, `about` and `contact`** and ignores the rest without error, and a GET serves the network's fields empty. Each curator reads and edits **only their own**; every page travels with the collection (`points` in `CollectionSerializer`, public, in every mode, address included in a network) except `email_note`, read back only by its curator and the founder.

### CollectionJoinView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/join/` |
| **Permission** | `IsAuthenticated` + the collection must be readable (`can_view`) and PUBLIC |
| **Rate limit** | 30/h per user, plus the operator's `COLLECTION_JOINS_PER_DAY` ceiling |

Lets a **signed-in** reader join a PUBLIC collection themselves — the mirror of `CollectionLeaveView`, and the half of login-to-act that was missing. The anonymous funnel (`POST /auth/join/`, reached from `/collections/{code}/join`) takes an email and answers with a magic link, which is no use to a session that already exists; so the one reader with an account and the most intent had no way into a public group, while `CollectionPage` offered them "Add thing" — an action `Collection.can_add_thing` refuses without an invite, after the form was filled and the photos uploaded.

Answers **404** whenever `can_view()` says no, so a PRIVATE or INACTIVE collection never confirms it exists; **400** for the owner ("You already own this collection."); **429** once the collection has spent its day's joins. There is also a **403** for a collection that is readable but not PUBLIC, and it is **unreachable as the guards stand** — `can_view` admits a non-owner only to a PUBLIC ACTIVE collection or one they are invited to, and `is_invited` is the same query the membership check above it runs. It is kept because that invariant lives in another file: widen `can_view` (a federated tier, a "readable by link" mode) and it is what stops a readable-but-not-public collection becoming joinable. The two tests that pin the invariant instead of the branch are `test_a_private_collection_does_not_confirm_it_exists` and `test_a_member_of_a_private_collection_is_told_they_are_already_in`. An existing member gets a plain `200` and nothing happens twice. On success it goes through `_join_collection` — the single funnel every join path shares — so it logs one `MEMBER_JOINED` (`Event.Source.PUBLIC`, the same door the anonymous half records), sends the welcome document if the owner set one, and consumes one of the day's joins. The ceiling applies here for the reason it exists: one that only stopped strangers would be a cap anyone with an account could walk around.

### CollectionLeaveView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/leave/` |
| **Permission** | `IsAuthenticated` + must be an invited member and not a curator |

Lets an invited member remove **themselves** from a collection (self-unlink) — the inverse of the curator-only `CollectionInviteView` DELETE. Returns 400 if the requester is the collection **owner** ("The owner can't leave their own collection." — owners delete instead), a **co-owner** ("A co-owner can't leave — ask the owner to demote you first." — staff, not a rank-and-file member; the owner demotes them via the co-owners endpoint), or is **not a member** ("You are not a member of this collection."). On success ends the membership through `membership_service.end_membership` (removes the user from `invites` and **deletes every thing they own in this collection**, any status, even with requests or loans running; the people who had asked are emailed), creates a `MEMBER_LEFT` in-app notification for the owner (payload: `collection_headline`, `member_name`, `collection_code`, `things_deleted`), and returns `200 {"message": "You have left the collection", "things_deleted": n}`. The frontend shows the "Leave the group" button (hero, `CollectionSerializer.is_member` gate) → `LeaveCollectionPage` confirm → back to Home.

### CollectionProposeInviteView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/invite/propose/` |
| **Permission** | `IsAuthenticated` + must be a member and not a curator + `collection.allow_member_proposals` |
| **Rate limit** | 30/day per member |

A member recommends somebody: `{email, note?}` → an `InvitationProposal` plus, **for every curator** (the founder and each co-curator, never the one recommending — `invitation_service.proposal_team`), an email in their language, an in-app `INVITE_PROPOSED` and an approve/reject pair of RSVPs minted to them. **Nothing reaches the proposed address** — no `User` row, no email — until a curator approves. Open in **both** modes: PROPRIETARY decides who may add a *thing*, never who may suggest a person, and a curator's approval is the gate either way. 400 for a curator — owner or co-owner (they invite directly), for a non-member, for someone already in the group, and for a duplicate pending suggestion; **403** when the owner has switched recommendations off.

**The last two 400s share one message, and must keep sharing it.** "Already in the group" and "already suggested" used to read differently, which made the first an email-membership oracle: a member could put any address to this endpoint 30 times a day and read a yes/no on whether it belongs to a co-member — the fact the roster withholds from non-owners (`invites` is `code` + `name`, no email). The single answer ("either they are already in this group, or someone has already suggested them") still tells the proposer the only thing they needed, which is that there is nothing to do. Pinned by `test_an_address_already_inside_is_answered_exactly_like_one_merely_queued`, which compares the two responses byte for byte.

The 30/day cap is high on purpose: abuse is not expected, and an owner has a better answer than a quota — removing the member.

### CollectionProposalActionView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/proposals/{proposal_code}/{approve\|reject}/` |
| **Permission** | `IsAuthenticated` + collection curator (owner or co-owner) |

The owner's or a co-owner's in-app answer; the email links reach the same two decisions through `VerifyLinkView`. **Whoever decides, it is settled for the whole team**: `approve_proposal` / `reject_proposal` end with `clear_proposal_traces`, which deletes every curator's `INVITE_PROPOSED` and every link minted for the suggestion. Curator-only — the proposer must not be able to wave their own suggestion through. Approving runs `invitation_service.proposal_approval_blocked` first — the owner's daily quota (429) and the collection's member ceiling (400), since an approval that can't be delivered should say so rather than half-happen — then goes through `approve_proposal`. The quota and the ceiling answer `{error, retryable: true}` — the suggestion stays pending and the owner may come back to it; an address already invited answers `invite_already_asked` with no `retryable` (still pending, for a curator to decline; `approval_refusal_response` decides both). 400 (with no `retryable`) on a suggestion that is no longer pending. That includes losing a race: `approve_proposal` / `reject_proposal` reserve the decision with a conditional update before any effect, and a curator who loses it (`ProposalAlreadyDecided`) gets the same `proposal_not_pending` 400 with nothing sent; the emailed link answers the same and burns the pressed RSVP.

**The guard is shared with the emailed approve link**, which used to apply neither: an owner clicking the link in their mail client instead of the button in the app walked straight past `INVITE_EMAILS_PER_DAY`, a cap that exists to protect the deployment's sending reputation. Nothing documented the difference and this view's own reasoning argued against it, so the two routes now answer identically. A blocked approval decides nothing and consumes no RSVP — "not now", not "never". **Declining is never blocked**: it adds nobody and mails one member who is already inside the count.

### CollectionDigestPrefView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/digest/` |
| **Permission** | `IsAuthenticated` + must be an invited member or the founder |
| **Rate limit** | 30 requests/hour per user |

A member — or the founder — silences (or un-silences) this one group's digest **and the daily sign-ups email to the team**: `{"muted": true|false}` → `Collection.digest_muted`. The digest goes to the whole team (`invites`, which holds the co-curators, and the founder), so each of them has the switch; anyone else gets **400**. Idempotent (`add`/`remove`), so a double POST is harmless.

This is the control that lets `User.notify_news` default to `True` without it being a pre-ticked opt-in (DESIGN §6): leaving one group's summaries costs the member none of their Cat. 2 activity email. Read back as `is_digest_muted` on `CollectionSerializer`. **Two ways out, both one click**: the "Mute the summary" / "Get the summary again" entry of the collection menu (for a member and for whoever runs the group; `useDigestPreference` in the frontend posts here and reads `is_digest_muted` back to word the entry), and the link in every digest's footer (`DigestMuteByTokenView`, below). The hero itself carries no switch any more (2026-09-21).

### InvitedCollectionsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/invited-collections/` |
| **Permission** | `IsAuthenticated` |

Lists ACTIVE collections where the current user is in the invites M2M. INACTIVE collections are excluded — they are only visible to their owner. Not paginated.

### MyPendingInvitationsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/my-invitations/` |
| **Permission** | `IsAuthenticated` |

Lists pending collection invitations (not yet accepted) for the current user. Returns `COLLECTION_INVITE` RSVPs for the user, joined with the collection and its owner. For each invitation returns: `accept_code`, `reject_code`, `collection_code`, `collection_headline`, `owner_name`. Used to display in-app invitation notifications on the HomePage.

### CollectionShareLinkView

| | |
|---|---|
| **Endpoints** | `POST` and `DELETE /api/v1/collections/{collection_code}/share-link/` |
| **Permission** | `IsAuthenticated` + collection curator (owner or co-owner) |
| **Rate limit** | POST: 30 requests/hour per user. DELETE: unrestricted. |

Curator management of the public share token — a co-owner may generate, rotate and revoke it just like the owner. The token is a 22-character URL-safe bearer credential (`secrets.token_urlsafe(16)`); anyone with the resulting `/share/{token}` link can join the collection by completing the join flow. The token is intentionally excluded from `CollectionSerializer` and any other read endpoint — it must never leak.

**`POST` behaviour:**
- Generates a new token if none exists. Returns the existing token unchanged on subsequent calls (idempotent).
- Pass `{"rotate": true}` to force a fresh token (invalidates any previously shared link).
- Returns `{share_url, share_token}`. `share_url` is built from `settings.SHARE_LINK_BASE_URL` (default `http://localhost:3000/share`).

**`DELETE` behaviour:**
- Sets `share_token` back to `null`. The shared link becomes invalid for everyone immediately.
- Returns `{"message": "Share link revoked"}`.

**Frontend integration:** `ShareCollectionMenu` (HDS Select with `IconEnvelope` / `IconShare` / `IconWhatsapp`) calls `POST` lazily the first time the owner triggers any share action. The URL is cached for the rest of the session to avoid extra round-trips.

### SharePreviewView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/share/{token}/preview/` |
| **Permission** | `AllowAny`, `authentication_classes = []` — the 22-char token is the whole credential |
| **Rate limit** | 30 requests/minute per IP |

The **name, description and language** of the collection a `/share/{token}` link opens, so `SharePage` can render "Join the Chalmercadillo" instead of "Join us on OIUEEI" — a stranger handed the link on WhatsApp has no idea what OIUEEI is. Returns **only** `{headline, description, language, kind, theeeme_colors, koro}` (the kind is as unrevealing as the language: the app needs it for the page that follows; the palette is the group's own colours — the join page is the door of that group and wears them, so a stranger holding the link needs them before they are anything to it). `headline`/`description` are **raw** (either may be a `{lang: text}` map the SPA resolves against the reader's language — same as every other collection read); `language` (added 2026-09-15) feeds `useCollectionLanguage` — this join door is reached before a stranger is a member of anything, so the collection's own language is the only signal there is yet, and it is no more sensitive than the other two. Never the owner, the roster, a member count or even the collection code.

Answers a **generic 404** (`Http404` → DRF's handler) for an unknown, revoked or INACTIVE token — the same `share_token=… , status=ACTIVE` filter `JoinView._resolve_target` uses — so the preview goes dark the instant the link does and reveals nothing the link itself doesn't already. The bearer link is the credential and whoever holds it already knows a real collection is behind it, so naming that collection to them is not a leak; naming anything *else* would be.

### ShareJoinView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/share/{token}/join/` |
| **Permission** | `IsAuthenticated` (cookie or Bearer, so CSRF applies like every other cookie-authenticated POST) |
| **Rate limit** | 30 requests/hour per user, plus the operator's `COLLECTION_JOINS_PER_DAY` ceiling |

Accepts a `/share/{token}` invitation with the session the reader already has. `SharePage` used to ask for an email even then — email, inbox, link, back — and in a neighbourhood the same people are in several groups while this link is the main viral route, so it was a round trip for the people who use it most. It is the token's twin of `CollectionJoinView` (which joins a **PUBLIC** collection by its code): there the credential is the collection being public, here it is the token.

**The token is looked up exactly as `SharePreviewView` looks it up** — `share_token=token`, `status=ACTIVE` — and an unknown, revoked or INACTIVE one is one generic **404** (`Http404`), the same body for all three (`test_an_unknown_a_revoked_and_an_inactive_token_answer_the_same_404` compares them). **Why that does not break the anti-enumeration the anonymous door keeps:** the preview already answers a bad token with that very 404, to anyone, with no account, so an account holder learns nothing new by asking here; the space is 22 URL-safe characters, and this adds 30/h per user on top of the preview's 30/min per IP. Nothing else can be probed: the collection's *code* (`PUBLIC` groups print it in their URL) is not looked up as a token (`test_a_public_group_code_is_not_a_token`), and a PRIVATE group is reachable only through its token.

- **Never returns or touches the token**, and creates no `User` and no `RSVP` (there is a session, and the magic link is what this replaces). The answer is `{"collection": code, "collection_kind": kind, "joined": bool}` — the code and kind are what the SPA navigates to (`/{kind}/{code}`), and the person is now a member who reads it on every page.
- **Idempotent.** The owner and any member — a co-curator is in `invites` — get `200` with `joined: false` and nothing else happens: a curator trying their own link lands on their collection instead of an error, and a double tap logs one `MEMBER_JOINED` and sends no second welcome PDF.
- **The one funnel.** A new member goes through `_join_collection(collection, user, source=Event.Source.SHARE)` — one `MEMBER_JOINED`, the welcome document if the owner set one, the member counter — after `join_quota_exhausted()` has been asked (**429**, the same `detail` as `CollectionJoinView`, nobody joins) and followed by `consume_join_quota()`. A ceiling that only stopped strangers would be one anyone with an account could walk around, and an account costs a free mailbox.
- **Unauthenticated → 401.** The SPA's `apiFetch` then sends the reader to `/login?next=/share/{token}` and, after the magic link, back to the button (see `RequestLinkView`'s `next`).

Pinned by `core/tests/integration/test_share_join.py`, each test named for its behaviour and each guarantee mutated (see the commit that added it).

### CollectionEmailNoteTestView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/email-note/test/` |
| **Permission** | `IsAuthenticated` + collection curator (owner or co-owner) |
| **Rate limit** | 10 requests/hour per user |

Mails the acting curator — and nobody else — their `email_note` **draft** (`{"email_note": "…"}`, unsaved, validated by `EmailNoteTestSerializer` with the collection field's own per-language limits: 512 visible / 2048 stored), rendered by `send_email_note_test_email` through the email's own `_note_blocks` and layout. A note written per language comes back with every version under its endonym. The note only ever reaches requesters, and a curator can't request their own things, so it was written blind; a page preview would lie (the email's Markdown subset has no headings or tables and prints a link's host after it). **Mandatory category** — the curator asked for it that moment, so an activity opt-out must not swallow it. 403 for a non-curator, 400 for an empty or over-long note, `{"status": "sent"}` otherwise.

### CollectionBroadcastView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/broadcast/` |
| **Permission** | `IsAuthenticated` + collection curator (owner or co-owner) |
| **Rate limit** | 5 requests/day per user |

Sends a broadcast email from the acting curator — the owner or a co-owner — to all invitees; the `Reply-To` and the name shown are whoever actually sent it, not necessarily the founding owner. **In a network it is signed with the `display_name` of the sender's pickup point** (the entity's name, else their own), by email and in the inbox notice. Validates `message` (SafeTextField, max 256) via `CollectionBroadcastSerializer`; the subject is auto-generated as `Hey! {collection_headline}` (the owner does not provide one). Returns 400 if the collection has no invitees. Emails carry a `Reply-To` header (the owner) and a link to the collection (labelled "Open the group" — it read "I can help!", a leftover of the retired WISH_THING call-for-help flow, until 2026-09); the in-app `BROADCAST` notification carries `collection_code` so it can deep-link there too. The email send is dispatched off the request thread in production (`_send_broadcast` → daemon thread when `EMAIL_SEND_ASYNC`, mirroring `_send_bulk_invites`) so a large group's sequential SMTP can't exhaust the Heroku 30s window (H12); the in-app notifications are still written synchronously.

**Request body:**
```json
{ "message": "Bring snacks please" }
```

**Response (200):**
```json
{ "message": "Broadcast sent", "recipients": 5 }
```

### CollectionBulkInviteView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/invite/bulk/` |
| **Permission** | `IsAuthenticated` + collection curator (owner or co-owner) |
| **Rate limit** | 5 requests/hour per user, plus the shared daily invitation-email quota (see `CollectionInviteView`) |

Invites many guests at once from a client-parsed CSV (`{"invites": [{"email": ..., "name": ...?}, ...]}`, capped at `MAX_ROWS=100`). Best-effort: valid, new addresses are invited (accept + reject RSVP pair created, invite email sent) and the rest are reported as skipped with a reason (`invalid`, `duplicate`, `already_member`, `already_asked`, `already_invited`, `daily_limit`) — one bad row never fails the batch. The **daily quota** (`INVITE_EMAILS_PER_DAY`, shared with the single endpoint) is enforced per email actually sent: an exhausted quota returns **429** outright; a batch that crosses the cap mid-way invites up to the remaining allowance and reports the overflow rows as skipped with reason `daily_limit` (no User row is created for those), so the owner sees exactly which addresses wait for tomorrow.

**Response (200):** `{ "invited": 2, "skipped": [{"email": "...", "reason": "..."}], "total": 3 }`

### CollectionStatsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/collections/{collection_code}/stats/` |
| **Permission** | `IsAuthenticated` + collection curator (owner or co-owner) |

Curator usage statistics for a collection, returned as a `metric,value` CSV download: a snapshot (members, pending invitations, things total/active) plus a 90-day activity window, and an aggregate age-range/postal-code breakdown (member demographics stay COMMUNITY-only and per-member on the guests page — this endpoint is aggregate-only). **A bracket or a postal code is named only when at least `STATS_MIN_GROUP` (3) members share it**: below that the figure is about a person ("Postal 48001: 1" in a group of two), so those members are summed into "Birth year shared by fewer than 3" / "Postal, other codes", and an empty bracket is left out too — were only the small ones missing, the gaps would name them. Same rule in every mode, since this file and the collection export that carries it travel. Pinned in `test_collection_stats.py`.

**In a NETWORK the founder gets the figures of the whole network and a dinamizador those of their own things**: the six rows about things, bookings and handovers (`Things total/active/reserved/added`, `Bookings`, `Handovers`) are cut to the dinamizador's, the members, invitations and breakdown stay the network's (the members belong to the network, not to an entity), and a first row `Pickup point` (the entity's name, else the dinamizador's own, quoted with an apostrophe if it starts like a formula) says whose figures they are. Same condition as the group copy; outside a network nothing changes. Pinned in `test_collection_stats.py`.

The metrics themselves live in [`export_service.collection_stats_rows()`](../services/CLAUDE.md#export_servicepy--data-portability-right-to-a-copy); this view only wraps them in a CSV. The collection export renders the same rows as a dict, so the two can't drift.

---

## FAQ Views (`core/views/faq.py`)

### ThingFAQListView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/faq/` |
| **Permission** | `AllowAny` (part of the public social layer — anyone who can view the thing may read its FAQs) |
| **Pagination** | `StandardResultsPagination` |

Lists FAQs for a thing. A **manager** — the owner, or a curator of a PROPRIETARY collection it sits in (`Thing.can_manage`, 2026-09) — sees all FAQs including hidden ones. Everyone else sees only visible FAQs.

**Response fields:** `code`, `thing`, `created`, `questioner` (user code), `questioner_name` (user display name — **empty for a reader who is not signed in**; see the anonymous-read note under Security), `question`, `answer`, `is_visible`.

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/faq/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` + not a **manager** (`Thing.can_manage`) |
| **Rate limit** | 20 requests/hour per user |

Creates a new FAQ question. A manager — the owner, or a PROPRIETARY collection's curator — cannot ask about a thing they run (400). Notifies **every manager** of the thing (`Thing.managers` — owner + a PROPRIETARY collection's curators, minus the asker) by email + in-app, each with a "View and reply" link; in COMMUNITY that is just the thing owner.

**Request body:**
```json
{ "question": "Is this available in blue?" }
```

### FAQDetailView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/faq/{faq_code}/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` |

Returns a single FAQ. Hidden FAQs are only visible to a **manager** of the thing (`Thing.can_manage` — owner or a PROPRIETARY collection's curator) and the questioner. Returns 404 for others.

### FAQAnswerView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/faq/{faq_code}/answer/` |
| **Permission** | `IsAuthenticated` + manager of the thing (`Thing.can_manage`) |

Answers a FAQ. Sends a notification email + in-app to the questioner, naming whoever answered (`request.user.name`, bare). **The rest of the team hears it too** (a question warns every manager but the answer warned only the asker, so a co-curator's inbox kept a `FAQ_QUESTION` asking for a decision the founder had already made): `send_faq_answered_to_team_email` reaches every other manager of the thing (minus the answerer, minus the questioner — the questioner gets their own answer email), and every `FAQ_QUESTION` notification for this FAQ is deleted for **all** managers (`_clear_faq_question_notifications`, matched by `payload__faq_code` — the key is written at creation since this change; older notifications without it never match and stay until dismissed by hand).

**Request body:**
```json
{ "answer": "Yes, it comes in blue." }
```

### FAQVisibilityView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/faq/{faq_code}/hide/` |
| **Permission** | `IsAuthenticated` + manager of the thing (`Thing.can_manage`) |

Hides a FAQ. Sends notification email to questioner (includes thing headline only, no question text). **The rest of the team hears it too** (as with `FAQAnswerView`): `send_faq_hidden_to_team_email` reaches every other manager (minus the hider and the questioner), and every `FAQ_QUESTION` notification for this FAQ is deleted for all managers via the shared `_clear_faq_question_notifications` — an unanswered one stopped owing anybody a reply the moment it was hidden. Hiding a FAQ that is **already hidden** is a no-op that tells nobody (200, same body) — a double click or a teammate hiding it a moment later must not mail the asker and the team twice.

| | |
|---|---|
| **Endpoint** | `POST /api/v1/faq/{faq_code}/show/` |
| **Permission** | `IsAuthenticated` + manager of the thing (`Thing.can_manage`) |

Shows a previously hidden FAQ. **No notice to anyone** — putting a question back is not something the team needs to hear.

---

## CSP Report View (`core/views/csp.py`)

### csp_report

| | |
|---|---|
| **Endpoint** | `POST /api/v1/csp-report/` |
| **Permission** | Anonymous — the reporter is a browser, and it sends no credentials. `@csrf_exempt` for the same reason |
| **Rate limit** | 30 requests/hour per IP |

Where the browser reports a Content-Security-Policy violation. It exists so that a blocked injection leaves a trace instead of failing silently — the CSP is the last net under `MarkdownText`, the one place the app hands the browser markup it did not write. Reports go to the `security` logger, alongside the auth events.

**First-party on purpose** (DESIGN §9): a hosted report collector would receive the URL of every page a member visits, which is exactly the tracking OIUEEI promises not to do.

**A plain Django view, not a DRF one**: browsers send `application/csp-report` or `application/reports+json`, which DRF's JSON parser rejects with a 415 before the handler runs.

**Always answers 204**, whatever arrives — the browser is not a client we owe an error to, and a report we can't parse is one to drop. Three guards keep the endpoint from becoming a liability of its own, since anyone can POST to it and browser extensions generate a lot of false reports:

- **Body cap** (`MAX_REPORT_BYTES`, 8 kB) — the log must not be a surface an anonymous POST can write megabytes into.
- **Field allowlist, each truncated** — only `violated-directive`, `effective-directive`, `document-uri`, `blocked-uri` and `script-sample` are logged (the two attacker-influenced ones get the shortest limits). A report can't smuggle its own payload into the log.
- **Newlines stripped** — `blocked-uri` is attacker-chosen, and a raw newline in it would forge extra `[SECURITY]` log lines.

Both report shapes are understood: the legacy `{"csp-report": {...}}` and a `report-to` batch (`[{"body": {...}}, ...]`, first entry only — the rest are repeats). Pinned by `core/tests/unit/test_csp_report.py`, whose negative assertions need the local `security_log` fixture: the `security` logger sets `propagate: False`, so plain `caplog` reads empty and every "must NOT be logged" test would pass vacuously.

---

## Upload Views (`core/views/upload.py`)

### UploadTicketView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/upload/ticket/` |
| **Permission** | `IsAuthenticated` |
| **Rate limit** | 120 requests/hour per user — one ticket per photo, so a ZIP import of up to 100 things fits in one hour — and, of those, **10/hour for document tickets** (`DOCUMENT_TICKETS_PER_HOUR`). A welcome PDF is set a few times in a group's life; at the photos' 120 any account could put 600 MB of public PDFs an hour on the bucket, served from the operator's domain until the orphan sweep reaches them. Not gated on curating a collection: the create form uploads the PDF before the collection exists |

Hands the browser a short-lived ticket to write **one** object to the media
bucket, so the binary never routes through Django. That property is unchanged
from the Cloudinary signature endpoint this replaces; what changed is who
enforces the rules. Before, the server computed an HMAC over a set of upload
parameters and the client echoed them back. Now the rules are signed into a
presigned `PUT` URL, and the storage provider refuses the upload with
`SignatureDoesNotMatch` if any of them is altered in flight.

Four things are decided here and cannot be moved by the client:

- **the key** — `secrets.token_urlsafe(16)` inside the folder, so a client can't
  name its own object and overwrite somebody else's. The key's entropy is also
  what keeps a *public* object unguessable: the bucket is private and does not
  list, so knowing the key is the only way to reach the object;
- **the folder** — one of `oiueei/users`, `oiueei/things`, `oiueei/collections`
  in image mode, and `oiueei/documents` **forced** in document mode. Anything
  else falls back to `oiueei/users`, `oiueei/documents` included, so an image can
  never be written where documents live;
- **the content type** — from an allowlist, signed exactly. Raster photo types
  only in image mode (**SVG is excluded** — it can carry script, and an
  `<img>`-rendered upload must never carry active content), `application/pdf`
  alone in document mode. Because it is signed rather than sniffed at read time,
  the type the bucket later serves is the type decided here — which is also what
  stops an upload coming back as `text/html` and turning the bucket into an XSS
  origin. It is not optional: an object stored without one is served as
  `binary/octet-stream`, and the welcome PDF then downloads instead of opening;
- **the size** — and this one is new. Cloudinary's signature computation
  *excluded* `max_file_size`, so signing it made ours diverge from theirs and
  every document upload failed with "Invalid Signature" (a production
  outage). The cap had to live in `PdfUpload`, in the browser, where anyone could
  skip it. There is no such exclusion here: the client declares
  `content_length`, this view refuses anything over the limit, and the exact
  number is signed into the URL. Declaring one size and sending another — in
  either direction — fails the signature, and JavaScript cannot forge it because
  it may not set `Content-Length`. Limits: **5 MB** documents (the welcome doc's
  long-standing figure, now enforced where it can't be skipped), **10 MB**
  images — a backstop against abuse rather than a UX limit, since the browser
  downscales to 1216px first and a real upload lands in the hundreds of kB.

Any `kind` other than the literal `"document"` is an image upload, so an unknown
value can only ever narrow to the image defaults.

**Request body:**
```json
{ "folder": "oiueei/things", "content_type": "image/webp", "content_length": 183422 }
{ "kind": "document", "content_type": "application/pdf", "content_length": 812004 }
```

**Response:**
```json
{
    "url": "https://<bucket>.<endpoint>/<key>?X-Amz-Algorithm=...&X-Amz-Signature=...",
    "method": "PUT",
    "headers": {
        "x-amz-acl": "public-read",
        "Content-Type": "image/webp",
        "Cache-Control": "public, max-age=31536000, immutable"
    },
    "key": "oiueei/things/<random>"
}
```

`Cache-Control` is signed with the upload because there is no CDN in front of
the bucket — without it every visit is another round trip to the storage region.
It is safe to make it `immutable`: keys are random and an object is never
rewritten.

**Frontend upload flow:**
1. Call this endpoint with the file's type and byte length.
2. `PUT` the file as the **raw request body** (not multipart) to `url`, with
   exactly the `headers` given.
3. Store `key` in the relevant model field (`thumbnail`, `User.photo`, an entry
   in a Thing's `gallery`, or `Collection.welcome_doc`) — the response has no
   body to read a name out of, because the key was decided before the upload.

---

## Theeeme Views (`core/views/theeemes.py`)

### TheeemeListView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/theeemes/` |
| **Permission** | `IsAuthenticated` |

Lists the twelve palettes a curator can pick for a collection (`theeeme` in the create/edit body). Returns `code`, `name` and the six colours for each via `TheeemeSerializer`. **It is the selector, and only the `theeemes` table**: the app's own palette (`Braaanding`) is never in it.

---

## Booking Views (`core/views/booking.py`)

### ThingCalendarView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/calendar/` |
| **Permission** | `AllowAny` + `get_viewable_thing()` (public read on a viewable thing) |

**The pause (`Thing.pause_period`) is served the same way**: to anyone who is asking to book (whoever does not manage the thing, and a manager with `?for=request`) it comes as one more whole-day stretch with the full ones; a manager without `?for=request` is served the real bookings only, as before. **With several units (`Thing.units`, RESERVE only)** a thing is taken only where all of them are on, so whoever does not manage it is served `saturated_periods(bookings, units)` — the full stretches, without names — instead of the bookings (with one unit it is the bookings, as before). A manager is served the real bookings with names, **unless they ask `?for=request`**: then they are served what a member would be (the request page asks for it, so a curator who books sees the same calendar), through the same serializer without names. `ThingSerializer.bookings` (the owner's list) keeps the real bookings.

Returns blocked periods for a thing's calendar — PENDING/ACCEPTED bookings not already over (`BookingPeriod.blocking_filter`: undated, or ending yesterday or later); a thing's past is not served, to anyone. A **manager** — the owner, or a curator of a PROPRIETARY collection it sits in (`Thing.can_manage`, 2026-09) — sees full details (`BookingPeriodOwnerCalendarSerializer`); guests see only dates and status (`BookingPeriodCalendarSerializer`).

### MyBookingsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/my-bookings/` |
| **Permission** | `IsAuthenticated` |
| **Pagination** | `StandardResultsPagination` |

Lists all booking requests made by the current user, ordered by `-created`.

### OwnerBookingsView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/owner-bookings/` |
| **Permission** | `IsAuthenticated` |
| **Pagination** | `StandardResultsPagination` |

Lists booking requests on the current user's own things, **plus** (2026-09) every booking on a thing in a **PROPRIETARY** collection they curate (owner or co-curator) — `.distinct()` over `Q(owner_code=user) | Q(thing_code__collections__mode=PROPRIETARY, …owner=user) | Q(…co_owners=user)`, since a shared catalogue's `booking.owner_code` is the thing's owner, who may be another curator. Ordered `-created`. Consumed by the frontend's **`/owner-bookings`** page — the owner's mirror of `/my-bookings`. **The founder of a NETWORK** also sees the requests on every entity's things, to be able to reject one (the rescue); a co-curator of a network sees only their own.

Each row also says whether the reader may **remind the borrower to return it** (`can_remind_return`, from `BookingPeriod.can_be_return_reminded` plus `Thing.can_manage` of the reader) and when that last went (`return_reminded_at`). The question "has this thing been lent again since?" is a `lent_again` `Exists` annotation on the list query, and `thing_code__collections` is prefetched manager-ready (`managers_ready_collections`), so a page of finished loans costs no query per row — pinned in `test_return_reminder.py` for the owner and for a co-curator.

### BookingCancelView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/bookings/{booking_code}/cancel/` |
| **Permission** | `IsAuthenticated` + booking requester (**or any curator of the reservations collection**, for a RESERVE booking) |

Allows the requester to cancel their own pending booking. Validates `booking.requester_code == request.user`, checks `is_valid()`. Calls `cancel_booking()` service (restores Thing status to ACTIVE for single-use types), and deletes related RSVPs. **The non-RESERVE branch stays requester-only** — a curator kills a LEND/RENT/GIFT/SELL hold by *rejecting* it (`BookingActionView`), which mails the requester a decision.

**RESERVE_THING branch:** when `booking.thing_type == RESERVE_THING` the view calls `cancel_reservation(booking, request.user)` instead — **any curator of the reservations collection may cancel** (2026-09, `Thing.can_manage`; rule 4: they may need the space), and only while the reservation hasn't started. Everyone who didn't cancel is notified — the member (unless they were the one) and every other curator, in-app + email; `other_name` is always whoever actually cancelled. A confirmed reservation is `ACCEPTED`, not `PENDING`, so the `is_valid()` path never applied to it.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Cancelled |
| 400 | Booking expired / already processed / reservation already started / not a reservation |
| 403 | Not the requester (or, for a reservation, not the requester or a curator) |
| 404 | Booking not found |

### BookingRemindReturnView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/bookings/{booking_code}/remind-return/` |
| **Permission** | `IsAuthenticated` + a **manager** of the thing (`Thing.can_manage`: its owner, or a curator of a PROPRIETARY collection it sits in) |
| **Rate limit** | 30 requests/hour per user |

"Remind them to return it": a manager nudges the borrower of a loan or rental whose return date has passed, from `/owner-bookings`. The daily command only speaks the day *before* a return, so until this existed whoever lent a drill had no way to ask for it once the date had gone. The assumption that a loan comes back (`close_transfers` closes the transfer by itself when the date passes) is unchanged; this is only a button to say it aloud.

Order of answers: **404** unknown booking, **403** not a manager, **400** when `BookingPeriod.can_be_return_reminded()` says no — not ACCEPTED, not LEND/RENT, the return date not **strictly** passed (the return day itself is still the borrower's: the day-before email has just gone), or a **later** ACCEPTED booking of the same thing has already started (the thing came back; only the last loan of each thing qualifies), coded `{"error", "code": "not_awaiting_return"}` so the page says it in the reader's language — and **429** with `{"error", "code": "already_reminded_today"}` when `return_reminded_at` is already today. That cap is the **booking's**, not the person's: two curators pressing in turn cannot mail the same borrower twice a day. It is claimed with one conditional `UPDATE … WHERE return_reminded_at IS NULL OR < start of today` **before** the email goes, so two presses at once cannot both match the row; "today" is the calendar day of the server's `TIME_ZONE`, not the last 24 hours. The hourly rate limit has no body and so no code.

`send_return_overdue_email` mails the borrower in their own language, naming **whoever pressed** (bare `name`, "A member" when there is none — never the address) with their address as `Reply-To` — the borrower's natural answer ("I'll bring it tomorrow") goes to that person. That is a deliberate exception to the rule that a manager's address never reaches the requester (their request and acceptance emails carry no `Reply-To`): here the manager chose to write, in their own name — and is told before pressing, by a line above the table on `/owner-bookings`. It does not record an event or an in-app notice, and a borrower who has switched activity email off simply receives nothing (the day is spent all the same).

### BookingActionView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/bookings/{booking_code}/accept/` |
| **Permission** | `IsAuthenticated` + a **manager** of the thing (`booking.owner_code == user` **or** `booking.thing_code.can_manage(user)`) |

Accepts a pending booking. Calls `finalize_booking_decision()` with `decided_by=request.user` (so a co-curator's decision is signed by the co-curator in the requester's notice), which sends the decision email via `send_booking_decision_email()` and deletes related RSVPs (`BOOKING_ACCEPT`/`BOOKING_REJECT`) to invalidate old email links. A curator of a PROPRIETARY collection decides its holds, not only the founder (2026-09).

**A curator may decide their own request — on purpose.** Nothing here refuses the requester: a co-curator (or the founder, when the thing is not theirs) who asked for a GIFT or SELL of their own group can accept it themselves, the thing goes `INACTIVE` and the `ThingTransfer` is recorded in their name. The email fan-out already leaves them out (`send_booking_request_notifications` mints no accept/reject links for the requester, so in practice they decide from the app), and the rest of the team hears of it through `BOOKING_DECIDED` — the requester gets their own `BOOKING_ACCEPTED`/`REJECTED`, never a `BOOKING_DECIDED` about their own request. A guard `requester == request.user → 403` or a second curator's sign-off were weighed and turned down; adding either would be a decision, not a fix. Pinned by `TestACuratorDecidingTheirOwnRequest` in `test_co_curator_bookings.py` (each test goes red with such a guard).

| | |
|---|---|
| **Endpoint** | `POST /api/v1/bookings/{booking_code}/reject/` |
| **Permission** | `IsAuthenticated` + a manager of the thing (same as accept) |

Rejects a pending booking. Same permission and validation as accept. **In a NETWORK the founder may reject a pending request on any entity's thing** (the rescue; `Thing.can_rescue`): it goes through `finalize_booking_decision(decided_by=founder)`, so the requester gets the usual decision email — signed by the network, not by the entity of the thing's owner, who did not decide — and the owner a `BOOKING_DECIDED`. Accepting stays the owner's, and an accepted loan is not touched.

**Responses:**
| Status | Condition |
|--------|-----------|
| 200 | Action completed |
| 400 | Booking expired or already processed |
| 403 | Not a manager of the thing |
| 404 | Booking not found |

---

## Reservation Views (`core/views/reservations.py`)

### ThingRequestView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/request/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` + not owner + **a place in the group**: for every verb the requester must be in `invites` of, or a curator of, **at least one ACTIVE collection of the thing** (`booking_service.require_a_seat`; RESERVE checks its own reservations collection in `request_reservation`). Otherwise **403** `code: "not_a_member"` — the founder of a group is not in `invites` and in COMMUNITY may ask for a member's thing, so curators count. A reader who only browses a PUBLIC group is joined and asked again by the client (see `frontend/CLAUDE.md`). |
| **Rate limit** | 10 requests/hour per user |

Creates a reservation/booking request. The view is **thin**: it runs the shared guards (auth, own-thing, availability, INACTIVE/paused collection, owner email) and validates the type-specific serializers, then dispatches to the `request_*` functions in `core.services.booking_service` (`request_date_based_booking`, `request_standard_booking`, `request_reservation`) which own the locked create + status transition + email fan-out. A business-rule failure raises `BookingRequestError(message, status_code, code=None, params=None)`, which the view maps back with `exc.as_body()`: `{"error": message}` with the same status, plus top-level `"code"` and `"params"` keys when set. **Every rule refusal is coded** — the model's violations return a `core.utils.Refusal` (a `str` carrying `code` + `params`) that `BookingRequestError` picks up on its own, and the service's direct raises name theirs (`not_a_member`, `reservation_max_active` with `{max}`, `time_taken`/`dates_taken` on the 409, …). `core` has no gettext catalogue, so the English `error` sentence is what an unaware client shows; the SPA says the code in the reader's language (`requestErrors.<code>`, `apiErrorMessage` in `frontend/src/services/api.js`). `core/tests/unit/test_refusal_codes.py` reads the codes out of the source and fails if one has no string in any of the three locales. The membership code stays special beyond that: the frontend's auto-join tells that 403 apart from this same endpoint's *other* one (`get_viewable_thing`'s "not authorized", carrying no code) without pattern-matching English prose or treating every 403 alike. Routes based on thing type (RESERVE checked first, since it is also in `DATE_BASED_TYPES`):

**RESERVE_THING (`_request_reservation`):**
- Body `{ "start_date", "duration_days"? (1–7), "start_time"?, "end_time"?, "project_note"? (≤512), "contact_phone"? }` via `ReservationRequestSerializer` — **either `duration_days` or `start_time`+`end_time`, never both, never neither**, matching whichever unit (`DAY`/`HOUR`) the resolved collection is in.
- `request_reservation` enforces membership (403 unless the requester is a collection member — login-to-act makes an anonymous visitor one first), `Collection.reservation_violation` or `reservation_hour_violation` (400, by unit — for `HOUR`, times in whole minutes, starting on the `reservation_min_minutes` grid from the block's opening and lasting a multiple of it, the same choices the request page offers, and not a slot that already began today by the deployment's `TIME_ZONE`), the horizon, the active-reservations cap, and `has_overlap` (409).
- **`contact_phone`** is optional and kept only when the collection asks (`reservation_asks_phone`; otherwise dropped without an error). Whoever manages the reservation reads it in `OwnerBookingsView` (`BookingPeriodSerializer`, the rule of `requester_email`), `""` from the day after the booking; it is in no email and no calendar file (the notice only says that one was left).
- **Auto-confirmed:** the booking is created `ACCEPTED`, both parties are emailed, the owner gets a `RESERVATION_MADE` in-app notice. No RSVP pair, no `ThingTransfer`. Response `201 {"message": "Reservation confirmed", "booking_code", "start_date", "end_date", "start_time", "end_time"}` — the last two `null` for a `DAY`-unit booking.

**Date-based (LEND/RENT):**
- Requires `start_date` and `end_date`.
- **Rental rules (#7):** resolves the applicable collection (the `collection_code` in the body — the SPA passes the collection context — **when the requester may read that collection**, else the thing's first collection with rules) and calls `collection.rental_violation(start, end)`. Returns 400 if the span isn't an allowed fixed duration, the pickup/return day isn't an allowed weekday, **or the pickup/return day is a `closed_dates` holiday** (only the handoff days — an interior closure doesn't matter for a loan). Collections without rules impose no constraint (legacy free range). This is the server-side backstop; the frontend already limits the picker.
- Checks for conflict via `BookingPeriod.has_overlap()` (**strict** overlap — a booking's return day may be the next's pickup day; only a shared interior day conflicts). Returns 409 if conflict.
- Thing stays `ACTIVE` (multiple bookings for different date ranges allowed).

**Request body:**
```json
{ "start_date": "2025-06-01", "end_date": "2025-06-15" }
```

**Standard (GIFT/SELL):**
- No extra fields required.
- Checks for existing pending request from same user. Returns 400 if duplicate.
- Thing status changes to `TAKEN` (blocks other requests).

**Common behaviour:**
0. Reads an optional **`collection_code`** from the body — the collection the requester was browsing. It already governed the rental rules (above); it now also decides which collection the managers' in-app notifications belong to, so the request shows up on the right collection's page (a thing lives in one, but a row from before that rule can sit in more — see `resolve_request_collection`). The SPA sends it from the card and the detail page whenever it has one; the standalone `/things/:code` page has none and the service approximates.
1. Validates owner email in the parent `post()` method (shared across all type handlers).
2. Creates `BookingPeriod` with status `PENDING`.
3. Creates, for **each manager** of the thing (`Thing.managers()` minus the requester), two RSVPs (`BOOKING_ACCEPT` and `BOOKING_REJECT`) minted to that manager for their email action links, via `booking_service.send_booking_request_notifications()`.
4. Sends each manager a booking request email with **their own** accept/reject links (in their own language), and a confirmation email to the requester ("Hold request sent"). Every manager of the thing (`Thing.managers()` — the owner plus a PROPRIETARY collection's curators, never the requester) also gets an in-app `BOOKING_REQUESTED`; the view's manager-ready collection prefetch is what keeps that fan-out from costing a query per collection (see `request_standard_booking` in `core/services/CLAUDE.md`).

**INACTIVE collection enforcement:**
If all collections containing the thing are INACTIVE, the request is blocked with 400 "This collection is currently inactive".

**Paused collection enforcement:**
If all active collections containing the thing have a non-empty `pause_message` (i.e. are paused), the request is blocked with 400 "This collection is currently paused". Collections that are paused remain visible but no new hold requests are accepted.

**Responses:**
| Status | Condition |
|--------|-----------|
| 201 | Request created (booking `PENDING`) |
| 400 | Own thing / already pending / invalid data / collection inactive |
| 403 | Not authorised to view thing |
| 409 | Date overlap (date-based only) |

---

## Transfer Views (`core/views/transfers.py`)

### ThingTransferView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/things/{thing_code}/transfers/` |
| **Permission** | `AllowAny` + `get_viewable_thing()` (public read on a viewable thing) |

Returns the transfer history (Loan Chain) and aggregate stats for a thing. **The four name fields are empty/null for a reader who is not signed in** (`` per hop, `null` for the two aggregates) — the counts and dates are the public story, the people are not; see the anonymous-read note under Security. The sample below is what a signed-in reader gets.

**Response (200):**
```json
{
  "total_transfers": 3,
  "unique_homes": 4,
  "current_holder": "ABC123",
  "current_holder_name": "Lala",
  "original_owner": "ABC123",
  "original_owner_name": "Lala",
  "transfers": [
    {
      "code": "XYZ789",
      "from_user": "ABC123",
      "to_user": "DEF456",
      "from_user_name": "Lala",
      "to_user_name": "Lele",
      "lent_date": "2026-04-01",
      "returned_date": "2026-04-10"
    }
  ]
}
```

**Behaviour:**
1. Looks up thing by `thing_code`. Returns 404 if not found.
2. Checks `thing.can_view(user_code)`. Returns 403 if not authorised.
3. Queries all transfers for the thing, ordered by `-lent_date`.
4. Computes `unique_homes` (distinct user codes across all `from_user` and `to_user` fields; NULL users — deleted accounts — count as at most one former home).
5. Computes `current_holder` from the most recent unreturned transfer's `to_user`.
6. Computes `original_owner` from the `from_user` of the oldest transfer (by `lent_date`). Null if no transfers.

---

## Report Views (`core/views/report.py`)

### ThingReportView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/things/{thing_code}/report/` |
| **Permission** | `IsAuthenticated` + `thing.can_view()` + not owner |
| **Rate limit** | 10 requests/hour per user |

A logged-in member flags a thing as inappropriate (content moderation, #12).

**Behaviour:**
1. Returns 400 if the requester is the thing owner ("You can't report your own listing").
2. Returns 403 if the requester can't view the thing (`deny_if_cannot_view`).
3. `get_or_create` a `Report` for `(thing, reporter)` with a `thing_headline` snapshot — **idempotent per member**, so re-reporting the same thing doesn't create a second row or re-notify.
4. On the **first** report only: emails the owner (`send_thing_reported_email`, Cat. 2) and creates a `THING_REPORTED` `InAppNotification` (payload `thing_headline`, `thing_code`). Both are **anonymous** — the reporter's identity is never included.
5. Always returns `200 {"message": "Thanks — we've let the owner know."}` (the reporter can't tell whether it was their first report).

The reporter is stored server-side only (`Report.reporter`) as a moderation trail; see the [`Report` model](../models/CLAUDE.md#report) and `ReportAdmin` for the platform-facing log.

---

### Management Command: `close_transfers`

Daily command (`python manage.py close_transfers`) that closes overdue transfers:
- Finds unreturned `ThingTransfer` records linked to `ACCEPTED` bookings whose `end_date < today`.
- Sets `returned_date = today` **and `auto_closed = True`** via bulk update — the date is inferred from the due date passing, not confirmed by anyone, and the journey timeline renders those hops as "Due back on" rather than "Returned on".
- Outputs count of closed transfers.

### Management Command: `send_reminders`

Daily command (`python manage.py send_reminders`) that sends reminder emails:
- **Booking return reminders**: ACCEPTED bookings with `end_date = tomorrow` — notifies **both sides**: the team that runs the thing, one email each (`Thing.managers()` minus the borrower — its owner and, in a PROPRIETARY collection, every curator, the people the request went to; `send_return_reminder_email` — "{thing} comes back tomorrow", nothing asked of them) and the **borrower** (`send_return_due_email` — "tomorrow you take it back", naming the owner they owe it to by their bare `name` — "a member" when there is none, never the address `display_name` falls back to — with a link to the listing). **RESERVE_THING is excluded** (`.exclude(thing_type=RESERVE_THING)`) — nothing is carried anywhere, so "take it back" is nonsense for an on-site reservation. **A single-day loan (start == end, tomorrow) is excluded too** — its return reminder is the pickup one, and one person is mailed once about the one day, not twice.
- **Reservation arrival reminders**: ACCEPTED `RESERVE_THING` bookings with `start_date = tomorrow` — one email to the **member who booked the slot** (`send_reservation_reminder_email` — "your reservation starts tomorrow"). A reservation auto-confirms and can be booked up to a year ahead, so this is the *only* nudge between the confirmation and the day, and a no-show costs a real slot. Owner not pinged — nobody has to carry anything.
- **Pickup reminders** (LEND/RENT): ACCEPTED `LEND/RENT` bookings with `start_date = tomorrow` — **both sides** again, the day before the handover: the borrower (`send_pickup_due_email` — "tomorrow you pick up {thing}", naming the owner by bare `name` as above, with a link to the listing) and the team that runs the thing, as above (`send_pickup_reminder_email` — "tomorrow you hand over {thing}", nothing asked of them). Until these existed the only pickup email was the acceptance, sent when the dates were agreed — weeks can pass before the day. RESERVE has its own arrival reminder above; GIFT/SELL have no dates.
- The borrower's half used to be missing: only the owner was told a loan was ending, so the one person who actually had to do something — carry the drill back — heard nothing. A lending library runs on that message.
- The fan-out is per recipient and swallows a failure with a warning on stderr, so one broken send costs neither the other side their reminder nor the rest of the run theirs (same reasoning as `send_digests`).
- Outputs the total count of reminder emails sent (one for the borrower plus one per member of the team for each due loan/rental, one per due reservation).

### Management Command: `send_join_summaries`

Daily command (`python manage.py send_join_summaries`), chained **before** `send_digests`: one email per curator (founder + co-curators) for each ACTIVE collection that had sign-ups, read from the `MEMBER_JOINED` events (`send_join_summary_email`, `CATEGORY_ACTIVITY`, button to `/{kind}/{code}/invites`).
- **Once per day without a table of sent mail**: `Collection.join_summary_sent_on` is the last day already told. The command claims `yesterday` there with a conditional UPDATE (`WHERE join_summary_sent_on = <what it read>`) **before** sending, so a second run, or two at once, finds nothing to do. The window runs from the day after that one to yesterday (`TIME_ZONE` days), at most 7 days back, so a skipped Scheduler day loses no sign-ups. NULL means "never looked at": its first summary names only yesterday (so arming the command drops no backlog), and **after the loop every pass dates yesterday on the collections still NULL** (they had nothing to tell; a group whose sends all failed is excluded, to be retried) — otherwise a group quiet for weeks would stay NULL and lose a first sign-up that fell on a skipped day.
- **Only people still in `invites` are named**: someone who joined and left inside the window is not counted. With everybody gone there is no email, but the days are claimed anyway.
- A curator who joined is not named to themselves (and gets nothing if they are the only one). At most 10 names, then "and N more". A curator who silenced the group (`Collection.digest_muted`, the same switch as the digest's) is skipped, and the email's footer carries the one-click mute link. Someone who never set a name is listed by their address (the team already reads it in the members list; no other member ever receives this email).
- A send that raises on every curator gives the claim back (the previous value is restored) so the next run retries; once any email is out the claim stays, or a retry would tell that curator twice.

### Management Command: `send_digests`

Daily command (`python manage.py send_digests`) that sends digest emails:
- **Weekly digests**: sent on Mondays for collections with `digest_frequency = "WEEKLY"`. Lists things added in the past 7 days.
- **Monthly digests**: sent on the 1st of each month for collections with `digest_frequency = "MONTHLY"`. Lists things added in the previous month.
- Skips collections with no new things or no invitees.
- Outputs count of digest emails sent.

### Management Command: `cleanup_orphan_images`

On-demand command (`python manage.py cleanup_orphan_images`) that deletes **orphaned images from object storage** (#9) — uploads whose form was never submitted, so no DB row ever referenced them (the complement to `core.services.asset_cleanup`, which handles record *deletes* and, since 2026-10-02, a *save* that drops a key — so what is left for this sweep is uploads that never became a row, plus anything that bypassed `save()`). No in-app endpoint: it runs from the shell, or — since 2026-10-02 — **daily as its own Heroku Scheduler job**, separate from the chain (`HEROKU.md` § Scheduled jobs: `cleanup_orphan_images --bucket <bucket> --commit`, safe to arm because of the age window, the mandatory `--bucket`, the upload-folders-only scope and the cross-reference of every asset field).

- **Dry-run by default.** It only lists what it would delete; pass `--commit` to actually delete. On Heroku, quote the inner command so the CLI doesn't eat the flag: `heroku run --app <app> "python manage.py cleanup_orphan_images --commit"`.
- **Only lists the upload folders** (`storage.ASSET_FOLDERS`: `oiueei/things`, `/collections`, `/users`, `/documents` — the folders a ticketed upload may write to). Scanning the whole `oiueei/` tree treated *everything* unreferenced as an orphan, and the production dry-run of 2026-09-28 duly listed `oiueei/assets/Curiosa-Variable.woff2` — the variable font the Heroku build downloads in `heroku-postbuild` (not in git, licence); deleting it would have broken every deploy after it. Any other prefix is out **by construction, not by an exception list**, and a `--prefix` that does not fall inside an upload folder is refused with a `CommandError` before anything is listed (the same stance as the `--bucket` guard). `--prefix` still narrows within a folder (`--prefix oiueei/things/`); the default sweeps every upload folder.
- **Cross-references every DB image field** — `Thing.thumbnail` + `Thing.gallery`, `User.photo`, `Collection.thumbnail` — so anything in use is kept.
- **Never touches `oiueei/seed/`** (the demo's shared image pool), even if unreferenced — structurally now (the seed folder is not an upload folder and is never listed); the explicit prefix check stays as a second lock.
- **Age window:** only assets older than `--min-age-hours` (default 24, so an in-flight upload mid-form isn't mistaken for an orphan) and younger than `--max-age-days` (default 30, keeping it a recent sweep). Run regularly (e.g. weekly) so every orphan is caught within its window.
- Pages through `storage.iter_objects` (prefix `oiueei/`), deletes in batches of 100 via `storage.delete_many`, and prints a per-run summary (scanned / in use / seed / outside window / orphans / deleted). The batch is kept well under S3's own limit of 1000 so a failed batch costs a hundred orphans rather than a thousand; a failure is reported and the run continues.
- The age window reads S3's `LastModified`, which for these objects **is** the upload time — a key is random, written once and never rewritten. That is why an object must never be overwritten in place: it would reset the clock and hide the object from the sweep for another day.

### Management Command: `purge_expired_data`

Enforces the retention table (GDPR art. 5.1.e): one period per category of data, each a `RETENTION_*` setting, **0 = keep indefinitely**. It **is** the sixth link of the daily Heroku Scheduler chain (README § Scheduled jobs, HEROKU.md § Scheduled jobs) — a period nothing enforces is a paragraph, not a retention policy. What protects you from arming it blind is that it is **dry-run by default**: an operator sets their own periods, runs it once by hand, reads the counts, and only then adds `--commit` to the chain. `cleanup_orphan_images` is the one that genuinely stays out of the chain.

- **Dry-run by default**, like `cleanup_orphan_images`; `--commit` applies it. The dry-run prints exactly the counts the commit would take.
- **Idempotent**: every step selects only rows still in the "before" state, so a second run is a no-op and a half-finished run can just be run again.
- **`Event` is anonymised, not deleted** (`actor_code` blanked at 14 months). What expires is the link to a person, not the fact — the series survives as aggregate and stops being personal data, which is what art. 5.1.e asks for. Deleting it would throw away the history to achieve the same thing.
- **Warned before anything happens — inactive accounts** (24m): sends the inactivity email and stamps `User.inactivity_notified`, from which the grace period is later counted. Skips anyone already warned (the stamp is what makes it idempotent), staff/superusers, and anyone holding a live `COLLECTION_INVITE` — telling somebody invited three days ago that their two-year-old account is expiring is true and useless. **A failed send leaves the stamp unwritten** so the clock never starts from an email that never arrived. Owning a live group does *not* skip the warning; it changes what the warning says (`send_inactivity_warning_email(..., will_delete=False)`), because an account that will not be deleted must not be told that it will. Coming back clears the stamp — `User.update_last_activity()` does it, which is the whole promise of the email.
- **Warned before anything is taken**, at most `--max-warnings` per run (default 200). The first armed run on an established database finds every dormant account at once and sends synchronously, so an uncapped one is a single dyno bursting thousands of SMTP calls at its own provider. Deferring costs nothing: the mark is written only on a successful send, so whoever is not reached tonight is a candidate again tomorrow, and each grace period is counted from that person's own warning — nobody is deleted un-warned by the cap. `--max-warnings 0` lifts it.
- **Deleted — inactive accounts**, once the grace period from the warning has run out. Two independent things must still be true and either one saves the account: the stamp is at least `RETENTION_INACTIVE_WARNING_DAYS` old **and** the account is still inactive. Coming back clears the stamp *and* refreshes `last_activity`, so somebody who did what the email asked is out of the queryset twice over — deliberate redundancy on an irreversible step. **An account that owns a collection with members is never deleted here**: `Collection.owner` is CASCADE, so erasing the founder of a working library takes the collection, its things and its photos from everyone who was still using it — a harm to everybody except the person who was actually inactive, decided by a nightly job. Those codes are printed for a human instead. Erasure goes through `account_service.delete_account`, the one written-down map of what dies with an account, so it leaves the same audit line a user-requested erasure does.
- **Deleted — guest accounts nobody ever answered for** (60d): `get_or_create(email=...)` writes a `User` row the moment an owner types an address, so an unanswered invitation leaves a stranger's email here indefinitely. Five conditions, each with its own negative test: no `last_activity`, in no collection's `invites` (membership is written on **accept**, so a row there is a real member who simply hasn't been back — the trap this step is most likely to fall into), owns no collection and no thing, has no live `COLLECTION_INVITE` RSVP, and is not staff/superuser (a `createsuperuser` account that never used the SPA matches everything else). Note the RSVP condition is *absence*, not expiry: `cleanup_rsvps` deletes expired rows daily, so by the time this looks there is nothing expired to find and `User.created` is what dates it.
- **Deleted**: `DailyActivity` (26m), `InAppNotification` (12m), `Report` (12m from `created` — the model has no "resolved" state to date from, and adding one would be a moderation feature rather than a retention decision).
- Periods are counted in **calendar months**, not 30-day blocks (`months_ago()`, day clamped to the target month's length). A person whose data goes six days early has a point.
- A commit run logs its counts to the `security` logger: automated erasure leaves the same trail a user-requested one does.

---

`purge_expired_data` also empties `BookingPeriod.contact_phone` where `end_date <= today` (the day after the booking; cancelled or not). Like the invitation records, that period is fixed and not a `RETENTION_*` setting: the request page's label promises it, so a deployment has to run the command with `--commit` daily. Dry-run counts and touches nothing.

`purge_expired_data` also deletes `InvitationRecord` rows whose `sent_at` is more than `INVITE_RECORD_MONTHS` (12) months old. That period is a constant in `core/models/invitation_record.py`, not a `RETENTION_*` setting and not switchable off: the invitation email promises "a year".

### Management Command: `backfill_events`

One-off, idempotent seed of the `Event` log from existing rows (users → `USER_JOINED` at `date_joined`, collections/things/bookings at their `created`; accepted bookings also get `HOLD_ACCEPTED`). Run **once**, the day tracking ships, before forward instrumentation accumulates. Kept out of migrations per repo convention. Re-running never double-counts (skips when an equal event already exists).

---

## Data Export Views (`core/views/export.py`)

Two downloads, one service. Both return a plain `HttpResponse` attachment rather than a DRF `Response`: what these serve is a **file** — it has a name, a disposition and a caching rule that a rendered JSON body doesn't carry. The tree itself, and the reasoning about what never leaves it, lives in [`export_service`](../services/CLAUDE.md#export_servicepy--data-portability-right-to-a-copy); these views are the HTTP layer around it — who may ask, how often, and what the browser may do with the answer.

Both set `Content-Disposition: attachment; filename="oiueei-{code}-{date}.json"` and `Cache-Control: private, no-store`, and both log to the `security` logger with the size of what they served: a sudden change in what an export weighs is the first sign it started carrying something new.

### AccountDataExportView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/auth/export/` |
| **Permission** | `IsAuthenticated` |
| **Rate limit** | 10 requests per day per user |

Your own data, as one JSON file — the self-service half of the right the privacy policy used to answer with "write to me" (GDPR art. 20). The twin of [`AccountDeleteRequestView`](#accountdeleterequestview): the same account page offers both, in that order, because reading your copy before erasing it is the sane sequence and the legally solid one.

### CollectionDataExportView

| | |
|---|---|
| **Endpoint** | `GET /api/v1/collections/{collection_code}/export/` |
| **Permission** | `IsAuthenticated` + collection curator, owner or co-owner (`require_collection_curator`) |
| **Rate limit** | 10 requests per day per user |

A whole group as its owner or a co-owner runs it, other members' things included. **A plain member gets 403, not a smaller file**: there is no partial export by design — "some of the group, depending on who asks" is a second access-control model to keep correct forever, and what a member is entitled to is their own account copy. **In a NETWORK the founder gets the whole group and a co-curator only the things they run** (and what hangs from them); the `.ics` calendar narrows the same way, and so does the `stats` block of the copy (the same rows as the stats CSV, with its `Pickup point` row: the file's things and its figures agree).

Deliberately not folded into the account export: a collection of 4,000 things would bloat every personal download, this button belongs beside the stats CSV, and keeping them apart lets the account copy stay honestly framed as *your* data while this one is what it is — an operational copy of a group, carrying other people's details, which the page has to say out loud.

**Query budgets.** `test_query_counts.py` pins both exports as constant in what they carry (a 200-thing group costs the same queries as a 5-thing one) plus a size ceiling on the 200-thing case — the half a query count can't see, and the reason photos travel as URLs rather than bytes. An N+1 here isn't a slow page; it's a 30-second Heroku timeout on the one request somebody makes when they're already unhappy enough to be leaving.

### CollectionCalendarExportView

| | |
|---|---|
| **Endpoint** | `POST /api/v1/collections/{collection_code}/calendar-export/` |
| **Permission** | `IsAuthenticated` + collection curator, owner or co-owner (`require_collection_curator`) |
| **Rate limit** | 20 requests per hour per user |

The collection's upcoming **date-based** reservations (LEND / RENT / RESERVE, status `ACCEPTED`, `end_date >= today`) as an **iCalendar (`.ics`) VCALENDAR** — one all-day `VEVENT` per reservation, spanning its block, or one timed `VEVENT` (in UTC) for an `HOUR`-unit reservation (its real start and end, on its one day). The tree is built by [`calendar_export_service`](../services/CLAUDE.md#calendar_export_servicepy--the-collection-calendar-ics); this view is who may ask and what the browser may keep.

**Every upcoming reservation, every call — not incremental any more.** The format switched from a Google Calendar CSV to `.ics` on 2026-09-28: the CSV's `MM/DD/YYYY` columns were misread by an importing account in a day/month locale (a real production report — a 1 October reservation landed on 10 January), and iCalendar's dates carry no such ambiguity. Each event's `UID` is stable per booking, so a calendar app that re-imports the file updates its own copy in place — which is what let the response drop the old incremental watermark (`CalendarExportMark`, leaving the schema — see [its model doc](../models/CLAUDE.md#calendarexportmark-leaving-the-schema)) and simply ship the collection's whole upcoming future every time. The response header **`X-Calendar-Events`** still carries the confirmed count, and **`X-Calendar-Cancelled`** (2026-09-29) the number of upcoming reservations cancelled since they were confirmed, which ride along as `STATUS:CANCELLED` revisions of their events (see [`calendar_export_service`](../services/CLAUDE.md)); both `0` means nothing to import and the SPA shows "no upcoming reservations" instead of triggering a download. Both headers are in `CORS_EXPOSE_HEADERS`. There is still no "download everything **but the future**" variant — there was never anything else to ask for.

**POST, kept for contract stability** — the call used to mutate (it marked reservations delivered), which is why it was never a GET; it does not mutate anything any more, but changing the method now would only move a working contract for no benefit, so it stays POST.

Response: `text/calendar; charset=utf-8` attachment named `{code}-calendar.ics`, `Cache-Control: private, no-store` (it carries member names), and a `security` log line with the event count and byte size. Curator-only; a plain member gets the standard `{"error": ...}` 403. The file holds every upcoming reservation of a PROPRIETARY collection, but in a COMMUNITY one only those of things the downloader owns (the app's rule for who sees whoever asks; see `calendar_export_service`).

---

## Collection addresses (`config/urls.py`)

A collection lives at **`/{kind}/{code}`** — `/stall/…`, `/library/…`, `/shed/…` — and `collection_address` answers a request for one under any *other* prefix of a collection that exists (`collections|stall|library|shed`, a 6-character code, then an optional `/rest`) with a **301** to its own, **keeping the rest of the path and the query string** (`?thing=` of the join page). `/collections/new` is a 301 to `/new`. A code that names nothing, or one already under its own prefix, is `spa_index` as before. **It asks nothing about permissions, deliberately**: an old link to a private collection has to reach its page so the member can sign in. What it tells a stranger is the kind of a collection whose code they already hold (that the code exists is already said by `GET /api/v1/collections/{code}/`, 403 against 404), and the 301 is safe to cache because a kind never changes. The link preview's rule (the body of a private collection is the site's card, byte for byte that of a code that names nothing) holds for the page served at the right prefix; the difference is only the redirect. It costs one query before `spa_index`'s own preview one.

---

## Middleware (`core/middleware.py`)

- **`SecurityHeadersMiddleware`** — adds CSP + Permissions-Policy to every response (all environments). The CSP names a violation collector in both syntaxes (`report-uri` and `report-to`, the latter resolved by the `Reporting-Endpoints` header) pointing at `csp_report` below. It also names the asset hosts, and **two of them, from two settings**: `img-src` gets `MEDIA_PUBLIC_BASE_URL` (where files are read from), `connect-src` gets that *and* `OBJECT_STORAGE_PUBLIC_URL` (the bucket, where a presigned `PUT` always goes — it does not follow a CDN). Deriving the second from the first is what made `MEDIA_PUBLIC_BASE_URL=https://cdn.your-domain.test` forbid every upload while the images already stored kept loading; `test_upload.py::TestTheBrowserIsActuallyAllowedToUseTheTicket` asks the question the browser asks, so the two cannot drift apart again.
- **`DailyActivityMiddleware`** — records the authenticated user's daily activity (see [`DailyActivity`](../models/CLAUDE.md#dailyactivity)). Registered **innermost** so it can read the DRF-authenticated `request.user` *after* the view (there is no Django session — auth is JWT-cookie via DRF authenticators, so `request.user` only resolves once a view/permission touches it). A DatabaseCache key gates it to one write per user per day; failures are swallowed so tracking can never 500 a good response. Anonymous / non-DRF requests are skipped.

---

## Custom Permissions (`core/permissions.py`)

| Permission | Logic |
|-----------|-------|
| `IsThingOwner` | `obj.owner_id == request.user.code` |
| `IsThingManager` | `obj.can_manage(request.user.code)` — the thing owner, or a curator of a PROPRIETARY collection it sits in. Gates the catalogue actions (update, activate, hide); delete keeps its own `_can_delete`. |
| `IsCollectionOwner` | `obj.owner_id == request.user.code` |
| `IsCollectionCurator` | `obj.is_curator(request.user.code)` — owner or co-owner. The admin tier: everything except deleting the collection, which stays `IsCollectionOwner`. Promoting/demoting a co-curator is curator-wide now (2026-09). |

---

## Security

### Authentication & Authorisation

1. **Invite-only registration, owner-controlled, with no open door** — there is no public self-registration. An account is created when a collection owner invites someone (`POST /collections/{code}/invite/`), or when a visitor joins a collection they were pointed at (`POST /auth/join/`, with a `share_token` from `/share/{token}` or the code of a PUBLIC collection). Both are somebody choosing to admit a specific person. `/login` (`POST /auth/request-link/`) only mails links to already-registered accounts and never creates users, and `/auth/join/` creates nothing without a valid target — so no request to this API mints an account that belongs to no group. A deployment that *wants* an open door adds one from its own URLconf (`DEPLOYMENT_URLCONFS`); it is not part of what is distributed.
2. **Magic link authentication** — Passwordless via email. RSVPs are one-time use and expire per action (magic links 24h; booking accept/reject 72h; collection invites ~30 days — `RSVP.expiry_hours_for`).
3. **JWT tokens** — HttpOnly cookie-based. Access tokens expire after 1 hour. Refresh tokens expire after 7 days. Tokens are rotated on refresh via `POST /api/v1/auth/refresh/`, old tokens blacklisted.
4. **CSRF (cookie auth)** — because the access token rides in a cookie, `CookieJWTAuthentication` runs DRF's CSRF check (`enforce_csrf`, mirroring `SessionAuthentication`) for **cookie-authenticated unsafe methods** — defence in depth behind the cookie's `SameSite=Lax`. Bearer-header auth is exempt (the header is never sent cross-site), so API clients and the Bearer-token test suite are unaffected. `MeView` GET sets the `csrftoken` cookie via `@ensure_csrf_cookie` (hit on every app load); the SPA reads it and sends it as `X-CSRFToken` on every unsafe request. **The decorator sits on `dispatch`, not `get`** — it forces the cookie by calling `get_token()` from inside the method it wraps, and DRF's `APIView.dispatch()` runs `check_permissions()` (raising 401 for `IsAuthenticated` before `get()` is ever called) — so decorating `get()` directly meant the cookie was never set for exactly the visitor who needs it most: someone brand new, whose first-ever hit here 401s because `App.jsx`'s app-load warm-up fires before the magic-link GET that authenticates them completes. That silently broke the first unsafe request (a reservation, a question) from anyone whose magic link drops them straight onto one thing with no earlier authenticated page ever calling this endpoint successfully. Pinned by `test_me_get_sets_csrftoken_cookie_even_when_it_401s`. The test client disables the check by default (`enforce_csrf_checks=False`), so only `test_csrf.py` (which opts in) exercises it.
5. **IDOR protection** — `can_view_user()` ensures users can only view profiles of people who are inside a group they are inside too.
6. **Custom DRF permissions** — `IsThingOwner`, `IsThingManager`, `IsCollectionOwner`, `IsCollectionCurator` in `core/permissions.py`.
7. **Public collections (anonymous read)** — a collection with `visibility=PUBLIC` (and ACTIVE) is readable without authentication. The read endpoints `CollectionViewSet.retrieve`, `ThingViewSet.retrieve`, the FAQ list (GET on `ThingFAQListView`), `ThingTransferView` and `ThingCalendarView` are `AllowAny`, each gated by an **anonymous-safe** `can_view` (a `viewer_code(request)` helper passes the user's code, or `None` for a visitor, into the model guard — `None` matches PUBLIC collections only). Every *write/act* endpoint (reserve, ask a question, answer, add a thing, manage invites/visibility) still requires authentication plus membership/ownership, so an anonymous visitor may browse a public collection but must log in to act. INACTIVE things are excluded from the serialised `things` for any non-owner, the member roster serialises **codes only** for anonymous readers (names are for logged-in members; emails for the owner), and the collection *list* (`GET /collections/`) stays private (it returns only what the caller owns or co-owns).

**No member is named to an anonymous reader, by any of these endpoints.** The roster rule above is the whole rule, and it took three passes to actually be: the FAQ list still carried `questioner_name` and the journey still carried the name of everyone who had held the thing, so a group's membership stayed legible from the open web through a thing rather than through the collection. Both now withhold (`FAQSerializer.get_questioner_name`, `core/serializers/transfer.py::_may_read_names`), both fail closed on a request-less context, and both keep the *content* public — the question, the hop count, the travel story. The third door was the grid itself: in COMMUNITY mode every card carries `owner_name`, the member who **contributed** the thing, so a group's membership stayed enumerable from the open web after both other doors had closed. `ThingComputedFieldsMixin.get_owner_name` now withholds it from a signed-out reader **whenever the thing's owner is not the collection's owner** — the leak stated exactly, with no mode check to drift. The one name such a reader still gets is the **curator's**, the person who published the collection: `CollectionSerializer.get_owner_name` already serves it to them in the page header, so withholding it on that person's own listings would be theatre. They chose to publish; the member who contributed, the person who asked and the people who borrowed did not.

### Input Validation

1. **Image IDs** — Only alphanumeric characters, underscores, hyphens, dots and slashes; no traversal. Each field is also **bound to its own folder** (`ImageIdField(folder=…)` → `validators.validate_key_folder`): the upload ticket refuses to sign a write outside a known folder, but the key that lands on the model arrives in a *separate* request, so nothing tied the two together — a member could put a collection's welcome PDF into their own `photo` and republish a document its owner shared with one group. The rule is deliberately narrow, refusing only a key naming one of the **other** `storage.ASSET_FOLDERS`: a bare Cloudinary-era id, an `oiueei/seed/` fixture (the demo's shared pool legitimately backs every kind of row) and any unknown namespace still save, because the guard arrived years after the keys did and refusing them would strand rows whose photo works perfectly.
2. **Headlines** — HTML tags rejected to prevent XSS.
3. **Quantities** — Order quantities capped at 99.
4. **Dates** — Start dates must be today or future. End dates must be >= start dates.
5. **Email HTML** — All user content escaped via `django.utils.html.escape()` in `email_service.py`.

### Mass-upload guards (per collection)

Independent of the rate limits below, and **off unless the deployment sets thresholds** — the standalone default. Two counters per collection, things and invitees, each with:

- a **silent alarm** (`COLLECTION_THINGS_ALARM` / `COLLECTION_INVITES_ALARM`) that emails the **superusers** once and changes nothing. The owner is never told: a tripwire, not a warning, so a legitimate bulk import is not interrupted and someone probing the endpoint does not learn where the line sits.
- a **hard ceiling** (`COLLECTION_THINGS_BLOCK` / `COLLECTION_INVITES_BLOCK`) that refuses adds with **400**, checked against the whole batch so bulk cannot walk past it. A superuser lifts it per collection with `capacity_unblocked` in the admin — there is no API.

Enforcement points: things — `ThingViewSet.create` (before the row is created), `ThingBulkCreateView` (whole batch, all-or-nothing). Members — `CollectionInviteView` and `CollectionBulkInviteView`, enforced where invitations are **sent** rather than accepted (refusing an invitee at the door would punish someone who did nothing wrong); the alarm fires from `_join_collection`, the single funnel every join path goes through.

**The ceiling counts what would land, not what was typed.** `adding` is the number of rows that genuinely move the counter, so both invite endpoints check *after* validation and dedup and exclude addresses that are **already members** — those sit inside the count the ceiling measures, and counting them again refused batches that added nobody (a re-invite at the ceiling now falls through to the accurate "already invited" 400). The thing paths count `len(validated)` for the same reason. All of it is gated on `Collection.capacity_ceiling()`, so a deployment with no thresholds runs no extra query.

**Concurrency.** `ThingBulkCreateView` re-checks under a `select_for_update()` on the collection row inside its transaction — one request there can carry up to `MAX_ROWS`, so two arriving together could otherwise land 200 rows through a ceiling of 100. The single-add paths accept a drift of at most one row per racing request and take no lock: a ceiling this coarse doesn't earn serialising every add to a busy COMMUNITY collection. The **invite** paths need no lock at all — they send invitations, they don't add members, so the count they read only moves when someone accepts, which is deliberately never refused.

### Rate Limiting

- **Every API request with no session** — `AnonymousApiThrottle` (`core/throttles.py`, `DEFAULT_THROTTLE_CLASSES`), **`ANON_API_RATE`, default 300 per minute per IP — one count shared with the two pages that ask the database for a visitor** (`spa_index`'s link preview of a collection, thing or share link, and `collection_address`'s 301; past the ceiling those serve the site's card with no query rather than a 429, and a route that asks nothing spends nothing) (`"0"`/empty = off; also off with `RATELIMIT_ENABLE=False`). **Not** DRF's `AnonRateThrottle`: the bucket is `core.utils.get_client_ip` (`TRUSTED_PROXY_COUNT`) like every other limit here. Counts only requests with no session — a signed-in member is never throttled by it — and, because DRF checks permissions before throttles, a 401/403 does not spend quota. Past the line: `429` through DRF's default `Throttled` handling (`api_exception_handler` delegates to it), body `{"detail": …}` and a `Retry-After` in whole seconds. This is what bounds scraping of a PUBLIC collection's reads (things, calendars, FAQ, journeys), which had no limit at all until 2026-09-29. **The count is in each web process's memory** (a module-level `LocMemCache`, fixed windows), not in `CACHES['default']`: a read, allowed or refused, asks the database nothing for it — pinned by `TestTheCountCostsTheDatabaseNothing`. Counted in the shared DatabaseCache (its first version, the same day) an anonymous read went from 4 statements to 16, a 429 still wrote its counter, and the one key per visitor address per minute crowded the daily quotas out of that table. The price is exactness: each process counts alone (so one address gets up to the rate × processes × dynos) and a restart forgets the count — acceptable for a ceiling meant for scripts, which is why every limit that must agree across processes still uses the shared cache. A count lost between `add` and `incr` restarts at one. `core.throttles.parse_rate` is the one reading of the setting, and the deploy check calls it too, so a malformed rate fails the deploy: `core.checks.check_anon_api_rate` (`core.E005`).
- `/auth/request-link/` — 5 requests per minute per IP **and** 5 per hour per account (email)
- `/auth/join/` — 5 requests per minute per IP **and** 5 per hour per account (email)
- Joins per **collection** — **unlimited unless the operator sets `COLLECTION_JOINS_PER_DAY`** (0/unset = off). The one door that needs no account, reached by a public collection code or a shared token; the two IP/email limits above cap one caller and one victim, this caps the relay
- `/auth/verify/{token}/` — 10 requests per minute per IP
- `/collections/{code}/invite/` POST — 30 requests per hour per user
- Invitation **emails** (single + bulk combined) — **unlimited unless the operator sets `INVITE_EMAILS_PER_DAY`** (counts emails, not requests, so the bulk fan-out can't multiply past it; 0/unset = off)
- `/things/{code}/request/` POST — 10 requests per hour per user
- `/things/{code}/faq/` POST — 20 requests per hour per user
- `/collections/{code}/email-note/test/` POST — 10 requests per hour per user
- `/collections/{code}/broadcast/` POST — 5 requests per day per user
- `/collections/{code}/share-link/` POST — 30 requests per hour per user
- `/share/{token}/join/` POST — 30 requests per hour per user (plus the per-collection daily ceiling, `COLLECTION_JOINS_PER_DAY`)
- `/things/{code}/report/` POST — 10 requests per hour per user
- `/bookings/{code}/remind-return/` POST — 30 requests per hour per user (plus the once-a-day cap per booking)
- `/notifications/token/{t}/` — GET 20/min per IP, PATCH 10/min per IP
- `/things/` POST (single create) — 60 requests per hour per user (so the 10/h bulk cap can't be bypassed one-by-one into unbounded rows)
- `/collections/` POST (single create) — 30 requests per hour per user
- `/collections/{code}/join/` POST — 30 requests per hour per user (plus the per-collection daily ceiling)
- `/collections/{code}/leave/` POST — 30 requests per hour per user
- `/auth/delete-account/` POST — 3 requests per hour per user
- `/auth/export/` GET — 10 requests per day per user
- `/collections/{code}/export/` GET — 10 requests per day per user. Building an export is the heaviest read in the app; the cap is what keeps "download my data" from being a way to walk a server out one file at a time
- `/collections/{code}/calendar-export/` POST — 20 requests per hour per user. A read-only download since the `.ics` (every call rebuilds the whole file; it used to write a watermark, which is why it once counted as a write); higher than the JSON exports since a curator may legitimately retry or pick up a just-confirmed reservation
- `/contact/` POST — 5 requests per hour per IP
- `/csp-report/` POST — 30 requests per hour per IP (violation reports; browser extensions make these noisy)
- `/health/` GET+HEAD — 60 requests per minute per IP. It reaches the database on every hit, so uncapped it is DB amplification rather than a monitor (it is not the only anonymous route that does: `spa_index`'s link preview and `config.urls.collection_address` ask a query per visit, and they spend the same per-IP count as the API's `ANON_API_RATE` — past it they ask nothing, answer no error and serve the plain `index.html`). Far above a real monitor's cadence (5 minutes = 0.2/m). It is a plain Django view, so it answers **429 itself** rather than letting `Ratelimited` surface as Django's 403 — DRF's exception handler doesn't run here. **The limiter is called by hand (`is_ratelimited`, inside a `try`), not through `@ratelimit`** (2026-09-21): its counter lives in `CACHES['default']`, which is `DatabaseCache` — the same Postgres the endpoint checks — so the outage `/health/` exists to report is also the one that breaks the limiter. As a decorator it ran before the body, and a refused connection escaped from it as an unhandled 500 (seen in production as an uptime monitor's HEAD probe during a database outage, reported by an error tracker) instead of the designed `503 degraded`. A limiter that cannot reach its counter now falls through to the real check. `core/tests/unit/test_health.py` pins it with a cache backend that refuses every operation (`RefusedCache`) — the earlier tests faked only the view's own cursor and left the limiter's cache answering, a state production never reaches, which is why they stayed green through the real outage. The group is kept as `core.urls.health_check`, the name the decorator derived, so live counters carry over

**Which IP a limit buckets on** is decided by `core.utils.get_client_ip` (wired in via `RATELIMIT_IP_META_KEY`), and by `TRUSTED_PROXY_COUNT`: how many proxies in front of the app are trusted to have appended to `X-Forwarded-For`. The entry is counted from the **right**, because only the tail of that header was written by a proxy we control — the rest is the caller's own text. Default `1` = the Heroku router. **A deployment with nothing trusted in front must set `0`**, or the header is entirely caller-supplied and one caller mints a fresh bucket per request, defeating every limit above. The chosen entry is validated as an IP before it is returned: django-ratelimit feeds it to `ipaddress.ip_network()`, so an unparseable value used to raise `ValueError` *inside the decorator* — a 500 on every limited endpoint from one header, before the view ran. Anything unparseable falls back to `REMOTE_ADDR`, then to a single shared bucket (`UNKNOWN_CLIENT_IP`), never to a fresh allowance.

### Secure Code Practices

1. **ID generation** — Uses `secrets.choice()` for cryptographically secure random IDs.
2. **SECRET_KEY** — Required from environment variable, not hardcoded.
3. **RSVP obfuscation + high-entropy links** — Email/magic links carry the RSVP's 26-char (~134-bit) `token` via `generate_token()`, never the 6-char PK or real object codes, so they resist both enumeration and brute force.
4. **Security logging** — Auth events logged with IP addresses.
5. **Production hardening** — HSTS, secure cookies, SSL redirect, custom admin path, JSON-only renderer.
6. **Data exports carry no credentials** — the two endpoints in `core/views/export.py` serve files people forward and leave on laptops, so `Collection.share_token` and every `RSVP.token` are absent from the bytes (pinned by tests that read the raw bytes, not the tree). They are `no-store` and owner-scoped: an account copy is only ever your own, and a collection copy is owner-only with no partial variant.

---

## Architecture Notes

### View Patterns

- All views use `get_object_or_404` for consistent 404 responses.
- `ThingViewSet` and `CollectionViewSet` use DRF `ModelViewSet` with `DefaultRouter`.
- `ThingUpdateSerializer` has `status` as read-only to prevent direct status manipulation. `type` is editable. Use `POST /api/v1/things/{code}/activate/` to set status ACTIVE (from INACTIVE), and `POST /api/v1/things/{code}/hide/` to set status INACTIVE (from ACTIVE only).
- `ThingSerializer` and `CollectionThingSummarySerializer` include `pending_booking` (first PENDING booking code, or null) and `pending_questions` (count of unanswered FAQs).
- Accept/reject actions can be performed via the unified RSVP endpoint (`VerifyLinkView`) for email links — **a POST commits, GET only previews** (booking decisions never fire from a bare GET) — or via authenticated `BookingActionView` endpoints for in-app use. Both paths converge on `finalize_booking_decision()`, which runs `accept_booking()`/`reject_booking()`.
- All email links use RSVP codes as intermediaries to avoid exposing real object codes in URLs.
- Security events are logged to the `security` logger with IP addresses.

### Service Layer

Business logic is extracted into `core/services/`:
- `join_quota.py` — The per-collection daily cap on `POST /auth/join/` (`COLLECTION_JOINS_PER_DAY`), the one door that needs no account. Off by default.
- `creator_policy.py` — Whether this deployment lets an account open a collection in a given mode or offer a thing under a given verb (`CREATOR_POLICY`; open to everyone in the standalone). Enforced at five doors — collection create/update, thing create/update, bulk import — and served to the SPA as `capabilities` on `GET /auth/me/`. Gates *initiating*, not a member *contributing* an owner-allow-listed type to a COMMUNITY collection they were invited to (`community_contribution_types`).
- `email_service.py` — All email HTML composition and sending (every `send_*` function; `send_test_emails` keeps a sample of each). Uses `django.utils.html.escape()`.
- `booking_service.py` — `accept_booking()`, `reject_booking()`, and `cancel_booking()` handle status transitions for Thing and BookingPeriod, wrapped in `transaction.atomic()`; both decision paths (`BookingActionView` and `VerifyLinkView`) go through `finalize_booking_decision()`, which calls the first two. The reservation-**request** side lives here too: `request_date_based_booking()`, `request_standard_booking()` and `request_reservation()` (plus `require_a_seat()`, `resolve_rental_collection()`, `resolve_request_collection()` and the notification helpers). They raise `BookingRequestError(message, status_code, code=None, params=None)` on a rule violation; `ThingRequestView` catches it and returns `exc.as_body()`.

### Utilities

- `core/utils.py`: `generate_id()`, `get_client_ip()`, `asset_url()` — `asset_url(key)` joins the stored key onto `MEDIA_PUBLIC_BASE_URL` via `core.services.storage.public_url`. It replaced a Cloudinary SDK call that asked for `fetch_format=auto`/`quality=auto`; an object store does not transform, so that job moved to the browser, which encodes to WebP before uploading.
- `core/validators.py`: `ImageIdField`, `SafeHeadlineField`, `SafeTextField`, `validate_image_id()`, `validate_headline()`
- `core/pagination.py`: `StandardResultsPagination` (max 100 items)
- `core/views/_helpers.py`: `viewer_code()`, `deny_if_cannot_view()`, `get_viewable_thing()`, `type_validity_error()`, `require_collection_curator()`, and **`body_dict(request)`** — `request.data` when the body is a JSON object, else `{}`. DRF parses a JSON *array* body into a `list`, which has no `.get`, so any view reading `request.data.get(...)` **before a serializer has run** answers 500 where it owes a 400. Use it on every such read; a non-object body then means "no fields given" and falls through to the view's own validation. Pinned by `core/tests/integration/test_array_body.py`.

## Coded refusals in the views (`refusal_body`)

A view that turns a request down writes `Response(refusal_body("English sentence", code="x", key="error"|"detail", **params), status=…)` (`core/views/_helpers.py`). The sentence stays under the key the view always used; `code` (and `params`, when the sentence interpolates something) is what the SPA words in the reader's language from `requestErrors.<code>`. A `Refusal` (`capacity_violation`, the invitation quota) carries its own code, so `refusal_body(refusal)` is enough. Every code needs a string in the three locales (`test_refusal_codes.py` reads the sources, so a new file with codes goes in its `SOURCES`); a param named `max`, `days`, `min` or `step` doubles as the plural `count`, so such a code is written as `<code>_one` / `<code>_other`.

A field-keyed 400 that must carry a code and its params (the single-create thing ceiling, `things_limit`) is raised as `core.exceptions.RefusedField(field, refusal)`: the handler lifts the code to the top of the body, as for `CODED_VALIDATION_REFUSALS`, and `params` with it.
