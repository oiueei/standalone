"""
Management command to send digest emails for collections.

Sends weekly digests on Mondays and monthly digests on the 1st of each month.
Each digest lists things added since the last digest period.

Run daily via Heroku Scheduler.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models.collection import Collection
from core.services.email_service import send_digest_email


class Command(BaseCommand):
    help = "Send digest emails for collections with digest_frequency enabled"

    def handle(self, *args, **options):
        today = date.today()
        total = 0

        # Weekly digests: send on Mondays (weekday 0)
        if today.weekday() == 0:
            total += self._send_digests("WEEKLY", today - timedelta(days=7), today)

        # Monthly digests: send on the 1st of the month
        if today.day == 1:
            # Calculate start of previous month
            first_of_this_month = today
            last_month = first_of_this_month - timedelta(days=1)
            first_of_last_month = last_month.replace(day=1)
            total += self._send_digests("MONTHLY", first_of_last_month, first_of_this_month)

        self.stdout.write(self.style.SUCCESS(f"Sent {total} digest emails"))

    def _send_digests(self, frequency, since, until):
        """Send digest emails for collections with the given frequency."""
        collections = Collection.objects.filter(
            digest_frequency=frequency,
            status="ACTIVE",
        ).prefetch_related("things", "invites")

        count = 0
        for collection in collections:
            new_things = collection.things.filter(
                created__date__gte=since,
                created__date__lt=until,
                status__in=["ACTIVE", "TAKEN"],
            )

            headlines = list(new_things.values_list("headline", flat=True))
            if not headlines:
                continue

            invitee_emails = list(collection.invites.values_list("email", flat=True))
            if not invitee_emails:
                continue

            send_digest_email(
                collection_headline=collection.headline,
                thing_headlines=headlines,
                emails=invitee_emails,
            )
            count += len(invitee_emails)

        return count
