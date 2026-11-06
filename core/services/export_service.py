"""
Data portability (GDPR art. 20): a copy of what OIUEEI holds about you.

The mirror image of ``account_service``. That module's docstring is the map of
what dies with an account, what survives anonymised and what was never
identifying in the first place; this one is its inverse — *what dies with you is
what you get to take with you* — so the two are meant to be read side by side.
When a new model arrives, both are wrong until both are updated.

Two exports, deliberately separate:

- ``build_account_export(user)`` — art. 20 in the strict sense: a person's own
  data, plus the public identity (code and name) of whoever they dealt with,
  because a booking with its counterpart removed is not a record of anything.
- ``build_collection_export(collection)`` — an operational copy of a group its
  owner runs, other members' things included. It is not art. 20 and doesn't
  pretend to be; it is what makes a library of things portable at all, and it is
  owner-only.

Invariants, each pinned by a test in ``core/tests/unit/test_export_service.py``:

- **No credential ever leaves.** ``Collection.share_token`` and every
  ``RSVP.token`` are absent from the bytes. A file gets forwarded; a token
  inside it is a set of keys forwarded with it.
- **Other people's data only where the exporter already sees it.** Member emails
  ride along in collections the exporter *owns* — the same list the guests page
  shows them — never in ones they were merely invited to. The optional
  demographics follow ``Collection.is_community()``, exactly as
  ``CollectionSerializer.get_invites`` does.
- **A group's copy is the history of that group.** A thing can sit in two
  groups and a booking records who asked, not through which group; so outside
  PROPRIETARY (whose curators manage every thing in it) the copy carries the
  requests made by the owner and the members, and the hidden questions of the
  same people, and leaves out what a person from another group asked about a
  member's thing. The organiser of a COMMUNITY group does not manage the
  members' things, and the app never shows them that.
- **Reports stay anonymous.** Reports the exporter filed are theirs; reports
  filed *against* their things appear in neither export. This file must not
  become the leak the notification carefully avoids.
- **Owner text stays raw.** A localized ``headline`` (``{"es": …, "ca": …}``)
  exports as the map the owner wrote, never resolved to one language: the file
  is for machines, and resolving would silently drop two thirds of it.
- **No tombstones.** Deleted is deleted; the file is a photo of what exists.

Photos and the welcome PDF travel as URLs, not bytes: it keeps the
response inside Heroku's 30-second window, and it is why the page that offers
the download has to say that deleting the account breaks those links.
"""

import json
from collections import Counter, defaultdict
from datetime import timedelta

from django.db.models import Count, Exists, OuterRef, Prefetch, Q, Subquery
from django.utils import timezone

from core.models import (
    FAQ,
    RSVP,
    BookingPeriod,
    Collection,
    Event,
    InvitationProposal,
    Thing,
    ThingTransfer,
)
from core.services.email_service import resolve_email_language
from core.utils import asset_url, doc_asset_url

ACCOUNT_FORMAT = "oiueei-account-export/1"
COLLECTION_FORMAT = "oiueei-collection-export/1"

# The rolling window every "(90d)" metric in the stats block measures. Lived on
# CollectionStatsView until the export needed the same numbers; one definition,
# two renderings (CSV for the owner's spreadsheet, a dict inside the export).
STATS_WINDOW_DAYS = 90

# The fewest members a birth-year bracket or a postal code must hold to be named
# in the stats. Below it the figure is about a person, not a group.
STATS_MIN_GROUP = 3

AGE_LABELS = {
    "PRE_1946": "Born 1945 or earlier",
    "BOOMER": "Born 1946-1964 (Boomers)",
    "GEN_X": "Born 1965-1980 (Gen X)",
    "GEN_Y": "Born 1981-1996 (Millennials)",
    "GEN_Z": "Born 1997-2012 (Gen Z)",
    "GEN_A": "Born 2013-2024 (Gen Alpha)",
    "GEN_B": "Born 2025-2039 (Gen Beta)",
}

# The keys of an account export that hold two lists rather than one, so the
# manifest can index them without guessing (a dict of scalars — `profile`,
# `stats` — has nothing to count, and `collection` holds lists that are content,
# not rows).
_GROUPED_ACCOUNT_KEYS = ("collections_member_of", "bookings", "faqs", "activity")


# --------------------------------------------------------------------------- #
# Readme
# --------------------------------------------------------------------------- #

# Shipped inside every file, in the reader's language, because a JSON tree
# doesn't explain its own omissions: someone who downloads their data and finds
# no reports about their things should learn here that they are anonymous by
# design, not conclude that the export is broken. The frontend page repeats the
# same points — this copy is the one that survives being saved to a disk.
README_TEXTS = {
    "en": {
        "account": {
            "about": (
                "This is a copy of your OIUEEI data, taken the moment you asked for it. "
                "Each key below is a part of your account, and `_manifest.counts` says how "
                "many rows each one has. Downloading it changes nothing in OIUEEI. "
                "`organisations` is the page you have in each group you run."
            ),
            "not_included": [
                "Credentials. The public link to your collections, the tokens behind magic "
                "links and your session cookies are deliberately left out: anyone holding "
                "this file could otherwise walk into your groups.",
                "Other people's data. Emails are here only for the groups you own — the same "
                "ones you already see when you manage invitations. Nothing from groups you "
                "were merely invited to, and nobody's birth range or postal code but yours.",
                "Other people's things that live in your collections: only their code, their "
                "title and their owner's public name. If you run the group and want the full "
                "record of everything inside it, download the collection copy instead.",
                "Reports about your things. They are anonymous by design: neither the app nor "
                "this file tells you who reported. The ones you filed yourself are here.",
                "Photos and PDFs travel as links, not as files. Careful: if you delete your "
                "account those links stop working — download your images first.",
                "Emails. We keep no copy of the ones we send you, and messages from the "
                "contact form are forwarded without being stored.",
                "Server logs (accesses, IP addresses) are not part of this file; the privacy "
                "policy says how they are handled and for how long.",
                "Anything you already deleted. Deleting in OIUEEI is final — there is no bin.",
            ],
        },
        "collection": {
            "about": (
                "This is an operational copy of a group you run: the collection, its members, "
                "everything inside it and the history of its handovers, whoever they belong "
                "to. It is not the same as the copy of your own data — that one lives in your "
                "profile."
            ),
            "your_responsibility": (
                "This file carries other people's data: their emails and, in a community "
                "group, their birth range and postal code. The moment it lands on your "
                "computer you are the one answering for it. Keep it somewhere safe and don't "
                "forward it."
            ),
            "not_included": [
                "Credentials: the group's public link and the tokens behind any pending "
                "invitation.",
                "Reports. They are anonymous in both directions.",
                "Your members' notifications and activity — those are theirs, not the group's.",
                "Birth ranges and postal codes, unless this is a community group: in every "
                "other mode nobody but each member sees them.",
                "In a community group, requests and hidden questions from people outside the "
                "group: they concern a member's thing, and only whoever runs that thing sees "
                "them.",
                "Photos and PDFs travel as links, not as files.",
            ],
        },
    },
    "es": {
        "account": {
            "about": (
                "Esta es una copia de tus datos en OIUEEI, hecha en el momento en que la "
                "pediste. Cada clave de abajo es una parte de tu cuenta, y `_manifest.counts` "
                "dice cuántas filas tiene cada una. Descargarla no cambia nada en OIUEEI. "
                "`organisations` es la página que tienes en cada grupo que dinamizas."
            ),
            "not_included": [
                "Credenciales. El enlace público de tus colecciones, los tokens de los "
                "enlaces mágicos y tus cookies de sesión se quedan fuera a propósito: quien "
                "tuviera este fichero podría entrar en tus grupos.",
                "Datos de otras personas. Los correos solo están aquí para los grupos que "
                "posees, los mismos que ya ves al gestionar las invitaciones. Nada de los "
                "grupos en los que solo eres invitado, ni el año de nacimiento ni el código "
                "postal de nadie más que tú.",
                "Las cosas de otras personas que viven en tus colecciones: aquí solo su "
                "código, su título y el nombre público de su dueño. Si gestionas el grupo y "
                "quieres la ficha completa de todo lo que hay dentro, descarga la copia de la "
                "colección.",
                "Las denuncias sobre tus cosas. Son anónimas por diseño: ni la app ni este "
                "fichero te dicen quién denunció. Las que has hecho tú sí están.",
                "Las fotos y los PDF viajan como enlaces, no como archivos. Ojo: si borras la "
                "cuenta esos enlaces dejan de funcionar; descarga tus imágenes antes.",
                "Los correos. No guardamos copia de los que te enviamos, y los mensajes del "
                "formulario de contacto se reenvían sin almacenarse.",
                "Los registros técnicos del servidor (accesos, direcciones IP) no forman "
                "parte de este fichero; la política de privacidad cuenta cómo se tratan y "
                "durante cuánto tiempo.",
                "Lo que ya has borrado. En OIUEEI borrar es definitivo: no hay papelera.",
            ],
        },
        "collection": {
            "about": (
                "Esta es una copia operativa de un grupo que gestionas: la colección, sus "
                "miembros, todo lo que hay dentro y el historial de préstamos, sea de quien "
                "sea. No es lo mismo que la copia de tus datos personales: esa vive en tu "
                "perfil."
            ),
            "your_responsibility": (
                "Este fichero lleva datos de otras personas: sus correos y, en un grupo "
                "comunitario, su generación y su código postal. En cuanto está en tu "
                "ordenador eres tú quien responde de él. Guárdalo en un sitio seguro y no lo "
                "reenvíes."
            ),
            "not_included": [
                "Credenciales: el enlace público del grupo y los tokens de las invitaciones "
                "pendientes.",
                "Las denuncias. Son anónimas en las dos direcciones.",
                "Las notificaciones y la actividad de tus miembros: son suyas, no del grupo.",
                "La generación y el código postal, salvo que este sea un grupo comunitario: "
                "en los demás modos no los ve nadie más que cada miembro.",
                "En un grupo comunitario, las solicitudes y las preguntas ocultas de gente de "
                "fuera del grupo: son sobre la cosa de un miembro, y solo las ve quien la "
                "gestiona.",
                "Las fotos y los PDF viajan como enlaces, no como archivos.",
            ],
        },
    },
    "ca": {
        "account": {
            "about": (
                "Aquesta és una còpia de les teves dades a OIUEEI, feta en el moment en què "
                "la vas demanar. Cada clau de sota és una part del teu compte, i "
                "`_manifest.counts` diu quantes files té cadascuna. Descarregar-la no canvia "
                "res a OIUEEI. `organisations` és la pàgina que tens a cada grup que dinamitzes."
            ),
            "not_included": [
                "Credencials. L'enllaç públic de les teves col·leccions, els tokens dels "
                "enllaços màgics i les teves galetes de sessió es queden fora expressament: "
                "qui tingués aquest fitxer podria entrar als teus grups.",
                "Dades d'altres persones. Els correus només hi són per als grups que tens, "
                "els mateixos que ja veus quan gestiones les invitacions. Res dels grups on "
                "només ets convidat, ni l'any de naixement ni el codi postal de ningú més "
                "que tu.",
                "Les coses d'altres persones que viuen a les teves col·leccions: aquí només "
                "el seu codi, el seu títol i el nom públic del seu propietari. Si gestiones "
                "el grup i vols la fitxa completa de tot el que hi ha dins, descarrega la "
                "còpia de la col·lecció.",
                "Les denúncies sobre les teves coses. Són anònimes per disseny: ni l'app ni "
                "aquest fitxer et diuen qui va denunciar. Les que has fet tu sí que hi són.",
                "Les fotos i els PDF viatgen com a enllaços, no com a fitxers. Compte: si "
                "esborres el compte aquests enllaços deixen de funcionar; descarrega't les "
                "imatges abans.",
                "Els correus. No guardem còpia dels que t'enviem, i els missatges del "
                "formulari de contacte es reenvien sense desar-se.",
                "Els registres tècnics del servidor (accessos, adreces IP) no formen part "
                "d'aquest fitxer; la política de privacitat explica com es tracten i durant "
                "quant de temps.",
                "El que ja has esborrat. A OIUEEI esborrar és definitiu: no hi ha paperera.",
            ],
        },
        "collection": {
            "about": (
                "Aquesta és una còpia operativa d'un grup que gestiones: la col·lecció, els "
                "seus membres, tot el que hi ha dins i l'historial de préstecs, sigui de qui "
                "sigui. No és el mateix que la còpia de les teves dades personals: aquella "
                "viu al teu perfil."
            ),
            "your_responsibility": (
                "Aquest fitxer porta dades d'altres persones: els seus correus i, en un grup "
                "comunitari, la seva generació i el seu codi postal. Així que és al teu "
                "ordinador ets tu qui en respon. Desa'l en un lloc segur i no el reenviïs."
            ),
            "not_included": [
                "Credencials: l'enllaç públic del grup i els tokens de les invitacions pendents.",
                "Les denúncies. Són anònimes en totes dues direccions.",
                "Les notificacions i l'activitat dels teus membres: són seves, no del grup.",
                "La generació i el codi postal, tret que aquest sigui un grup comunitari: en "
                "els altres modes no els veu ningú més que cada membre.",
                "En un grup comunitari, les sol·licituds i les preguntes amagades de gent de "
                "fora del grup: són sobre la cosa d'un membre, i només les veu qui la gestiona.",
                "Les fotos i els PDF viatgen com a enllaços, no com a fitxers.",
            ],
        },
    },
}


def _readme(lang, kind):
    """The ``_readme`` block for ``kind`` in the reader's language.

    Falls back to English for a deployment whose ``EMAIL_LANGUAGE`` is a
    language this catalogue doesn't speak yet — the same forgiving rule the
    email texts use, and better than an export that raises.
    """
    return README_TEXTS.get(lang, README_TEXTS["en"])[kind]


# --------------------------------------------------------------------------- #
# Value helpers
# --------------------------------------------------------------------------- #


def _iso(value):
    """ISO-8601 for a date or datetime, ``None`` for a null column."""
    return value.isoformat() if value is not None else None


def _money(value):
    """A price as a decimal string — never a float, which would round it."""
    return str(value) if value is not None else None


def _person(user):
    """Somebody else's public identity, or ``None`` when the account is gone.

    Code and name only: everywhere in an export where a third party appears,
    this is the whole of what appears. A ``None`` is a real state, not an error
    — the SET_NULL rows of ``account_service`` land here.
    """
    if user is None:
        return None
    return {"code": user.code, "name": user.name}


def _counts(data, grouped=()):
    """One entry per key that holds rows, so ``_manifest`` indexes the file.

    Nested one level for the keys named in ``grouped``, which hold two lists
    each. Keys holding a single object — ``profile``, ``collection``, ``stats``
    — have nothing to count and are not listed.
    """
    counts = {}
    for key, value in data.items():
        if isinstance(value, list):
            counts[key] = len(value)
        elif key in grouped:
            counts[key] = {inner: len(rows) for inner, rows in value.items()}
    return counts


# --------------------------------------------------------------------------- #
# Shared row shapes
# --------------------------------------------------------------------------- #


def _collection_columns(collection):
    """A collection's own columns, owner text raw — minus ``share_token``.

    The internal bookkeeping (both ``*_alarm_sent`` flags and
    ``capacity_unblocked``) stays out too: that is this deployment's moderation
    ledger, not anything the owner wrote or would recognise.
    """
    return {
        "code": collection.code,
        "created": _iso(collection.created),
        "headline": collection.headline,
        "description": collection.description,
        "status": collection.status,
        "mode": collection.mode,
        "visibility": collection.visibility,
        "language": collection.language,
        "digest_frequency": collection.digest_frequency,
        "allow_member_proposals": collection.allow_member_proposals,
        "is_onboarding": collection.is_onboarding,
        "rental_durations": collection.rental_durations,
        "rental_weekdays": collection.rental_weekdays,
        "allowed_thing_types": collection.allowed_thing_types,
        "tags": collection.tags,
        "pause_message": collection.pause_message,
        "thumbnail_url": asset_url(collection.thumbnail),
        "welcome_doc_url": doc_asset_url(collection.welcome_doc),
    }


def _thing_columns(thing):
    """A thing's full record, owner text raw. Its ``deal`` M2M stays out: those
    are third parties, and the bookings already say who asked for what."""
    return {
        "code": thing.code,
        "type": thing.type,
        "created": _iso(thing.created),
        "headline": thing.headline,
        "description": thing.description,
        "tags": thing.tags,
        "status": thing.status,
        "fee": _money(thing.fee),
        "availability": thing.availability,
        "location": thing.location,
        "condition": thing.condition,
        "is_endless": thing.is_endless,
        "thumbnail_url": asset_url(thing.thumbnail),
        "gallery_urls": [asset_url(image_id) for image_id in thing.gallery],
    }


def _booking_columns(booking):
    """A reservation, minus ``requester_email``: the counterpart's name and code
    say who it was, and their email is theirs."""
    return {
        "code": booking.code,
        "created": _iso(booking.created),
        "status": booking.status,
        "thing_type": booking.thing_type,
        "start_date": _iso(booking.start_date),
        "end_date": _iso(booking.end_date),
        "thing": {"code": booking.thing_code_id, "headline": booking.thing_code.headline},
    }


def _faq_columns(faq):
    return {
        "code": faq.code,
        "created": _iso(faq.created),
        "question": faq.question,
        "answer": faq.answer,
        "is_visible": faq.is_visible,
        "thing": {"code": faq.thing_id, "headline": faq.thing.headline},
    }


def _transfer_columns(transfer):
    return {
        "code": transfer.code,
        "thing": {"code": transfer.thing_id, "headline": transfer.thing.headline},
        "lent_date": _iso(transfer.lent_date),
        "returned_date": _iso(transfer.returned_date),
        "auto_closed": transfer.auto_closed,
        "booking_code": transfer.booking_id,
    }


def _pending_invitations_by_collection(collection_codes):
    """Pending ``COLLECTION_INVITE`` RSVPs grouped by collection — no token.

    The token is the invitation: whoever holds it becomes that member. It is the
    single most dangerous field in the schema to put in a file people email
    around, so it is read here and dropped by never being selected.
    """
    grouped = defaultdict(list)
    rows = RSVP.objects.filter(
        action=RSVP.Action.COLLECTION_INVITE, target_code__in=collection_codes
    ).order_by("created")
    for rsvp in rows:
        grouped[rsvp.target_code].append({"email": rsvp.user_email, "created": _iso(rsvp.created)})
    return grouped


def _proposals_by_collection(collection_codes):
    """Member suggestions grouped by collection, as their owner sees them."""
    grouped = defaultdict(list)
    rows = (
        InvitationProposal.objects.filter(collection__in=collection_codes)
        .select_related("proposer")
        .order_by("created")
    )
    for proposal in rows:
        grouped[proposal.collection_id].append(
            {
                "code": proposal.code,
                "email": proposal.email,
                "note": proposal.note,
                "status": proposal.status,
                "created": _iso(proposal.created),
                "resolved": _iso(proposal.resolved),
                "proposer": _person(proposal.proposer),
            }
        )
    return grouped


# --------------------------------------------------------------------------- #
# Account export
# --------------------------------------------------------------------------- #


def _profile(user):
    """Everything on the ``User`` row except the two things that aren't theirs:
    the password hash and the staff flags."""
    return {
        "code": user.code,
        "email": user.email,
        "name": user.name,
        "created": _iso(user.created),
        "last_activity": _iso(user.last_activity),
        "headline": user.headline,
        "about": user.about,
        "photo_url": asset_url(user.photo),
        "notify_activity": user.notify_activity,
        "notify_news": user.notify_news,
        "age_range": user.age_range,
        "postal_code": user.postal_code,
        "language": user.language,
    }


def _collections_owned(user):
    """The exporter's own groups, with the membership they already manage.

    Member emails are here — and only here — because this is the list the guests
    page already shows their owner. Other members' things appear as a code, a
    title and a public name; their full record belongs to the collection export,
    which is a separate, deliberate download.
    """
    collections = list(
        user.owned_collections.prefetch_related(
            "invites",
            Prefetch("things", queryset=Thing.objects.select_related("owner")),
        ).order_by("created")
    )
    codes = [collection.code for collection in collections]
    invitations = _pending_invitations_by_collection(codes)
    proposals = _proposals_by_collection(codes)
    return [
        {
            **_collection_columns(collection),
            "members": [
                {"code": member.code, "name": member.name, "email": member.email}
                for member in collection.invites.all()
            ],
            "things": [
                {
                    "code": thing.code,
                    "headline": thing.headline,
                    "owner_code": thing.owner_id,
                    "owner_name": thing.owner.name,
                    "is_mine": thing.owner_id == user.code,
                }
                for thing in collection.things.all()
            ],
            "pending_invitations": invitations.get(collection.code, []),
            "proposals_received": proposals.get(collection.code, []),
        }
        for collection in collections
    ]


def _collections_member_of(user):
    """Groups somebody was let into — the group's shape, never its roster.

    A member sees a headline, an owner and how many people are in there; that is
    exactly what comes out. No emails, no member list, and the pending
    invitations carry no token, so this half of the file is worthless to
    anyone who steals it.
    """
    muted = Collection.objects.filter(pk=OuterRef("pk"), digest_muted=user)
    # Counted in a subquery, not with ``Count("invites")``: the queryset is
    # already filtered through the same M2M, Django reuses that join for the
    # annotation, and every group would report exactly one member — the reader.
    member_count = (
        Collection.objects.filter(pk=OuterRef("pk")).annotate(n=Count("invites")).values("n")[:1]
    )
    joined = (
        user.invited_to_collections.select_related("owner")
        .annotate(_member_count=Subquery(member_count), _muted=Exists(muted))
        .order_by("created")
    )
    rows = [
        {
            "code": collection.code,
            "headline": collection.headline,
            "description": collection.description,
            "mode": collection.mode,
            "visibility": collection.visibility,
            "owner": _person(collection.owner),
            "member_count": collection._member_count,
            "digest_muted": collection._muted,
        }
        for collection in joined
    ]
    invites = list(user.rsvps.filter(action=RSVP.Action.COLLECTION_INVITE).order_by("created"))
    headlines = dict(
        Collection.objects.filter(code__in=[rsvp.target_code for rsvp in invites]).values_list(
            "code", "headline"
        )
    )
    return {
        "joined": rows,
        "pending_invitations": [
            {
                "collection_code": rsvp.target_code,
                "headline": headlines.get(rsvp.target_code),
                "created": _iso(rsvp.created),
            }
            for rsvp in invites
        ],
    }


def _things(user):
    """Everything they own, wherever it currently sits."""
    things = user.owned_things.prefetch_related("collections").order_by("created")
    return [
        {
            **_thing_columns(thing),
            "collection_codes": [collection.code for collection in thing.collections.all()],
        }
        for thing in things
    ]


def _bookings(user):
    """Both sides of every reservation they were part of."""
    requested = user.booking_requests.select_related("thing_code", "owner_code").order_by("created")
    received = user.booking_owned.select_related("thing_code", "requester_code").order_by("created")
    return {
        "requested_by_me": [
            {**_booking_columns(booking), "owner": _person(booking.owner_code)}
            for booking in requested
        ],
        "received_by_me": [
            {
                **_booking_columns(booking),
                "owner": _person(booking.owner_code),
                "requester": _person(booking.requester_code),
            }
            for booking in received
        ],
    }


def _faqs(user):
    """Questions they asked, and questions asked of them.

    A ``questioner`` of ``None`` is somebody who has since deleted their
    account: the answer survived them, the attribution did not.
    """
    asked = user.asked_faqs.select_related("thing").order_by("created")
    on_my_things = (
        FAQ.objects.filter(thing__owner=user)
        .select_related("thing", "questioner")
        .order_by("created")
    )
    return {
        "asked_by_me": [_faq_columns(faq) for faq in asked],
        "on_my_things": [
            {**_faq_columns(faq), "questioner": _person(faq.questioner)} for faq in on_my_things
        ],
    }


def _proposals_made(user):
    """People they suggested for a group: the email and the note are theirs — they
    wrote both."""
    proposals = user.invitation_proposals.select_related("collection").order_by("created")
    return [
        {
            "code": proposal.code,
            "collection": {
                "code": proposal.collection_id,
                "headline": proposal.collection.headline,
            },
            "email": proposal.email,
            "note": proposal.note,
            "status": proposal.status,
            "created": _iso(proposal.created),
            "resolved": _iso(proposal.resolved),
        }
        for proposal in proposals
    ]


def _transfers(user):
    """Every handover they were an end of, in either direction.

    ``counterpart`` is ``null`` when the other party deleted their account — the
    handoff happened, the name went (``ThingTransfer.from_user``/``to_user`` are
    SET_NULL). Exporting the hop without it is the honest record.
    """
    out = user.transfers_out.select_related("thing", "to_user").order_by("lent_date")
    incoming = user.transfers_in.select_related("thing", "from_user").order_by("lent_date")
    rows = [
        {**_transfer_columns(t), "direction": "out", "counterpart": _person(t.to_user)} for t in out
    ]
    rows += [
        {**_transfer_columns(t), "direction": "in", "counterpart": _person(t.from_user)}
        for t in incoming
    ]
    return sorted(rows, key=lambda row: row["lent_date"])


def _notifications(user):
    """Their inbox, payloads included: those carry the same public names the
    bandeja already renders."""
    return [
        {
            "code": notification.code,
            "type": notification.type,
            "created": _iso(notification.created),
            "payload": notification.payload,
        }
        for notification in user.inbox_notifications.order_by("created")
    ]


def _organisations(user):
    """The page they have in each group they run: name, logo, about and contact, and in a
    network the pickup point and the conditions of their own loans. Public with the
    group, except ``email_note`` (theirs and the founder's), which is theirs to keep here.
    The logo travels as a link, like every image."""
    rows = []
    for point in user.network_points.select_related("collection").order_by("collection__created"):
        row = {
            "collection": point.collection_id,
            "collection_headline": point.collection.headline,
            "entity_name": point.entity_name,
            "logo": asset_url(point.logo) if point.logo else None,
            "about": point.about,
            "contact": point.contact,
        }
        if point.collection.is_network():
            row.update(
                address=point.address,
                hours_note=point.hours_note,
                weekdays=point.weekdays,
                closed_dates=point.closed_dates,
                deposit_policy=point.deposit_policy,
                request_info=point.request_info,
                email_note=point.email_note,
            )
        rows.append(row)
    return rows


def _reports_filed(user):
    """Reports they filed. Reports about *their* things are absent on purpose:
    reporting is anonymous in both the app and this file."""
    return [
        {
            "code": report.code,
            "created": _iso(report.created),
            "thing_code": report.thing_id,
            "thing_headline": report.thing_headline,
        }
        for report in user.reports_made.order_by("created")
    ]


def _activity(user):
    """Their own rows of the two observed-behaviour logs.

    ``Event`` is never exposed to a read endpoint (DESIGN §9) — that rule
    protects it as an aggregate product surface, and arts. 15/20 still cover one
    person's rows. The exception is exactly this, scoped to
    ``actor_code == user.code``; no other actor's events are readable here.
    """
    events = Event.objects.filter(actor_code=user.code).order_by("created")
    return {
        "days": [
            _iso(day) for day in user.daily_activity.order_by("date").values_list("date", flat=True)
        ],
        "events": [
            {
                "kind": event.kind,
                "created": _iso(event.created),
                "collection_code": event.collection_code,
                "thing_code": event.thing_code,
                "thing_type": event.thing_type,
                "source": event.source,
            }
            for event in events
        ],
    }


def build_account_export(user):
    """The whole of one person's data, as a JSON-serialisable tree."""
    data = {
        "profile": _profile(user),
        "collections_owned": _collections_owned(user),
        "collections_member_of": _collections_member_of(user),
        "organisations": _organisations(user),
        "things": _things(user),
        "bookings": _bookings(user),
        "faqs": _faqs(user),
        "proposals_made": _proposals_made(user),
        "transfers": _transfers(user),
        "notifications": _notifications(user),
        "reports_filed": _reports_filed(user),
        "activity": _activity(user),
    }
    return {
        "_manifest": {
            "format": ACCOUNT_FORMAT,
            "generated_at": _iso(timezone.now()),
            "user_code": user.code,
            "counts": _counts(data, grouped=_GROUPED_ACCOUNT_KEYS),
        },
        "_readme": _readme(resolve_email_language(user=user), "account"),
        **data,
    }


# --------------------------------------------------------------------------- #
# Collection export
# --------------------------------------------------------------------------- #


def _spreadsheet_safe(text):
    """``text`` with an apostrophe in front when a spreadsheet would read it as a formula."""
    return f"'{text}" if text.lstrip()[:1] in ("=", "+", "-", "@") else text


def collection_stats_rows(collection, user=None):
    """``[(metric, value)]`` — the owner-only usage figures for a collection.

    In a network, a ``user`` who is not the founder gets the figures of their own
    things (the six rows about things, bookings and handovers), headed by a
    ``Pickup point`` row saying whose they are; the members, the invitations and the
    breakdown stay the network's. Without ``user``, or for the founder, or outside a
    network, the figures are the collection's.

    The single definition of every metric, rendered two ways: ``CollectionStatsView``
    writes it as a CSV, the collection export carries it as a dict. Aggregate
    only — the per-member demographics behind the breakdown stay on the guests
    page, and stay COMMUNITY-only there.

    Public rather than private despite living beside the ``_helpers``: a view in
    another module imports it, and a leading underscore would say the opposite.
    """
    win = STATS_WINDOW_DAYS
    since = timezone.now() - timedelta(days=win)
    since_date = since.date()
    members = list(collection.invites.all())
    member_codes = [member.code for member in members]

    things = collection.things
    bookings = BookingPeriod.objects.filter(thing_code__collections=collection)
    transfers = ThingTransfer.objects.filter(thing__collections=collection)
    rows = []
    if collection.is_network() and user is not None and not collection.is_owner(user.code):
        things = things.filter(owner=user)
        bookings = bookings.filter(thing_code__owner=user)
        transfers = transfers.filter(thing__owner=user)
        point = collection.point_for(user.code)
        rows.append(["Pickup point", _spreadsheet_safe(point.display_name if point else user.name)])

    rows.append(["Members", len(members)])
    rows.append(
        [
            "Pending invitations",
            RSVP.objects.filter(
                action=RSVP.Action.COLLECTION_INVITE, target_code=collection.code
            ).count(),
        ]
    )
    rows.append(["Things total", things.count()])
    rows.append(["Things active", things.filter(status=Thing.Status.ACTIVE).count()])
    rows.append(["Things reserved", things.filter(status=Thing.Status.TAKEN).count()])
    rows.append([f"Things added ({win}d)", things.filter(created__gte=since).count()])
    rows.append([f"Bookings ({win}d)", bookings.filter(created__gte=since).distinct().count()])
    rows.append(
        [f"Handovers ({win}d)", transfers.filter(lent_date__gte=since_date).distinct().count()]
    )
    rows.append(
        [
            f"Invitations sent ({win}d)",
            RSVP.objects.filter(
                action=RSVP.Action.COLLECTION_INVITE,
                target_code=collection.code,
                created__gte=since,
            ).count(),
        ]
    )
    active = set(
        Thing.objects.filter(
            collections=collection, created__gte=since, owner_id__in=member_codes
        ).values_list("owner_id", flat=True)
    ) | set(
        BookingPeriod.objects.filter(
            thing_code__collections=collection,
            created__gte=since,
            requester_code_id__in=member_codes,
        ).values_list("requester_code_id", flat=True)
    )
    rows.append([f"Active members ({win}d)", len(active)])

    # A bracket or a postal code shared by fewer than STATS_MIN_GROUP members is
    # not named: in a group of two, "Postal 48001: 1" is one person's postal code.
    # The rows it would have had are summed into one "smaller groups" row, and a
    # bracket nobody is in is left out as well — were only the small ones missing,
    # the absent row would name them.
    age_counts = Counter(member.age_range for member in members if member.age_range)
    for age_code, label in AGE_LABELS.items():
        if age_counts.get(age_code, 0) >= STATS_MIN_GROUP:
            rows.append([label, age_counts[age_code]])
    rows.append(
        [
            f"Birth year shared by fewer than {STATS_MIN_GROUP}",
            sum(count for count in age_counts.values() if count < STATS_MIN_GROUP),
        ]
    )
    rows.append(["Birth year not specified", sum(1 for member in members if not member.age_range)])

    postal_counts = Counter(member.postal_code for member in members if member.postal_code)
    named = [(p, c) for p, c in postal_counts.most_common(10) if c >= STATS_MIN_GROUP]
    for postal, count in named:
        # The code follows the literal "Postal " label, so the cell never
        # starts with =, +, - or @ — no spreadsheet-formula injection.
        rows.append([f"Postal {postal}", count])
    # Everyone who gave a code that is not named above: the small groups, and any
    # code past the ten most common.
    rows.append(["Postal, other codes", sum(postal_counts.values()) - sum(c for _, c in named)])
    rows.append(["Postal not specified", sum(1 for member in members if not member.postal_code)])
    return rows


def _collection_members(collection):
    """The roster its owner already manages, demographics gated by mode.

    The row shape is ``Collection.owner_member_rows`` — the same one
    ``CollectionSerializer.get_invites`` serves the guests page, so
    ``age_range``/``postal_code`` ride along only in a COMMUNITY group and a
    PROPRIETARY export cannot be the back door to what the API withholds. It
    used to be a second copy of that loop, which is a privacy invariant kept true
    by vigilance rather than by construction.

    The ordering is this file's own: an export is read by a person scanning a
    file, not by a UI that sorts for them.
    """
    return collection.owner_member_rows(collection.invites.all().order_by("name", "code"))


def _group_people(collection):
    """Who counts as *inside* this group, or ``None`` when everything does.

    ``None`` for PROPRIETARY: its curators run every thing in it, so the app
    already shows them each request and each hidden question. In any other mode
    the curator manages nothing but the group itself (``Thing.can_manage``), and
    a thing can sit in a second group whose members are none of this one's
    business — a booking records *who asked*, not *through which group*, so the
    only honest line to draw is the person: the owner and the invited members.
    """
    if collection.mode == Collection.Mode.PROPRIETARY:
        return None
    return {collection.owner_id, *collection.invites.values_list("code", flat=True)}


def _collection_bookings(thing_codes, people=None):
    bookings = BookingPeriod.objects.filter(thing_code__in=thing_codes)
    if people is not None:
        bookings = bookings.filter(requester_code_id__in=people)
    bookings = bookings.select_related("thing_code", "owner_code", "requester_code").order_by(
        "created"
    )
    return [
        {
            **_booking_columns(booking),
            "owner": _person(booking.owner_code),
            "requester": _person(booking.requester_code),
        }
        for booking in bookings
    ]


def _collection_faqs(thing_codes, people=None):
    faqs = FAQ.objects.filter(thing__in=thing_codes)
    if people is not None:
        # A visible question shows its author to anyone who sees the thing; a
        # hidden one is only its questioner's and its managers'. A deleted
        # account (``questioner`` NULL) is nobody in this group.
        faqs = faqs.filter(Q(is_visible=True) | Q(questioner_id__in=people))
    faqs = faqs.select_related("thing", "questioner").order_by("created")
    return [{**_faq_columns(faq), "questioner": _person(faq.questioner)} for faq in faqs]


def _collection_transfers(thing_codes):
    transfers = (
        ThingTransfer.objects.filter(thing__in=thing_codes)
        .select_related("thing", "from_user", "to_user")
        .order_by("lent_date")
    )
    return [
        {
            **_transfer_columns(transfer),
            "from": _person(transfer.from_user),
            "to": _person(transfer.to_user),
        }
        for transfer in transfers
    ]


def build_collection_export(collection, user=None):
    """A whole group, as a curator runs it. **Curator-only** (owner or
    co-curator) — the caller is what enforces that
    (``require_collection_curator``); this function trusts it.

    In a network, ``user`` narrows the copy of a co-curator to the things they run
    (and what hangs from them): the founder gets the whole group."""
    things = collection.things.select_related("owner").order_by("created")
    if collection.is_network() and (user is None or not collection.is_owner(user.code)):
        things = things.filter(owner=user) if user is not None else things.none()
    things = list(things)
    thing_codes = [thing.code for thing in things]
    people = _group_people(collection)
    data = {
        "collection": {
            **_collection_columns(collection),
            # The group's own palette: part of what the group is, so part of its copy.
            # (The account export leaves it out: the palette is no longer a person's.)
            "theeeme": {"code": collection.theeeme.code, "name": collection.theeeme.name},
            "koro": collection.koro,
            "owner": _person(collection.owner),
        },
        "members": _collection_members(collection),
        "pending_invitations": _pending_invitations_by_collection([collection.code]).get(
            collection.code, []
        ),
        "proposals": _proposals_by_collection([collection.code]).get(collection.code, []),
        "things": [
            {
                **_thing_columns(thing),
                "owner": _person(thing.owner),
                "is_mine": thing.owner_id == collection.owner_id,
            }
            for thing in things
        ],
        "bookings": _collection_bookings(thing_codes, people),
        "faqs": _collection_faqs(thing_codes, people),
        "transfers": _collection_transfers(thing_codes),
        "stats": dict(collection_stats_rows(collection, user)),
    }
    return {
        "_manifest": {
            "format": COLLECTION_FORMAT,
            "generated_at": _iso(timezone.now()),
            "collection_code": collection.code,
            "counts": _counts(data),
        },
        "_readme": _readme(
            resolve_email_language(user=collection.owner, collection=collection), "collection"
        ),
        **data,
    }


# --------------------------------------------------------------------------- #
# The file
# --------------------------------------------------------------------------- #


def export_bytes(payload):
    """The file itself: indented UTF-8 JSON, accents intact.

    ``default=str`` is the safety net, not the plan: every builder above already
    hands back JSON-native values, so a type reaching it means a new column
    arrived without a decision about how it should read.
    """
    return json.dumps(payload, ensure_ascii=False, indent=2, default=str).encode("utf-8")


def export_filename(code):
    """``oiueei-ABC123-2026-08-21.json`` — the code says which copy this is, the
    date says when it stopped being true."""
    return f"oiueei-{code}-{timezone.localdate().isoformat()}.json"
