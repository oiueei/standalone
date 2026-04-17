"""
Management command to close completed transfers.

Finds ThingTransfer records linked to ACCEPTED bookings whose end_date
has passed, and sets returned_date. Run daily via Heroku Scheduler.
"""

from datetime import date

from django.core.management.base import BaseCommand

from core.models.transfer import ThingTransfer


class Command(BaseCommand):
    help = "Close transfers for bookings that have ended"

    def handle(self, *args, **options):
        today = date.today()

        # Find unreturned transfers whose booking has an end_date in the past
        transfers = ThingTransfer.objects.filter(
            returned_date__isnull=True,
            booking__isnull=False,
            booking__end_date__lt=today,
            booking__status="ACCEPTED",
        )

        count = transfers.update(returned_date=today)
        self.stdout.write(self.style.SUCCESS(f"Closed {count} transfers"))
