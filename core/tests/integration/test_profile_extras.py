"""
Integration tests for the optional profile extras: a Markdown `about` field and
a Cloudinary `photo` on User.
"""

import pytest


@pytest.mark.django_db
class TestProfileAbout:
    def test_update_about_persists(self, authenticated_client, user):
        res = authenticated_client.put(
            f"/api/v1/users/{user.code}/",
            {"about": "Find me at [my site](https://example.com)\n- one\n- two"},
            format="json",
        )
        assert res.status_code == 200
        assert "my site" in res.data["about"]
        user.refresh_from_db()
        assert user.about.startswith("Find me at")

    def test_about_rejects_html(self, authenticated_client, user):
        res = authenticated_client.put(
            f"/api/v1/users/{user.code}/",
            {"about": "<script>alert(1)</script>"},
            format="json",
        )
        assert res.status_code == 400

    def test_about_rejects_over_max_length(self, authenticated_client, user):
        res = authenticated_client.put(
            f"/api/v1/users/{user.code}/",
            {"about": "x" * 2001},
            format="json",
        )
        assert res.status_code == 400

    def test_clear_about(self, authenticated_client, user):
        user.about = "Some bio"
        user.save(update_fields=["about"])
        res = authenticated_client.put(f"/api/v1/users/{user.code}/", {"about": ""}, format="json")
        assert res.status_code == 200
        assert res.data["about"] == ""


@pytest.mark.django_db
class TestProfilePhoto:
    def test_update_photo_sets_photo_url(self, authenticated_client, user):
        res = authenticated_client.put(
            f"/api/v1/users/{user.code}/",
            {"photo": "oiueei/users/abc123"},
            format="json",
        )
        assert res.status_code == 200
        assert res.data["photo"] == "oiueei/users/abc123"
        assert res.data["photo_url"]  # cloudinary URL built from the public_id

    def test_photo_rejects_path_traversal(self, authenticated_client, user):
        res = authenticated_client.put(
            f"/api/v1/users/{user.code}/",
            {"photo": "../../../etc/passwd"},
            format="json",
        )
        assert res.status_code == 400

    def test_no_photo_yields_null_photo_url(self, authenticated_client, user):
        res = authenticated_client.get("/api/v1/auth/me/")
        assert res.status_code == 200
        assert res.data["photo"] == ""
        assert res.data["photo_url"] is None

    def test_clear_photo(self, authenticated_client, user):
        user.photo = "oiueei/users/abc123"
        user.save(update_fields=["photo"])
        res = authenticated_client.put(f"/api/v1/users/{user.code}/", {"photo": ""}, format="json")
        assert res.status_code == 200
        assert res.data["photo"] == ""
        assert res.data["photo_url"] is None


@pytest.mark.django_db
class TestPublicProfileExtras:
    def test_connected_user_sees_about_and_photo_url(
        self, authenticated_client2, user, user2, collection
    ):
        # Connect the two users: user2 is invited to user's collection.
        collection.invites.add(user2)
        user.about = "Hello from the owner"
        user.photo = "oiueei/users/owner1"
        user.save(update_fields=["about", "photo"])

        res = authenticated_client2.get(f"/api/v1/users/{user.code}/")
        assert res.status_code == 200
        assert res.data["about"] == "Hello from the owner"
        assert res.data["photo_url"]  # exposed for display
        # Raw public_id is NOT leaked on other people's profiles
        assert "photo" not in res.data
