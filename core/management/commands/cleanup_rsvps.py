from datetime import timedelta

from django.conf import settings
from django.core.management.base import BaseCommand
from django.utils import timezone

from core.models import RSVP


class Command(BaseCommand):
    help = "Delete expired RSVP tokens"

    def handle(self, *args, **options):
        expiry_hours = getattr(settings, "MAGIC_LINK_EXPIRY_HOURS", 24)
        cutoff = timezone.now() - timedelta(hours=expiry_hours)
        count, _ = RSVP.objects.filter(created__lt=cutoff).delete()
        self.stdout.write(self.style.SUCCESS(f"Cleaned up {count} expired RSVPs"))
