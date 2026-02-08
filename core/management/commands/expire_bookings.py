from django.core.management.base import BaseCommand

from core.models.booking import BookingPeriod


class Command(BaseCommand):
    help = "Expire PENDING bookings that have passed the expiry time"

    def handle(self, *args, **options):
        count = BookingPeriod.expire_old_pending()
        self.stdout.write(self.style.SUCCESS(f"Expired {count} bookings"))
