"""Sealing contact details at rest: `core.services.contact_seal`.

What matters is what the column never holds (the details as readable text), that a token
nobody can open is `None` and not a 500, and that the key follows `SECRET_KEY`.
"""

import base64
import json

import pytest
from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF
from django.conf import settings
from django.db import connection

from core.models import BookingPeriod, Thing, User
from core.services.contact_seal import (
    LENDING_INFO,
    _fernet,
    is_sealed_phone,
    seal,
    seal_phone,
    unseal,
    unseal_phone,
)

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
        token = _fernet(LENDING_INFO).encrypt(json.dumps(["not", "a", "mapping"]).encode()).decode()

        assert unseal(token) is None

    def test_a_valid_token_that_is_not_json(self):
        assert unseal(_fernet(LENDING_INFO).encrypt(b"plain words").decode()) is None

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


class TestThePhone:
    """A reservation's phone: the same sealing, with a key of its own."""

    def test_what_is_sealed_comes_back(self):
        assert unseal_phone(seal_phone("+34 600 123 456")) == "+34 600 123 456"

    def test_the_token_does_not_show_the_number(self):
        token = seal_phone("600123456")

        assert "600123456" not in token
        assert is_sealed_phone(token)

    def test_nothing_to_seal_is_empty(self):
        assert seal_phone("") == ""
        assert seal_phone("   ") == ""
        assert seal_phone(None) == ""

    def test_the_spaces_around_it_do_not_stay(self):
        assert unseal_phone(seal_phone("  600123456  ")) == "600123456"

    @pytest.mark.parametrize("empty", ["", None])
    def test_an_empty_value_is_empty(self, empty):
        assert unseal_phone(empty) == ""

    def test_a_token_of_another_key_is_empty(self):
        foreign = Fernet(Fernet.generate_key()).encrypt(b"600123456").decode()

        assert unseal_phone(foreign) == ""

    def test_a_tampered_token_is_empty(self):
        token = seal_phone("600123456")
        flipped = token[:-6] + ("A" if token[-6] != "A" else "B") + token[-5:]

        assert unseal_phone(flipped) == ""

    def test_a_loan_token_does_not_open_as_a_phone_and_the_phone_not_as_a_loan(self):
        # Two keys, two `info`s: a token of one is no token of the other.
        assert unseal_phone(seal(DETAILS)) == ""
        assert unseal(seal_phone("600123456")) is None

    def test_other_text_that_is_no_phone_is_empty(self):
        assert unseal_phone("not a phone at all") == ""
        assert unseal_phone("12345") == ""  # fewer than six digits
        assert unseal_phone("6" * 33) == ""  # longer than a phone

    def test_a_phone_left_in_plain_text_by_the_release_before_is_read_as_it_is(self):
        assert unseal_phone("+34 600 123 456") == "+34 600 123 456"
        assert unseal_phone("(93) 123-45.67") == "(93) 123-45.67"

    def test_a_plain_phone_is_not_a_sealed_one(self):
        assert not is_sealed_phone("600123456")
        assert not is_sealed_phone("")

    def test_rotating_the_secret_key_leaves_it_empty(self, settings):
        token = seal_phone("600123456")
        settings.SECRET_KEY = "another-secret-key-not-the-first-0123456789"

        assert unseal_phone(token) == ""


class TestLoanDetailsSealedBeforeStillOpen:
    """The loan's key is unchanged by the module's new shape, or what is stored would
    be unreadable."""

    def test_a_token_made_with_the_info_of_before_opens(self):
        key = HKDF(
            algorithm=hashes.SHA256(), length=32, salt=None, info=b"oiueei-lending-contact"
        ).derive(settings.SECRET_KEY.encode())
        token = Fernet(base64.urlsafe_b64encode(key)).encrypt(
            json.dumps(DETAILS, ensure_ascii=False, sort_keys=True).encode()
        )

        assert unseal(token.decode()) == DETAILS
