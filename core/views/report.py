"""
Content-report views for OIUEEI.
"""

from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Report, Thing
from core.models.notification import InAppNotification
from core.services.email_service import send_thing_reported_email
from core.views._helpers import deny_if_cannot_view


class ThingReportView(APIView):
    """
    POST /api/v1/things/{thing_code}/report/

    A logged-in member flags a thing as inappropriate. The report is:
    - **Authenticated only** — no anonymous reports (the reporter is recorded
      server-side purely as a moderation trail).
    - **Anonymous to the owner** — they're told *someone* reported the listing
      (with the thing, so they can go look), never who.
    - **Logged** — every first-time report creates a `Report` row so the
      platform can see how many landed in a period.
    - **Idempotent per member** — re-reporting the same thing is a no-op that
      doesn't spam the owner (one `Report` per reporter+thing).
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="10/h", method="POST", block=True))
    def post(self, request, thing_code):
        thing = get_object_or_404(Thing, code=thing_code)

        # Reporting your own listing makes no sense — and would notify yourself.
        if thing.is_owner(request.user.code):
            return Response(
                {"error": "You can't report your own listing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        denied = deny_if_cannot_view(
            thing, request.user.code, "Not authorized to report this thing"
        )
        if denied:
            return denied

        _report, created = Report.objects.get_or_create(
            thing=thing,
            reporter=request.user,
            defaults={"thing_headline": thing.headline},
        )

        # Only notify the owner the first time this member reports it — a repeat
        # tap is swallowed so the owner isn't spammed. The response is identical
        # either way (the reporter can't tell whether it was their first report).
        if created:
            owner = thing.owner
            if owner and owner.email:
                send_thing_reported_email(thing, owner.email)
            if owner:
                InAppNotification.objects.create(
                    user=owner,
                    type=InAppNotification.Type.THING_REPORTED,
                    payload={"thing_headline": thing.headline, "thing_code": thing.code},
                )

        return Response(
            {"message": "Thanks — we've let the owner know."},
            status=status.HTTP_200_OK,
        )
