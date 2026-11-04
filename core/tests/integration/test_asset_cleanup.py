"""Stored-asset cleanup when a Thing / Collection / User is deleted.

The cleanup runs on transaction commit, so every test wraps the delete in
``django_capture_on_commit_callbacks(execute=True)`` and patches
``storage.delete`` (no real network calls).

What these protect is that a deleted record takes its objects with it — the
bucket has no notion of a foreign key, so nothing else will ever notice they are
unreachable — and, just as importantly, that a delete which *fails* to reach the
bucket still deletes the row. An orphaned object costs storage; a delete that
raises costs the user their action.
"""

from unittest.mock import patch

import pytest
from django.db import transaction

from core.models import Collection, NetworkPoint, Thing, User
from core.services import asset_cleanup


@pytest.mark.django_db
class TestAssetCleanup:
    def test_thing_delete_destroys_thumbnail_and_gallery(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="lala@your-domain.test")
        thing = Thing.objects.create(
            owner=owner,
            headline="Drill",
            type="GIFT_THING",
            thumbnail="oiueei/things/cover",
            gallery=["oiueei/things/g1", "oiueei/things/g2"],
        )
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                thing.delete()

        destroyed = {call.args[0] for call in destroy.call_args_list}
        assert destroyed == {
            "oiueei/things/cover",
            "oiueei/things/g1",
            "oiueei/things/g2",
        }

    def test_collection_delete_destroys_thumbnail(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="lele@your-domain.test")
        coll = Collection.objects.create(
            owner=owner, headline="C", thumbnail="oiueei/collections/c1"
        )
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                coll.delete()

        assert [c.args[0] for c in destroy.call_args_list] == ["oiueei/collections/c1"]

    def test_a_point_delete_destroys_its_logo(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="lele2@your-domain.test")
        coll = Collection.objects.create(owner=owner, headline="C", mode="NETWORK")
        point = NetworkPoint.objects.create(
            collection=coll, user=owner, logo="oiueei/collections/logo1"
        )
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                point.delete()

        assert [c.args[0] for c in destroy.call_args_list] == ["oiueei/collections/logo1"]

    def test_a_point_that_goes_with_its_dinamizador_takes_its_logo(
        self, django_capture_on_commit_callbacks
    ):
        owner = User.objects.create(email="lala3@your-domain.test")
        member = User.objects.create(email="lili3@your-domain.test")
        coll = Collection.objects.create(owner=owner, headline="C", mode="NETWORK")
        NetworkPoint.objects.create(collection=coll, user=member, logo="oiueei/collections/logo2")
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                coll.points.filter(user=member).delete()

        assert [c.args[0] for c in destroy.call_args_list] == ["oiueei/collections/logo2"]

    def test_replacing_a_logo_destroys_the_old_one_only(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="lolo3@your-domain.test")
        coll = Collection.objects.create(owner=owner, headline="C", mode="NETWORK")
        NetworkPoint.objects.create(collection=coll, user=owner, logo="oiueei/collections/old")
        point = NetworkPoint.objects.get(user=owner)
        point.logo = "oiueei/collections/new"
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                point.save()

        assert [c.args[0] for c in destroy.call_args_list] == ["oiueei/collections/old"]

    def test_the_orphan_sweep_keeps_a_logo_a_point_holds(self, db):
        owner = User.objects.create(email="lulu3@your-domain.test")
        coll = Collection.objects.create(owner=owner, headline="C", mode="NETWORK")
        NetworkPoint.objects.create(collection=coll, user=owner, logo="oiueei/collections/kept")

        assert "oiueei/collections/kept" in asset_cleanup.referenced_keys()
        assert asset_cleanup.is_referenced("oiueei/collections/kept")

    def test_user_delete_cascades_to_collection_and_thing_assets(
        self, django_capture_on_commit_callbacks
    ):
        owner = User.objects.create(email="lili@your-domain.test", photo="oiueei/users/p1")
        Collection.objects.create(owner=owner, headline="C", thumbnail="oiueei/collections/c2")
        Thing.objects.create(
            owner=owner, headline="T", type="GIFT_THING", thumbnail="oiueei/things/t1"
        )
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                owner.delete()  # FK cascade deletes the collection and the thing

        destroyed = {call.args[0] for call in destroy.call_args_list}
        assert {"oiueei/users/p1", "oiueei/collections/c2", "oiueei/things/t1"} <= destroyed

    def test_empty_image_fields_destroy_nothing(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="lolo@your-domain.test")  # no photo
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                owner.delete()
        destroy.assert_not_called()

    def test_a_storage_failure_does_not_break_the_delete(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="lulu@your-domain.test")
        thing = Thing.objects.create(
            owner=owner, headline="T", type="GIFT_THING", thumbnail="oiueei/things/boom"
        )
        with patch("core.services.storage.delete", side_effect=RuntimeError("bucket down")):
            with django_capture_on_commit_callbacks(execute=True):
                thing.delete()  # must not raise
        assert not Thing.objects.filter(code=thing.code).exists()

    def test_seed_reset_does_not_touch_the_bucket(self, django_capture_on_commit_callbacks):
        from django.core.management import call_command

        call_command("seed_demo")  # demo things carry real shared storage keys
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                call_command("seed_demo", "--reset")  # deletes then re-creates
        destroy.assert_not_called()

    def test_suspended_context_blocks_cleanup(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="lala1@your-domain.test", photo="oiueei/users/keep")
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                with asset_cleanup.suspended():
                    owner.delete()
        destroy.assert_not_called()


@pytest.mark.django_db
class TestARollbackKeepsTheImages:
    """A delete that does not survive its transaction keeps its objects.

    This is what ``transaction.on_commit`` buys, and nothing tested it. Every
    other test in this file runs its delete inside
    ``django_capture_on_commit_callbacks(execute=True)`` and then asserts *which*
    keys were destroyed — which is true whether the destroy was deferred to
    commit or fired inline, so replacing ``on_commit(...)`` with a direct call
    left the whole suite green.

    It matters because a bucket delete is not undoable. A request that removes a
    thing and then fails — a later validation, a 500, a rolled-back
    ``atomic()`` — leaves the row exactly where it was, and the photographs have
    to still be there when the owner retries.
    """

    def test_a_rolled_back_thing_delete_destroys_nothing(self):
        owner = User.objects.create(email="lele1@your-domain.test")
        thing = Thing.objects.create(
            owner=owner,
            headline="Drill",
            type="GIFT_THING",
            thumbnail="oiueei/things/cover",
            gallery=["oiueei/things/g1"],
        )
        # Read before the delete: Django clears the PK on the in-memory instance.
        code = thing.code

        with patch("core.services.storage.delete") as destroy:
            with pytest.raises(RuntimeError):
                with transaction.atomic():
                    thing.delete()
                    raise RuntimeError("something later in the request failed")

        destroy.assert_not_called()
        assert Thing.objects.filter(code=code).exists(), "the row came back"

    def test_a_rolled_back_user_delete_keeps_the_whole_cascade_s_assets(self):
        """The cascade is the case that would hurt most: a user delete reaches
        their collections and things too, so an inline destroy would empty
        several buckets' worth of objects for a transaction that never committed.
        """
        owner = User.objects.create(email="lili1@your-domain.test", photo="oiueei/users/face")
        collection = Collection.objects.create(
            code="RBC001", owner=owner, headline="Group", thumbnail="oiueei/collections/cover"
        )
        Thing.objects.create(
            owner=owner, headline="Saw", type="GIFT_THING", thumbnail="oiueei/things/saw"
        )
        owner_code = owner.code

        with patch("core.services.storage.delete") as destroy:
            with pytest.raises(RuntimeError):
                with transaction.atomic():
                    owner.delete()
                    raise RuntimeError("rolled back")

        destroy.assert_not_called()
        assert User.objects.filter(code=owner_code).exists()
        assert Collection.objects.filter(code=collection.code).exists()

    def test_the_same_delete_committed_does_destroy_them(self, django_capture_on_commit_callbacks):
        """The counterpart, so the two above can't pass by the cleanup being
        broken outright."""
        owner = User.objects.create(email="lolo1@your-domain.test")
        thing = Thing.objects.create(
            owner=owner, headline="Drill", type="GIFT_THING", thumbnail="oiueei/things/cover2"
        )

        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                with transaction.atomic():
                    thing.delete()

        destroy.assert_called_once_with("oiueei/things/cover2")


@pytest.mark.django_db
class TestSeedPoolIsNeverDestroyed:
    """The demo's fixture pool survives any delete.

    These exist because the pool was destroyed for real: deleting the demo from
    the Django admin emptied the whole ``oiueei/seed/`` folder. ``seed_demo
    --reset`` was safe because it suspends the mechanism; every other door —
    the admin, a cascade, a shell delete — was not. The pool is shared by every
    database that has ever seeded, so one row's delete must never reach it.
    """

    def test_thing_delete_spares_seed_keys(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="lulu1@your-domain.test")
        thing = Thing.objects.create(
            owner=owner,
            headline="Demo drill",
            type="GIFT_THING",
            thumbnail="oiueei/seed/l1l112",
            gallery=["oiueei/seed/l1l112_b"],
        )
        with patch.object(asset_cleanup.storage, "delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                thing.delete()
        destroy.assert_not_called()

    def test_collection_and_user_deletes_spare_seed_keys(self, django_capture_on_commit_callbacks):
        owner = User.objects.create(email="lala2@your-domain.test", photo="oiueei/seed/1u1uPH")
        collection = Collection.objects.create(
            owner=owner, headline="Demo group", thumbnail="oiueei/seed/l1l1C1"
        )
        with patch.object(asset_cleanup.storage, "delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                collection.delete()
                owner.delete()
        destroy.assert_not_called()

    def test_a_real_upload_alongside_a_seed_key_still_goes(
        self, django_capture_on_commit_callbacks
    ):
        """The skip is per key, not per record — a genuine upload is still cleaned."""
        owner = User.objects.create(email="lele2@your-domain.test")
        thing = Thing.objects.create(
            owner=owner,
            headline="Half and half",
            type="GIFT_THING",
            thumbnail="oiueei/seed/l1l112",
            gallery=["oiueei/things/a-real-upload"],
        )
        with patch.object(asset_cleanup.storage, "delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                thing.delete()
        destroy.assert_called_once_with("oiueei/things/a-real-upload")


@pytest.mark.django_db
class TestAKeyAnotherRecordHoldsIsKept:
    """Deleting a record never deletes a photo another record still shows.

    A row does not own its keys. A key is the path of its photo's public URL, and
    ``ImageIdField`` binds it to a folder, not to whoever uploaded it — so anyone
    who can see a photo can save its key on a thing of their own. Before
    2026-10-02, deleting that thing deleted the photo for its real owner too.
    """

    BORROWED = "oiueei/things/someone-elses-photo"

    def test_a_member_cannot_delete_someone_elses_photo_by_borrowing_its_key(
        self, authenticated_client, collection, user2, django_capture_on_commit_callbacks
    ):
        theirs = Thing.objects.create(
            owner=user2, headline="Their lamp", type="GIFT_THING", thumbnail=self.BORROWED
        )
        created = authenticated_client.post(
            "/api/v1/things/",
            {
                "headline": "Mine, with their photo",
                "type": "GIFT_THING",
                "collection_code": collection.code,
                "thumbnail": self.BORROWED,
            },
            format="json",
        )
        assert created.status_code == 201

        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                deleted = authenticated_client.delete(f"/api/v1/things/{created.data['code']}/")

        assert deleted.status_code == 204
        destroy.assert_not_called()
        theirs.refresh_from_db()
        assert theirs.thumbnail == self.BORROWED

    @pytest.mark.parametrize(
        "holder",
        [
            lambda u: Thing.objects.create(
                owner=u, headline="x", type="GIFT_THING", thumbnail="oiueei/things/shared"
            ),
            lambda u: Thing.objects.create(
                owner=u,
                headline="x",
                type="GIFT_THING",
                gallery=["oiueei/things/other", "oiueei/things/shared"],
            ),
            lambda u: setattr(u, "photo", "oiueei/things/shared") or u.save(),
            lambda u: Collection.objects.create(
                owner=u, headline="x", thumbnail="oiueei/things/shared"
            ),
            lambda u: Collection.objects.create(
                owner=u, headline="x", welcome_doc="oiueei/things/shared"
            ),
        ],
        ids=["thing-thumbnail", "thing-gallery", "user-photo", "cover", "welcome-doc"],
    )
    def test_any_column_that_still_holds_the_key_keeps_it(
        self, holder, django_capture_on_commit_callbacks
    ):
        holder(User.objects.create(email="lili2@your-domain.test"))
        deleting = Thing.objects.create(
            owner=User.objects.create(email="lolo2@your-domain.test"),
            headline="Going",
            type="GIFT_THING",
            thumbnail="oiueei/things/shared",
            gallery=["oiueei/things/only-mine"],
        )
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                deleting.delete()

        # Its own, unshared key still goes: the check spares keys, not records.
        assert [c.args[0] for c in destroy.call_args_list] == ["oiueei/things/only-mine"]

    def test_a_key_that_only_contains_the_deleted_key_does_not_save_it(
        self, django_capture_on_commit_callbacks
    ):
        # The gallery check matches text first; a longer key with this one as its
        # prefix is a different object and must not keep it alive.
        owner = User.objects.create(email="lulu2@your-domain.test")
        Thing.objects.create(
            owner=owner, headline="x", type="GIFT_THING", gallery=["oiueei/things/pic-2"]
        )
        deleting = Thing.objects.create(
            owner=owner, headline="y", type="GIFT_THING", gallery=["oiueei/things/pic"]
        )
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                deleting.delete()

        assert [c.args[0] for c in destroy.call_args_list] == ["oiueei/things/pic"]

    def test_once_the_last_holder_goes_the_key_goes_too(self, django_capture_on_commit_callbacks):
        first = Thing.objects.create(
            owner=User.objects.create(email="lala7@your-domain.test"),
            headline="a",
            type="GIFT_THING",
            thumbnail="oiueei/things/shared",
        )
        second = Thing.objects.create(
            owner=User.objects.create(email="lele3@your-domain.test"),
            headline="b",
            type="GIFT_THING",
            thumbnail="oiueei/things/shared",
        )
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                first.delete()
            destroy.assert_not_called()
            with django_capture_on_commit_callbacks(execute=True):
                second.delete()

        assert [c.args[0] for c in destroy.call_args_list] == ["oiueei/things/shared"]


def _destroyed(destroy):
    return [call.args[0] for call in destroy.call_args_list]


@pytest.mark.django_db
class TestASaveThatDropsAPhotoDestroysIt:
    """Removing or replacing a photo takes the old object out of the bucket.

    Until 2026-10-02 only deleting the whole record did. A removed profile
    photo, a swapped cover or a photo taken out of a gallery stayed in the
    bucket, unreachable, until someone ran the orphan sweep by hand inside its
    30-day window — and past it, for good, against the ``/legal`` promise that
    a photo goes when you remove it.
    """

    def test_removing_your_profile_photo_destroys_it(
        self, authenticated_client, user, django_capture_on_commit_callbacks
    ):
        user.photo = "oiueei/users/me-old"
        user.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                res = authenticated_client.put(
                    f"/api/v1/users/{user.code}/", {"photo": ""}, format="json"
                )
        assert res.status_code == 200
        assert _destroyed(destroy) == ["oiueei/users/me-old"]

    def test_replacing_your_profile_photo_destroys_only_the_old_one(
        self, authenticated_client, user, django_capture_on_commit_callbacks
    ):
        user.photo = "oiueei/users/me-old"
        user.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                res = authenticated_client.put(
                    f"/api/v1/users/{user.code}/", {"photo": "oiueei/users/me-new"}, format="json"
                )
        assert res.status_code == 200
        assert _destroyed(destroy) == ["oiueei/users/me-old"]

    def test_a_photo_taken_out_of_a_gallery_goes_and_the_rest_stay(
        self, authenticated_client, thing, django_capture_on_commit_callbacks
    ):
        thing.gallery = ["oiueei/things/g1", "oiueei/things/g2", "oiueei/things/g3"]
        thing.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                res = authenticated_client.patch(
                    f"/api/v1/things/{thing.code}/",
                    {"gallery": ["oiueei/things/g3", "oiueei/things/g1"]},
                    format="json",
                )
        assert res.status_code == 200
        assert _destroyed(destroy) == ["oiueei/things/g2"]

    def test_a_gallery_edited_in_place_still_reads_as_a_change(
        self, thing, django_capture_on_commit_callbacks
    ):
        # Code that mutates the stored list rather than assigning a new one must
        # not slip past: the remembered keys are a copy, not the list itself.
        thing.gallery = ["oiueei/things/g1", "oiueei/things/g2"]
        thing.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                thing.gallery.remove("oiueei/things/g1")
                thing.save()
        assert _destroyed(destroy) == ["oiueei/things/g1"]

    def test_reordering_a_gallery_destroys_nothing(
        self, authenticated_client, thing, django_capture_on_commit_callbacks
    ):
        thing.gallery = ["oiueei/things/g1", "oiueei/things/g2"]
        thing.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                authenticated_client.patch(
                    f"/api/v1/things/{thing.code}/",
                    {"gallery": ["oiueei/things/g2", "oiueei/things/g1"]},
                    format="json",
                )
        destroy.assert_not_called()

    def test_a_new_cover_on_a_thing_destroys_the_old_one(
        self, authenticated_client, thing, django_capture_on_commit_callbacks
    ):
        thing.thumbnail = "oiueei/things/cover-old"
        thing.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                res = authenticated_client.patch(
                    f"/api/v1/things/{thing.code}/",
                    {"thumbnail": "oiueei/things/cover-new"},
                    format="json",
                )
        assert res.status_code == 200
        assert _destroyed(destroy) == ["oiueei/things/cover-old"]

    def test_a_collection_drops_its_cover_and_its_welcome_pdf(
        self, authenticated_client, collection, django_capture_on_commit_callbacks
    ):
        collection.thumbnail = "oiueei/collections/cover-old"
        collection.welcome_doc = "oiueei/documents/rules-old"
        collection.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                res = authenticated_client.patch(
                    f"/api/v1/collections/{collection.code}/",
                    {"thumbnail": "oiueei/collections/cover-new", "welcome_doc": ""},
                    format="json",
                )
        assert res.status_code == 200
        assert set(_destroyed(destroy)) == {
            "oiueei/collections/cover-old",
            "oiueei/documents/rules-old",
        }

    def test_a_save_that_rolls_back_destroys_nothing(self, user):
        user.photo = "oiueei/users/kept"
        user.save()
        with patch("core.services.storage.delete") as destroy:
            with pytest.raises(RuntimeError):
                with transaction.atomic():
                    user.photo = ""
                    user.save()
                    raise RuntimeError("the request failed after the save")
        destroy.assert_not_called()

    def test_a_column_left_out_of_update_fields_drops_nothing(
        self, user, django_capture_on_commit_callbacks
    ):
        user.photo = "oiueei/users/stored"
        user.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                user.photo = "oiueei/users/never-written"
                user.save(update_fields=["name"])
            destroy.assert_not_called()
            # The row still holds the stored key, so that is what a real write drops.
            with django_capture_on_commit_callbacks(execute=True):
                user.save()
        assert _destroyed(destroy) == ["oiueei/users/stored"]

    def test_a_seed_photo_is_never_destroyed_by_a_save(
        self, thing, django_capture_on_commit_callbacks
    ):
        thing.thumbnail = "oiueei/seed/lala-cup"
        thing.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                thing.thumbnail = "oiueei/things/mine"
                thing.save()
        destroy.assert_not_called()

    def test_a_dropped_key_another_record_holds_is_kept(
        self, thing, user2, django_capture_on_commit_callbacks
    ):
        thing.thumbnail = "oiueei/things/shared"
        thing.save()
        Thing.objects.create(
            owner=user2, headline="x", type="GIFT_THING", thumbnail="oiueei/things/shared"
        )
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                thing.thumbnail = ""
                thing.save()
        destroy.assert_not_called()

    def test_suspended_blocks_a_save_too(self, user, django_capture_on_commit_callbacks):
        user.photo = "oiueei/users/keep"
        user.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                with asset_cleanup.suspended():
                    user.photo = ""
                    user.save()
        destroy.assert_not_called()

    def test_a_deferred_photo_column_is_never_read_nor_destroyed(
        self, user, django_assert_num_queries, django_capture_on_commit_callbacks
    ):
        user.photo = "oiueei/users/deferred"
        user.save()
        # Remembering the stored keys must not load a column the query deferred:
        # one query for the row, not one more per deferred photo.
        with django_assert_num_queries(1):
            loaded = User.objects.only("code", "name").get(code=user.code)
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                loaded.name = "Renamed"
                loaded.save(update_fields=["name"])
        destroy.assert_not_called()
