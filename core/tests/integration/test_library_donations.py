"""A library may accept donated things: a switch and the instructions its page shows.

Two fields, so that switching donations off for a season keeps what was written. Only a
library has them; on with no words in any language is refused, because the button would
lead to a blank page.
"""

import json

import pytest
from rest_framework import status
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import Collection
from core.tests.factories import CollectionFactory, UserFactory

pytestmark = pytest.mark.django_db

URL = "/api/v1/collections/{}/"
INFO = "## What we take\n\n- Books"


def _as(api_client, who):
    api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(who).access_token}")
    return api_client


@pytest.fixture
def library(db):
    owner = UserFactory(code="DNOW01", email="lala@your-domain.test", name="Lala")
    coll = CollectionFactory(
        owner=owner,
        kind=Collection.Kind.LIBRARY,
        allowed_thing_types=["LEND_THING", "RENT_THING"],
        visibility=Collection.Visibility.PUBLIC,
    )
    return coll


def _patch(api_client, who, coll, body):
    return _as(api_client, who).patch(URL.format(coll.code), body, format="json")


class TestALibraryTurnsDonationsOn:
    def test_it_is_off_by_default_and_served_so(self, api_client, library):
        res = api_client.get(URL.format(library.code))

        assert res.status_code == status.HTTP_200_OK
        assert res.data["accepts_donations"] is False
        assert res.data["donations_info"] == ""

    def test_the_owner_turns_it_on_with_text_and_anyone_reads_it_without_a_session(
        self, api_client, library
    ):
        res = _patch(
            api_client, library.owner, library, {"accepts_donations": True, "donations_info": INFO}
        )
        assert res.status_code == status.HTTP_200_OK, res.data

        api_client.credentials()
        read = api_client.get(URL.format(library.code))
        assert read.data["accepts_donations"] is True
        assert read.data["donations_info"] == INFO

    def test_on_with_no_text_is_a_coded_refusal_on_the_text_field(self, api_client, library):
        res = _patch(api_client, library.owner, library, {"accepts_donations": True})

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["code"] == "donations_info_required"
        assert "donations_info" in res.data
        library.refresh_from_db()
        assert library.accepts_donations is False

    def test_a_map_of_blank_texts_counts_as_empty(self, api_client, library):
        res = _patch(
            api_client,
            library.owner,
            library,
            {"accepts_donations": True, "donations_info": json.dumps({"es": "", "ca": ""})},
        )

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["code"] == "donations_info_required"

    def test_a_map_with_words_in_one_language_is_enough(self, api_client, library):
        res = _patch(
            api_client,
            library.owner,
            library,
            {"accepts_donations": True, "donations_info": json.dumps({"es": "Libros", "ca": ""})},
        )

        assert res.status_code == status.HTTP_200_OK, res.data

    def test_clearing_the_text_while_on_is_refused_too(self, api_client, library):
        library.accepts_donations = True
        library.donations_info = INFO
        library.save()

        res = _patch(api_client, library.owner, library, {"donations_info": ""})

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert res.data["code"] == "donations_info_required"

    def test_turning_it_off_keeps_the_text(self, api_client, library):
        library.accepts_donations = True
        library.donations_info = INFO
        library.save()

        res = _patch(api_client, library.owner, library, {"accepts_donations": False})

        assert res.status_code == status.HTTP_200_OK, res.data
        library.refresh_from_db()
        assert library.accepts_donations is False
        assert library.donations_info == INFO

    def test_text_can_be_written_while_off(self, api_client, library):
        res = _patch(api_client, library.owner, library, {"donations_info": INFO})

        assert res.status_code == status.HTTP_200_OK, res.data
        library.refresh_from_db()
        assert library.donations_info == INFO
        assert library.accepts_donations is False

    def test_a_patch_that_names_neither_field_is_not_judged(self, api_client, library):
        library.accepts_donations = True
        library.donations_info = ""
        library.save()  # old data: on with no text

        res = _patch(api_client, library.owner, library, {"headline": "Renamed"})

        assert res.status_code == status.HTTP_200_OK, res.data


class TestOnlyALibraryHasDonations:
    @pytest.mark.parametrize(
        ("kind", "types"),
        [
            (Collection.Kind.STALL, ["GIFT_THING", "SELL_THING"]),
            (Collection.Kind.SHED, ["RESERVE_THING"]),
        ],
    )
    def test_the_switch_and_the_text_are_each_a_400_elsewhere(self, api_client, kind, types):
        owner = UserFactory(code="DNOW02", email="lele@your-domain.test", name="Lele")
        coll = CollectionFactory(owner=owner, kind=kind, allowed_thing_types=types)

        on = _patch(api_client, owner, coll, {"accepts_donations": True, "donations_info": INFO})
        text = _patch(api_client, owner, coll, {"donations_info": INFO})

        assert on.status_code == status.HTTP_400_BAD_REQUEST
        assert "accepts_donations" in on.data
        assert text.status_code == status.HTTP_400_BAD_REQUEST
        assert "donations_info" in text.data
        coll.refresh_from_db()
        assert coll.accepts_donations is False
        assert coll.donations_info == ""

    def test_naming_them_switched_off_and_empty_is_harmless_elsewhere(self, api_client):
        owner = UserFactory(code="DNOW03", email="lili@your-domain.test", name="Lili")
        coll = CollectionFactory(owner=owner, kind=Collection.Kind.STALL)

        res = _patch(api_client, owner, coll, {"accepts_donations": False, "donations_info": ""})

        assert res.status_code == status.HTTP_200_OK, res.data

    def test_creation_does_not_take_them(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "Books",
                "kind": "LIBRARY",
                "accepts_donations": True,
                "donations_info": INFO,
            },
            format="json",
        )

        assert res.status_code == status.HTTP_201_CREATED, res.data
        created = Collection.objects.get(code=res.data["code"])
        assert created.accepts_donations is False
        assert created.donations_info == ""


class TestWhoMayEdit:
    def test_a_plain_member_may_not(self, api_client, library):
        member = UserFactory(code="DNME01", email="lolo@your-domain.test", name="Lolo")
        library.invites.add(member)

        res = _patch(
            api_client, member, library, {"accepts_donations": True, "donations_info": INFO}
        )

        assert res.status_code == status.HTTP_403_FORBIDDEN
        library.refresh_from_db()
        assert library.accepts_donations is False

    def test_in_a_network_a_dinamizador_may_not_and_the_founder_may(self, api_client):
        founder = UserFactory(code="DNFO01", email="lulu@your-domain.test", name="Lulu")
        dinamizador = UserFactory(code="DNDI01", email="lala2@your-domain.test", name="Lala 2")
        network = CollectionFactory(
            owner=founder,
            kind=Collection.Kind.LIBRARY,
            mode=Collection.Mode.NETWORK,
            allowed_thing_types=["LEND_THING"],
        )
        network.invites.add(dinamizador)
        network.co_owners.add(dinamizador)
        body = {"accepts_donations": True, "donations_info": INFO}

        refused = _patch(api_client, dinamizador, network, body)
        accepted = _patch(api_client, founder, network, body)

        assert refused.status_code == status.HTTP_403_FORBIDDEN
        assert accepted.status_code == status.HTTP_200_OK, accepted.data


class TestTheTextLimitIsPerLanguage:
    def test_2001_characters_in_one_language_is_a_400(self, api_client, library):
        text = json.dumps({"es": "a" * 2001, "ca": "b"})

        res = _patch(api_client, library.owner, library, {"donations_info": text})

        assert res.status_code == status.HTTP_400_BAD_REQUEST
        assert "donations_info" in res.data

    def test_2001_characters_of_plain_text_is_a_400(self, api_client, library):
        res = _patch(api_client, library.owner, library, {"donations_info": "a" * 2001})

        assert res.status_code == status.HTTP_400_BAD_REQUEST

    def test_2000_in_each_of_the_three_languages_is_accepted(self, api_client, library):
        text = json.dumps({"es": "a" * 2000, "ca": "b" * 2000, "en": "c" * 2000})

        res = _patch(
            api_client,
            library.owner,
            library,
            {"accepts_donations": True, "donations_info": text},
        )

        assert res.status_code == status.HTTP_200_OK, res.data
        library.refresh_from_db()
        assert library.donations_info == text
