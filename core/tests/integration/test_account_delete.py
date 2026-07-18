"""Integration tests for account deletion (right to erasure).

The flow is deliberately two-step: an authenticated POST to
/auth/delete-account/ only emails a single-use ACCOUNT_DELETE RSVP link;
the deletion itself commits on an explicit POST to the verify endpoint —
GET only previews, so a mail scanner can never erase an account.

The erasure map (see core/services/account_service.py): the user, their
collections, things, bookings, notifications and RSVPs cascade away; their
FAQ questions on other people's things and their hops in other people's
things' journeys survive with the user FK nulled (SET_NULL) — content stays,
attribution goes.
"""

import pytest
from django.core import mail
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import FAQ, RSVP, Collection, Thing, User
from core.models.booking import BookingPeriod
from core.models.notification import InAppNotification
from core.models.transfer import ThingTransfer

DELETE_REQUEST_URL = "/api/v1/auth/delete-account/"


def verify_url(rsvp):
    return f"/api/v1/auth/verify/{rsvp.token}/"


@pytest.fixture
def deletable_world(db, user, user2, collection, thing):
    """user owns `collection`+`thing`; user2 keeps a thing user interacted with."""
    other_collection = Collection.objects.create(
        code="OTHC01", owner=user2, headline="Survivor's collection", mode="COMMUNITY"
    )
    other_thing = Thing.objects.create(
        code="OTHT01", type="LEND_THING", owner=user2, headline="Survivor's drill"
    )
    other_collection.things.add(other_thing)
    other_collection.invites.add(user)
    # user asked a question on user2's thing (should survive, anonymised).
    faq = FAQ.objects.create(
        code="DELFA1", thing=other_thing, questioner=user, question="Does it work?"
    )
    # user borrowed and returned user2's thing (hop should survive, anonymised).
    transfer = ThingTransfer.objects.create(
        code="DELTR1",
        thing=other_thing,
        from_user=user2,
        to_user=user,
        lent_date="2026-06-01",
        returned_date="2026-06-08",
    )
    # user has a pending request on user2's thing (should cascade away).
    booking = BookingPeriod.objects.create(
        code="DELBK1",
        thing_code=other_thing,
        thing_type="LEND_THING",
        requester_code=user,
        requester_email=user.email,
        owner_code=user2,
        start_date="2026-08-01",
        end_date="2026-08-08",
    )
    InAppNotification.objects.create(code="DELNO1", user=user, type="FAQ_ANSWERED", payload={})
    return {
        "other_thing": other_thing,
        "faq": faq,
        "transfer": transfer,
        "booking": booking,
    }


@pytest.mark.django_db
class TestAccountDeleteRequest:
    def test_requires_authentication(self, api_client):
        assert api_client.post(DELETE_REQUEST_URL).status_code == 401

    def test_creates_rsvp_and_emails_confirmation_link(self, authenticated_client, user):
        response = authenticated_client.post(DELETE_REQUEST_URL)
        assert response.status_code == 200
        rsvp = RSVP.objects.get(user_code=user, action=RSVP.Action.ACCOUNT_DELETE)
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]
        assert rsvp.token in mail.outbox[0].body
        # Nothing was deleted by the request step.
        assert User.objects.filter(code=user.code).exists()

    def test_resend_replaces_the_previous_link(self, authenticated_client, user):
        authenticated_client.post(DELETE_REQUEST_URL)
        first = RSVP.objects.get(user_code=user, action=RSVP.Action.ACCOUNT_DELETE)
        authenticated_client.post(DELETE_REQUEST_URL)
        live = RSVP.objects.filter(user_code=user, action=RSVP.Action.ACCOUNT_DELETE)
        assert live.count() == 1
        assert live.first().token != first.token


@pytest.mark.django_db
class TestAccountDeleteConfirmation:
    def _request_rsvp(self, user):
        return RSVP.objects.create(
            user_code=user, user_email=user.email, action=RSVP.Action.ACCOUNT_DELETE
        )

    def test_get_previews_and_deletes_nothing(self, api_client, user, collection, thing):
        rsvp = self._request_rsvp(user)
        response = api_client.get(verify_url(rsvp))
        assert response.status_code == 200
        assert response.data["requires_confirmation"] is True
        assert response.data["action"] == "ACCOUNT_DELETE"
        assert response.data["collections"] == 1
        assert response.data["things"] == 1
        # A scanner's GET (even repeated) erases nothing and keeps the link alive.
        api_client.get(verify_url(rsvp))
        assert User.objects.filter(code=user.code).exists()
        assert RSVP.objects.filter(code=rsvp.code).exists()

    def test_post_deletes_the_account_and_everything_owned(
        self, api_client, user, user2, collection, thing, deletable_world
    ):
        rsvp = self._request_rsvp(user)
        response = api_client.post(verify_url(rsvp))
        assert response.status_code == 200
        assert response.data["action"] == "ACCOUNT_DELETE"

        # The account and everything it owned are gone.
        assert not User.objects.filter(code=user.code).exists()
        assert not Collection.objects.filter(code=collection.code).exists()
        assert not Thing.objects.filter(code=thing.code).exists()
        # So are their pending bookings, notifications and the RSVP itself.
        assert not BookingPeriod.objects.filter(code="DELBK1").exists()
        assert not InAppNotification.objects.filter(code="DELNO1").exists()
        assert not RSVP.objects.filter(code=rsvp.code).exists()
        # The other member's world is untouched.
        assert User.objects.filter(code=user2.code).exists()
        assert Thing.objects.filter(code="OTHT01").exists()

    def test_content_on_others_things_survives_anonymised(self, api_client, user, deletable_world):
        rsvp = self._request_rsvp(user)
        api_client.post(verify_url(rsvp))

        faq = FAQ.objects.get(code="DELFA1")
        assert faq.questioner is None
        assert faq.question == "Does it work?"
        transfer = ThingTransfer.objects.get(code="DELTR1")
        assert transfer.to_user is None
        assert transfer.from_user is not None  # the surviving member keeps their name

    def test_anonymised_rows_serialise_without_a_name(
        self, api_client, user, user2, deletable_world
    ):
        rsvp = self._request_rsvp(user)
        api_client.post(verify_url(rsvp))

        client = APIClient()
        refresh = RefreshToken.for_user(user2)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        faqs = client.get("/api/v1/things/OTHT01/faq/")
        assert faqs.status_code == 200
        row = faqs.data["results"][0]
        assert row["questioner"] is None
        assert row["questioner_name"] == ""
        transfers = client.get("/api/v1/things/OTHT01/transfers/")
        assert transfers.status_code == 200
        assert transfers.data["transfers"][0]["to_user_name"] == ""
        assert transfers.data["unique_homes"] == 2  # user2 + one former member

    def test_the_link_is_single_use(self, api_client, user):
        rsvp = self._request_rsvp(user)
        assert api_client.post(verify_url(rsvp)).status_code == 200
        # The RSVP cascaded away with the user: a replay finds nothing.
        assert api_client.post(verify_url(rsvp)).status_code == 401
