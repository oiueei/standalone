"""
Integration tests for the thing transfers endpoint.
"""

from datetime import date, timedelta

import pytest

from core.models.transfer import ThingTransfer


@pytest.mark.django_db
class TestThingTransferEndpoint:
    """Tests for GET /api/v1/things/{code}/transfers/."""

    def test_owner_can_view_transfers(self, authenticated_client, user, user2, thing):
        """Owner should see transfer history."""
        ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            lent_date=date.today() - timedelta(days=7),
            returned_date=date.today(),
        )

        response = authenticated_client.get(f"/api/v1/things/{thing.code}/transfers/")
        assert response.status_code == 200
        data = response.json()
        assert data["total_transfers"] == 1
        assert data["unique_homes"] == 2
        assert len(data["transfers"]) == 1
        assert data["transfers"][0]["from_user"] == user.code
        assert data["transfers"][0]["to_user"] == user2.code

    def test_invited_user_can_view_transfers(
        self, authenticated_client2, user, user2, thing, collection
    ):
        """Invited user should see transfer history."""
        collection.invites.add(user2)
        ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            lent_date=date.today(),
        )

        response = authenticated_client2.get(f"/api/v1/things/{thing.code}/transfers/")
        assert response.status_code == 200
        data = response.json()
        assert data["total_transfers"] == 1
        assert data["current_holder"] == user2.code

    def test_uninvited_user_cannot_view_transfers(self, authenticated_client2, user, user2, thing):
        """Uninvited user should get 403."""
        response = authenticated_client2.get(f"/api/v1/things/{thing.code}/transfers/")
        assert response.status_code == 403

    def test_empty_transfers(self, authenticated_client, thing):
        """Should return zero stats for a thing with no transfers."""
        response = authenticated_client.get(f"/api/v1/things/{thing.code}/transfers/")
        assert response.status_code == 200
        data = response.json()
        assert data["total_transfers"] == 0
        assert data["unique_homes"] == 0
        assert data["current_holder"] is None
        assert data["transfers"] == []

    def test_current_holder_shown_for_unreturned(self, authenticated_client, user, user2, thing):
        """Current holder should reflect the most recent unreturned transfer."""
        ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            lent_date=date.today(),
        )

        response = authenticated_client.get(f"/api/v1/things/{thing.code}/transfers/")
        data = response.json()
        assert data["current_holder"] == user2.code
        assert data["current_holder_name"] == user2.name

    def test_transfer_count_in_thing_serializer(self, authenticated_client, user, user2, thing):
        """Thing detail should include transfer_count."""
        ThingTransfer.objects.create(
            thing=thing,
            from_user=user,
            to_user=user2,
            lent_date=date.today(),
        )

        response = authenticated_client.get(f"/api/v1/things/{thing.code}/")
        assert response.status_code == 200
        assert response.json()["transfer_count"] == 1
