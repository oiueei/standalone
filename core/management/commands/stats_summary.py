"""Weekly first-party stats summary for OIUEEI.

Computes product metrics from three sources — current state (domain tables),
accumulated history (the Event log), and retention (DailyActivity) — and prints
them to stdout, emailing them to Carlos on Mondays (weekday-gated like
``send_digests``; pass ``--email`` to force a send for a manual run).

Demo data never mixes into the real numbers: the five seed users
(Lala/Lele/Lili/Lolo/Lulu), ``is_onboarding`` collections, and pop-in users who
only ever landed in onboarding collections are split off into a separate
"Demo funnel" section. Everything stays first-party and in our DB (DESIGN §9).

Run daily via Heroku Scheduler (it self-gates to Mondays):
    ... && python manage.py stats_summary
Manual, any day:
    heroku run --app <app> "python manage.py stats_summary --email"
"""

from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Count, Min, Q
from django.utils import timezone

from core.management.commands.seed_data.common import USERS as _SEED_USERS
from core.models import FAQ, BookingPeriod, Collection, DailyActivity, Event, Thing, User
from core.services.email_service import send_stats_summary_email

SEED_USER_CODES = frozenset(u["code"] for u in _SEED_USERS)
STATS_RECIPIENT = "oiueei@disroot.org"


def _pct(part, whole):
    return f"{100 * part / whole:.0f}%" if whole else "—"


def _avg(total, count, unit=""):
    return f"{total / count:.1f}{unit}" if count else "—"


class Command(BaseCommand):
    help = "Print (and, on Mondays, email) the first-party product stats summary."

    def add_arguments(self, parser):
        parser.add_argument(
            "--email",
            action="store_true",
            help="Send the email regardless of weekday (for a manual run).",
        )

    def handle(self, *args, **options):
        sections = build_report()
        self.stdout.write(render_text(sections))

        today = timezone.localdate()
        if options["email"] or today.weekday() == 0:  # Monday
            send_stats_summary_email(
                STATS_RECIPIENT, f"OIUEEI stats — {today.isoformat()}", sections
            )
            self.stdout.write(self.style.SUCCESS(f"Stats email sent to {STATS_RECIPIENT}"))
        else:
            self.stdout.write("Not Monday — email skipped (use --email to force a send).")


# --- Demo/real partition --------------------------------------------------------


def _partition():
    """Split the population into real vs demo.

    Returns a dict of code sets:
    - ``creators``  real users owning ≥1 non-onboarding collection
    - ``guests``    real users invited to ≥1 non-onboarding collection (not creators)
    - ``real``      creators ∪ guests
    - ``demo``      everyone else (seed users + onboarding-only pop-in users)
    - ``demo_collections`` onboarding collection codes
    """
    demo_collections = set(
        Collection.objects.filter(is_onboarding=True).values_list("code", flat=True)
    )
    creators = (
        set(Collection.objects.filter(is_onboarding=False).values_list("owner_id", flat=True))
        - SEED_USER_CODES
    )
    invited_real = (
        set(
            User.objects.filter(invited_to_collections__is_onboarding=False).values_list(
                "code", flat=True
            )
        )
        - SEED_USER_CODES
    )
    guests = invited_real - creators
    real = creators | guests
    demo = set(User.objects.values_list("code", flat=True)) - real
    return {
        "creators": creators,
        "guests": guests,
        "real": real,
        "demo": demo,
        "demo_collections": demo_collections,
    }


# --- Report ---------------------------------------------------------------------


def build_report():
    """Compute every section. Returns a list of ``{title, rows, note?}`` dicts."""
    now = timezone.now()
    today = timezone.localdate()
    p = _partition()
    real, creators, guests = p["real"], p["creators"], p["guests"]
    demo, demo_collections = p["demo"], p["demo_collections"]
    real_list = list(real)

    sections = [
        _users_section(real, creators, guests),
        _collections_section(creators, guests),
        _things_section(real_list),
        _holds_section(real_list, guests),
        _history_section(demo, demo_collections, now),
        _conversion_section(demo, demo_collections),
        _retention_section(real, creators, guests, today),
        _demo_section(demo, demo_collections),
    ]
    return sections


def _users_section(real, creators, guests):
    return {
        "title": "Users (real)",
        "rows": [
            ("Total real users", len(real)),
            ("Creators (own ≥1 real collection)", len(creators)),
            ("Guests (invited only)", len(guests)),
        ],
    }


def _collections_section(creators, guests):
    real = Collection.objects.filter(is_onboarding=False)
    total = real.count()
    active = real.filter(status=Collection.Status.ACTIVE).count()
    community = real.filter(mode=Collection.Mode.COMMUNITY).count()
    public = real.filter(visibility=Collection.Visibility.PUBLIC).count()
    invites = real.aggregate(n=Count("invites"))["n"] or 0
    # Distinct guests per creator: a guest under two of the same creator's
    # collections counts once for that creator. Anonymous visitors aren't tracked.
    per_creator = real.values("owner_id").annotate(g=Count("invites", distinct=True))
    guests_per_creator = sum(r["g"] for r in per_creator)
    n_creators = len(creators)
    return {
        "title": "Collections (real)",
        "rows": [
            ("Total", total),
            ("Active (status ACTIVE)", active),
            ("COMMUNITY / PROPRIETARY", f"{community} / {total - community}"),
            ("PUBLIC / PRIVATE", f"{public} / {total - public}"),
            ("Avg collections per creator", _avg(total, n_creators)),
            ("Avg guests per collection", _avg(invites, total)),
            ("Avg guests brought per creator", _avg(guests_per_creator, n_creators)),
        ],
    }


def _things_section(real_list):
    things = Thing.objects.filter(owner_id__in=real_list)
    total = things.count()
    active = things.filter(status=Thing.Status.ACTIVE).count()
    by_type = dict(things.values_list("type").annotate(n=Count("code")).values_list("type", "n"))
    faqs = FAQ.objects.filter(thing__owner_id__in=real_list).count()
    holds = BookingPeriod.objects.filter(thing_code__owner_id__in=real_list).count()
    type_rows = [(t, f"{c} ({_pct(c, total)})") for t, c in sorted(by_type.items())]

    # Things per (real) collection, by M2M membership — added vs currently active.
    real_collections = Collection.objects.filter(is_onboarding=False)
    n_collections = real_collections.count()
    agg = real_collections.aggregate(
        members=Count("things"),
        active=Count("things", filter=Q(things__status=Thing.Status.ACTIVE)),
    )
    per_coll = (
        f"{_avg(agg['members'] or 0, n_collections)} / {_avg(agg['active'] or 0, n_collections)}"
    )
    return {
        "title": "Things (real)",
        "rows": [
            ("Total", total),
            ("Available (status ACTIVE)", active),
            *type_rows,
            ("Avg things per collection (added / active)", per_coll),
            ("Avg FAQs per thing", _avg(faqs, total)),
            ("Avg holds per thing", _avg(holds, total)),
        ],
    }


def _holds_section(real_list, guests):
    bookings = BookingPeriod.objects.filter(thing_code__owner_id__in=real_list)
    total = bookings.count()
    accepted = bookings.filter(status=BookingPeriod.Status.ACCEPTED).count()

    # Time-to-first-hold: for each thing that got a hold, first hold minus thing
    # creation, averaged (in days).
    first_holds = bookings.values("thing_code_id").annotate(
        first=Min("created"), created=Min("thing_code__created")
    )
    deltas = [
        (r["first"] - r["created"]).total_seconds()
        for r in first_holds
        if r["first"] and r["created"]
    ]
    ttfh = _avg(sum(deltas) / 86400, len(deltas), unit="d") if deltas else "—"

    booked_guests = set(
        bookings.filter(requester_code__in=guests).values_list("requester_code", flat=True)
    )
    never_booked = len(guests - booked_guests)

    return {
        "title": "Holds (real, current bookings)",
        "rows": [
            ("Total hold requests", total),
            ("Success rate (accepted / requested)", _pct(accepted, total)),
            ("Avg time from thing added → first hold", ttfh),
            ("Guests who never booked", f"{never_booked} ({_pct(never_booked, len(guests))})"),
        ],
    }


def _real_events(demo, demo_collections):
    return Event.objects.exclude(actor_code__in=demo).exclude(collection_code__in=demo_collections)


def _history_section(demo, demo_collections, now):
    events = _real_events(demo, demo_collections)
    d7, d30 = now - timedelta(days=7), now - timedelta(days=30)

    def n(kind, since=None):
        qs = events.filter(kind=kind)
        return qs.filter(created__gte=since).count() if since else qs.count()

    K = Event.Kind
    joined = f"{n(K.USER_JOINED, d7)} / {n(K.USER_JOINED, d30)} / {n(K.USER_JOINED)}"
    requested, accepted = n(K.HOLD_REQUESTED), n(K.HOLD_ACCEPTED)
    added, removed = n(K.THING_ADDED), n(K.THING_REMOVED)
    # The same real add/remove lifecycle averaged over the real (non-onboarding)
    # collections, so it reads right below the global counts.
    n_collections = Collection.objects.filter(is_onboarding=False).count()
    return {
        "title": "History (accumulated, from Event log)",
        "rows": [
            ("Users joined (7d / 30d / all)", joined),
            (
                "Collections created / deleted",
                f"{n(K.COLLECTION_CREATED)} / {n(K.COLLECTION_DELETED)}",
            ),
            ("Things added / removed", f"{added} / {removed}"),
            (
                "Avg added / removed per collection",
                f"{_avg(added, n_collections)} / {_avg(removed, n_collections)}",
            ),
            ("Members joined / left", f"{n(K.MEMBER_JOINED)} / {n(K.MEMBER_LEFT)}"),
            ("FAQs asked", n(K.FAQ_ASKED)),
            ("Holds requested / accepted", f"{requested} / {accepted}"),
            ("Hold success rate (all time)", _pct(accepted, requested)),
        ],
    }


def _conversion_section(demo, demo_collections):
    """Guest→creator: an actor with a MEMBER_JOINED that predates their first
    COLLECTION_CREATED — i.e. someone who arrived as a guest and later started
    their own collection. Derived, never stored (per the spec)."""
    events = _real_events(demo, demo_collections)
    joined = dict(
        events.filter(kind=Event.Kind.MEMBER_JOINED)
        .values("actor_code")
        .annotate(first=Min("created"))
        .values_list("actor_code", "first")
    )
    created = dict(
        events.filter(kind=Event.Kind.COLLECTION_CREATED)
        .values("actor_code")
        .annotate(first=Min("created"))
        .values_list("actor_code", "first")
    )
    deltas = [
        (created[a] - joined[a]).total_seconds()
        for a in joined
        if a in created and created[a] > joined[a]
    ]
    avg_days = _avg(sum(deltas) / 86400, len(deltas), unit="d") if deltas else "—"
    return {
        "title": "Conversion",
        "rows": [
            ("Guest → creator conversions", len(deltas)),
            ("Avg time guest → first collection", avg_days),
        ],
    }


def _retention_section(real, creators, guests, today):
    cut7, cut30 = today - timedelta(days=7), today - timedelta(days=30)
    active7 = set(DailyActivity.objects.filter(date__gte=cut7).values_list("user_id", flat=True))
    active30 = set(DailyActivity.objects.filter(date__gte=cut30).values_list("user_id", flat=True))

    day_counts = dict(
        DailyActivity.objects.values("user_id")
        .annotate(n=Count("date", distinct=True))
        .values_list("user_id", "n")
    )
    returners = {c for c, days in day_counts.items() if days >= 2}
    one_visit = {c for c, days in day_counts.items() if days == 1}

    def split(codes):
        return f"{len(codes & creators)} creators / {len(codes & guests)} guests"

    def returns_for(role):
        role_returners = returners & role
        avg_days = _avg(sum(day_counts[c] for c in role_returners), len(role_returners))
        return f"{len(role_returners)} returned (avg {avg_days} active days)"

    return {
        "title": "Retention (from DailyActivity)",
        "rows": [
            ("WAU — active last 7d", f"{len(active7 & real)} ({split(active7 & real)})"),
            ("MAU — active last 30d", f"{len(active30 & real)} ({split(active30 & real)})"),
            ("Creator returns (active ≥2 days)", returns_for(creators)),
            ("Guest returns (active ≥2 days)", returns_for(guests)),
            ("Guests who never came back after 1st visit", len(one_visit & guests)),
        ],
    }


def _demo_section(demo, demo_collections):
    """Demo funnel — reported apart so it never contaminates the real metrics."""
    onboarding_joins = Event.objects.filter(
        kind=Event.Kind.MEMBER_JOINED, collection_code__in=demo_collections
    ).count()
    demo_holds = Event.objects.filter(kind=Event.Kind.HOLD_REQUESTED, actor_code__in=demo).count()
    return {
        "title": "Demo funnel (NOT real metrics)",
        "rows": [
            ("Seed + onboarding-only users", len(demo)),
            ("Onboarding collections", len(demo_collections)),
            ("Onboarding joins (MEMBER_JOINED)", onboarding_joins),
            ("Holds requested by demo users", demo_holds),
        ],
    }


def render_text(sections):
    """Plain-text rendering for stdout (and the manual/scheduler log)."""
    lines = ["", "=== OIUEEI stats summary ===", ""]
    for section in sections:
        lines.append(section["title"])
        lines.append("-" * len(section["title"]))
        for label, value in section["rows"]:
            lines.append(f"  {label}: {value}")
        if section.get("note"):
            lines.append(f"  ({section['note']})")
        lines.append("")
    return "\n".join(lines)
