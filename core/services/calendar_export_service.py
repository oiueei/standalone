"""The collection calendar export — date-based reservations as iCalendar (.ics).

A curator downloads their collection's upcoming loans, rentals and on-site
reservations as an RFC 5545 VCALENDAR. A whole-day booking (every LEND/RENT,
and a DAY-unit RESERVE) is **one all-day event covering the days the thing is
unavailable** — from the pickup day up to (not including) the return day, since
the return day is already free for the next booking. A one-week loan picked up
Monday blocks Mon–Sun and leaves the next Monday open. An **HOUR-unit
RESERVE_THING** (`booking.start_time` set) is instead one *timed* event,
rendered in UTC so the file needs no VTIMEZONE and imports at the same wall
clock everywhere.

**Why .ics and not the CSV this used to be.** Google Calendar's CSV importer
reads dates in the format of the *importing account* — an early adopter's
day/month account read ``10/01/2026`` as the 10th of January (the earlier
"verified" import was against a US-locale
account, so the MM/DD/YYYY assumption was never true in general). iCalendar's
dates are unambiguous and carry their timezone, and Google, Apple Calendar and
Outlook all import them — on a phone, opening the file is enough.

**Every upcoming reservation, not just the new ones.** Each VEVENT's UID is
``{booking.code}@oiueei``, stable across downloads, so a calendar that
re-imports the file updates its events in place instead of duplicating them —
which is what made the old incremental watermark unnecessary, and the
``CalendarExportMark`` model and its table are gone.

**A cancelled reservation travels too, marked as cancelled.** A calendar that
imported a reservation keeps it after the member (or a curator) cancels it —
the file is a copy, not a subscription. So every download also carries each
upcoming reservation that was cancelled, under the same UID, with
``STATUS:CANCELLED`` and ``SEQUENCE:1`` (live events are ``SEQUENCE:0``): RFC
5545 has a calendar accept a revision only when its SEQUENCE is higher than
the copy it holds, and one that honours the status then drops or strikes out
its copy. Only RESERVE_THING can get here — it is the one verb that goes from
ACCEPTED to CANCELLED; a loan or rental is only ever cancelled while PENDING,
so it never reached a calendar in the first place. How an importing app treats
a cancellation it receives by file differs from app to app; the file says what
the standard lets it say.

**Whose reservations the file holds follows the app's rule.** In a PROPRIETARY
collection its curators run every thing, so they get every reservation. In a
COMMUNITY collection the people who ask for a member's thing are for that
member's eyes (the app shows them in ``/owner-bookings`` and on the thing's
calendar only to whoever manages the thing, which in COMMUNITY is its owner), so
the file holds only the reservations of things the downloader owns; with no
downloader given it holds none. The file carries accepted reservations only (and
cancelled RESERVE_THINGs): the pending, refused and cancelled requests that stay
private never reach an ``.ics``. RESERVE_THING lives only in PROPRIETARY
collections.

Everything user-written that reaches a TEXT property — a thing headline, a
member name, a project note — is escaped per RFC 5545 §3.3.11 (backslash,
semicolon, comma, newline), which replaces the spreadsheet-formula guard the
CSV needed. Owner headlines that carry one text per language (inline JSON)
resolve to the collection's language.
"""

import datetime
from zoneinfo import ZoneInfo

from django.conf import settings
from django.db.models import Q
from django.utils import timezone

from core.models import BookingPeriod, Collection
from core.models.booking import DATE_BASED_TYPES
from core.models.thing import Thing
from core.services.email_service import resolve_email_language
from core.utils import resolve_localized

# RFC 5545 §3.1: content lines are delimited by CRLF and must not be longer
# than 75 OCTETS — bytes, not characters, so a multibyte UTF-8 sequence must
# never be split. A longer line folds with CRLF followed by a single space.
_LINE_OCTETS = 75

# One text catalogue per language, kept in parity by
# ``test_calendar_export_service.py`` (the pattern ``export_service.README_TEXTS``
# uses). Not part of the email catalogue: this is a file for a machine, not a
# message, and the operator-facing senders that carry data rather than copy are
# already outside ``email_texts``.
CALENDAR_TEXTS = {
    "en": {
        "subject_LEND_THING": "{thing} → {person}",
        "kind_LEND_THING": "Loan",
        "subject_RENT_THING": "{thing} → {person}",
        "kind_RENT_THING": "Rental",
        "subject_RESERVE_THING": "{thing} — {person}",
        "kind_RESERVE_THING": "Reservation",
        "a_member": "a member",
        "return_by": "Return by {date}",
        "deposit": "Deposit: {amount}",
        "note": "Project: {note}",
        "provenance": "OIUEEI · {collection}",
    },
    "es": {
        "subject_LEND_THING": "{thing} → {person}",
        "kind_LEND_THING": "Préstamo",
        "subject_RENT_THING": "{thing} → {person}",
        "kind_RENT_THING": "Alquiler",
        "subject_RESERVE_THING": "{thing} — {person}",
        "kind_RESERVE_THING": "Reserva",
        "a_member": "un miembro",
        "return_by": "Devolución el {date}",
        "deposit": "Fianza: {amount}",
        "note": "Proyecto: {note}",
        "provenance": "OIUEEI · {collection}",
    },
    "ca": {
        "subject_LEND_THING": "{thing} → {person}",
        "kind_LEND_THING": "Préstec",
        "subject_RENT_THING": "{thing} → {person}",
        "kind_RENT_THING": "Lloguer",
        "subject_RESERVE_THING": "{thing} — {person}",
        "kind_RESERVE_THING": "Reserva",
        "a_member": "un membre",
        "return_by": "Devolució el {date}",
        "deposit": "Dipòsit: {amount}",
        "note": "Projecte: {note}",
        "provenance": "OIUEEI · {collection}",
    },
}


def _esc(value):
    """A TEXT value per RFC 5545 §3.3.11 — backslash, semicolon and comma are
    escaped, and a line break becomes a literal ``\\n``. The escaping a TEXT
    property needs; the CSV's spreadsheet-formula guard has no equivalent here
    because nothing downstream evaluates a calendar entry as an expression."""
    text = "" if value is None else str(value)
    text = text.replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,")
    return text.replace("\r\n", "\\n").replace("\r", "\\n").replace("\n", "\\n")


def _fold(line):
    """One content line as the physical lines RFC 5545 allows — ≤75 octets each,
    continuations prefixed with a space, never splitting a UTF-8 character.

    The leading space on every continuation is the fold marker itself (RFC
    5545 §3.1): the unfolder strips exactly one such character from each
    continuation before rejoining. It must be *added* here, not merely
    budgeted for — a fold that reserves the octet but never writes the space
    silently eats the continuation's first real character on unfold instead
    (found reading the production `.ics` back: a headline or description long
    enough to fold came back missing one letter at each fold point)."""
    raw = line.encode("utf-8")
    if len(raw) <= _LINE_OCTETS:
        return [line]

    parts = []
    start = 0
    limit = _LINE_OCTETS
    first = True
    while start < len(raw):
        end = min(start + limit, len(raw))
        # Back off to a character boundary: a UTF-8 continuation byte is
        # 0b10xxxxxx, so step left while the byte we would cut at is one.
        while end < len(raw) and raw[end] & 0xC0 == 0x80:
            end -= 1
        piece = raw[start:end].decode("utf-8")
        parts.append(piece if first else " " + piece)
        start = end
        limit = _LINE_OCTETS - 1  # room for the next continuation's own leading space
        first = False
    return parts


def _ddmy(value):
    """A date the way OIUEEI shows dates to people everywhere else — DD/MM/YYYY."""
    return value.strftime("%d/%m/%Y") if value else ""


def _utc(day, clock):
    """A wall-clock time on ``day``, read in the deployment's timezone, as UTC.

    ``TIME_ZONE`` is the zone ``opening_hours`` and reservation times are
    written in, so it is the only honest reading of ``start_time``. UTC output
    is what lets the file carry no VTIMEZONE and still land on the right wall
    clock in every importing calendar.
    """
    local = datetime.datetime.combine(day, clock, tzinfo=ZoneInfo(settings.TIME_ZONE))
    return local.astimezone(datetime.timezone.utc)


def _fmt_utc(moment):
    return moment.strftime("%Y%m%dT%H%M%SZ")


def _upcoming_bookings(collection, user=None):
    """The collection's date-based, not-yet-finished reservations that belong
    in a calendar, oldest start first: every confirmed one, and every
    reservation cancelled after it was confirmed (RESERVE_THING, the only verb
    that goes from ACCEPTED to CANCELLED — see the module docstring). Every one
    of them — the stable UID is what keeps a re-import from duplicating, so
    there is no watermark to respect.

    **Limited to what ``user`` manages outside PROPRIETARY.** In a COMMUNITY
    collection that is the things they own (``Thing.can_manage`` is only the
    owner there), asked in the query rather than per row; with no ``user``, none.
    A PROPRIETARY collection's curators get all of it."""
    today = timezone.localdate()
    bookings = (
        BookingPeriod.objects.filter(
            Q(status=BookingPeriod.Status.ACCEPTED)
            | Q(
                status=BookingPeriod.Status.CANCELLED,
                thing_type=Thing.Type.RESERVE_THING,
            ),
            thing_code__collections=collection,
            thing_type__in=DATE_BASED_TYPES,
            end_date__gte=today,
        )
        .select_related("thing_code", "requester_code")
        .distinct()
        .order_by("start_date", "code")
    )
    if collection.mode == Collection.Mode.PROPRIETARY:
        return bookings
    # A network's founder reads every entity's reservations; a co-curator only those of
    # the things they run (below).
    if user is not None and collection.can_rescue(user.code):
        return bookings
    if user is None:
        return bookings.none()
    return bookings.filter(thing_code__owner=user)


def _is_cancelled(booking):
    return booking.status == BookingPeriod.Status.CANCELLED


def _event_lines(booking, texts, lang, collection_headline, now):
    """One VEVENT for one reservation."""
    thing = booking.thing_code
    headline = resolve_localized(thing.headline, lang)
    person = (booking.requester_code.name or "").strip() or texts["a_member"]
    summary = texts[f"subject_{booking.thing_type}"].format(thing=headline, person=person)

    # The kind of reservation leads the description: the title no longer carries it,
    # and in a library that holds both loans and rentals the title alone cannot say
    # which one an event is.
    description = [texts[f"kind_{booking.thing_type}"]]
    if booking.thing_type in (Thing.Type.LEND_THING, Thing.Type.RENT_THING):
        description.append(texts["return_by"].format(date=_ddmy(booking.end_date)))
        if booking.deposit_amount:
            description.append(texts["deposit"].format(amount=booking.deposit_amount))
    if booking.thing_type == Thing.Type.RESERVE_THING and booking.project_note.strip():
        description.append(texts["note"].format(note=booking.project_note.strip()))
    description.append(
        texts["provenance"].format(collection=resolve_localized(collection_headline, lang))
    )

    lines = [
        "BEGIN:VEVENT",
        # Stable across downloads: a calendar that re-imports the file updates
        # this event in place instead of growing a duplicate.
        f"UID:{booking.code}@oiueei",
        f"DTSTAMP:{_fmt_utc(now)}",
        # A cancellation is the event's one revision, so it outranks the
        # confirmed copy a calendar already holds (RFC 5545 §3.8.7.4).
        f"SEQUENCE:{1 if _is_cancelled(booking) else 0}",
        f"STATUS:{'CANCELLED' if _is_cancelled(booking) else 'CONFIRMED'}",
    ]
    if booking.start_time is not None and booking.end_time is not None:
        # An HOUR-unit reservation: a timed event, both clock times on
        # `start_date`. Never `end_date`, which for an hourly booking stores
        # `start_date + 1` purely as the day-based "free again" marker every
        # other consumer reads — using it would push the event a day late.
        lines.append(f"DTSTART:{_fmt_utc(_utc(booking.start_date, booking.start_time))}")
        lines.append(f"DTEND:{_fmt_utc(_utc(booking.start_date, booking.end_time))}")
    else:
        # A whole-day booking: iCalendar's all-day DTEND is exclusive — exactly
        # OIUEEI's own `end_date`, the day the thing is free again (matches
        # `has_overlap` and the availability walk). A one-week loan picked up
        # Monday the 14th has `end_date` the 21st, blocks the 14th–20th, and
        # leaves the 21st open. Do NOT "fix" this by subtracting a day.
        lines.append(f"DTSTART;VALUE=DATE:{booking.start_date:%Y%m%d}")
        lines.append(f"DTEND;VALUE=DATE:{booking.end_date:%Y%m%d}")
    lines.append(f"SUMMARY:{_esc(summary)}")
    lines.append(f"DESCRIPTION:{_esc(' — '.join(description))}")
    location = (thing.location or "").strip()
    if location:
        lines.append(f"LOCATION:{_esc(location)}")
    lines.append("END:VEVENT")
    return lines


def _ics_bytes(bookings, texts, lang, collection):
    now = timezone.now().astimezone(datetime.timezone.utc)
    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//OIUEEI//Calendar export//EN",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        f"X-WR-CALNAME:{_esc(resolve_localized(collection.headline, lang))}",
    ]
    for booking in bookings:
        lines.extend(_event_lines(booking, texts, lang, collection.headline, now))
    lines.append("END:VCALENDAR")

    physical = []
    for line in lines:
        physical.extend(_fold(line))
    return ("\r\n".join(physical) + "\r\n").encode("utf-8")


def calendar_filename(code):
    """``ABC123-calendar.ics`` — the stats CSV's shape, the iCalendar extension."""
    return f"{code}-calendar.ics"


def build_calendar_export(collection, user=None):
    """Return ``(ics_bytes, count, cancelled)`` for every upcoming reservation.

    ``count`` is how many confirmed events the file holds, ``cancelled`` how
    many cancellations ride along with them — a file of cancellations alone is
    still worth downloading, since it is what takes them off a calendar.

    The whole future of the collection, not just what a previous download
    missed: the per-booking UID makes re-importing idempotent, which is what
    retired the incremental watermark — and that watermark was exactly what
    locked a curator out of downloading again after a failed import.
    ``CalendarExportMark`` no longer exists.

    **``user`` also decides which reservations are in it** in a COMMUNITY
    collection: only those of things they own, none without a ``user`` (see
    ``_upcoming_bookings``); a PROPRIETARY collection's file holds them all.

    The event copy speaks the downloading curator's language, then the group's,
    then the deployment default — the same hierarchy every email follows
    (``resolve_email_language``).
    """
    lang = resolve_email_language(user=user, collection=collection)
    texts = CALENDAR_TEXTS.get(lang, CALENDAR_TEXTS["en"])

    bookings = list(_upcoming_bookings(collection, user))
    cancelled = sum(1 for booking in bookings if _is_cancelled(booking))
    return (
        _ics_bytes(bookings, texts, lang, collection),
        len(bookings) - cancelled,
        cancelled,
    )
