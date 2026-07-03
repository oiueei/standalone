"""Integration tests for content reports (#12).

A logged-in member flags a thing. The report is authenticated-only, anonymous to
the owner (they learn only *that* it was reported, and which thing — never by
whom), logged for platform moderation, and idempotent per reporter+thing.
"""

import pytest
from django.core import mail

from core.models import Report
from core.models.notification import InAppNotification

pytestmark = pytest.mark.django_db

URL = "/api/v1/things/{}/report/"


def _invite(collection, member):
    collection.invites.add(member)


def test_member_report_creates_log_and_notifies_owner(
    authenticated_client2, user, user2, thing, collection
):
    _invite(collection, user2)
    mail.outbox.clear()

    res = authenticated_client2.post(URL.format(thing.code))

    assert res.status_code == 200
    # A moderation-log row is created, tied to the reporter (server-side only).
    report = Report.objects.get(thing=thing, reporter=user2)
    assert report.thing_headline == thing.headline
    # The owner gets an in-app notification that names the thing, not the reporter.
    noti = InAppNotification.objects.get(user=user, type=InAppNotification.Type.THING_REPORTED)
    assert noti.payload == {"thing_headline": thing.headline, "thing_code": thing.code}
    assert "reporter" not in noti.payload
    # The owner is emailed too (Cat. 2 activity, on by default).
    assert len(mail.outbox) == 1
    assert user.email in mail.outbox[0].to


def test_report_response_never_leaks_reporter(authenticated_client2, user2, thing, collection):
    _invite(collection, user2)
    body = authenticated_client2.post(URL.format(thing.code)).json()
    # The reporter-facing response is just a thank-you — no identity echoed back.
    assert "reporter" not in body
    assert set(body.keys()) == {"message"}


def test_owner_cannot_report_own_thing(authenticated_client, user, thing):
    res = authenticated_client.post(URL.format(thing.code))
    assert res.status_code == 400
    assert not Report.objects.exists()
    assert not InAppNotification.objects.filter(
        type=InAppNotification.Type.THING_REPORTED
    ).exists()


def test_anonymous_cannot_report(api_client, thing):
    res = api_client.post(URL.format(thing.code))
    assert res.status_code in (401, 403)
    assert not Report.objects.exists()


def test_non_viewer_cannot_report(authenticated_client2, thing):
    # user2 is NOT invited to the (private) collection → can't see, can't report.
    res = authenticated_client2.post(URL.format(thing.code))
    assert res.status_code == 403
    assert not Report.objects.exists()


def test_duplicate_report_is_idempotent(authenticated_client2, user, user2, thing, collection):
    _invite(collection, user2)
    mail.outbox.clear()

    first = authenticated_client2.post(URL.format(thing.code))
    second = authenticated_client2.post(URL.format(thing.code))

    assert first.status_code == 200
    assert second.status_code == 200
    # One report, one notification, one email — a repeat tap doesn't spam the owner.
    assert Report.objects.filter(thing=thing, reporter=user2).count() == 1
    assert (
        InAppNotification.objects.filter(
            user=user, type=InAppNotification.Type.THING_REPORTED
        ).count()
        == 1
    )
    assert len(mail.outbox) == 1


def test_missing_thing_returns_404(authenticated_client2):
    res = authenticated_client2.post(URL.format("NOPE00"))
    assert res.status_code == 404
