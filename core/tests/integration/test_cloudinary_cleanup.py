"""Cloudinary asset cleanup when a Thing / Collection / User is deleted.

The cleanup runs on transaction commit, so every test wraps the delete in
``django_capture_on_commit_callbacks(execute=True)`` and patches
``cloudinary.uploader.destroy`` (no real network calls).
"""

from unittest.mock import patch

import pytest

from core.models import Collection, Thing, User
from core.services import cloudinary_cleanup


@pytest.mark.django_db
class TestCloudinaryCleanup:
    def test_thing_delete_destroys_thumbnail_and_gallery(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="o1@example.com")
        thing = Thing.objects.create(
            owner=owner,
            headline="Drill",
            type="GIFT_THING",
            thumbnail="oiueei/things/cover",
            gallery=["oiueei/things/g1", "oiueei/things/g2"],
        )
        with patch("cloudinary.uploader.destroy") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                thing.delete()

        destroyed = {call.args[0] for call in destroy.call_args_list}
        assert destroyed == {
            "oiueei/things/cover",
            "oiueei/things/g1",
            "oiueei/things/g2",
        }

    def test_collection_delete_destroys_thumbnail(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="o2@example.com")
        coll = Collection.objects.create(
            owner=owner, headline="C", thumbnail="oiueei/collections/c1"
        )
        with patch("cloudinary.uploader.destroy") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                coll.delete()

        assert [c.args[0] for c in destroy.call_args_list] == ["oiueei/collections/c1"]

    def test_user_delete_cascades_to_collection_and_thing_assets(
        self, django_capture_on_commit_callbacks
    ):
        owner = User.objects.create(email="o3@example.com", photo="oiueei/users/p1")
        Collection.objects.create(owner=owner, headline="C", thumbnail="oiueei/collections/c2")
        Thing.objects.create(
            owner=owner, headline="T", type="GIFT_THING", thumbnail="oiueei/things/t1"
        )
        with patch("cloudinary.uploader.destroy") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                owner.delete()  # FK cascade deletes the collection and the thing

        destroyed = {call.args[0] for call in destroy.call_args_list}
        assert {"oiueei/users/p1", "oiueei/collections/c2", "oiueei/things/t1"} <= destroyed

    def test_empty_image_fields_destroy_nothing(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="o4@example.com")  # no photo
        with patch("cloudinary.uploader.destroy") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                owner.delete()
        destroy.assert_not_called()

    def test_cloudinary_failure_does_not_break_the_delete(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="o5@example.com")
        thing = Thing.objects.create(
            owner=owner, headline="T", type="GIFT_THING", thumbnail="oiueei/things/boom"
        )
        with patch("cloudinary.uploader.destroy", side_effect=RuntimeError("cloudinary down")):
            with django_capture_on_commit_callbacks(execute=True):
                thing.delete()  # must not raise
        assert not Thing.objects.filter(code=thing.code).exists()

    def test_seed_reset_does_not_touch_cloudinary(self, django_capture_on_commit_callbacks):
        from django.core.management import call_command

        call_command("seed_demo")  # demo things carry real shared public ids
        with patch("cloudinary.uploader.destroy") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                call_command("seed_demo", "--reset")  # deletes then re-creates
        destroy.assert_not_called()

    def test_suspended_context_blocks_cleanup(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="o6@example.com", photo="oiueei/users/keep")
        with patch("cloudinary.uploader.destroy") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                with cloudinary_cleanup.suspended():
                    owner.delete()
        destroy.assert_not_called()
