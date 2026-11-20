"""The document a borrower accepted stays in the bucket while a loan names it.

A library replacing its welcome PDF destroys the old object unless some other row still holds
its key; `BookingPeriod.terms_doc` is such a row. The bucket is mocked (`storage.delete`) and the
on-commit callbacks are run, as in the other asset-cleanup tests.
"""

from unittest.mock import patch

import pytest

from core.models import BookingPeriod, Collection, Thing, User
from core.services import asset_cleanup

pytestmark = pytest.mark.django_db

OLD = "oiueei/documents/terms-old"
NEW = "oiueei/documents/terms-new"


@pytest.fixture
def owner():
    return User.objects.create(code="TDOWN1", email="lala13@your-domain.test")


@pytest.fixture
def borrower():
    return User.objects.create(code="TDBOR1", email="lele13@your-domain.test")


@pytest.fixture
def library(owner):
    return Collection.objects.create(
        code="TDCOL1",
        owner=owner,
        headline="Tool library",
        kind=Collection.Kind.LIBRARY,
        allowed_thing_types=["LEND_THING"],
        welcome_doc=OLD,
        lending_asks_terms=True,
    )


@pytest.fixture
def drill(owner, library):
    thing = Thing.objects.create(code="TDTH01", owner=owner, headline="Drill", type="LEND_THING")
    library.things.add(thing)
    return thing


def _loan(drill, borrower, owner, doc=OLD, code=None):
    kwargs = {"code": code} if code else {}
    return BookingPeriod.objects.create(
        thing_code=drill,
        thing_type="LEND_THING",
        requester_code=borrower,
        requester_email=borrower.email,
        owner_code=owner,
        terms_doc=doc,
        **kwargs,
    )


def _destroyed(destroy):
    return [c.args[0] for c in destroy.call_args_list]


class TestReplacingTheDocument:
    def test_the_old_one_is_kept_while_a_loan_accepted_it(
        self, library, drill, borrower, owner, django_capture_on_commit_callbacks
    ):
        _loan(drill, borrower, owner)
        library.welcome_doc = NEW
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                library.save()

        assert _destroyed(destroy) == []

    def test_the_old_one_is_destroyed_when_no_loan_accepted_it(
        self, library, django_capture_on_commit_callbacks
    ):
        library.welcome_doc = NEW
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                library.save()

        assert _destroyed(destroy) == [OLD]


class TestDeletingLoans:
    def test_the_last_loan_naming_it_destroys_it(
        self, library, drill, borrower, owner, django_capture_on_commit_callbacks
    ):
        _loan(drill, borrower, owner)
        library.welcome_doc = NEW
        library.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                BookingPeriod.objects.get().delete()

        assert _destroyed(destroy) == [OLD]

    def test_a_loan_is_not_the_last_while_another_names_it(
        self, library, drill, borrower, owner, django_capture_on_commit_callbacks
    ):
        first = _loan(drill, borrower, owner, code="TDBK01")
        _loan(drill, borrower, owner, code="TDBK02")
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                first.delete()

        assert _destroyed(destroy) == []

    def test_a_loan_that_accepted_nothing_destroys_nothing(
        self, drill, borrower, owner, django_capture_on_commit_callbacks
    ):
        loan = _loan(drill, borrower, owner, doc="")
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                loan.delete()

        destroy.assert_not_called()

    def test_deleting_the_borrowers_account_destroys_a_replaced_document(
        self, library, drill, borrower, owner, django_capture_on_commit_callbacks
    ):
        _loan(drill, borrower, owner)
        library.welcome_doc = NEW
        library.save()
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                borrower.delete()

        assert _destroyed(destroy) == [OLD]

    def test_deleting_the_collection_keeps_the_document_while_its_loans_survive(
        self, library, drill, borrower, owner, django_capture_on_commit_callbacks
    ):
        _loan(drill, borrower, owner)
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                library.delete()

        assert _destroyed(destroy) == []
        assert BookingPeriod.objects.get().terms_doc == OLD

    def test_deleting_the_collection_and_its_things_destroys_the_document(
        self, library, drill, borrower, owner, django_capture_on_commit_callbacks
    ):
        _loan(drill, borrower, owner)
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                library.delete()
                drill.delete()  # the loans go with their thing

        # Named by the collection and by the loan: once from each, the same object.
        assert set(_destroyed(destroy)) == {OLD}

    def test_a_rolled_back_loan_delete_destroys_nothing(self, drill, borrower, owner):
        from django.db import transaction

        loan = _loan(drill, borrower, owner)
        with patch("core.services.storage.delete") as destroy:
            with pytest.raises(RuntimeError):
                with transaction.atomic():
                    loan.delete()
                    raise RuntimeError("later failure")

        destroy.assert_not_called()

    def test_expiring_or_wiping_a_loan_leaves_its_document(
        self, drill, borrower, owner, django_capture_on_commit_callbacks
    ):
        _loan(drill, borrower, owner)
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                BookingPeriod.objects.update(contact_phone="", lending_contact="")

        destroy.assert_not_called()
        assert BookingPeriod.objects.get().terms_doc == OLD

    def test_a_seed_key_is_never_destroyed(
        self, drill, borrower, owner, django_capture_on_commit_callbacks
    ):
        loan = _loan(drill, borrower, owner, doc="oiueei/seed/terms")
        with patch("core.services.storage.delete") as destroy:
            with django_capture_on_commit_callbacks(execute=True):
                loan.delete()

        destroy.assert_not_called()


class TestTheOrphanSweep:
    def test_a_loan_keeps_its_document_in_the_in_use_set(self, drill, borrower, owner):
        _loan(drill, borrower, owner)

        assert OLD in asset_cleanup.referenced_keys()
        assert asset_cleanup.is_referenced(OLD)

    def test_the_command_keeps_it_on_a_dry_run_and_on_commit(self, drill, borrower, owner):
        from datetime import timedelta
        from io import StringIO

        from django.conf import settings
        from django.core.management import call_command
        from django.utils import timezone

        _loan(drill, borrower, owner)
        listing = [{"key": OLD, "last_modified": timezone.now() - timedelta(days=2), "size": 1}]
        for commit in (False, True):
            out = StringIO()
            with (
                patch("core.services.storage.iter_objects", return_value=iter(listing)),
                patch("core.services.storage.delete_many", side_effect=len) as delete_many,
            ):
                call_command(
                    "cleanup_orphan_images",
                    commit=commit,
                    bucket=settings.OBJECT_STORAGE_BUCKET,
                    stdout=out,
                )
            delete_many.assert_not_called()
            assert "1 in use" in out.getvalue()
