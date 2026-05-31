"""
Slots view for APPOINTMENT_THING weekly schedule.
"""

from datetime import datetime, timedelta

from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Thing
from core.models.booking import BookingPeriod


class ThingSlotsView(APIView):
    """
    GET /api/v1/things/{thing_code}/slots/?week_start=2026-04-20

    Returns weekly slot grid for APPOINTMENT_THING.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, thing_code):
        thing = Thing.objects.filter(code=thing_code).first()
        if not thing:
            return Response({"error": "Thing not found"}, status=status.HTTP_404_NOT_FOUND)

        if not thing.can_view(request.user.code):
            return Response({"error": "Not authorised"}, status=status.HTTP_403_FORBIDDEN)

        if thing.type != Thing.Type.APPOINTMENT_THING:
            return Response(
                {"error": "Slots only available for appointment things"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        schedule = thing.availability_schedule
        duration = thing.slot_duration
        if not schedule or not duration:
            return Response(
                {
                    "week_start": request.query_params.get("week_start", ""),
                    "slot_duration": duration,
                    "days": [],
                }
            )

        # Parse week_start (default to current week's Monday)
        week_start_str = request.query_params.get("week_start")
        if week_start_str:
            try:
                week_start = datetime.strptime(week_start_str, "%Y-%m-%d").date()
            except ValueError:
                return Response(
                    {"error": "Invalid week_start format (use YYYY-MM-DD)"},
                    status=status.HTTP_400_BAD_REQUEST,
                )
        else:
            today = datetime.now().date()
            week_start = today - timedelta(days=today.weekday())  # Monday

        week_end = week_start + timedelta(days=6)

        # Fetch bookings for this week
        bookings = BookingPeriod.objects.filter(
            thing_code=thing,
            start_date__gte=week_start,
            start_date__lte=week_end,
            status__in=[BookingPeriod.Status.PENDING, BookingPeriod.Status.ACCEPTED],
        ).select_related("requester_code")

        # Index bookings by (date, start_time)
        booking_map = {}
        for b in bookings:
            key = (str(b.start_date), str(b.start_time)[:5] if b.start_time else "")
            booking_map[key] = {
                "status": "pending" if b.status == BookingPeriod.Status.PENDING else "booked",
                "requester_name": b.requester_code.name or b.requester_code.email,
            }

        # Generate slots for each day
        days = []
        for day_offset in range(7):
            current_date = week_start + timedelta(days=day_offset)
            day_of_week = current_date.isoweekday()  # 1=Monday, 7=Sunday

            day_slots = []
            for window in schedule:
                if day_of_week not in window.get("days", []):
                    continue

                w_start = _parse_time(window.get("start_time", "00:00"))
                w_end = _parse_time(window.get("end_time", "23:59"))

                slot_start = w_start
                while slot_start + timedelta(minutes=duration) <= w_end:
                    slot_end = slot_start + timedelta(minutes=duration)
                    start_str = _format_time(slot_start)
                    end_str = _format_time(slot_end)

                    key = (str(current_date), start_str)
                    booking_info = booking_map.get(key)

                    slot = {
                        "start_time": start_str,
                        "end_time": end_str,
                    }
                    if booking_info:
                        slot["status"] = booking_info["status"]
                        slot["requester_name"] = booking_info["requester_name"]
                    else:
                        slot["status"] = "available"

                    day_slots.append(slot)
                    slot_start = slot_end

            days.append(
                {
                    "date": str(current_date),
                    "day_of_week": day_of_week,
                    "slots": day_slots,
                }
            )

        return Response(
            {
                "week_start": str(week_start),
                "slot_duration": duration,
                "days": days,
            }
        )


def _parse_time(time_str):
    """Parse HH:MM string to timedelta from midnight."""
    parts = time_str.split(":")
    return timedelta(hours=int(parts[0]), minutes=int(parts[1]))


def _format_time(td):
    """Format timedelta from midnight to HH:MM string."""
    total_minutes = int(td.total_seconds() // 60)
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours:02d}:{minutes:02d}"
