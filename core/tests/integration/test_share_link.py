"""
Integration tests for the collection share-link feature.

Covers:
- Generating, rotating and revoking the share token (owner only).
- Token never exposed via the standard collection retrieve endpoint.
- Pop-in flow with valid / invalid / revoked share tokens.
"""

import pytest
from django.core import mail
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, Collection, User


@pytest.fixture
def share_link_setup(db):
    owner = User.objects.create(code="SHOWN1", email="shown@test.com", name="Owner")
    stranger = User.objects.create(code="SHSTR1", email="shstr@test.com", name="Stranger")

    collection = Collection.objects.create(
        code="SHCOL1", owner=owner, headline="Share Club", status="ACTIVE"
    )

    owner_client = APIClient()
    owner_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(owner).access_token}"
    )

    stranger_client = APIClient()
    stranger_client.credentials(
        HTTP_AUTHORIZATION=f"Bearer {RefreshToken.for_user(stranger).access_token}"
    )

    anon_client = APIClient()

    return {
        "owner": owner,
        "stranger": stranger,
        "collection": collection,
        "owner_client": owner_client,
        "stranger_client": stranger_client,
        "anon_client": anon_client,
    }


URL = "/api/v1/collections/{}/share-link/"
POP_IN_URL = "/api/v1/auth/pop-in/"


@pytest.mark.django_db
class TestShareLinkGeneration:
    def test_owner_generates_token_on_first_post(self, share_link_setup):
        collection = share_link_setup["collection"]
        assert collection.share_token is None

        resp = share_link_setup["owner_client"].post(URL.format(collection.code))

        assert resp.status_code == 200
        assert "share_url" in resp.data
        assert "share_token" in resp.data
        token = resp.data["share_token"]
        assert len(token) >= 20  # 22-char URL-safe token
        assert resp.data["share_url"].endswith(f"/share/{token}")

        collection.refresh_from_db()
        assert collection.share_token == token

    def test_post_returns_existing_token_idempotently(self, share_link_setup):
        collection = share_link_setup["collection"]
        client = share_link_setup["owner_client"]

        first = client.post(URL.format(collection.code)).data["share_token"]
        second = client.post(URL.format(collection.code)).data["share_token"]

        assert first == second

    def test_rotate_replaces_token(self, share_link_setup):
        collection = share_link_setup["collection"]
        client = share_link_setup["owner_client"]

        original = client.post(URL.format(collection.code)).data["share_token"]
        rotated = client.post(URL.format(collection.code), {"rotate": True}, format="json").data[
            "share_token"
        ]

        assert original != rotated

    def test_stranger_cannot_generate(self, share_link_setup):
        resp = share_link_setup["stranger_client"].post(
            URL.format(share_link_setup["collection"].code)
        )
        assert resp.status_code == 403

    def test_anonymous_cannot_generate(self, share_link_setup):
        resp = share_link_setup["anon_client"].post(URL.format(share_link_setup["collection"].code))
        assert resp.status_code in (401, 403)


@pytest.mark.django_db
class TestShareLinkRevocation:
    def test_owner_revokes_token(self, share_link_setup):
        collection = share_link_setup["collection"]
        client = share_link_setup["owner_client"]

        client.post(URL.format(collection.code))
        collection.refresh_from_db()
        assert collection.share_token is not None

        resp = client.delete(URL.format(collection.code))
        assert resp.status_code == 200

        collection.refresh_from_db()
        assert collection.share_token is None

    def test_stranger_cannot_revoke(self, share_link_setup):
        collection = share_link_setup["collection"]
        share_link_setup["owner_client"].post(URL.format(collection.code))

        resp = share_link_setup["stranger_client"].delete(URL.format(collection.code))
        assert resp.status_code == 403


@pytest.mark.django_db
class TestShareTokenLeakProtection:
    def test_share_token_not_in_collection_retrieve(self, share_link_setup):
        """The bearer token must never appear in any read endpoint payload."""
        collection = share_link_setup["collection"]
        owner_client = share_link_setup["owner_client"]

        owner_client.post(URL.format(collection.code))
        resp = owner_client.get(f"/api/v1/collections/{collection.code}/")

        assert resp.status_code == 200
        assert "share_token" not in resp.data


@pytest.mark.django_db
class TestPopInWithShareToken:
    def test_valid_token_adds_user_to_collection(self, share_link_setup):
        collection = share_link_setup["collection"]
        token = (
            share_link_setup["owner_client"].post(URL.format(collection.code)).data["share_token"]
        )

        resp = share_link_setup["anon_client"].post(
            POP_IN_URL,
            {"email": "newjoiner@test.com", "share_token": token},
            format="json",
        )

        assert resp.status_code == 200
        new_user = User.objects.get(email="newjoiner@test.com")
        assert collection.invites.filter(code=new_user.code).exists()

    def test_invalid_token_falls_back_silently(self, share_link_setup):
        """Invalid tokens are ignored — we don't reveal whether a token exists."""
        resp = share_link_setup["anon_client"].post(
            POP_IN_URL,
            {"email": "probe@test.com", "share_token": "definitely-not-a-real-token"},
            format="json",
        )

        assert resp.status_code == 200
        # User is created but not added to the share-target collection
        new_user = User.objects.get(email="probe@test.com")
        assert not share_link_setup["collection"].invites.filter(code=new_user.code).exists()

    def test_revoked_token_does_not_grant_access(self, share_link_setup):
        collection = share_link_setup["collection"]
        owner_client = share_link_setup["owner_client"]

        token = owner_client.post(URL.format(collection.code)).data["share_token"]
        owner_client.delete(URL.format(collection.code))

        resp = share_link_setup["anon_client"].post(
            POP_IN_URL,
            {"email": "afterrevoke@test.com", "share_token": token},
            format="json",
        )

        assert resp.status_code == 200
        new_user = User.objects.get(email="afterrevoke@test.com")
        assert not collection.invites.filter(code=new_user.code).exists()

    def test_inactive_collection_token_does_not_grant_access(self, share_link_setup):
        collection = share_link_setup["collection"]
        token = (
            share_link_setup["owner_client"].post(URL.format(collection.code)).data["share_token"]
        )
        collection.status = "INACTIVE"
        collection.save(update_fields=["status"])

        resp = share_link_setup["anon_client"].post(
            POP_IN_URL,
            {"email": "inactive@test.com", "share_token": token},
            format="json",
        )

        assert resp.status_code == 200
        new_user = User.objects.get(email="inactive@test.com")
        assert not collection.invites.filter(code=new_user.code).exists()

    def test_existing_user_can_join_via_share_token(self, share_link_setup):
        collection = share_link_setup["collection"]
        token = (
            share_link_setup["owner_client"].post(URL.format(collection.code)).data["share_token"]
        )

        existing = User.objects.create(code="SHEXST", email="existing@test.com", name="Existing")

        resp = share_link_setup["anon_client"].post(
            POP_IN_URL,
            {"email": "existing@test.com", "share_token": token},
            format="json",
        )

        assert resp.status_code == 200
        assert collection.invites.filter(code=existing.code).exists()

    def test_share_token_stamps_target_and_redirects(self, share_link_setup):
        # #6: a private-share join should land on the collection after login, not
        # the generic /welcome. Pop-in stamps target_code on the magic-link RSVP
        # and verifying it returns invited_collection for the SPA to redirect.
        collection = share_link_setup["collection"]
        token = (
            share_link_setup["owner_client"].post(URL.format(collection.code)).data["share_token"]
        )
        share_link_setup["anon_client"].post(
            POP_IN_URL,
            {"email": "redirshare@test.com", "share_token": token},
            format="json",
        )
        user = User.objects.get(email="redirshare@test.com")
        rsvp = RSVP.objects.get(user_code=user, action=RSVP.Action.MAGIC_LINK)
        assert rsvp.target_code == collection.code

        resp = APIClient().get(f"/api/v1/auth/verify/{rsvp.token}/")
        assert resp.status_code == 200
        assert resp.data["action"] == "MAGIC_LINK"
        assert resp.data["invited_collection"] == collection.code

    def test_share_token_magic_link_subject_names_collection(self, share_link_setup):
        # A private-share join names the collection in the magic-link subject.
        collection = share_link_setup["collection"]
        token = (
            share_link_setup["owner_client"].post(URL.format(collection.code)).data["share_token"]
        )
        mail.outbox.clear()
        share_link_setup["anon_client"].post(
            POP_IN_URL,
            {"email": "sharesubj@test.com", "share_token": token},
            format="json",
        )
        assert "Share Club" in mail.outbox[0].subject


@pytest.mark.django_db
class TestStaleCookieAuth:
    """A live ``access_token`` cookie whose user was wiped (e.g. ``seed_demo
    --reset`` in dev) must not 401 the AllowAny onboarding endpoints."""

    def _stale_cookie_client(self):
        ghost = User.objects.create(code="GHOST1", email="ghost@test.com", name="Ghost")
        token = str(RefreshToken.for_user(ghost).access_token)
        ghost.delete()  # token stays cryptographically valid, the user is gone
        client = APIClient()
        client.cookies["access_token"] = token
        return client

    def test_pop_in_works_with_stale_cookie_for_deleted_user(self):
        resp = self._stale_cookie_client().post(
            POP_IN_URL, {"email": "freshstart@test.com"}, format="json"
        )

        assert resp.status_code == 200
        assert User.objects.filter(email="freshstart@test.com").exists()

    def test_request_link_works_with_stale_cookie_for_deleted_user(self):
        resp = self._stale_cookie_client().post(
            "/api/v1/auth/request-link/", {"email": "freshstart@test.com"}, format="json"
        )

        assert resp.status_code == 200

    def test_protected_endpoint_401s_with_stale_cookie(self):
        resp = self._stale_cookie_client().get("/api/v1/auth/me/")

        assert resp.status_code == 401
