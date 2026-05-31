"""
Management command to send daily reminder emails.

Sends reminders for:
- Booking returns due tomorrow (end_date = tomorrow)
- Order deliveries due tomorrow (delivery_date = tomorrow)
- Events happening tomorrow (event_date = tomorrow)

Run daily via Heroku Scheduler.
"""

from datetime import date, datetime, timedelta, timezone

from django.core.management.base import BaseCommand

from core.models.booking import BookingPeriod
from core.models.thing import Thing
from core.services.email_service import (
    send_delivery_reminder_email,
    send_event_reminder_email,
    send_return_reminder_email,
)


class Command(BaseCommand):
    help = "Send daily reminder emails for bookings, deliveries, and events"

    def handle(self, *args, **options):
        tomorrow = date.today() + timedelta(days=1)
        total = 0

        # 1. Booking return reminders (end_date = tomorrow)
        return_bookings = BookingPeriod.objects.filter(
            end_date=tomorrow,
            status=BookingPeriod.Status.ACCEPTED,
        ).select_related("thing_code__owner", "requester_code")

        for booking in return_bookings:
            thing = booking.thing_code
            requester = booking.requester_code
            requester_name = requester.name or requester.email
            send_return_reminder_email(
                requester_name=requester_name,
                thing_headline=thing.headline,
                end_date=booking.end_date,
                owner_email=thing.owner.email,
            )
            total += 1

        # 2. Order delivery reminders (delivery_date = tomorrow)
        delivery_bookings = BookingPeriod.objects.filter(
            delivery_date=tomorrow,
            status=BookingPeriod.Status.ACCEPTED,
        ).select_related("thing_code__owner", "requester_code")

        for booking in delivery_bookings:
            thing = booking.thing_code
            requester = booking.requester_code
            requester_name = requester.name or requester.email
            send_delivery_reminder_email(
                requester_name=requester_name,
                thing_headline=thing.headline,
                delivery_date=booking.delivery_date,
                owner_email=thing.owner.email,
            )
            total += 1

        # 3. Event reminders (event_date = tomorrow)
        tomorrow_start = datetime.combine(tomorrow, datetime.min.time(), tzinfo=timezone.utc)
        tomorrow_end = datetime.combine(tomorrow, datetime.max.time(), tzinfo=timezone.utc)
        events = (
            Thing.objects.filter(
                type="EVENT_THING",
                status="ACTIVE",
                event_date__gte=tomorrow_start,
                event_date__lte=tomorrow_end,
            )
            .select_related("owner")
            .prefetch_related("deal")
        )

        for event in events:
            attendee_emails = list(event.deal.values_list("email", flat=True))
            if attendee_emails:
                owner_name = event.owner.name or event.owner.email
                send_event_reminder_email(
                    owner_name=owner_name,
                    thing_headline=event.headline,
                    event_date=event.event_date,
                    emails=attendee_emails,
                )
                total += len(attendee_emails)

        self.stdout.write(self.style.SUCCESS(f"Sent {total} reminder emails"))
