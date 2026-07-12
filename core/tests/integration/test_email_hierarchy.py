"""
Email language hierarchy (O5): deployment default → collection → recipient.

The deployment speaks one language by default (``EMAIL_LANGUAGE``); a collection
owner can set their group's; a member can set their own, which always wins.
"""

import pytest
from django.core import mail

from core.models import Language, Thing, User
from core.models.booking import BookingPeriod
from core.services.email_service import (
    resolve_email_language,
    send_booking_confirmation_email,
    send_broadcast_email,
    send_collection_invite_email,
    send_faq_question_email,
)


@pytest.fixture(autouse=True)
def english_deployment(settings):
    """Pin the deployment default so each test shows which level actually spoke."""
    settings.EMAIL_LANGUAGE = "en"


class _Obj:
    def __init__(self, language=""):
        self.language = language


class TestResolveEmailLanguage:
    """The full matrix: each level only speaks when the stronger ones are blank."""

    def test_nothing_set_falls_back_to_the_deployment(self):
        assert resolve_email_language() == "en"
        assert resolve_email_language(user=_Obj(), collection=_Obj()) == "en"

    def test_collection_overrides_the_deployment(self):
        assert resolve_email_language(collection=_Obj("ca")) == "ca"
        assert resolve_email_language(user=_Obj(), collection=_Obj("ca")) == "ca"

    def test_user_overrides_the_collection(self):
        assert resolve_email_language(user=_Obj("es"), collection=_Obj("ca")) == "es"

    def test_user_overrides_the_deployment_with_no_collection(self):
        assert resolve_email_language(user=_Obj("ca")) == "ca"

    def test_a_missing_user_is_not_a_preference(self):
        # A not-yet-registered invitee has no User row at all.
        assert resolve_email_language(user=None, collection=_Obj("ca")) == "ca"


@pytest.mark.django_db
class TestSendersSpeakTheRightLanguage:
    def test_an_invite_speaks_the_collections_language(self, user, collection):
        collection.language = Language.ES
        collection.save()

        send_collection_invite_email(
            "Lala", collection.headline, "invitee@test.com", "a", "r", collection=collection
        )

        assert "Tienes una invitación" in mail.outbox[0].subject

    def test_a_members_own_preference_beats_the_collections(self, user2, collection):
        collection.language = Language.ES
        collection.save()
        user2.language = Language.CA
        user2.save()

        send_collection_invite_email(
            "Lala", collection.headline, user2.email, "a", "r", collection=collection
        )

        assert "Tens una invitació" in mail.outbox[0].subject

    def test_a_thing_email_follows_only_the_recipient(self, user, user2, collection, thing):
        # Thing-scoped 1:1 emails pass no collection — there's no group to speak for.
        collection.language = Language.CA
        collection.save()
        user.language = Language.ES
        user.save()

        send_faq_question_email("Lele", thing, "¿Funciona?", user.email)

        # Spanish (the owner's own preference), not Catalan (the group's).
        assert mail.outbox[0].subject == "Hay una pregunta por responder"

    def test_a_bilingual_group_gets_one_broadcast_per_language(self, user, collection):
        collection.language = Language.ES
        collection.save()
        catalan = User.objects.create(email="ca@test.com", language=Language.CA)
        spanish = User.objects.create(email="es@test.com")  # inherits the collection's
        collection.invites.add(catalan, spanish)

        send_broadcast_email(
            "Lala",
            user.email,
            collection.headline,
            collection.code,
            "Hola",
            [catalan.email, spanish.email],
            collection=collection,
        )

        by_recipient = {m.to[0]: m for m in mail.outbox}
        assert "Ei!" in by_recipient["ca@test.com"].subject
        assert "¡Hey!" in by_recipient["es@test.com"].subject


@pytest.mark.django_db
class TestLanguagePreferences:
    def test_pop_in_stores_the_language_of_a_new_user(self, api_client):
        api_client.post(
            "/api/v1/auth/pop-in/",
            {"email": "nou@test.com", "language": "ca"},
            format="json",
        )

        assert User.objects.get(email="nou@test.com").language == "ca"
        # The very first magic link already speaks it.
        assert "benvinguda" in mail.outbox[0].subject

    def test_pop_in_never_overwrites_an_existing_users_preference(self, api_client, user):
        user.language = Language.ES
        user.save()

        api_client.post(
            "/api/v1/auth/pop-in/",
            {"email": user.email, "language": "ca"},
            format="json",
        )

        user.refresh_from_db()
        assert user.language == Language.ES

    def test_an_unknown_language_is_ignored(self, api_client):
        api_client.post(
            "/api/v1/auth/pop-in/",
            {"email": "raro@test.com", "language": "klingon"},
            format="json",
        )

        assert User.objects.get(email="raro@test.com").language == ""

    def test_a_user_can_save_their_language(self, authenticated_client, user):
        # The profile endpoint is PUT-only (partial=True server-side).
        res = authenticated_client.put(
            f"/api/v1/users/{user.code}/", {"language": "ca"}, format="json"
        )

        assert res.status_code == 200
        user.refresh_from_db()
        assert user.language == "ca"

    def test_an_owner_can_save_the_collections_language(self, authenticated_client, collection):
        res = authenticated_client.patch(
            f"/api/v1/collections/{collection.code}/", {"language": "ca"}, format="json"
        )

        assert res.status_code == 200
        collection.refresh_from_db()
        assert collection.language == "ca"

    def test_an_invalid_language_is_rejected(self, authenticated_client, collection):
        res = authenticated_client.patch(
            f"/api/v1/collections/{collection.code}/", {"language": "klingon"}, format="json"
        )

        assert res.status_code == 400


@pytest.mark.django_db
def test_a_booking_email_follows_the_saved_profile_language(user, user2, collection):
    """The whole point, end to end: change your language, your next email changes."""
    thing = Thing.objects.create(
        code="LANG01", type=Thing.Type.GIFT_THING, owner=user, headline="Silla"
    )
    collection.things.add(thing)
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=Thing.Type.GIFT_THING,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
    )

    send_booking_confirmation_email(user2, thing, booking)
    english_subject = mail.outbox[-1].subject

    user2.language = Language.ES
    user2.save()
    send_booking_confirmation_email(user2, thing, booking)

    assert mail.outbox[-1].subject != english_subject
    assert "solicitud" in mail.outbox[-1].subject.lower()
