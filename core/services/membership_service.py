"""Ending a membership: the one place a person leaves a group's ``invites``.

A thing lives in one collection and its owner always has access to it. A member who
leaves, or is removed, would otherwise leave things behind that nobody can manage from
inside the group, so the things go with the person: every one they own in that group,
whatever its status, in both modes (their contributions in a COMMUNITY collection, a
co-curator's catalogue entries in a PROPRIETARY one).
"""

from django.db import transaction
from django.utils import timezone

from core.models import BookingPeriod, Thing
from core.models.booking import RETURNABLE_TYPES
from core.services.deletion_events import deleting_as
from core.services.email_service import (
    send_thing_left_with_owner_email,
    send_thing_withdrawn_email,
)


def things_leaving_with(collection, user):
    """The things of ``user`` in ``collection`` that will go with them: all, any status."""
    return Thing.objects.filter(owner=user, collections=collection).order_by("created", "code")


def _people_to_tell(leaving, user):
    """Who must hear that a thing is going: one entry per (requester, thing) with a live
    request or reservation (``BookingPeriod.blocking_filter``), read before the delete
    takes the bookings with it. ``holding`` is true when they have the thing now — an
    accepted loan or rental that has already started. The leaving member's own bookings
    are not announced to them."""
    today = timezone.localdate()
    told = {}
    bookings = BookingPeriod.objects.filter(
        BookingPeriod.blocking_filter(), thing_code__in=leaving
    ).select_related("thing_code")
    for booking in bookings:
        if booking.requester_code_id == user.code:
            continue
        holding = (
            booking.status == BookingPeriod.Status.ACCEPTED
            and booking.thing_type in RETURNABLE_TYPES
            and booking.start_date is not None
            and booking.start_date <= today
        )
        key = (booking.requester_email, booking.thing_code_id)
        _, already = told.get(key, (None, False))
        told[key] = (booking.thing_code.headline, already or holding)
    return [(email, headline, holding) for (email, _), (headline, holding) in told.items()]


def things_out_on_loan(collection, user):
    """Headlines of ``user``'s things in ``collection`` that someone has in hand now: an
    accepted loan or rental that has started and has not reached its end date."""
    leaving = list(things_leaving_with(collection, user))
    return [headline for _, headline, holding in _people_to_tell(leaving, user) if holding]


def loans_in_hand(collection, user):
    """Headlines of the things of ``collection`` that ``user`` has in hand now, whoever
    lent them: an accepted loan or rental they asked for, already started, still running."""
    today = timezone.localdate()
    bookings = BookingPeriod.objects.filter(
        BookingPeriod.blocking_filter(),
        requester_code=user,
        status=BookingPeriod.Status.ACCEPTED,
        thing_type__in=RETURNABLE_TYPES,
        start_date__lte=today,
        thing_code__collections=collection,
    ).select_related("thing_code")
    return sorted({b.thing_code.headline for b in bookings})


def network_exit_block(collection, user, *, removing):
    """Why a dinamizador (or member) of a network cannot be taken out right now, or ``None``.

    Their things go with them, and a thing someone has in hand cannot vanish: so the exit
    waits for the loan to end (there is no "returned" state; the end date is the limit).
    ``removing`` also looks at what they hold themselves, which only matters when the
    person leaves the group; demoting keeps them a member, so only their things count.
    Returns ``(code, headlines)`` or ``None``; always ``None`` outside a network.
    """
    if not collection.is_network():
        return None
    lent_out = things_out_on_loan(collection, user)
    if lent_out:
        return "curator_things_lent_out", lent_out
    if removing:
        held = loans_in_hand(collection, user)
        if held:
            return "member_holds_loans", held
    return None


def demote_curator(collection, user, *, actor):
    """Take ``user`` out of ``co_owners`` in a network and delete the things they ran there.

    A dinamizador who stops being one cannot keep things in the network (nobody else
    may decide them), so demoting counts as leaving for their things. Whoever had a live
    request on one is emailed once the transaction commits, as when a member leaves.
    Returns how many things went.
    """
    with transaction.atomic(), deleting_as(actor):
        leaving = list(things_leaving_with(collection, user))
        to_tell = _people_to_tell(leaving, user)
        for thing in leaving:
            thing.delete()
        collection.co_owners.remove(user)
        # The entity they answered for goes with the role, like their things.
        collection.points.filter(user=user).delete()
        group_headline = collection.headline

        def tell():
            for email, headline, holding in to_tell:
                send_thing_left_with_owner_email(
                    headline, group_headline, email, holding=holding, collection=collection
                )

        transaction.on_commit(tell)
    return len(leaving)


def end_membership(collection, user, *, actor):
    """Take ``user`` out of the group and delete their things there.

    ``actor`` is whoever does it (the member leaving, or the curator removing them):
    each ``THING_REMOVED`` event names them. Whoever had a live request or reservation on
    one of those things is emailed once the transaction commits, and never if it rolls
    back. Returns how many things were deleted.

    The founder is not a member (an FK, never an ``invites`` row): ending theirs would
    delete things nobody else may delete, so it raises before touching anything.
    """
    if collection.is_owner(user.code):
        raise ValueError("The owner can't be removed from their own collection.")
    with transaction.atomic(), deleting_as(actor):
        leaving = list(things_leaving_with(collection, user))
        to_tell = _people_to_tell(leaving, user)
        for thing in leaving:
            thing.delete()
        collection.invites.remove(user)
        # co_owners is a subset of invites by construction (promotion, never a
        # separate door in): losing membership must never leave a stale co-owner
        # row behind. A no-op for anyone who was never promoted.
        collection.co_owners.remove(user)
        collection.points.filter(user=user).delete()

        group_headline = collection.headline

        def tell():
            for email, headline, holding in to_tell:
                send_thing_left_with_owner_email(
                    headline, group_headline, email, holding=holding, collection=collection
                )

        transaction.on_commit(tell)
    return len(leaving)


def people_told_on_delete(thing, actor):
    """Who will be emailed if ``actor`` deletes ``thing``: one entry per person with a live
    request or reservation on it, ``actor`` left out. The page that asks before deleting
    counts these, so the number it shows is the number of emails that go."""
    return _people_to_tell([thing], actor)


def delete_thing(thing, *, actor):
    """Delete ``thing`` and tell whoever had a live request or reservation on it.

    Deleting is allowed whatever hangs from the thing (the bookings go with it); what
    this adds is that nobody is left asking for something that is gone. The live
    requests (``BookingPeriod.blocking_filter``) are read before the delete takes them,
    and each requester gets one email once the transaction commits, never when it rolls
    back — except ``actor``, who knows. Whoever has the thing in hand is told to return
    it, and in a network is given the pickup point of its owner to return it to.
    """
    collection = next(iter(thing.collections_in_order()), None)
    with transaction.atomic(), deleting_as(actor):
        to_tell = people_told_on_delete(thing, actor)
        group_headline = collection.headline if collection else ""
        point = collection.point_for(thing.owner_id) if collection else None
        thing.delete()

        def tell():
            for email, headline, holding in to_tell:
                send_thing_withdrawn_email(
                    headline,
                    group_headline,
                    email,
                    holding=holding,
                    collection=collection,
                    point=point if holding else None,
                )

        # A thing lives in one collection and always has: with none there is no group to
        # name in the email, and nobody to have asked for it through one.
        if collection is not None:
            transaction.on_commit(tell)
