"""Sealing a borrower's contact details: `core.services.lending_contact`.

What matters is what the column never holds (the details as readable text), that a token
nobody can open is `None` and not a 500, and that the key follows `SECRET_KEY`.
"""

import json

import pytest
from cryptography.fernet import Fernet
from django.db import connection

from core.models import BookingPeriod, Thing, User
from core.services.lending_contact import _fernet, seal, unseal

DETAILS = {
    "full_name": "Laura Pérez Gómez",
    "address": "C/ de la Fusteria 12, 3r 2a\n08003 Barcelona",
    "phone": "+34 600 000 000",
    "identity_document": "12345678Z",
}


class TestRoundTrip:
    def test_what_is_sealed_comes_back_whole(self):
        assert unseal(seal(DETAILS)) == DETAILS

    def test_accents_and_line_breaks_survive(self):
        assert unseal(seal(DETAILS))["address"] == "C/ de la Fusteria 12, 3r 2a\n08003 Barcelona"
        assert unseal(seal(DETAILS))["full_name"] == "Laura Pérez Gómez"

    def test_the_token_is_text_for_a_text_column_and_shows_nothing(self):
        token = seal(DETAILS)

        assert isinstance(token, str)
        for secret in ("12345678Z", "Laura", "Fusteria", "600"):
            assert secret not in token

    def test_two_seals_of_the_same_details_differ(self):
        assert seal(DETAILS) != seal(DETAILS)


class TestWhatCannotBeOpenedIsNone:
    @pytest.mark.parametrize("token", [None, "", "not a token", "gAAAAA", "x" * 200])
    def test_an_empty_or_garbage_token(self, token):
        assert unseal(token) is None

    def test_a_tampered_token(self):
        token = seal(DETAILS)
        flipped = token[:-4] + ("AAAA" if token[-4:] != "AAAA" else "BBBB")

        assert unseal(flipped) is None

    def test_a_token_sealed_under_another_secret_key(self, settings):
        original = settings.SECRET_KEY
        settings.SECRET_KEY = "another-secret-key-0123456789-0123456789"
        token = seal(DETAILS)
        settings.SECRET_KEY = original

        assert unseal(token) is None

    def test_a_valid_token_of_this_key_that_holds_no_mapping(self):
        token = _fernet().encrypt(json.dumps(["not", "a", "mapping"]).encode()).decode()

        assert unseal(token) is None

    def test_a_valid_token_that_is_not_json(self):
        assert unseal(_fernet().encrypt(b"plain words").decode()) is None

    def test_a_token_made_with_a_key_that_is_not_derived_from_the_secret(self):
        assert unseal(Fernet(Fernet.generate_key()).encrypt(b"{}").decode()) is None


class TestTheKeyIsDerivedFromTheSecretKey:
    def test_the_same_secret_opens_it_in_a_new_process(self, settings):
        token = seal(DETAILS)

        # A fresh Fernet from the same settings: nothing is kept in memory.
        assert unseal(token) == DETAILS
        settings.SECRET_KEY = settings.SECRET_KEY + "-rotated"
        assert unseal(token) is None


@pytest.mark.django_db
class TestTheColumnNeverHoldsThemInTheClear:
    def test_the_raw_row_has_neither_the_document_nor_the_name(self):
        owner = User.objects.create(code="LCOWN1", email="lala7@your-domain.test", name="Lala")
        borrower = User.objects.create(code="LCBOR1", email="lele9@your-domain.test", name="Lele")
        thing = Thing.objects.create(
            code="LCTHN1", owner=owner, headline="Drill", type="LEND_THING"
        )
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="LEND_THING",
            requester_code=borrower,
            requester_email=borrower.email,
            owner_code=owner,
            lending_contact=seal(DETAILS),
        )

        with connection.cursor() as cursor:
            cursor.execute("SELECT * FROM booking_periods WHERE code = %s", [booking.code])
            raw = " ".join(str(value) for value in cursor.fetchone())

        for secret in ("12345678Z", "Laura", "Pérez", "Fusteria", "600 000 000"):
            assert secret not in raw
        assert unseal(BookingPeriod.objects.get(pk=booking.pk).lending_contact) == DETAILS
