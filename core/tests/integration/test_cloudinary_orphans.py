"""Integration tests for the `cleanup_orphan_images` command (#9).

Cloudinary is mocked — we assert the command's classification logic: which
assets it treats as orphans, that dry-run deletes nothing, that --commit deletes
only orphans, and that referenced / seed / out-of-window assets are always kept.
"""

from datetime import timedelta
from io import StringIO
from unittest.mock import patch

import pytest
from django.core.management import call_command
from django.utils import timezone

from core.models import Collection, Thing

pytestmark = pytest.mark.django_db


def _iso(dt):
    return dt.strftime("%Y-%m-%dT%H:%M:%SZ")


def _asset(public_id, *, days_ago=2):
    return {"public_id": public_id, "created_at": _iso(timezone.now() - timedelta(days=days_ago))}


def _run(resources, commit=False):
    """Run the command with Cloudinary's list mocked; return (out, delete_mock)."""
    out = StringIO()
    with (
        patch(
            "cloudinary.api.resources", return_value={"resources": resources, "next_cursor": None}
        ),
        patch("cloudinary.api.delete_resources", return_value={"deleted": {}}) as delete_mock,
    ):
        call_command("cleanup_orphan_images", commit=commit, stdout=out)
    return out.getvalue(), delete_mock


def test_dry_run_lists_orphan_but_deletes_nothing():
    out, delete_mock = _run([_asset("oiueei/things/orphan1")])
    assert "orphan: oiueei/things/orphan1" in out
    assert "DRY-RUN" in out
    delete_mock.assert_not_called()


def test_commit_deletes_only_orphans(user):
    Thing.objects.create(
        code="THKEEP",
        type="GIFT_THING",
        owner=user,
        headline="Keep",
        thumbnail="oiueei/things/keep",
    )
    resources = [_asset("oiueei/things/keep"), _asset("oiueei/things/orphan1")]
    out, delete_mock = _run(resources, commit=True)

    delete_mock.assert_called_once()
    deleted_ids = delete_mock.call_args.args[0]
    assert deleted_ids == ["oiueei/things/orphan1"]
    assert "Deleted 1 orphan" in out


@pytest.mark.parametrize(
    "make_ref",
    [
        lambda u: Thing.objects.create(
            code="THREF1", type="GIFT_THING", owner=u, headline="x", thumbnail="oiueei/things/ref"
        ),
        lambda u: Thing.objects.create(
            code="THREF2", type="GIFT_THING", owner=u, headline="x", gallery=["oiueei/things/ref"]
        ),
        lambda u: setattr(u, "photo", "oiueei/things/ref") or u.save(),
        lambda u: Collection.objects.create(
            code="COREF1", owner=u, headline="x", thumbnail="oiueei/things/ref"
        ),
    ],
)
def test_referenced_assets_are_kept(user, make_ref):
    make_ref(user)
    out, delete_mock = _run([_asset("oiueei/things/ref")], commit=True)
    delete_mock.assert_not_called()
    assert "1 in use" in out


def test_seed_folder_is_never_touched():
    # Unreferenced, old enough, in window — but under oiueei/seed/, so untouchable.
    out, delete_mock = _run([_asset("oiueei/seed/lala-cup")], commit=True)
    delete_mock.assert_not_called()
    assert "1 seed" in out


def test_recent_uploads_are_skipped():
    # 1 hour old → younger than the 24h min-age → treated as maybe-in-flight.
    out, delete_mock = _run([_asset("oiueei/things/fresh", days_ago=0)], commit=True)
    delete_mock.assert_not_called()
    assert "outside the age window" in out


def test_old_uploads_are_skipped():
    out, delete_mock = _run([_asset("oiueei/things/ancient", days_ago=40)], commit=True)
    delete_mock.assert_not_called()
    assert "1 orphan" not in out  # counted under the age window, not as an orphan


def test_pagination_walks_all_pages():
    pages = [
        {"resources": [_asset("oiueei/things/orphan1")], "next_cursor": "cur"},
        {"resources": [_asset("oiueei/things/orphan2")], "next_cursor": None},
    ]
    out = StringIO()
    with (
        patch("cloudinary.api.resources", side_effect=pages),
        patch("cloudinary.api.delete_resources", return_value={"deleted": {}}) as delete_mock,
    ):
        call_command("cleanup_orphan_images", commit=True, stdout=out)
    deleted_ids = delete_mock.call_args.args[0]
    assert set(deleted_ids) == {"oiueei/things/orphan1", "oiueei/things/orphan2"}
