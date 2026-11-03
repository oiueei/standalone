# Running OIUEEI yourself, and running it for others

This repository is the whole product. Clone it, point it at a database, and you
have OIUEEI: collections, things, the verbs, invitations, magic links,
digests, the loan chain. Nothing is held back to be sold to you later.

What it does **not** contain is the layer a particular operator wraps around it
to run OIUEEI as a service for strangers: an open sign-up door, a queue of
people asking to be allowed to lend, a subscription. That layer is where an
operator's judgement lives — who gets in, on what terms, and what a "no" says —
and it differs for every one of them. Shipping ours would give you rules to
delete before you could use your own.

So the **mechanism** is here and the **policy** is not. This document is the
list of places a deployment plugs into, and the guarantee that comes with them:
you never have to edit a file this repository also edits.

That guarantee is the whole design. A deployment that patches `config/urls.py`
or a serializer inherits a merge conflict on every update, forever, and
eventually stops updating. Everything below exists so a deployment adds files
of its own instead.

---

## 1. `DEPLOYMENT_URLCONFS` — routes of your own

A comma-separated list of dotted paths to Django URLconf modules, mounted at the
root:

```bash
DEPLOYMENT_URLCONFS=deployment.urls,intranet.urls
```

```python
# deployment/urls.py
from django.urls import path
from . import views

urlpatterns = [path("request-access/", views.RequestAccess.as_view())]
```

They mount **before** the SPA catch-all, and that ordering is the point. The
catch-all matches everything outside `static/`, `api/` and the admin prefix, so
a page registered after it is answered with `index.html` and a **200** — the
wrong page under a success status, which is harder to notice than a 404 because
nothing about it looks broken.

Upstream ships none: every route the product serves is already in `core.urls`.

Name that app of yours anything **except** a module Python already has.
`operator`, `types`, `platform` and `email` are all in the standard library and
are imported before any of your code runs, so `INSTALLED_APPS += ["operator"]`
installs the stdlib module and `operator.urls` raises `ModuleNotFoundError:
'operator' is not a package` — a failure that names the collision nowhere near
where you would look for it.

## 2. `CREATOR_POLICY` — who may create what

A dotted path to a class, the way `AUTH_USER_MODEL` is a dotted path to a model:

```bash
CREATOR_POLICY=deployment.policy.VettedCreatorPolicy
```

```python
# deployment/policy.py
from core.models import Collection, Thing
from core.services.creator_policy import Capabilities, CreatorPolicy


class VettedCreatorPolicy(CreatorPolicy):
    """Giving and selling are open; anything that comes back is vetted."""

    def capabilities(self, user):
        vetted = CreatorValidation.objects.filter(user=user, approved=True).exists()
        if vetted:
            return Capabilities(
                collection_modes=tuple(Collection.Mode.values),
                thing_types=tuple(Thing.Type.values),
            )
        return Capabilities(
            collection_modes=(Collection.Mode.PROPRIETARY,),
            thing_types=(Thing.Type.GIFT_THING, Thing.Type.SELL_THING),
            request_url="https://your-domain.test/request-access/",
        )
```

The default, `core.services.creator_policy.OpenCreatorPolicy`, says **yes to
everyone, always** — an account is the only requirement to open a collection in
either mode or offer a thing under any of the verbs (GIFT, SELL, RENT, LEND, and
RESERVE, the on-site reservation). That is OIUEEI as a product, and it is what an
upstream checkout runs. An operator running OIUEEI *as a service* usually wants a
narrower answer for the things that put someone else on the hook — a COMMUNITY
collection, a loan or a rental that has to come back, a reservation that commits
their premises — and a `CreatorPolicy` subclass is where that judgement lives.

A subclass overrides **one method**. `allows_collection_mode()` and
`allows_thing_type()` are derived from it, so a policy cannot enforce something
it does not advertise — which is the failure mode of every gate written twice.

It must be **stateless** — one instance is built with no arguments and shared
across requests — but it need not be cheap. The example above hits the database
on every call, which is the normal shape for a real policy, so OIUEEI asks it
**once per decision**: a refusal reads both the allowed list and the request URL
off a single `capabilities()` call, and the bulk CSV import resolves it once for
the whole file rather than once per row (whether the deployment offers a verb is
a fact about the person, not about line 40 of the spreadsheet).

**A wrong path here fails the deploy, not the first request.** The setting is
resolved lazily, so a typo used to boot cleanly and then 500 `GET /auth/me/` —
the endpoint the SPA calls on every load. A system check now imports and
instantiates the policy at check time, and `manage.py migrate` runs system
checks, so a Heroku release phase aborts on it and keeps the previous release.

**The kinds of collection need nothing of a policy.** A collection is a stall
(give or sell), a library (lend or rent out) or a shed (book), and which of them an
account may open is *derived* from the verbs the policy offers: a kind is open when
at least one of its verbs is in `thing_types`. A policy keeps declaring only modes
and verbs — no deployment's class has to learn about kinds — and the one above, which
gives GIFT and SELL, lets an account open a stall and a library and a shed only
after it is vetted. `collection_kind_denial()` refuses the others with the
request URL, like the two denials beside it.

Enforced at five doors: collection create (its mode **and** its kind) and update, thing
create and update, and the bulk CSV import. The two edit paths only judge a **change**, so
narrowing a deployment never freezes what people already own — an owner who
could no longer fix a typo on their own lending collection would be the product
punishing them for a decision they had no part in.

## 3. `capabilities` on `GET /auth/me/` — what the UI is told

The same policy, served to the frontend on the endpoint the app already calls on
every load:

```json
"capabilities": {
  "collection_modes": ["PROPRIETARY", "COMMUNITY"],
  "collection_kinds": ["STALL", "LIBRARY", "SHED"],
  "thing_types": ["GIFT_THING", "SELL_THING", "RENT_THING", "LEND_THING", "RESERVE_THING"],
  "request_url": null,
  "co_owners_enabled": true
}
```

`collection_kinds` is computed from `thing_types`, never declared: the chooser at
`/new` shows a card for each kind but a button only for the ones listed.

The forms build their options from this, so a narrowed deployment stops offering
what its API would refuse instead of letting someone fill a form in and meet a
403 at the end of it. Where something *is* withheld, a quiet line names it and —
if `request_url` is set — links to where it is requested.

`request_url: null` means there is nowhere to ask, and the copy changes
accordingly: "not available here" rather than "ask over there". Both messages
are generic, both live upstream, and neither ever renders under the default
policy, because nothing is withheld.

## 4. `frontend/src/deployment/` — pages, doors and copy of your own

A directory a deployment **replaces wholesale**:

```js
export const deploymentRoutes = [
  { path: '/join', Component: lazy(() => import('./JoinPage')) },
];

export const popInPath = '/join';        // the "new here?" button on /login
export const aboutPath = '/about';       // the footer's "what this is" link
export const faqPath = '/faq';           // the help link under /login's form
// A guide for whoever runs a group (`curatorGuidePath`, null upstream): when set, a curator's
// collection menu gets an entry "If you run a group" after the downloads, and the notice
// that tells a member they were made a co-curator ends with the same link.
export const curatorGuidePath = '/guide';

// Forms hosted elsewhere (a form service) that stand in for the app's own ways of
// writing to you: the footer's "Contact us", "Ideas and bugs" and "Request access".
// One address per language; leave a key out (or the whole object `null`) for none.
export const externalForms = {
  contact: { es: 'https://forms.example/c-es', ca: 'https://forms.example/c-ca', en: 'https://forms.example/c-en' },
  feedback: { es: 'https://forms.example/f-es', ca: 'https://forms.example/f-ca', en: 'https://forms.example/f-en' },
  requestAccess: { es: 'https://forms.example/r-es', ca: 'https://forms.example/r-ca', en: 'https://forms.example/r-en' },
};

// Where "Request access" goes *inside the app*, by the value a policy withholds (the
// values of the three capability lists: `LIBRARY`, `COMMUNITY`, `RENT_THING`…). Leave a
// value out for none.
export const requestAccessPaths = { LIBRARY: '/access/library' };

export const deploymentI18n = {
  en: { join: { title: 'Come and see' } },
  es: { join: { title: 'Pásate a vernos' } },
};
```

Upstream exports the empty values: no extra routes, no open door, no about page,
no FAQ link, no guide for whoever runs a group, no forms of its own, no pages to ask on, no extra copy. `App.jsx`, `LoginPage.jsx`,
`SiteFooter.jsx`, `CollectionPage.jsx` and `VerifyPage.jsx` read them and are
**byte-identical in both**.

`externalForms` is `{ contact, feedback, requestAccess }`, each `{ es, ca, en }`.
When a deployment has one, the place that used to lead to the app's own way opens the
form instead, **in a new tab and exactly as the address is written** (no language,
user or page is added to it): the footer's "Contact us" opens the `contact` form
(otherwise `/contact`, the app's own page, which stays in either case); "Ideas and
bugs" opens `feedback` (otherwise the build variable `VITE_FEEDBACK_URL` — one address
for every language — or nothing); "Request access" opens `requestAccess` (otherwise
`capabilities.request_url` from section 3). The address of the reader's language is
used; a language without one uses `es`; no address at all, and the place behaves as
it does upstream. Core knows nothing about who hosts the forms.

`requestAccessPaths` is `{ <withheld value>: '<route of the app>' }`. Where the notice
"some of these need approval" (section 3) offers its "Request access" button, the first
withheld value, in the order the form lists them, that has a route here decides: the
button becomes a link to that page of the app, **in the same tab** and through the
router (no new-tab announcement), instead of the form hosted elsewhere. A withheld value
with no route keeps `externalForms.requestAccess`, then `capabilities.request_url`, in a
new tab as above. Upstream it is `{}`.

`deploymentI18n` is deep-merged into the `translation` namespace every time a
language file lands, so a deployment's strings stay out of
`i18n/locales/*.json` — three files upstream edits constantly.

One string set is worth knowing about because it turns a feature on rather than
just relabelling one: **`demoNotice.title` / `.body` / `.realNote`**. Supply them
and every page of an `is_onboarding` collection — the collection, its things, a
hold request — carries a "this is a demo" banner (`components/DemoNotice.jsx`,
which renders nothing until the keys exist). `.body` says what *is* demo (shared,
periodically reset); `.realNote` says what is not (the visitor's own collections
are real and kept) — a demo warning that scared people off their own work would
be worse than none.

## 5. `VIRAL_LINE_PROVIDER` — which growth line each recipient gets

Every email ends with one line inviting its reader to start something of their
own, a highlighted callout above the preferences and legal links. Upstream picks
one at random from a catalogue (`core/services/email_texts/`) for everybody,
which is right when everybody can do everything. A deployment where recipients
can do different things — one may open a kind of collection straight away and
another has to ask first — points a setting at a function of its own, so each
reader is sent to the place where *they* can act:

```bash
VIRAL_LINE_PROVIDER=deployment.viral.pick_line
```

```python
# deployment/viral.py
def pick_line(user, lang):
    """`user` is the recipient's User, or None for an address with no account."""
    if user is not None and can_open_libraries(user):
        return {"text": "...", "cta": "...", "path": "/library/new"}
    return {"text": "...", "cta": "...", "path": "/your-own-page"}
```

- **It receives** the recipient's `User` (`None` for an invitee with no account yet)
  and the language the email is written in, already resolved (`es`, `ca` or `en`).
- **It returns** `{"text": str, "cta": str, "path": str}` or `None`. `path` is a
  path on this site: it has to start with `/` and not with `//` (nor `/\`), and the
  email links to the frontend's address plus that path. The text and the label are
  escaped; the link is plain, never routed through a redirect or a tracker.
- **`None`, an incomplete answer or an unsafe `path` means no line** in that email;
  the rest of the footer is untouched.
- **If it raises, the email is still sent, without the line**, and a warning with
  the setting's path (never the recipient) goes to the log. A deployment's bug
  cannot cost anyone their sign-in link.
- **It is asked once per email, for that one recipient, and never for someone who
  runs a collection** (owner or co-curator): they already did what the line asks,
  so they get no line at all, whatever the function would have said.
- It is imported once per dotted path and shared across requests, so write it
  stateless. If it looks something up, it is looked up once per email.
- Empty (the default) keeps the catalogue, exactly as before.

**A wrong path fails the deploy, not the first email.** A system check imports the
setting at check time (`core.E006`), so a typo aborts the release phase instead of
quietly switching the line off for everybody.

---

## 6. `Braaanding` — the colours of the app itself

Everything that is not a collection's page — Home, the account pages, the front door,
the legal text, the 404, a deployment's own pages — and **every email** is painted with
one palette, the app's own, which no curator can pick (a collection's pages wear the
palette its curators chose among the twelve of the `Theeeme` table). It is a single
row of the `Braaanding` table, and **a deployment changes it in the Django admin, with
no code**: six hexadecimal colours (`#RRGGBB`) and a Koros wave.

- `color_01` primary button, the secondary button's border, links · `color_02` page and
  the wave's fill · `color_03` hero · `color_04` body text and the secondary button's
  label · `color_05` hero text and table headers · `color_06` primary button label.
- **The admin refuses a palette that would paint unreadable text**: it asks for 4.5:1
  where the twelve collection palettes are held to it (body text on the page, the primary
  button's label on its fill, the hero's text on the hero, the text colour on white, the
  front door's warning on the page). A malformed colour is refused before that.
- The pages receive it inside the HTML (`spa_index` writes it into the `<head>`: no
  request, no flash) and the emails read the same row, so the web and the mail agree.
  Each web worker remembers the row for up to a minute, so a change shows within that.
- A fresh install starts with the palette migration `0164` seeds
  (`#191919 #F4E5DD #D77452 #191919 #191919 #FAFAFA`, koro `basic`); there is no setting
  or environment variable for it.

---

## 7. The daily `purge_expired_data --commit` — a promise the app makes

A shed can ask, when someone books, for an optional contact phone, and the request page's label promises it
is **deleted the day after the booking**. The app stops serving it that day by itself, but the deletion is
done by `purge_expired_data`, whose period for this is fixed (no `RETENTION_*` setting, nothing to switch
off). A deployment must therefore run `python manage.py purge_expired_data --commit` **every day** (the
daily chain in [HEROKU.md](HEROKU.md) does); left in dry-run, the label would not be true.

---

## What upstream deliberately does not have

- **No open sign-up.** `POST /auth/join/` creates nothing without a valid share
  token or PUBLIC collection code. An account exists because somebody chose to
  admit a specific person.
- **No "what this is" page.** What OIUEEI is belongs in this README; what *your*
  deployment is belongs to you (`aboutPath`).
- **No product-stats report.** The `Event` log and `DailyActivity` are written as
  always — they are product instrumentation — but what you ask them is yours.

If you want an open door, `is_onboarding` is still on `Collection` and
`seed_demo` still sets it: a view of your own, mounted through
`DEPLOYMENT_URLCONFS`, can create the account and join it to every collection
carrying that flag. The column, the flag and the landing rule (a link from
your door goes to the one real group its visitor has, and to Home when they have
none or several — the demonstration collections are not counted) are all still
here, working, waiting for a door you write — and the `demoNotice.*` strings
above put an honest banner on the seed collections your visitors land in.

## Licence, and the honest version of "auditable"

OIUEEI is open source under the **EUPL-1.2** (see `LICENSE`) — a strong copyleft
licence. You may run it, modify it and self-host it for your own community. What
it asks in return is reciprocity: distribute a modified OIUEEI, *or run one as a
service*, and those changes are owed to your users under the same licence. An
unmodified deployment owes nothing beyond keeping the notices.

One consequence is easy to trip over, so it is said here: the **first** thing
this guide has you do — edit `frontend/src/legal/{lang}.js` with your own
identity — already makes you a modifier. Private to your group, that changes
nothing in practice. Run it as a service for others and those edits (and any
others) are source you owe them. Complying is trivial — publish your fork — but
nobody tells you.

Every line of the **product** is in this repository and can be read, audited and
changed. An operator's **service layer** — their sign-up door, their vetting
queue, their billing — is a separate body of code written against the four
extension points above. Where it builds on and extends OIUEEI it is likely a
derivative work, and the EUPL's reciprocity then reaches it too. What that layer
may and may not do is bounded by what it plugs into — exactly those four points.
