"""
Integration tests for OIUEEI API views.
"""

import pytest
from rest_framework import status

from core.models import RSVP, Collection


@pytest.mark.django_db
class TestAuthViews:
    """Tests for authentication views."""

    def test_request_link_non_existent_user_returns_200(self, api_client):
        """Should return 200 with unified message for non-existent user (no enumeration)."""
        response = api_client.post(
            "/api/v1/auth/request-link/",
            {"email": "lala@oiueei.org"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "If this email is registered" in response.data["message"]

    def test_request_link_existing_user(self, api_client, user):
        """Should send magic link for existing user with unified message."""
        response = api_client.post(
            "/api/v1/auth/request-link/",
            {"email": user.email},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "If this email is registered" in response.data["message"]
        assert "email" not in response.data or response.data.get("email") is None

    def test_request_link_invalid_email(self, api_client):
        """Should reject invalid email."""
        response = api_client.post(
            "/api/v1/auth/request-link/",
            {"email": "not-an-email"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_verify_link_valid(self, api_client, rsvp, user):
        """Should verify valid RSVP and set auth cookies."""
        response = api_client.get(f"/api/v1/auth/verify/{rsvp.token}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["user"]["code"] == user.code
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies
        # L11: auth is JWT-only — no shadow Django session is opened.
        assert "sessionid" not in response.cookies

    def test_verify_link_invalid(self, api_client):
        """Should reject invalid RSVP code."""
        response = api_client.get("/api/v1/auth/verify/INVALID/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_six_char_pk_does_not_authenticate(self, api_client, rsvp):
        """H1: the old 6-char PK is no longer a valid magic link — only the
        high-entropy token resolves an RSVP. Presenting the PK must 401."""
        assert rsvp.code != rsvp.token
        response = api_client.get(f"/api/v1/auth/verify/{rsvp.code}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert "access_token" not in response.cookies

    def test_magic_link_token_is_high_entropy(self, rsvp):
        """H1: the RSVP token is 26 lowercase alphanumerics (~134 bits), distinct
        from the 6-char uppercase PK."""
        import string

        assert len(rsvp.token) == 26
        allowed = set(string.ascii_lowercase + string.digits)
        assert set(rsvp.token) <= allowed
        assert rsvp.token != rsvp.code

    def test_email_ratelimit_key_lowercases_email(self):
        """H1 per-account throttle keys on the lowercased email; malformed → ''."""
        from types import SimpleNamespace

        from core.views.auth import email_ratelimit_key

        assert (
            email_ratelimit_key(None, SimpleNamespace(data={"email": " Lala@Oiueei.ORG "}))
            == "lala@oiueei.org"
        )
        assert email_ratelimit_key(None, SimpleNamespace(data={})) == ""
        assert email_ratelimit_key(None, SimpleNamespace(data={"email": None})) == ""

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

    def test_logout_blacklists_refresh_from_cookie(self, authenticated_client, user):
        """M4: logout reads the refresh token from its cookie (now scoped to
        /api/v1/auth/ so it reaches logout) and blacklists it — reusing it to
        refresh must 401."""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = str(RefreshToken.for_user(user))
        authenticated_client.cookies["refresh_token"] = refresh
        logout_resp = authenticated_client.post("/api/v1/auth/logout/")
        assert logout_resp.status_code == status.HTTP_200_OK

        # The blacklisted token can no longer be exchanged for a new pair.
        authenticated_client.cookies["refresh_token"] = refresh
        refresh_resp = authenticated_client.post("/api/v1/auth/refresh/")
        assert refresh_resp.status_code == status.HTTP_401_UNAUTHORIZED

    def test_logout_with_invalid_refresh_token(self, authenticated_client):
        """Should logout successfully even when refresh token is invalid."""
        response = authenticated_client.post(
            "/api/v1/auth/logout/",
            {"refresh": "invalid-token-string"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Successfully logged out"

    def test_logout_clears_cookies(self, authenticated_client):
        """Should clear auth cookies on logout."""
        response = authenticated_client.post("/api/v1/auth/logout/")
        assert response.status_code == status.HTTP_200_OK
        assert response.cookies["access_token"].value == ""
        assert response.cookies["refresh_token"].value == ""

    def test_token_refresh_without_cookie(self, api_client):
        """Should return 401 when no refresh cookie is present."""
        response = api_client.post("/api/v1/auth/refresh/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED

    def test_token_refresh_with_valid_cookie(self, api_client, user):
        """Should set new auth cookies when refresh cookie is valid."""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        api_client.cookies["refresh_token"] = str(refresh)
        response = api_client.post("/api/v1/auth/refresh/")
        assert response.status_code == status.HTTP_200_OK
        assert "access_token" in response.cookies
        assert "refresh_token" in response.cookies

    def test_cookie_auth(self, api_client, user):
        """Should authenticate using access_token cookie."""
        from rest_framework_simplejwt.tokens import RefreshToken

        refresh = RefreshToken.for_user(user)
        api_client.cookies["access_token"] = str(refresh.access_token)
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["code"] == user.code


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

    def test_update_own_profile_koro(self, authenticated_client, user):
        """Should update koro preference and persist it."""
        response = authenticated_client.put(
            f"/api/v1/users/{user.code}/",
            {"koro": "wave"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["koro"] == "wave"

        user.refresh_from_db()
        assert user.koro == "wave"

    def test_update_own_profile_koro_invalid(self, authenticated_client, user):
        """Should reject invalid koro values."""
        response = authenticated_client.put(
            f"/api/v1/users/{user.code}/",
            {"koro": "invalid_koro"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

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
        assert response.data["count"] == 1
        assert response.data["results"][0]["code"] == collection.code

    def test_create_collection(self, authenticated_client, user):
        """Should create a new collection."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "New Collection"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["headline"] == "New Collection"

    def test_create_collection_without_headline_fails(self, authenticated_client):
        """Should fail to create collection without headline."""
        response = authenticated_client.post(
            "/api/v1/collections/",
            {"description": "No headline"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert "headline" in response.data

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

        # Verify RSVP was created with target_code
        rsvp = RSVP.objects.filter(user_email="newuser@oiueei.org").first()
        assert rsvp is not None
        assert rsvp.target_code == collection.code

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

        # Create a user and RSVP with target_code and COLLECTION_INVITE action
        invited_user = User.objects.create(
            code="INVTD1",
            email="invited@oiueei.org",
        )
        rsvp = RSVP.objects.create(
            user_code=invited_user,
            user_email=invited_user.email,
            action="COLLECTION_INVITE",
            target_code=collection.code,
        )

        # Verify the link
        response = api_client.get(f"/api/v1/auth/verify/{rsvp.token}/")
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
        assert "revoked" in mail.outbox[0].subject

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
            f"/api/v1/collections/{collection.code}/add-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Thing added to collection"
        assert any(t["code"] == thing.code for t in response.data["collection"]["things"])

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
            f"/api/v1/collections/{collection.code}/add-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN

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
            f"/api/v1/collections/{collection.code}/add-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == status.HTTP_403_FORBIDDEN
        assert response.data["error"] == "You can only add your own things to collections"

    def test_add_thing_already_in_collection(self, authenticated_client, thing, collection):
        """Should return error when thing is already in collection."""
        response = authenticated_client.post(
            f"/api/v1/collections/{collection.code}/add-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert response.data["error"] == "Thing is already in this collection"

    def test_add_nonexistent_thing_to_collection(self, authenticated_client, collection):
        """Should return 404 for nonexistent thing."""
        response = authenticated_client.post(
            f"/api/v1/collections/{collection.code}/add-thing/",
            {"thing_code": "NOEXST"},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND

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
            "/api/v1/collections/NOEXST/add-thing/",
            {"thing_code": thing.code},
            format="json",
        )
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestThingViews:
    """Tests for thing views."""

    def test_list_things(self, authenticated_client, thing):
        """Should list user's things."""
        response = authenticated_client.get("/api/v1/things/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["count"] == 1

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

    def test_create_thing_with_detail_fields(self, authenticated_client):
        """Should create a thing with availability, location, and condition."""
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "headline": "Gift with details",
                "type": "GIFT_THING",
                "availability": "IMMEDIATE",
                "location": "Helsinki",
                "condition": "GOOD",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        assert response.data["availability"] == "IMMEDIATE"
        assert response.data["location"] == "Helsinki"
        assert response.data["condition"] == "GOOD"

    def test_update_thing_detail_fields(self, authenticated_client, thing):
        """Should update availability, location, and condition."""
        response = authenticated_client.patch(
            f"/api/v1/things/{thing.code}/",
            {
                "availability": "NEXT_WEEK",
                "location": "Espoo",
                "condition": "FAIR",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["availability"] == "NEXT_WEEK"
        assert response.data["location"] == "Espoo"
        assert response.data["condition"] == "FAIR"

    def test_thing_detail_includes_new_fields(self, authenticated_client, thing):
        """Should include availability, location, condition in detail response."""
        response = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert "availability" in response.data
        assert "location" in response.data
        assert "condition" in response.data

    def test_delete_thing(self, authenticated_client, thing):
        """Should delete thing."""
        response = authenticated_client.delete(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_collection_owner_can_delete_others_thing(self, user, user2, thing, collection):
        """Collection owner can delete a thing they do not own."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        from core.models import Thing, User

        # user3 is the collection owner; thing belongs to user (invited)
        user3 = User.objects.create(email="colowner@test.com", code="COL003")
        col_owner_col = collection.__class__.objects.create(
            code="COWNC1", owner=user3, headline="Col Owner Collection"
        )
        other_thing = Thing.objects.create(
            code="OTHRT1", type="GIFT_THING", owner=user, headline="Other's Thing"
        )
        col_owner_col.invites.add(user)
        col_owner_col.things.add(other_thing)

        client3 = APIClient()
        client3.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user3).access_token}"
        )
        response = client3.delete(f"/api/v1/things/{other_thing.code}/")
        assert response.status_code == status.HTTP_204_NO_CONTENT

    def test_thing_owner_cannot_delete_after_transfer(self, db, user, user2):
        """Thing owner cannot delete if transfers exist and they don't own the collection."""
        import datetime

        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        from core.models import Collection, Thing
        from core.models.transfer import ThingTransfer

        # user2 owns the collection; user is just an invited member
        col = Collection.objects.create(code="TRNFC1", owner=user2, headline="Col owned by u2")
        col.mode = "COMMUNITY"
        col.save()
        col.invites.add(user)

        share_thing = Thing.objects.create(
            code="SHRTR1", type="SHARE_THING", owner=user, headline="Shared Thing"
        )
        col.things.add(share_thing)

        ThingTransfer.objects.create(
            code="TRFR01",
            thing=share_thing,
            from_user=user,
            to_user=user2,
            lent_date=datetime.date.today(),
        )

        client = APIClient()
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}")
        response = client.delete(f"/api/v1/things/{share_thing.code}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_non_collection_owner_cannot_delete_others_thing(self, user, user2, thing, collection):
        """Invited user cannot delete a thing owned by someone else."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        from core.models import User

        user3 = User.objects.create(email="invited3@test.com", code="INV003")
        collection.invites.add(user3)

        client3 = APIClient()
        client3.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user3).access_token}"
        )
        response = client3.delete(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

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

    def test_hide_thing(self, authenticated_client, thing):
        """Owner can hide an ACTIVE thing (sets status to INACTIVE)."""
        assert thing.status == "ACTIVE"

        response = authenticated_client.post(f"/api/v1/things/{thing.code}/hide/")

        assert response.status_code == status.HTTP_200_OK
        thing.refresh_from_db()
        assert thing.status == "INACTIVE"

    def test_hide_thing_denied_for_non_owner(self, user, user2, thing, collection):
        """Non-owner cannot hide a thing."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        collection.add_invite(user2.code)
        client2 = APIClient()
        client2.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user2).access_token}"
        )

        response = client2.post(f"/api/v1/things/{thing.code}/hide/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_hide_thing_requires_active_status(self, authenticated_client, thing):
        """Cannot hide a TAKEN thing — must cancel the hold first."""
        thing.status = "TAKEN"
        thing.save()

        response = authenticated_client.post(f"/api/v1/things/{thing.code}/hide/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_activate_thing(self, authenticated_client, thing):
        """Owner can reactivate an INACTIVE thing (sets status to ACTIVE)."""
        thing.status = "INACTIVE"
        thing.save()

        response = authenticated_client.post(f"/api/v1/things/{thing.code}/activate/")

        assert response.status_code == status.HTTP_200_OK
        thing.refresh_from_db()
        assert thing.status == "ACTIVE"

    def test_activate_thing_denied_for_non_owner(self, user, user2, thing, collection):
        """Non-owner cannot activate a thing."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        thing.status = "INACTIVE"
        thing.save()
        collection.add_invite(user2.code)
        client2 = APIClient()
        client2.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user2).access_token}"
        )

        response = client2.post(f"/api/v1/things/{thing.code}/activate/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_activate_thing_requires_inactive_status(self, authenticated_client, thing):
        """Cannot activate an already ACTIVE thing."""
        assert thing.status == "ACTIVE"

        response = authenticated_client.post(f"/api/v1/things/{thing.code}/activate/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_my_pending_booking_field(self, user, user2, thing, collection):
        """my_pending_booking should return own PENDING booking code, null for others."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        from core.models.booking import BookingPeriod

        collection.add_invite(user2.code)

        # Create a PENDING booking for user2
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )

        # Requester sees their own booking code
        client2 = APIClient()
        client2.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user2).access_token}"
        )
        response = client2.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["my_pending_booking"] == booking.code

        # Owner sees null (it's not their booking request)
        owner_client = APIClient()
        owner_client.credentials(
            HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(user).access_token}"
        )
        response = owner_client.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["my_pending_booking"] is None


@pytest.mark.django_db
class TestFAQViews:
    """Tests for FAQ views."""

    def test_list_faqs(self, authenticated_client, thing, faq):
        """Should list FAQs for a thing."""
        response = authenticated_client.get(f"/api/v1/things/{thing.code}/faq/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1

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
        assert "question to be answered" in mail.outbox[0].subject

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
        assert "has been answered" in mail.outbox[0].subject

    def test_hide_faq_sends_email_to_questioner(self, authenticated_client, user, user2, faq):
        """Hiding FAQ should send email to questioner."""
        from django.core import mail

        response = authenticated_client.post(f"/api/v1/faq/{faq.code}/hide/")
        assert response.status_code == status.HTTP_200_OK

        # Check email was sent to questioner
        assert len(mail.outbox) == 1
        assert mail.outbox[0].to == [user2.email]
        assert "has been hidden" in mail.outbox[0].subject


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
        assert response.data["results"] == []

    def test_invited_things_returns_invited(self, user, user2, thing, collection):
        """Should return things from collections user is invited to."""
        # Invite user2
        collection.add_invite(user2.code)

        client2 = self._get_client_for_user(user2)
        response = client2.get("/api/v1/invited-things/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["code"] == thing.code

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

    def test_user_profile_access_allowed_when_they_invited_to_your_collection(self, user, user2):
        """Should allow profile access when user is in your invites."""
        from core.models import Collection

        # User2 creates a collection and invites user
        coll2 = Collection.objects.create(
            code="COLL02",
            owner=user2,
            headline="User2 Collection",
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
        """Should create a booking request, change thing status to TAKEN, and send two emails."""
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

        # Verify both emails sent: owner request + requester confirmation
        from django.core import mail

        assert len(mail.outbox) == 2
        owner_email = mail.outbox[0]
        confirmation_email = mail.outbox[1]
        assert owner_email.to == [user.email]
        assert confirmation_email.to == [user2.email]

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
        response = api_client.get(f"/api/v1/rsvp/{rsvp.token}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Booking accepted"
        assert response.data["action"] == "BOOKING_ACCEPT"

        # Verify thing status and booking status
        thing.refresh_from_db()
        booking.refresh_from_db()
        assert thing.status == "INACTIVE"
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
        response = api_client.get(f"/api/v1/rsvp/{rsvp.token}/")

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

        response = api_client.get(f"/api/v1/rsvp/{rsvp.token}/")

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
class TestThingStatusVisibility:
    """Tests for thing status visibility rules.

    Status controls visibility:
    - ACTIVE: Visible to owner AND invited users, available for reservation
    - TAKEN: Visible to owner AND invited users, not available for new reservation
    - INACTIVE: Visible ONLY to owner (hidden from guests)
    """

    def _get_client_for_user(self, user):
        """Create an authenticated client for a user."""
        from rest_framework.test import APIClient
        from rest_framework_simplejwt.tokens import RefreshToken

        client = APIClient()
        refresh = RefreshToken.for_user(user)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {refresh.access_token}")
        return client

    def test_inactive_thing_visible_to_owner(self, authenticated_client, thing):
        """Owner can view their thing even when INACTIVE."""
        thing.status = "INACTIVE"
        thing.save()

        response = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["code"] == thing.code

    def test_inactive_thing_not_visible_to_invited_user(self, user, user2, thing, collection):
        """Invited user cannot view INACTIVE things."""
        collection.add_invite(user2.code)

        thing.status = "INACTIVE"
        thing.save()

        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_403_FORBIDDEN

    def test_active_thing_visible_to_invited_user(self, user, user2, thing, collection):
        """Invited user can view ACTIVE things."""
        collection.add_invite(user2.code)

        client2 = self._get_client_for_user(user2)
        response = client2.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == status.HTTP_200_OK

    def test_invited_things_excludes_inactive(self, user, user2, thing, collection):
        """Invited things endpoint should exclude INACTIVE things."""
        from core.models import Thing

        collection.add_invite(user2.code)

        inactive_thing = Thing.objects.create(
            code="INACT1",
            type="GIFT_THING",
            owner=user,
            headline="Inactive Thing",
            status="INACTIVE",
        )
        collection.add_thing(inactive_thing.code)

        client2 = self._get_client_for_user(user2)
        response = client2.get("/api/v1/invited-things/")
        assert response.status_code == status.HTTP_200_OK

        thing_codes = [t["code"] for t in response.data["results"]]
        assert thing.code in thing_codes
        assert inactive_thing.code not in thing_codes

    def test_owner_sees_all_things_including_inactive(self, authenticated_client, user, collection):
        """Owner's thing list includes INACTIVE things."""
        from core.models import Thing

        inactive_thing = Thing.objects.create(
            code="INACT2",
            type="GIFT_THING",
            owner=user,
            headline="Owner Inactive Thing",
            status="INACTIVE",
        )

        response = authenticated_client.get("/api/v1/things/")
        assert response.status_code == status.HTTP_200_OK

        thing_codes = [t["code"] for t in response.data["results"]]
        assert inactive_thing.code in thing_codes

    def test_can_view_method_respects_thing_status(self, user, user2, thing, collection):
        """Thing.can_view() respects status field."""
        collection.add_invite(user2.code)

        # ACTIVE: invited user can view
        assert thing.status == "ACTIVE"
        assert thing.can_view(user2.code) is True

        # INACTIVE: invited user cannot view
        thing.status = "INACTIVE"
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

    def test_quantity_max_99(self, user, user2, collection):
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
        """New users get same response as existing users (no enumeration)."""
        response = api_client.post(
            "/api/v1/auth/request-link/",
            {"email": "newuser@example.com"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert "If this email is registered" in response.data["message"]

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


@pytest.mark.django_db
class TestAuthViewEdgeCases:
    """Tests for auth view edge cases and uncovered branches."""

    def test_verify_expired_rsvp(self, api_client, user):
        """Expired RSVP should return 401 and be deleted."""
        from datetime import timedelta

        from django.utils import timezone

        rsvp = RSVP.objects.create(
            user_code=user,
            user_email=user.email,
        )
        rsvp.created = timezone.now() - timedelta(hours=25)
        rsvp.save(update_fields=["created"])

        response = api_client.get(f"/api/v1/auth/verify/{rsvp.token}/")
        assert response.status_code == status.HTTP_401_UNAUTHORIZED
        assert not RSVP.objects.filter(code=rsvp.code).exists()

    def test_verify_unknown_action(self, api_client, user):
        """RSVP with unknown action should return 400."""
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email=user.email,
            action="UNKNOWN_ACTION",
        )
        response = api_client.get(f"/api/v1/auth/verify/{rsvp.token}/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
        assert not RSVP.objects.filter(code=rsvp.code).exists()

    def test_collection_reject_via_rsvp(self, api_client, user, user2, collection):
        """Collection reject RSVP should decline invitation and notify owner."""
        from unittest.mock import patch

        # Create accept and reject RSVPs
        RSVP.objects.create(
            user_code=user2,
            user_email=user2.email,
            action="COLLECTION_INVITE",
            target_code=collection.code,
        )
        reject_rsvp = RSVP.objects.create(
            user_code=user2,
            user_email=user2.email,
            action="COLLECTION_REJECT",
            target_code=collection.code,
        )

        with patch("core.views.auth.send_invite_rejected_email") as mock_email:
            response = api_client.get(f"/api/v1/auth/verify/{reject_rsvp.token}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["action"] == "COLLECTION_REJECT"
        mock_email.assert_called_once()
        # Both RSVPs should be deleted
        assert not RSVP.objects.filter(user_code=user2, target_code=collection.code).exists()

    def test_collection_reject_deleted_collection(self, api_client, user2):
        """Collection reject for deleted collection should still succeed."""
        reject_rsvp = RSVP.objects.create(
            user_code=user2,
            user_email=user2.email,
            action="COLLECTION_REJECT",
            target_code="NOCODE",
        )
        response = api_client.get(f"/api/v1/auth/verify/{reject_rsvp.token}/")
        assert response.status_code == status.HTTP_200_OK

    def test_booking_accept_via_rsvp(self, api_client, user, user2, thing, collection):
        """Booking accept RSVP should accept the booking."""
        from unittest.mock import patch

        from core.models.booking import BookingPeriod

        collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )
        accept_rsvp = RSVP.objects.create(
            user_code=user,
            user_email=user.email,
            action="BOOKING_ACCEPT",
            target_code=booking.code,
        )

        with patch("core.services.email_service.send_booking_decision_email"):
            response = api_client.get(f"/api/v1/auth/verify/{accept_rsvp.token}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["action"] == "BOOKING_ACCEPT"
        booking.refresh_from_db()
        assert booking.status == "ACCEPTED"
        # Single-action (H1): a booking token performs the action only — it must
        # never authenticate the owner as a side effect (no auth cookies set).
        assert "access_token" not in response.cookies
        assert "refresh_token" not in response.cookies

    def test_booking_reject_via_rsvp(self, api_client, user, user2, thing, collection):
        """Booking reject RSVP should reject the booking."""
        from unittest.mock import patch

        from core.models.booking import BookingPeriod

        collection.invites.add(user2)
        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
        )
        reject_rsvp = RSVP.objects.create(
            user_code=user,
            user_email=user.email,
            action="BOOKING_REJECT",
            target_code=booking.code,
        )

        with patch("core.services.email_service.send_booking_decision_email"):
            response = api_client.get(f"/api/v1/auth/verify/{reject_rsvp.token}/")

        assert response.status_code == status.HTTP_200_OK
        assert response.data["action"] == "BOOKING_REJECT"
        booking.refresh_from_db()
        assert booking.status == "REJECTED"

    def test_booking_rsvp_not_found(self, api_client, user):
        """Booking RSVP for nonexistent booking should return 404."""
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email=user.email,
            action="BOOKING_ACCEPT",
            target_code="NOCODE",
        )
        response = api_client.get(f"/api/v1/auth/verify/{rsvp.token}/")
        assert response.status_code == status.HTTP_404_NOT_FOUND


@pytest.mark.django_db
class TestPopInView:
    """Tests for the open-door onboarding endpoint."""

    def _make_onboarding_collection(self, owner, code, headline):
        """Helper to create an onboarding collection."""
        return Collection.objects.create(
            code=code,
            owner=owner,
            headline=headline,
            is_onboarding=True,
        )

    def test_new_user_is_created_and_added_to_onboarding_collections(self, api_client, user):
        """New email should create a user and add them to all onboarding collections."""
        from unittest.mock import patch

        col = self._make_onboarding_collection(user, "ONBD01", "Onboarding Collection")

        with patch("core.views.auth.send_magic_link_email"):
            response = api_client.post(
                "/api/v1/auth/pop-in/",
                {"email": "newperson@example.com"},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        from core.models import User as UserModel

        new_user = UserModel.objects.get(email="newperson@example.com")
        assert col.invites.filter(code=new_user.code).exists()

    def test_existing_user_is_added_to_onboarding_collections(self, api_client, user):
        """Existing user should be added to onboarding collections and receive a magic link."""
        from unittest.mock import patch

        col = self._make_onboarding_collection(user, "ONBD01", "Onboarding Collection")

        with patch("core.views.auth.send_magic_link_email") as mock_email:
            response = api_client.post(
                "/api/v1/auth/pop-in/",
                {"email": user.email},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert col.invites.filter(code=user.code).exists()
        mock_email.assert_called_once()

    def test_magic_link_rsvp_is_created(self, api_client, user):
        """Should create a MAGIC_LINK RSVP for the user."""
        from unittest.mock import patch

        with patch("core.views.auth.send_magic_link_email"):
            api_client.post(
                "/api/v1/auth/pop-in/",
                {"email": user.email},
                format="json",
            )

        assert RSVP.objects.filter(user_code=user, action="MAGIC_LINK").exists()

    def test_only_onboarding_collections_are_joined(self, api_client, user):
        """Non-onboarding collections should not be touched."""
        from unittest.mock import patch

        onboarding_col = self._make_onboarding_collection(user, "ONBD01", "Onboarding")
        regular_col = Collection.objects.create(
            code="REGC01", owner=user, headline="Regular", is_onboarding=False
        )

        with patch("core.views.auth.send_magic_link_email"):
            api_client.post(
                "/api/v1/auth/pop-in/",
                {"email": user.email},
                format="json",
            )

        assert onboarding_col.invites.filter(code=user.code).exists()
        assert not regular_col.invites.filter(code=user.code).exists()

    def test_invalid_email_returns_400(self, api_client):
        """Should reject invalid email."""
        response = api_client.post(
            "/api/v1/auth/pop-in/",
            {"email": "not-an-email"},
            format="json",
        )
        assert response.status_code == status.HTTP_400_BAD_REQUEST

    def test_returns_unified_message(self, api_client, user):
        """Should always return 200 with a message (no user enumeration)."""
        from unittest.mock import patch

        with patch("core.views.auth.send_magic_link_email"):
            response = api_client.post(
                "/api/v1/auth/pop-in/",
                {"email": "anyone@example.com"},
                format="json",
            )

        assert response.status_code == status.HTTP_200_OK
        assert "message" in response.data

    def test_booking_rsvp_expired_booking(self, api_client, user, user2, thing):
        """Booking RSVP for expired booking should return 400."""
        from core.models.booking import BookingPeriod

        booking = BookingPeriod.objects.create(
            thing_code=thing,
            thing_type="GIFT_THING",
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            status="ACCEPTED",
        )
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email=user.email,
            action="BOOKING_ACCEPT",
            target_code=booking.code,
        )
        response = api_client.get(f"/api/v1/auth/verify/{rsvp.token}/")
        assert response.status_code == status.HTTP_400_BAD_REQUEST
