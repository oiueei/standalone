"""Integration tests for login-to-act auto-join on PUBLIC collections (#5, phase 3).

A visitor who tries to act on a PUBLIC collection submits their email plus the
collection code to pop-in; on submission they are added to that collection's
invitees and emailed a magic link. The code only joins PUBLIC, ACTIVE
collections — never a PRIVATE one — and an unknown/non-public code is silently
ignored (same unified response, no enumeration oracle).
"""

import pytest
from django.core import mail
from rest_framework.test import APIClient

from core.models import RSVP, Collection, User

POP_IN_URL = "/api/v1/auth/pop-in/"


@pytest.fixture
def join_setup(db):
    owner = User.objects.create(code="JNOWN1", email="jnown@test.com", name="Owner")
    public = Collection.objects.create(
        code="JPUB01",
        owner=owner,
        headline="Open community",
        status="ACTIVE",
        visibility=Collection.Visibility.PUBLIC,
    )
    private = Collection.objects.create(
        code="JPRV01",
        owner=owner,
        headline="Closed group",
        status="ACTIVE",
        visibility=Collection.Visibility.PRIVATE,
    )
    inactive_public = Collection.objects.create(
        code="JINA01",
        owner=owner,
        headline="Archived",
        status="INACTIVE",
        visibility=Collection.Visibility.PUBLIC,
    )
    onboarding = Collection.objects.create(
        code="JONB01",
        owner=owner,
        headline="Demo",
        status="ACTIVE",
        is_onboarding=True,
    )
    return {
        "public": public,
        "private": private,
        "inactive_public": inactive_public,
        "onboarding": onboarding,
        "anon": APIClient(),
    }


@pytest.mark.django_db
class TestPublicAutoJoin:
    def test_public_code_adds_user_and_sends_magic_link(self, join_setup):
        resp = join_setup["anon"].post(
            POP_IN_URL,
            {"email": "visitor@test.com", "collection_code": "JPUB01"},
            format="json",
        )
        assert resp.status_code == 200
        user = User.objects.get(email="visitor@test.com")
        assert join_setup["public"].invites.filter(code=user.code).exists()
        # A magic-link RSVP was issued so the visitor can log in and then act.
        assert RSVP.objects.filter(user_code=user, action=RSVP.Action.MAGIC_LINK).exists()

    def test_public_code_does_not_also_join_onboarding(self, join_setup):
        join_setup["anon"].post(
            POP_IN_URL,
            {"email": "visitor2@test.com", "collection_code": "JPUB01"},
            format="json",
        )
        user = User.objects.get(email="visitor2@test.com")
        assert join_setup["public"].invites.filter(code=user.code).exists()
        assert not join_setup["onboarding"].invites.filter(code=user.code).exists()

    def test_private_code_does_not_join(self, join_setup):
        resp = join_setup["anon"].post(
            POP_IN_URL,
            {"email": "probe@test.com", "collection_code": "JPRV01"},
            format="json",
        )
        assert resp.status_code == 200
        user = User.objects.get(email="probe@test.com")
        assert not join_setup["private"].invites.filter(code=user.code).exists()
        # Falls back to onboarding since no valid public target was given.
        assert join_setup["onboarding"].invites.filter(code=user.code).exists()

    def test_inactive_public_code_does_not_join(self, join_setup):
        resp = join_setup["anon"].post(
            POP_IN_URL,
            {"email": "inactive@test.com", "collection_code": "JINA01"},
            format="json",
        )
        assert resp.status_code == 200
        user = User.objects.get(email="inactive@test.com")
        assert not join_setup["inactive_public"].invites.filter(code=user.code).exists()

    def test_unknown_code_is_ignored(self, join_setup):
        resp = join_setup["anon"].post(
            POP_IN_URL,
            {"email": "ghost@test.com", "collection_code": "NOPE00"},
            format="json",
        )
        assert resp.status_code == 200
        assert User.objects.filter(email="ghost@test.com").exists()

    def test_existing_user_can_join_via_public_code(self, join_setup):
        existing = User.objects.create(code="JEXST1", email="member@test.com", name="Member")
        resp = join_setup["anon"].post(
            POP_IN_URL,
            {"email": "member@test.com", "collection_code": "JPUB01"},
            format="json",
        )
        assert resp.status_code == 200
        assert join_setup["public"].invites.filter(code=existing.code).exists()

    def test_public_code_stamps_target_on_rsvp(self, join_setup):
        # The magic-link RSVP carries the collection as target_code so that, after
        # verifying, the visitor is redirected straight back to it (login-to-act).
        join_setup["anon"].post(
            POP_IN_URL,
            {"email": "redir@test.com", "collection_code": "JPUB01"},
            format="json",
        )
        user = User.objects.get(email="redir@test.com")
        rsvp = RSVP.objects.get(user_code=user, action=RSVP.Action.MAGIC_LINK)
        assert rsvp.target_code == "JPUB01"

    def test_onboarding_fallback_leaves_target_empty(self, join_setup):
        # No specific public target → no redirect target (lands on home/welcome).
        join_setup["anon"].post(
            POP_IN_URL,
            {"email": "demo@test.com"},
            format="json",
        )
        user = User.objects.get(email="demo@test.com")
        rsvp = RSVP.objects.get(user_code=user, action=RSVP.Action.MAGIC_LINK)
        assert rsvp.target_code == ""

    def test_verify_public_join_returns_invited_collection(self, join_setup):
        # End-to-end #6: after pop-in via a public code, verifying the magic link
        # returns invited_collection so the SPA drops the visitor straight onto the
        # collection they came to act on — not the generic /welcome.
        join_setup["anon"].post(
            POP_IN_URL,
            {"email": "roundtrip@test.com", "collection_code": "JPUB01"},
            format="json",
        )
        user = User.objects.get(email="roundtrip@test.com")
        rsvp = RSVP.objects.get(user_code=user, action=RSVP.Action.MAGIC_LINK)

        resp = APIClient().get(f"/api/v1/auth/verify/{rsvp.token}/")
        assert resp.status_code == 200
        assert resp.data["action"] == "MAGIC_LINK"
        assert resp.data["invited_collection"] == "JPUB01"

    def test_verify_onboarding_join_has_no_redirect(self, join_setup):
        # No specific target → no invited_collection → SPA falls through to /welcome.
        join_setup["anon"].post(
            POP_IN_URL,
            {"email": "nodest@test.com"},
            format="json",
        )
        user = User.objects.get(email="nodest@test.com")
        rsvp = RSVP.objects.get(user_code=user, action=RSVP.Action.MAGIC_LINK)

        resp = APIClient().get(f"/api/v1/auth/verify/{rsvp.token}/")
        assert resp.status_code == 200
        assert "invited_collection" not in resp.data

    def test_public_code_magic_link_subject_names_collection(self, join_setup):
        # Joining a PUBLIC collection by code names it in the magic-link subject.
        mail.outbox.clear()
        join_setup["anon"].post(
            POP_IN_URL,
            {"email": "subj@test.com", "collection_code": "JPUB01"},
            format="json",
        )
        assert "Open community" in mail.outbox[0].subject

    def test_plain_popin_magic_link_subject_stays_generic(self, join_setup):
        # The onboarding fallback carries no collection → generic subject.
        mail.outbox.clear()
        join_setup["anon"].post(
            POP_IN_URL,
            {"email": "generic@test.com"},
            format="json",
        )
        assert mail.outbox[0].subject == "Hello, welcome to OIUEEI!"
