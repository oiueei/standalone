"""
Booking business logic for OIUEEI.

Extracts accept/reject logic from views into reusable service functions.
Uses transaction.atomic to ensure BookingPeriod and Thing updates are consistent.
"""

from datetime import date

from django.db import transaction

from core.models import Thing
from core.models.booking import SINGLE_USE_TYPES
from core.models.transfer import ThingTransfer


def cancel_booking(booking):
    """Cancel a booking by the requester and restore the Thing if single-use.

    Wrapped in transaction.atomic with select_for_update to prevent race
    conditions when updating both BookingPeriod status and Thing status.
    """
    with transaction.atomic():
        booking.cancel()
        thing = Thing.objects.select_for_update().get(code=booking.thing_code_id)
        if booking.thing_type in SINGLE_USE_TYPES:
            thing.status = "ACTIVE"
            thing.save(update_fields=["status"])
    return thing


def accept_booking(booking):
    """Accept a booking and update the Thing if it's single-use.

    Wrapped in transaction.atomic with select_for_update to prevent race
    conditions when updating both BookingPeriod status and Thing status.

    For SHARE_THING: transfers ownership to the requester. The thing stays
    ACTIVE so the new owner can continue sharing it.

    For SWAP_THING: bilateral ownership transfer — requested thing goes to
    requester, all offered things go to the original owner. All things stay
    ACTIVE. ThingTransfer records are created for each transfer.
    """
    with transaction.atomic():
        booking.accept()
        thing = Thing.objects.select_for_update().get(code=booking.thing_code_id)
        if booking.thing_type in SINGLE_USE_TYPES:
            thing.status = "INACTIVE"
            thing.save(update_fields=["status"])
            thing.deal.add(booking.requester_code)
        elif booking.thing_type == "SHARE_THING":
            thing.owner = booking.requester_code
            thing.save(update_fields=["owner"])
        elif booking.thing_type == "SWAP_THING":
            # Requested thing → requester
            thing.owner = booking.requester_code
            thing.save(update_fields=["owner"])
            # Offered things → original owner
            for offered in booking.offered_things.select_for_update():
                ThingTransfer.objects.create(
                    thing=offered,
                    from_user=booking.requester_code,
                    to_user=booking.owner_code,
                    booking=booking,
                    lent_date=date.today(),
                )
                offered.owner = booking.owner_code
                offered.save(update_fields=["owner"])

        # Record the transfer (item changing hands)
        ThingTransfer.objects.create(
            thing=thing,
            from_user=booking.owner_code,
            to_user=booking.requester_code,
            booking=booking,
            lent_date=booking.start_date or date.today(),
        )

    # Send document download links to the requester if thing has documents
    if thing.documents:
        from core.services.email_service import send_documents_email

        send_documents_email(booking.requester_email, thing.headline, thing.documents)

    return thing


def reject_booking(booking):
    """Reject a booking and restore the Thing if it's single-use.

    Wrapped in transaction.atomic with select_for_update to prevent race
    conditions when updating both BookingPeriod status and Thing status.
    """
    with transaction.atomic():
        booking.reject()
        thing = Thing.objects.select_for_update().get(code=booking.thing_code_id)
        if booking.thing_type in SINGLE_USE_TYPES:
            thing.status = "ACTIVE"
            thing.save(update_fields=["status"])
    return thing
