"""
Booking business logic for OIUEEI.

Extracts accept/reject logic from views into reusable service functions.
"""

from core.models.booking import SINGLE_USE_TYPES


def accept_booking(booking):
    """Accept a booking and update the Thing if it's single-use."""
    booking.accept()
    thing = booking.thing_code
    if booking.thing_type in SINGLE_USE_TYPES:
        thing.status = "INACTIVE"
        thing.available = False
        thing.save(update_fields=["status", "available"])
        thing.deal.add(booking.requester_code)
    return thing


def reject_booking(booking):
    """Reject a booking and restore the Thing if it's single-use."""
    booking.reject()
    thing = booking.thing_code
    if booking.thing_type in SINGLE_USE_TYPES:
        thing.status = "ACTIVE"
        thing.save(update_fields=["status"])
    return thing
