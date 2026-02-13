"""
Scenario tests for complete user flows in OIUEEI.
"""

import pytest
from rest_framework import status
from rest_framework.test import APIClient
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, User


@pytest.mark.django_db
class TestMagicLinkFlow:
    """
    Scenario: Magic link authentication flow.
    1. User (already invited) requests magic link
    2. User verifies magic link
    3. User gets session with JWT
    """

    def test_complete_magic_link_flow(self, api_client):
        """Test complete magic link authentication flow for existing user."""
        email = "inviteduser@example.com"

        # Pre-condition: User must exist (was invited to a collection)
        user = User.objects.create(email=email)

        # Step 1: Request magic link
        response = api_client.post(
            "/api/v1/auth/request-link/",
            {"email": email},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        # Verify RSVP was created
        rsvp = RSVP.objects.get(user_code=user)

        # Step 2: Verify magic link
        response = api_client.get(f"/api/v1/auth/verify/{rsvp.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert "token" in response.data
        assert "refresh" in response.data
        assert response.data["user"]["code"] == user.code

        # Verify RSVP was deleted (one-time use)
        assert not RSVP.objects.filter(code=rsvp.code).exists()

        # Step 3: Use token to access protected endpoint
        token = response.data["token"]
        api_client.credentials(HTTP_AUTHORIZATION=f"Bearer {token}")
        response = api_client.get("/api/v1/auth/me/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["email"] == email


@pytest.mark.django_db
class TestCreateCollectionFlow:
    """
    Scenario: Create collection and add things.
    1. Login
    2. Create collection
    3. Add things to collection
    """

    def test_complete_create_collection_flow(self, authenticated_client, user):
        """Test complete collection creation flow."""
        # Step 1: Create collection
        response = authenticated_client.post(
            "/api/v1/collections/",
            {
                "headline": "My Birthday Wishlist",
                "description": "Things I want for my birthday",
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        collection_code = response.data["code"]

        # Step 2: Create thing and add to collection
        response = authenticated_client.post(
            "/api/v1/things/",
            {
                "headline": "Red Bicycle",
                "type": "GIFT_THING",
                "description": "A shiny red bicycle",
                "collection_code": collection_code,
            },
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        thing_code = response.data["code"]

        # Step 3: Verify thing is in collection
        response = authenticated_client.get(f"/api/v1/collections/{collection_code}/")
        assert response.status_code == status.HTTP_200_OK
        assert any(t["code"] == thing_code for t in response.data["things"])

        # Step 4: Verify user's collections and things are updated
        response = authenticated_client.get("/api/v1/auth/me/")
        assert collection_code in response.data["own_collections"]
        assert thing_code in response.data["things"]


@pytest.mark.django_db
class TestShareCollectionFlow:
    """
    Scenario: Share collection with friend.
    1. Owner creates collection with things
    2. Owner invites friend
    3. Friend views collection
    4. Friend reserves thing
    """

    def test_complete_share_collection_flow(self):
        """Test complete collection sharing flow."""
        client = APIClient()

        # Create owner
        owner = User.objects.create(
            code="OWNER1",
            email="owner@example.com",
            name="Owner",
        )
        owner_token = RefreshToken.for_user(owner)

        # Create friend
        friend = User.objects.create(
            code="FRND01",
            email="friend@example.com",
            name="Friend",
        )
        friend_token = RefreshToken.for_user(friend)

        # Step 1: Owner creates collection
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token.access_token}")
        response = client.post(
            "/api/v1/collections/",
            {"headline": "Gift Ideas"},
            format="json",
        )
        collection_code = response.data["code"]

        # Step 2: Owner creates thing
        response = client.post(
            "/api/v1/things/",
            {
                "headline": "Coffee Machine",
                "type": "GIFT_THING",
                "collection_code": collection_code,
            },
            format="json",
        )
        thing_code = response.data["code"]

        # Step 3: Owner invites friend
        response = client.post(
            f"/api/v1/collections/{collection_code}/invite/",
            {"email": "friend@example.com"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        # Step 3.5: Friend accepts invitation by verifying RSVP
        from core.models import RSVP

        rsvp = RSVP.objects.get(user_email="friend@example.com", action="COLLECTION_INVITE")
        response = client.get(f"/api/v1/auth/verify/{rsvp.code}/")
        assert response.status_code == status.HTTP_200_OK

        # Step 4: Friend views shared collections
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {friend_token.access_token}")
        friend.refresh_from_db()

        response = client.get("/api/v1/invited-collections/")
        assert response.status_code == status.HTTP_200_OK
        assert any(c["code"] == collection_code for c in response.data)

        # Step 5: Friend views collection
        response = client.get(f"/api/v1/collections/{collection_code}/")
        assert response.status_code == status.HTTP_200_OK
        assert any(t["code"] == thing_code for t in response.data["things"])

        # Step 6: Friend requests thing (BookingPeriod flow)
        response = client.post(f"/api/v1/things/{thing_code}/request/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Booking request sent"
        booking_code = response.data["booking_code"]

        # Thing status should be TAKEN (awaiting owner approval)
        from core.models import Thing

        thing = Thing.objects.get(code=thing_code)
        assert thing.status == "TAKEN"

        # Step 7: Owner accepts the booking via RSVP
        # Find the accept RSVP
        accept_rsvp = RSVP.objects.get(
            action="BOOKING_ACCEPT",
            target_code=booking_code,
        )
        response = client.get(f"/api/v1/rsvp/{accept_rsvp.code}/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["action"] == "BOOKING_ACCEPT"

        # Step 8: Verify thing is now INACTIVE and friend is in deal
        thing.refresh_from_db()
        assert thing.status == "INACTIVE"
        assert thing.available is False
        assert thing.deal.filter(code=friend.code).exists()


@pytest.mark.django_db
class TestFAQFlow:
    """
    Scenario: FAQ flow.
    1. Friend asks question about thing
    2. Owner answers question
    3. Question is visible to all
    """

    def test_complete_faq_flow(self):
        """Test complete FAQ flow."""
        client = APIClient()

        # Create owner
        owner = User.objects.create(
            code="OWNER2",
            email="owner2@example.com",
            name="Owner",
        )
        owner_token = RefreshToken.for_user(owner)

        # Create friend
        friend = User.objects.create(
            code="FRND02",
            email="friend2@example.com",
            name="Friend",
        )
        friend_token = RefreshToken.for_user(friend)

        # Owner creates collection and thing
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token.access_token}")
        response = client.post(
            "/api/v1/collections/",
            {"headline": "For Sale"},
            format="json",
        )
        collection_code = response.data["code"]

        response = client.post(
            "/api/v1/things/",
            {
                "headline": "Vintage Camera",
                "type": "SELL_THING",
                "fee": "150.00",
                "collection_code": collection_code,
            },
            format="json",
        )
        thing_code = response.data["code"]

        # Owner invites friend
        client.post(
            f"/api/v1/collections/{collection_code}/invite/",
            {"email": "friend2@example.com"},
            format="json",
        )

        # Friend accepts invitation by verifying RSVP
        rsvp = RSVP.objects.get(user_email="friend2@example.com", action="COLLECTION_INVITE")
        client.get(f"/api/v1/auth/verify/{rsvp.code}/")

        # Step 1: Friend asks question
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {friend_token.access_token}")
        response = client.post(
            f"/api/v1/things/{thing_code}/faq/",
            {"question": "Does it work with film?"},
            format="json",
        )
        assert response.status_code == status.HTTP_201_CREATED
        faq_code = response.data["code"]
        assert response.data["answer"] == ""

        # Step 2: Owner answers question
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {owner_token.access_token}")
        response = client.post(
            f"/api/v1/faq/{faq_code}/answer/",
            {"answer": "Yes, it works with 35mm film!"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK
        assert response.data["answer"] == "Yes, it works with 35mm film!"

        # Step 3: Friend can see answered question
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {friend_token.access_token}")
        response = client.get(f"/api/v1/things/{thing_code}/faq/")
        assert response.status_code == status.HTTP_200_OK
        assert len(response.data["results"]) == 1
        assert response.data["results"][0]["answer"] == "Yes, it works with 35mm film!"


@pytest.mark.django_db
class TestCompleteUserJourney:
    """
    Scenario: Complete user journey from signup to transaction.
    """

    def test_complete_user_journey(self):
        """Test a complete user journey through the application."""
        client = APIClient()

        # === Alice signs up and creates a wishlist ===

        # Alice was invited earlier (user must exist first in invite-only system)
        alice = User.objects.create(email="alice@example.com")

        # Alice requests magic link
        response = client.post(
            "/api/v1/auth/request-link/",
            {"email": "alice@example.com"},
            format="json",
        )
        assert response.status_code == status.HTTP_200_OK

        alice_rsvp = RSVP.objects.get(user_code=alice)

        # Alice verifies and gets token
        response = client.get(f"/api/v1/auth/verify/{alice_rsvp.code}/")
        alice_token = response.data["token"]

        # Alice updates profile
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {alice_token}")
        client.put(
            f"/api/v1/users/{alice.code}/",
            {"name": "Alice", "headline": "Birthday coming up!"},
            format="json",
        )

        # Alice creates birthday wishlist
        response = client.post(
            "/api/v1/collections/",
            {
                "headline": "Alice's Birthday Wishlist",
                "description": "Things I'd love for my birthday!",
            },
            format="json",
        )
        wishlist_code = response.data["code"]

        # Alice adds items to wishlist
        items = [
            {"headline": "Wireless Headphones", "fee": "100.00"},
            {"headline": "Cozy Blanket", "fee": "50.00"},
            {"headline": "Book: Clean Code", "fee": "35.00"},
        ]

        thing_codes = []
        for item in items:
            response = client.post(
                "/api/v1/things/",
                {
                    **item,
                    "type": "GIFT_THING",
                    "collection_code": wishlist_code,
                },
                format="json",
            )
            thing_codes.append(response.data["code"])

        # === Alice invites Bob and Charlie ===

        response = client.post(
            f"/api/v1/collections/{wishlist_code}/invite/",
            {"email": "bob@example.com"},
            format="json",
        )
        bob = User.objects.get(email="bob@example.com")

        response = client.post(
            f"/api/v1/collections/{wishlist_code}/invite/",
            {"email": "charlie@example.com"},
            format="json",
        )
        charlie = User.objects.get(email="charlie@example.com")

        # === Bob and Charlie accept invitations ===

        bob_rsvp = RSVP.objects.get(user_email="bob@example.com", action="COLLECTION_INVITE")
        client.get(f"/api/v1/auth/verify/{bob_rsvp.code}/")

        charlie_rsvp = RSVP.objects.get(
            user_email="charlie@example.com", action="COLLECTION_INVITE"
        )
        client.get(f"/api/v1/auth/verify/{charlie_rsvp.code}/")

        # === Bob logs in and requests an item ===

        bob_token = RefreshToken.for_user(bob)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {bob_token.access_token}")

        # Bob views shared collections
        response = client.get("/api/v1/invited-collections/")
        assert len(response.data) == 1

        # Bob requests headphones (BookingPeriod flow)
        response = client.post(f"/api/v1/things/{thing_codes[0]}/request/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Booking request sent"
        bob_booking_code = response.data["booking_code"]

        # Alice accepts Bob's request
        bob_accept_rsvp = RSVP.objects.get(
            action="BOOKING_ACCEPT",
            target_code=bob_booking_code,
        )
        client.get(f"/api/v1/rsvp/{bob_accept_rsvp.code}/")

        # === Charlie asks a question ===

        charlie_token = RefreshToken.for_user(charlie)
        client.credentials(HTTP_AUTHORIZATION=f"Bearer {charlie_token.access_token}")

        # Charlie asks about the book
        response = client.post(
            f"/api/v1/things/{thing_codes[2]}/faq/",
            {"question": "Is it the paperback or hardcover?"},
            format="json",
        )
        faq_code = response.data["code"]

        # === Alice answers the question ===

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {alice_token}")
        response = client.post(
            f"/api/v1/faq/{faq_code}/answer/",
            {"answer": "Paperback is fine!"},
            format="json",
        )

        # === Charlie requests the book ===

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {charlie_token.access_token}")
        response = client.post(f"/api/v1/things/{thing_codes[2]}/request/")
        assert response.status_code == status.HTTP_200_OK
        assert response.data["message"] == "Booking request sent"
        charlie_booking_code = response.data["booking_code"]

        # Alice accepts Charlie's request
        charlie_accept_rsvp = RSVP.objects.get(
            action="BOOKING_ACCEPT",
            target_code=charlie_booking_code,
        )
        client.get(f"/api/v1/rsvp/{charlie_accept_rsvp.code}/")

        # === Final state verification ===

        client.credentials(HTTP_AUTHORIZATION=f"Bearer {alice_token}")

        # Alice sees her collection status
        response = client.get(f"/api/v1/collections/{wishlist_code}/")
        assert len(response.data["things"]) == 3

        # Check reservations
        response = client.get(f"/api/v1/things/{thing_codes[0]}/")
        assert bob.code in response.data["deal"]

        response = client.get(f"/api/v1/things/{thing_codes[2]}/")
        assert charlie.code in response.data["deal"]

        # Blanket still available
        response = client.get(f"/api/v1/things/{thing_codes[1]}/")
        assert response.data["available"] is True
