"""
Direct service-level tests for booking_service's race guards.

cancel_booking / reject_booking / finalize_booking_decision each re-check the
booking's PENDING status under a row lock and return None (no-op) if a
concurrent transition already handled it. These call the service functions
directly on an already-decided booking to exercise that None-return branch —
previously only ever exercised indirectly through the view/RSVP layer.
"""

import pytest

from core.models.booking import BookingPeriod
from core.services.booking_service import cancel_booking, finalize_booking_decision, reject_booking


@pytest.fixture
def accepted_booking(db, user, user2, thing):
    thing.status = "INACTIVE"
    thing.save(update_fields=["status"])
    return BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        status=BookingPeriod.Status.ACCEPTED,
    )


@pytest.fixture
def rejected_booking(db, user, user2, thing):
    return BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        status=BookingPeriod.Status.REJECTED,
    )


@pytest.mark.django_db
class TestRaceGuardReturnsNone:
    def test_cancel_booking_noops_on_already_accepted(self, accepted_booking, thing):
        assert cancel_booking(accepted_booking) is None

        accepted_booking.refresh_from_db()
        thing.refresh_from_db()
        assert accepted_booking.status == BookingPeriod.Status.ACCEPTED
        assert thing.status == "INACTIVE"

    def test_reject_booking_noops_on_already_rejected(self, rejected_booking, thing):
        assert reject_booking(rejected_booking) is None

        rejected_booking.refresh_from_db()
        thing.refresh_from_db()
        assert rejected_booking.status == BookingPeriod.Status.REJECTED
        assert thing.status == "ACTIVE"

    def test_finalize_booking_decision_noops_on_already_accepted(self, accepted_booking):
        assert finalize_booking_decision(accepted_booking, accepted=True) is None

        accepted_booking.refresh_from_db()
        assert accepted_booking.status == BookingPeriod.Status.ACCEPTED

    def test_finalize_booking_decision_noops_on_already_rejected(self, rejected_booking):
        assert finalize_booking_decision(rejected_booking, accepted=False) is None

        rejected_booking.refresh_from_db()
        assert rejected_booking.status == BookingPeriod.Status.REJECTED
