"""
Management command to send digest emails for collections.

Sends weekly digests on Mondays and monthly digests on the 1st of each month.
Each digest lists things added since the last digest period.

Run daily via Heroku Scheduler.
"""

from datetime import date, timedelta

from django.core.management.base import BaseCommand

from core.models.collection import Collection
from core.models.transfer import ThingTransfer
from core.services.email_service import send_digest_email, send_newsletter_email


class Command(BaseCommand):
    help = "Send digest emails for collections with digest_frequency enabled"

    def handle(self, *args, **options):
        today = date.today()
        total = 0

        # Weekly digests: send on Mondays (weekday 0)
        if today.weekday() == 0:
            total += self._send_digests("WEEKLY", today - timedelta(days=7), today)
            total += self._send_newsletters(today - timedelta(days=7), today)

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
                collection_code=collection.code,
                thing_headlines=headlines,
                emails=invitee_emails,
            )
            count += len(invitee_emails)

        return count

    def _send_newsletters(self, since, until):
        """Send weekly newsletters for share collections with newsletter enabled."""
        collections = Collection.objects.filter(
            newsletter_enabled=True,
            is_share=True,
            status="ACTIVE",
        ).prefetch_related("things", "invites")

        count = 0
        for collection in collections:
            invitee_emails = list(collection.invites.values_list("email", flat=True))
            if not invitee_emails:
                continue

            # Block 1: new things added in the period
            new_things = collection.things.filter(
                created__date__gte=since,
                created__date__lt=until,
                status__in=["ACTIVE", "TAKEN"],
            )
            new_thing_headlines = list(new_things.values_list("headline", flat=True))

            # Block 2: ownership changes in the period
            thing_ids = list(collection.things.values_list("code", flat=True))
            transfers = ThingTransfer.objects.filter(
                thing_id__in=thing_ids,
                lent_date__gte=since,
                lent_date__lt=until,
            ).select_related("thing", "from_user", "to_user")

            transfer_entries = [
                {
                    "date": t.lent_date,
                    "thing": t.thing.headline,
                    "from_name": t.from_user.name or t.from_user.email,
                    "to_name": t.to_user.name or t.to_user.email,
                }
                for t in transfers
            ]

            if not new_thing_headlines and not transfer_entries:
                continue

            send_newsletter_email(
                collection_headline=collection.headline,
                collection_code=collection.code,
                new_thing_headlines=new_thing_headlines,
                transfer_entries=transfer_entries,
                emails=invitee_emails,
            )
            count += len(invitee_emails)

        return count
