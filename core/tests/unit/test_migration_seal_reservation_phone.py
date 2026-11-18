"""0180 — the contact phone of a reservation is sealed in place.

The two data functions of the migration are run against the live models: what is
readable gets sealed, what is already a token is left alone (a second run changes
nothing) and the reverse opens the tokens again, so a rollback does not leave tokens in a
column the previous release shows as they are.
"""

import importlib
from datetime import timedelta

import pytest
from django.apps import apps
from django.utils import timezone

from core.models import BookingPeriod, Thing, User
from core.services.contact_seal import is_sealed_phone, seal_phone, unseal_phone

migration = importlib.import_module("core.migrations.0180_seal_reservation_phone")

pytestmark = pytest.mark.django_db


def _row(code, phone):
    owner, _ = User.objects.get_or_create(code="MIGOWN", defaults={"email": "o@your-domain.test"})
    guest, _ = User.objects.get_or_create(code="MIGGST", defaults={"email": "g@your-domain.test"})
    thing, _ = Thing.objects.get_or_create(
        code="MIGTHG",
        defaults={"type": Thing.Type.RESERVE_THING, "owner": owner, "headline": "Lathe"},
    )
    today = timezone.localdate()
    return BookingPeriod.objects.create(
        code=code,
        thing_code=thing,
        thing_type=Thing.Type.RESERVE_THING,
        requester_code=guest,
        requester_email=guest.email,
        owner_code=owner,
        start_date=today,
        end_date=today + timedelta(days=1),
        contact_phone=phone,
        status=BookingPeriod.Status.ACCEPTED,
    )


def _stored(code):
    return BookingPeriod.objects.get(code=code).contact_phone


def test_what_is_readable_gets_sealed_and_an_empty_one_stays_empty():
    _row("MIGP01", "600123456")
    _row("MIGP02", "")

    migration.seal_phones(apps, None)

    assert is_sealed_phone(_stored("MIGP01"))
    assert "600123456" not in _stored("MIGP01")
    assert unseal_phone(_stored("MIGP01")) == "600123456"
    assert _stored("MIGP02") == ""


def test_a_second_run_seals_nothing_twice():
    _row("MIGP03", "600123456")
    migration.seal_phones(apps, None)
    token = _stored("MIGP03")

    migration.seal_phones(apps, None)

    assert _stored("MIGP03") == token
    assert unseal_phone(token) == "600123456"


def test_a_row_already_sealed_by_the_new_release_is_left_alone():
    _row("MIGP04", seal_phone("600123456"))
    token = _stored("MIGP04")

    migration.seal_phones(apps, None)

    assert _stored("MIGP04") == token


def test_the_reverse_opens_the_tokens_back_to_plain_text():
    _row("MIGP05", seal_phone("+34 600 123 456"))
    _row("MIGP06", "")

    migration.unseal_phones(apps, None)

    assert _stored("MIGP05") == "+34 600 123 456"
    assert _stored("MIGP06") == ""


def test_the_reverse_empties_a_token_it_cannot_open_rather_than_leave_it_in_32_characters():
    _row("MIGP07", "g" * 120)

    migration.unseal_phones(apps, None)

    assert _stored("MIGP07") == ""


def test_the_reverse_leaves_a_plain_phone_as_it_is():
    _row("MIGP08", "600123456")

    migration.unseal_phones(apps, None)

    assert _stored("MIGP08") == "600123456"
