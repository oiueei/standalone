"""
Usage statistics views for OIUEEI shared assets.
"""

from django.db.models import Count
from django.db.models.functions import TruncMonth
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Thing
from core.models.booking import BookingPeriod


class ThingStatsView(APIView):
    """
    GET /api/v1/things/{thing_code}/stats/
    Returns aggregated usage statistics for a thing.

    Response includes bookings per user per month for all ACCEPTED bookings.
    Available to any user who can view the thing.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, thing_code):
        thing = get_object_or_404(Thing, code=thing_code)

        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorized to view this thing"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Aggregate ACCEPTED bookings per user per month
        usage = (
            BookingPeriod.objects.filter(
                thing_code=thing,
                status=BookingPeriod.Status.ACCEPTED,
            )
            .annotate(month=TruncMonth("created"))
            .values("month", "requester_code_id")
            .annotate(count=Count("code"))
            .order_by("-month", "requester_code_id")
        )

        # Build response with user names
        from core.models import User

        user_codes = set(entry["requester_code_id"] for entry in usage)
        users = {u.code: u.name or u.email for u in User.objects.filter(code__in=user_codes)}

        monthly_usage = []
        for entry in usage:
            monthly_usage.append(
                {
                    "month": entry["month"].strftime("%Y-%m"),
                    "user_code": entry["requester_code_id"],
                    "user_name": users.get(entry["requester_code_id"], ""),
                    "bookings": entry["count"],
                }
            )

        # Total stats
        total_bookings = BookingPeriod.objects.filter(
            thing_code=thing,
            status=BookingPeriod.Status.ACCEPTED,
        ).count()

        unique_users = (
            BookingPeriod.objects.filter(
                thing_code=thing,
                status=BookingPeriod.Status.ACCEPTED,
            )
            .values("requester_code_id")
            .distinct()
            .count()
        )

        return Response(
            {
                "total_bookings": total_bookings,
                "unique_users": unique_users,
                "monthly_usage": monthly_usage,
            },
            status=status.HTTP_200_OK,
        )
