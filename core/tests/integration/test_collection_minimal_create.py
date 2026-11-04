"""A collection created with the short form's body is the one the long form used to make.

The create form sends only ``kind``, ``headline``, ``description``, ``mode``, ``visibility``,
``allowed_thing_types`` and ``language``. Everything it used to send besides (the palette, the
wave, the tags, the summary frequency, the recommend switch, the rules of a loan or a
reservation) is left to the model, and the model's defaults must be the values the form
used to start from.
"""

import pytest
from rest_framework import status

from core.models import Collection, Theeeme

URL = "/api/v1/collections/"
GIFT, SELL, LEND, RENT, RESERVE = (
    "GIFT_THING",
    "SELL_THING",
    "LEND_THING",
    "RENT_THING",
    "RESERVE_THING",
)


def _body(kind, verbs, **extra):
    return {
        "kind": kind,
        "headline": "Short form",
        "description": "Made with the short form",
        "mode": "PROPRIETARY",
        "visibility": "PRIVATE",
        "allowed_thing_types": verbs,
        "language": "ca",
        **extra,
    }


def _post(client, body):
    res = client.post(URL, body, format="json")
    assert res.status_code == status.HTTP_201_CREATED, res.data
    return Collection.objects.get(code=res.data["code"])


@pytest.mark.django_db
class TestMinimalCreateBody:
    def test_the_values_the_long_form_used_to_send_come_from_the_model(self, authenticated_client):
        c = _post(authenticated_client, _body("STALL", [GIFT, SELL]))

        assert c.digest_frequency == "MONTHLY"
        assert c.koro == "basic"
        assert c.allow_member_proposals is False
        assert c.tags == []
        assert c.thumbnail == ""
        assert c.home_page == ""
        assert c.welcome_doc == ""
        assert c.email_note == ""
        assert c.language == "ca"  # the one value the form still sends
        assert c.visibility == "PRIVATE"
        assert c.status == "ACTIVE"

    def test_a_palette_is_drawn_when_none_is_sent(self, authenticated_client):
        c = _post(authenticated_client, _body("STALL", [GIFT, SELL]))

        assert Theeeme.objects.filter(code=c.theeeme_id).exists()

    def test_a_library_has_no_rules_until_the_owner_writes_them(self, authenticated_client):
        c = _post(authenticated_client, _body("LIBRARY", [LEND, RENT]))

        assert c.rental_durations == []
        assert c.rental_weekdays == []
        assert c.closed_dates == []
        assert c.request_info == ""
        assert c.deposit_policy == ""

    def test_a_shed_is_born_by_day_with_the_usual_limits(self, authenticated_client):
        c = _post(authenticated_client, _body("SHED", [RESERVE]))

        assert c.mode == "PROPRIETARY"
        assert c.reservation_unit == "DAY"
        assert c.reservation_horizon_days == 90
        assert c.reservation_max_active_per_member == 10
        assert c.reservation_max_days == 1
        assert c.reservation_asks_phone is False
        assert c.reservation_min_minutes == 60
        assert c.reservation_max_minutes == 180
        assert c.opening_hours == {}
        assert c.rental_weekdays == []

    def test_a_community_stall_without_prices_keeps_only_the_free_verb(self, authenticated_client):
        body = _body("STALL", [GIFT], mode="COMMUNITY")
        c = _post(authenticated_client, body)

        assert c.mode == "COMMUNITY"
        assert c.allowed_thing_types == [GIFT]

    def test_a_network_library_is_created_from_the_short_body(self, authenticated_client):
        c = _post(authenticated_client, _body("LIBRARY", [LEND, RENT], mode="NETWORK"))

        assert c.mode == "NETWORK"
        assert c.kind == "LIBRARY"
