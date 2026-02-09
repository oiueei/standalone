"""
Integration tests for OIUEEI API views.
"""

import pytest
from rest_framework import status


@pytest.mark.django_db
class TestAuthViews:
    """Tests for authentication views."""

    def test_request_link_non_existent_user_denied(self, api_client):
        """Should deny magic link for non-existent user (invite-only)."""
        response = api_client.post(
            "/api/v1/auth/request-link/",
            {"email": "lala@oiueei.org"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "No account found" in response.data["error"]

    def test_request_link_existing_user(self, api_client, user):
        """Should send magic link for existing user."""
        response = api_client.post(
            "/api/v1/auth/request-link/",
            {"email": user.email},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == user.email

    def test_request_link_invalid_email(self, api_client):
        """Should reject invalid email."""
        response = api_client.post(
            "/api/v1/auth/request-link/",
            {"email": "not-an-email"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_link_valid(self, api_client, rsvp, user):
        """Should verify valid RSVP and return token."""
        response = api_client.get(f"/api/v1/auth/verify/{rsvp.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["code"] == user.code

    def test_verify_link_invalid(self, api_client):
        """Should reject invalid RSVP code."""
        response = api_client.get("/api/v1/auth/verify/INVALID/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_me_authenticated(self, authenticated_client, user):
        """Should return current user."""
        response = authenticated_client.get("/api/v1/auth/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["code"] == user.code

    def test_me_unauthenticated(self, api_client):
        """Should reject unauthenticated request."""
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_authenticated(self, authenticated_client):
        """Should logout authenticated user."""
        response = authenticated_client.post("/api/v1/auth/logout/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Successfully logged out"

    def test_logout_unauthenticated(self, api_client):
        """Should reject logout for unauthenticated user."""
        response = api_client.post("/api/v1/auth/logout/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_with_refresh_token(self, authenticated_client, user):
        """Should logout and attempt to blacklist refresh token."""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        response = authenticated_client.post(
            "/api/v1/auth/logout/",
            {"refresh": str(refresh)},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Successfully logged out"


@pytest.mark.django_db
class TestUserViews:
    """Tests for user views."""

    def test_get_own_profile(self, authenticated_client, user):
        """Should return full profile for own user."""
        response = authenticated_client.get(f"/api/v1/users/{user.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert "email" in response.data

    def test_get_other_profile_denied_for_unrelated_user(self, authenticated_client, user2):
        """Should deny access to profile for unrelated user."""
        response = authenticated_client.get(f"/api/v1/users/{user2.code}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_get_other_profile_allowed_when_connected(
        self, authenticated_client, user, user2, collection
    ):
        """Should return public profile for connected user (invited to same collection)."""
        # Invite user2 to user's collection
        collection.add_invite(user2.code)

        response = authenticated_client.get(f"/api/v1/users/{user2.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert "email" not in response.data

    def test_update_own_profile(self, authenticated_client, user):
        """Should update own profile."""
        response = authenticated_client.put(
            f"/api/v1/users/{user.code}/",
            {"name": "Lala"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["name"] == "Lala"

    def test_update_other_profile(self, authenticated_client, user2):
        """Should reject updating other user's profile."""
        response = authenticated_client.put(
            f"/api/v1/users/{user2.code}/",
            {"name": "Hacked"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN


@pytest.mark.django_db
class TestCollectionViews:
    """Tests for collection views."""

    def test_list_collections(self, authenticated_client, collection):
        """Should list user's collections."""
        response = authenticated_client.get("/api/v1/collections/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["code"] == collection.code

    def test_create_collection(self, authenticated_client, user):
        """Should create a new collection."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "New Collection"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["headline"] == "New Collection"

    def test_create_collection_uses_default_theeeme(self, authenticated_client):
        """Should use default theeeme (BAR_CEL_ONA) when not specified."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "New Collection"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["theeeme"] == "JMPA01"

    def test_create_collection_without_headline_fails(self, authenticated_client):
        """Should fail to create collection without headline."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"description": "No headline"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "headline" in response.data

    def test_create_collection_with_invalid_theeeme_fails(self, authenticated_client):
        """Should fail to create collection with non-existent theeeme."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "New Collection",
                "theeeme": "NOEXST",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "theeeme" in response.data

    def test_get_collection(self, authenticated_client, collection):
        """Should get collection details."""
        response = authenticated_client.get(f"/api/v1/collections/{collection.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["headline"] == collection.headline

    def test_update_collection(self, authenticated_client, collection):
        """Should update collection."""
        response = authenticated_client.put(
            f"/api/v1/collections/{collection.code}/",
            {"headline": "Updated Collection"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["headline"] == "Updated Collection"

    def test_update_collection_theeeme_denied_for_non_owner(self, user, user2, collection):
        """Should deny theeeme update for non-owner."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = client2.put(
            f"/api/v1/collections/{collection.code}/",
            {"theeeme": "JMPA01"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "Only the owner can update this collection"

    def test_delete_collection(self, authenticated_client, collection):
        """Should delete collection."""
        response = authenticated_client.delete(f"/api/v1/collections/{collection.code}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_invite_to_collection(self, authenticated_client, collection):
        """Should invite user to collection."""
        response = authenticated_client.post(
            f"/api/v1/collections/{collection.code}/invite/",
            {"email": "lele@oiueei.org"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == "lele@oiueei.org"

    def test_invite_to_collection_denied_for_non_owner(self, user, user2, collection):
        """Should deny invite for non-owner of collection."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        # user2 is NOT the owner of collection
        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = client2.post(
            f"/api/v1/collections/{collection.code}/invite/",
            {"email": "someone@oiueei.org"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "Only the owner can invite users"

    def test_invited_collections(self, authenticated_client, user, collection, user2):
        """Should list collections where user is invited."""
        # Add user to collection invites
        collection.add_invite(user.code)

        response = authenticated_client.get("/api/v1/invited-collections/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["code"] == collection.code

    def test_invite_creates_rsvp_with_collection_code(self, authenticated_client, collection):
        """Should create RSVP with collection_code when inviting."""
        from core.models import RSVP

        response = authenticated_client.post(
            f"/api/v1/collections/{collection.code}/invite/",
            {"email": "newuser@oiueei.org"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        # Verify RSVP was created with collection_code
        rsvp = RSVP.objects.filter(user_email="newuser@oiueei.org").first()
        assert rsvp is not None
        assert rsvp.collection_code == collection.code

    def test_invite_does_not_add_user_to_collection_immediately(
        self, authenticated_client, collection
    ):
        """User should NOT be in invites until they accept."""
        from core.models import User

        response = authenticated_client.post(
            f"/api/v1/collections/{collection.code}/invite/",
            {"email": "pending@oiueei.org"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        # User should NOT be in invites yet
        invited_user = User.objects.get(email="pending@oiueei.org")
        collection.refresh_from_db()
        assert not collection.invites.filter(code=invited_user.code).exists()

    def test_verify_invite_link_adds_user_to_collection(self, api_client, collection):
        """Verifying invite RSVP should add user to collection."""
        from core.models import RSVP, User

        # Create a user and RSVP with collection_code and COLLECTION_INVITE action
        invited_user = User.objects.create(
            code="INVTD1",
            email="invited@oiueei.org",
        )
        rsvp = RSVP.objects.create(
            user_code=invited_user,
            user_email=invited_user.email,
            action="COLLECTION_INVITE",
            collection_code=collection.code,
        )

        # Verify the link
        response = api_client.get(f"/api/v1/auth/verify/{rsvp.code}/")
        assert response.status_code == status.HTTP_200_OK

        # User should now be in invites
        collection.refresh_from_db()
        invited_user.refresh_from_db()
        assert collection.invites.filter(code=invited_user.code).exists()
        assert invited_user.invited_to_collections.filter(code=collection.code).exists()

        # Response should include invited_collection and action
        assert response.data["invited_collection"] == collection.code
        assert response.data["action"] == "COLLECTION_INVITE"

    def test_remove_invite_from_collection(self, authenticated_client, user, user2, collection):
        """Should remove a user from collection invites."""
        # First add user2 to collection invites
        collection.add_invite(user2.code)

        response = authenticated_client.delete(
            f"/api/v1/collections/{collection.code}/invite/",
            {"user_code": user2.code},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "User removed from collection"

        # Verify user was removed
        collection.refresh_from_db()
        user2.refresh_from_db()
        assert not collection.invites.filter(code=user2.code).exists()
        assert not user2.invited_to_collections.filter(code=collection.code).exists()

    def test_remove_invite_sends_notification_email(
        self, authenticated_client, user, user2, collection
    ):
        """Removing invite should send notification email to removed user."""
        from django.core import mail

        # First add user2 to collection invites
        collection.add_invite(user2.code)

        response = authenticated_client.delete(
            f"/api/v1/collections/{collection.code}/invite/",
            {"user_code": user2.code},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        # Check email was sent to removed user
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user2.email]
        assert "revocado" in mail.outbox[0].subject
        assert collection.headline in mail.outbox[0].subject

    def test_remove_invite_denied_for_non_owner(self, user, user2, collection):
        """Should deny removing invite for non-owner."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        collection.add_invite(user2.code)

        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = client2.delete(
            f"/api/v1/collections/{collection.code}/invite/",
            {"user_code": user2.code},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "Only the owner can remove invites"

    def test_remove_invite_user_not_invited(self, authenticated_client, user2, collection):
        """Should return error when user is not invited."""
        response = authenticated_client.delete(
            f"/api/v1/collections/{collection.code}/invite/",
            {"user_code": user2.code},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "User is not invited to this collection"

    def test_add_thing_to_collection(self, authenticated_client, user, collection):
        """Should add an existing thing to a collection."""
        from core.models import Thing

        # Create a thing not in any collection
        thing = Thing.objects.create(
            code="THING2",
            owner=user,
            headline="New Thing",
            type="GIFT_THING",
        )

        response = authenticated_client.post(
            f"/api/v1/collections/{collection.code}/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Thing added to collection"
        assert thing.code in response.data["collection"]["things"]

    def test_add_thing_to_collection_denied_for_non_owner(self, user, user2, collection):
        """Should deny adding thing for non-owner of collection."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        from core.models import Thing

        # Create thing owned by user2
        thing = Thing.objects.create(
            code="THING2",
            owner=user2,
            headline="User2 Thing",
            type="GIFT_THING",
        )

        # user2 tries to add to user's collection
        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = client2.post(
            f"/api/v1/collections/{collection.code}/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "Only the owner can add things to this collection"

    def test_add_other_users_thing_to_collection_denied(
        self, authenticated_client, user, user2, collection
    ):
        """Should deny adding another user's thing to collection."""
        from core.models import Thing

        # Create thing owned by user2
        thing = Thing.objects.create(
            code="THING2",
            owner=user2,
            headline="User2 Thing",
            type="GIFT_THING",
        )

        # user (owner of collection) tries to add user2's thing
        response = authenticated_client.post(
            f"/api/v1/collections/{collection.code}/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "You can only add your own things to collections"

    def test_add_thing_already_in_collection(self, authenticated_client, thing, collection):
        """Should return error when thing is already in collection."""
        response = authenticated_client.post(
            f"/api/v1/collections/{collection.code}/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Thing is already in this collection"

    def test_add_nonexistent_thing_to_collection(self, authenticated_client, collection):
        """Should return 404 for nonexistent thing."""
        response = authenticated_client.post(
            f"/api/v1/collections/{collection.code}/",
            {"thing_code": "NOEXST"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["error"] == "Thing not found"

    def test_add_thing_to_nonexistent_collection(self, authenticated_client, user):
        """Should return 404 for nonexistent collection."""
        from core.models import Thing

        thing = Thing.objects.create(
            code="THING2",
            owner=user,
            headline="New Thing",
            type="GIFT_THING",
        )

        response = authenticated_client.post(
            "/api/v1/collections/NOEXST/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert response.data["error"] == "Collection not found"


@pytest.mark.django_db
class TestThingViews:
    """Tests for thing views."""

    def test_list_things(self, authenticated_client, thing):
        """Should list user's things."""
        response = authenticated_client.get("/api/v1/things/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_create_thing(self, authenticated_client):
        """Should create a new thing."""
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "headline": "New Thing",
                "type": "GIFT_THING",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["headline"] == "New Thing"

    def test_get_thing(self, authenticated_client, thing):
        """Should get thing details."""
        response = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["headline"] == thing.headline

    def test_update_thing(self, authenticated_client, thing):
        """Should update thing."""
        response = authenticated_client.put(
            f"/api/v1/things/{thing.code}/",
            {"headline": "Updated Thing"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["headline"] == "Updated Thing"

    def test_delete_thing(self, authenticated_client, thing):
        """Should delete thing."""
        response = authenticated_client.delete(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_request_thing(self, authenticated_client, user, user2, thing, collection):
        """Should request thing via BookingPeriod flow."""
        # Share collection with user2 first
        collection.add_invite(user2.code)

        # Create new client for user2
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Use /request/ endpoint (BookingPeriod flow)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Booking request sent"
        assert "booking_code" in response.data

        # For GIFT_THING, status changes to TAKEN (awaiting owner approval)
        thing.refresh_from_db()
        assert thing.status == "TAKEN"

    def test_cannot_request_own_thing(self, authenticated_client, thing):
        """Should not request own thing."""
        response = authenticated_client.post(f"/api/v1/things/{thing.code}/request/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Cannot request your own thing"


@pytest.mark.django_db
class TestFAQViews:
    """Tests for FAQ views."""

    def test_list_faqs(self, authenticated_client, thing, faq):
        """Should list FAQs for a thing."""
        response = authenticated_client.get(f"/api/v1/things/{thing.code}/faq/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1

    def test_create_faq(self, user, user2, thing, collection):
        """Should create a new FAQ as invited user."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        # Invite user2 to the collection
        collection.add_invite(user2.code)

        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = client2.post(
            f"/api/v1/things/{thing.code}/faq/",
            {"question": "How big is it?"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["question"] == "How big is it?"
        assert response.data["questioner"] == user2.code

    def test_get_faq(self, authenticated_client, faq):
        """Should get FAQ details."""
        response = authenticated_client.get(f"/api/v1/faq/{faq.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["question"] == faq.question

    def test_answer_faq(self, authenticated_client, faq):
        """Should answer FAQ as thing owner."""
        response = authenticated_client.post(
            f"/api/v1/faq/{faq.code}/answer/",
            {"answer": "It's not very big!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["answer"] == "It's not very big!"

    def test_answer_faq_denied_for_non_owner(self, user, user2, faq):
        """Should deny answering FAQ for non-owner of the thing."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        # user2 is the questioner but NOT the thing owner
        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = client2.post(
            f"/api/v1/faq/{faq.code}/answer/",
            {"answer": "I shouldn't be able to answer this!"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "Only the thing owner can answer questions"

    def test_create_faq_denied_for_owner(self, authenticated_client, thing):
        """Owner cannot ask questions about their own thing."""
        response = authenticated_client.post(
            f"/api/v1/things/{thing.code}/faq/",
            {"question": "Can I ask myself?"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Owner cannot ask questions about their own thing"

    def test_hide_faq(self, authenticated_client, faq):
        """Owner can hide a FAQ."""
        response = authenticated_client.post(f"/api/v1/faq/{faq.code}/hide/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "FAQ hidden"
        assert response.data["faq"]["is_visible"] is False

    def test_show_faq(self, authenticated_client, faq):
        """Owner can show a hidden FAQ."""
        # First hide it
        from core.models import FAQ

        faq_obj = FAQ.objects.get(code=faq.code)
        faq_obj.is_visible = False
        faq_obj.save()

        response = authenticated_client.post(f"/api/v1/faq/{faq.code}/show/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "FAQ shown"
        assert response.data["faq"]["is_visible"] is True

    def test_hide_faq_denied_for_non_owner(self, user, user2, faq):
        """Non-owner cannot hide a FAQ."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = client2.post(f"/api/v1/faq/{faq.code}/hide/")
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "Only the thing owner can change FAQ visibility"

    def test_create_faq_sends_email_to_owner(self, user, user2, thing, collection):
        """Creating FAQ should send email to thing owner."""
        from django.core import mail
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        collection.add_invite(user2.code)

        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        response = client2.post(
            f"/api/v1/things/{thing.code}/faq/",
            {"question": "Is this still available?"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED

        # Check email was sent to owner
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user.email]
        assert "Nueva pregunta" in mail.outbox[0].subject

    def test_answer_faq_sends_email_to_questioner(self, authenticated_client, user, user2, faq):
        """Answering FAQ should send email to questioner."""
        from django.core import mail

        response = authenticated_client.post(
            f"/api/v1/faq/{faq.code}/answer/",
            {"answer": "Yes, it is available!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        # Check email was sent to questioner
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user2.email]
        assert "respondida" in mail.outbox[0].subject

    def test_hide_faq_sends_email_to_questioner(self, authenticated_client, user, user2, faq):
        """Hiding FAQ should send email to questioner."""
        from django.core import mail

        response = authenticated_client.post(f"/api/v1/faq/{faq.code}/hide/")
        assert response.status_code == status.HTTP_200_OK

        # Check email was sent to questioner
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user2.email]
        assert "ocultada" in mail.outbox[0].subject


@pytest.mark.django_db
class TestSecurityRestrictions:
    """Tests for security restrictions on resource access."""

    def _get_client_for_user(self, user):
        """Create an authenticated client for a user."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    # Collection access tests

    def test_collection_access_denied_for_non_invited_user(
        self, authenticated_client, user, user2, collection
    ):
        """Should deny access to collection for non-invited user."""
        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/collections/{collection.code}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_collection_access_allowed_for_owner(self, authenticated_client, collection):
        """Should allow owner to view their collection."""
        response = authenticated_client.get(f"/api/v1/collections/{collection.code}/")
        assert response.status_code == status.HTTP_200_OK

    def test_collection_access_allowed_for_invited_user(self, user, user2, collection):
        """Should allow invited user to view collection."""
        # Invite user2
        collection.add_invite(user2.code)

        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/collections/{collection.code}/")
        assert response.status_code == status.HTTP_200_OK

    # Invited collections endpoint tests

    def test_invited_collections_empty_when_no_invites(self, authenticated_client):
        """Should return empty list when user has no invites."""
        response = authenticated_client.get("/api/v1/invited-collections/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_invited_collections_returns_invited(self, user, user2, collection):
        """Should return collections user is invited to."""
        # Invite user2
        collection.add_invite(user2.code)

        client2 = self._get_client_for_user(user2)
        response = client2.get("/api/v1/invited-collections/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["code"] == collection.code

    # Thing access tests

    def test_thing_access_denied_for_non_invited_user(self, user, user2, thing):
        """Should deny access to thing for non-invited user."""
        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_thing_access_allowed_for_owner(self, authenticated_client, thing):
        """Should allow owner to view their thing."""
        response = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_200_OK

    def test_thing_access_allowed_for_invited_user(self, user, user2, thing, collection):
        """Should allow invited user to view thing in collection."""
        # Invite user2 to collection that contains the thing
        collection.add_invite(user2.code)

        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_200_OK

    # Invited things endpoint tests

    def test_invited_things_empty_when_no_invites(self, authenticated_client):
        """Should return empty list when user has no invites."""
        response = authenticated_client.get("/api/v1/invited-things/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data == []

    def test_invited_things_returns_invited(self, user, user2, thing, collection):
        """Should return things from collections user is invited to."""
        # Invite user2
        collection.add_invite(user2.code)

        client2 = self._get_client_for_user(user2)
        response = client2.get("/api/v1/invited-things/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data) == 1
        assert response.data[0]["code"] == thing.code

    # FAQ access tests

    def test_faq_list_denied_for_non_invited_user(self, user, user2, thing):
        """Should deny FAQ list for non-invited user."""
        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{thing.code}/faq/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_faq_list_allowed_for_invited_user(self, user, user2, thing, collection, faq):
        """Should allow FAQ list for invited user."""
        collection.add_invite(user2.code)

        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{thing.code}/faq/")
        assert response.status_code == status.HTTP_200_OK

    def test_faq_detail_denied_for_non_invited_user(self, user, user2, faq, thing):
        """Should deny FAQ detail for non-invited user."""
        # Make FAQ visible first
        faq.is_visible = True
        faq.save()

        # Create a third user (not owner, not questioner, not invited)
        from core.models import User

        user3 = User.objects.create(
            code="TEST03",
            email="test3@example.com",
            name="Test User 3",
        )

        client3 = self._get_client_for_user(user3)
        response = client3.get(f"/api/v1/faq/{faq.code}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_faq_create_denied_for_non_invited_user(self, user, user2, thing):
        """Should deny FAQ creation for non-invited user."""
        # Create a third user
        from core.models import User

        user3 = User.objects.create(
            code="TEST03",
            email="test3@example.com",
            name="Test User 3",
        )

        client3 = self._get_client_for_user(user3)
        response = client3.post(
            f"/api/v1/things/{thing.code}/faq/",
            {"question": "Is this available?"},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

    # User profile access tests

    def test_user_profile_access_denied_for_unrelated_user(self, user, user2):
        """Should deny profile access for unrelated user."""
        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/users/{user.code}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_user_profile_access_allowed_for_self(self, authenticated_client, user):
        """Should allow viewing own profile."""
        response = authenticated_client.get(f"/api/v1/users/{user.code}/")
        assert response.status_code == status.HTTP_200_OK

    def test_user_profile_access_allowed_when_invited_to_their_collection(
        self, user, user2, collection
    ):
        """Should allow profile access when invited to their collection."""
        # User invites user2 to their collection
        collection.add_invite(user2.code)

        # User2 can now see user's profile (owner of collection they're invited to)
        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/users/{user.code}/")
        assert response.status_code == status.HTTP_200_OK

    def test_user_profile_access_allowed_when_they_invited_to_your_collection(
        self, user, user2, theeeme
    ):
        """Should allow profile access when user is in your invites."""
        from core.models import Collection

        # User2 creates a collection and invites user
        coll2 = Collection.objects.create(
            code="COLL02",
            owner=user2,
            headline="User2 Collection",
            theeeme=theeeme,
        )
        coll2.add_invite(user.code)

        # User can now see user2's profile (they invited me)
        client1 = self._get_client_for_user(user)
        response = client1.get(f"/api/v1/users/{user2.code}/")
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestReservationViews:
    """Tests for reservation request flow."""

    def _get_client_for_user(self, user):
        """Create an authenticated client for a user."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    def test_request_reservation(self, user, user2, thing, collection):
        """Should create a booking request and change thing status to TAKEN."""
        # Invite user2 to collection
        collection.add_invite(user2.code)

        client2 = self._get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Booking request sent"
        assert "booking_code" in response.data

        # Verify thing status changed to TAKEN
        thing.refresh_from_db()
        assert thing.status == "TAKEN"

    def test_request_reservation_denied_for_owner(self, authenticated_client, thing):
        """Should deny owner from requesting their own thing."""
        response = authenticated_client.post(f"/api/v1/things/{thing.code}/request/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Cannot request your own thing"

    def test_request_reservation_denied_for_non_invited(self, user, user2, thing):
        """Should deny non-invited user from requesting."""
        client2 = self._get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")

        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_request_reservation_denied_for_non_active_thing(self, user, user2, thing, collection):
        """Should deny request for non-active thing."""
        collection.add_invite(user2.code)
        thing.status = "TAKEN"
        thing.save()

        client2 = self._get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Thing is not available for reservation"

    def test_accept_reservation(self, api_client, user, user2, thing, collection):
        """Should accept reservation via RSVP and change thing status to INACTIVE."""
        from core.models import RSVP
        from core.models.booking import BookingPeriod

        collection.add_invite(user2.code)

        # Create booking request (for GIFT_THING)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=None,
            end_date=None,
        )
        thing.status = "TAKEN"
        thing.save()

        # Create RSVP for accept action (as would be done when sending email)
        rsvp = RSVP.create_for_booking("BOOKING_ACCEPT", booking, user.email)

        # Accept via RSVP link
        response = api_client.get(f"/api/v1/rsvp/{rsvp.code}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Booking accepted"
        assert response.data["action"] == "BOOKING_ACCEPT"

        # Verify thing status and booking status
        thing.refresh_from_db()
        booking.refresh_from_db()
        assert thing.status == "INACTIVE"
        assert thing.available is False
        assert thing.deal.filter(code=user2.code).exists()
        assert booking.status == "ACCEPTED"

    def test_reject_reservation(self, api_client, user, user2, thing, collection):
        """Should reject reservation via RSVP and change thing status back to ACTIVE."""
        from core.models import RSVP
        from core.models.booking import BookingPeriod

        collection.add_invite(user2.code)

        # Create booking request (for GIFT_THING)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=None,
            end_date=None,
        )
        thing.status = "TAKEN"
        thing.save()

        # Create RSVP for reject action
        rsvp = RSVP.create_for_booking("BOOKING_REJECT", booking, user.email)

        # Reject via RSVP link
        response = api_client.get(f"/api/v1/rsvp/{rsvp.code}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Booking rejected"
        assert response.data["action"] == "BOOKING_REJECT"

        # Verify thing status and booking status
        thing.refresh_from_db()
        booking.refresh_from_db()
        assert thing.status == "ACTIVE"
        assert booking.status == "REJECTED"

    def test_reservation_expired(self, api_client, user, user2, thing):
        """Should return error for expired booking via RSVP."""
        from datetime import timedelta

        from django.utils import timezone

        from core.models import RSVP
        from core.models.booking import BookingPeriod

        # Create expired booking
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=None,
            end_date=None,
        )
        booking.created = timezone.now() - timedelta(hours=100)
        booking.save()

        # Create RSVP for accept action
        rsvp = RSVP.create_for_booking("BOOKING_ACCEPT", booking, user.email)

        response = api_client.get(f"/api/v1/rsvp/{rsvp.code}/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Booking expired or already processed"

    def test_duplicate_request_denied(self, user, user2, thing, collection):
        """Should deny duplicate pending request."""
        from core.models.booking import BookingPeriod

        collection.add_invite(user2.code)

        # Create existing pending booking
        BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            status="PENDING",
            start_date=None,
            end_date=None,
        )

        client2 = self._get_client_for_user(user2)
        response = client2.post(f"/api/v1/things/{thing.code}/request/")

        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "You already have a pending request for this thing"


@pytest.mark.django_db
class TestThingAvailabilityVisibility:
    """Tests for available visibility rules.

    available controls visibility:
    - True: Visible to owner AND all invites
    - False: Visible ONLY to owner (hidden from invites)
    """

    def _get_client_for_user(self, user):
        """Create an authenticated client for a user."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    def test_hidden_thing_visible_to_owner(self, authenticated_client, thing):
        """Owner can view their thing even when available=False."""
        thing.available = False
        thing.save()

        response = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["code"] == thing.code

    def test_hidden_thing_not_visible_to_invited_user(self, user, user2, thing, collection):
        """Invited user cannot view thing when available=False."""
        # Invite user2 to collection
        collection.add_invite(user2.code)

        # Hide the thing
        thing.available = False
        thing.save()

        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_visible_thing_visible_to_invited_user(self, user, user2, thing, collection):
        """Invited user can view thing when available=True."""
        # Invite user2 to collection
        collection.add_invite(user2.code)

        # Ensure thing is visible
        thing.available = True
        thing.save()

        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_200_OK

    def test_invited_things_excludes_hidden(self, user, user2, thing, collection):
        """Invited things endpoint should exclude hidden things."""
        from core.models import Thing

        # Invite user2 to collection
        collection.add_invite(user2.code)

        # Create a second thing that is hidden
        hidden_thing = Thing.objects.create(
            code="HIDDN1",
            type="GIFT_THING",
            owner=user,
            headline="Hidden Thing",
            available=False,
        )
        collection.add_thing(hidden_thing.code)

        client2 = self._get_client_for_user(user2)
        response = client2.get("/api/v1/invited-things/")
        assert response.status_code == status.HTTP_200_OK

        # Should only see the visible thing, not the hidden one
        thing_codes = [t["code"] for t in response.data]
        assert thing.code in thing_codes
        assert hidden_thing.code not in thing_codes

    def test_owner_sees_all_things_in_own_list(self, authenticated_client, user, collection):
        """Owner's thing list includes hidden things."""
        from core.models import Thing

        # Create hidden thing
        hidden_thing = Thing.objects.create(
            code="HIDDN2",
            type="GIFT_THING",
            owner=user,
            headline="Owner Hidden Thing",
            available=False,
        )

        response = authenticated_client.get("/api/v1/things/")
        assert response.status_code == status.HTTP_200_OK

        # Owner should see all their things including hidden
        thing_codes = [t["code"] for t in response.data]
        assert hidden_thing.code in thing_codes

    def test_can_view_method_respects_thing_available(self, user, user2, thing, collection):
        """Thing.can_view() respects available flag."""
        collection.add_invite(user2.code)

        # When visible, invited user can view
        thing.available = True
        thing.save()
        assert thing.can_view(user2.code) is True

        # When hidden, invited user cannot view
        thing.available = False
        thing.save()
        assert thing.can_view(user2.code) is False

        # Owner can always view
        assert thing.can_view(user.code) is True


@pytest.mark.django_db
class TestSecurityInputValidation:
    """Tests for security input validation (XSS, injection prevention)."""

    def test_headline_rejects_html_tags(self, authenticated_client):
        """Should reject HTML tags in collection headline."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "<script>alert(1)</script>"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "headline" in response.data

    def test_headline_accepts_plain_text(self, authenticated_client):
        """Should accept plain text in collection headline."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "My Wedding List 2024"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["headline"] == "My Wedding List 2024"

    def test_image_id_rejects_path_traversal(self, authenticated_client, user):
        """Should reject path traversal attempts in image IDs."""
        response = authenticated_client.put(
            f"/api/v1/users/{user.code}/",
            {"thumbnail": "../etc/passwd"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "thumbnail" in response.data

    def test_image_id_accepts_valid_alphanumeric(self, authenticated_client, user):
        """Should accept valid alphanumeric image IDs."""
        response = authenticated_client.put(
            f"/api/v1/users/{user.code}/",
            {"thumbnail": "abc123_XYZ"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["thumbnail"] == "abc123_XYZ"

    def test_quantity_max_99(self, user, user2, collection, theeeme):
        """Should reject order quantity over 99."""
        from datetime import date, timedelta

        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        from core.models import Thing

        # Create ORDER_THING
        order_thing = Thing.objects.create(
            code="ORDER1",
            type="ORDER_THING",
            owner=user,
            headline="Cookies",
            status="ACTIVE",
        )
        collection.add_thing(order_thing.code)
        collection.add_invite(user2.code)

        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # Try to order 100 (should fail)
        response = client2.post(
            f"/api/v1/things/{order_thing.code}/request/",
            {
                "delivery_date": str(date.today() + timedelta(days=7)),
                "quantity": 100,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

        # Order 99 should succeed
        response = client2.post(
            f"/api/v1/things/{order_thing.code}/request/",
            {
                "delivery_date": str(date.today() + timedelta(days=7)),
                "quantity": 99,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK


@pytest.mark.django_db
class TestSecurityAuth:
    """Tests for authentication security features."""

    def test_invite_only_registration(self, api_client):
        """New users cannot request magic links without being invited first."""
        response = api_client.post(
            "/api/v1/auth/request-link/",
            {"email": "newuser@example.com"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND
        assert "No account found" in response.data["error"]
        assert "invite" in response.data["error"].lower()

    def test_existing_user_can_request_magic_link(self, api_client, user):
        """Existing users can request magic links."""
        response = api_client.post(
            "/api/v1/auth/request-link/",
            {"email": user.email},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

    def test_email_not_exposed_in_public_profile(self, user, user2, collection):
        """User email should not be exposed in public profile."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        # Connect users via collection
        collection.add_invite(user2.code)

        client2 = APIClient()
        refresh = RefreshToken.for_user(user2)
        client2.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")

        # View profile of collection owner
        response = client2.get(f"/api/v1/users/{user.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert "email" not in response.data

    def test_email_visible_in_own_profile(self, authenticated_client, user):
        """User can see their own email in their profile."""
        response = authenticated_client.get(f"/api/v1/users/{user.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert "email" in response.data
        assert response.data["email"] == user.email
