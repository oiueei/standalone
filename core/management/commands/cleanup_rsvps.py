from datetime import timedelta

from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from core.models import RSVP


class Command(BaseCommand):
    help = "Delete expired RSVP tokens"

    def handle(self, *args, **options):
        # Delete each RSVP only once it is past its own action's expiry (a booking
        # link outlives the old flat 24h window; an invite outlives it by weeks),
        # using the model's per-action lifetime so this can't drift from is_valid().
        now = timezone.now()
        expired = Q()
        for action in RSVP.Action.values:
            cutoff = now - timedelta(hours=RSVP.expiry_hours_for(action))
            expired |= Q(action=action, created__lt=cutoff)
        count, _ = RSVP.objects.filter(expired).delete()
        self.stdout.write(self.style.SUCCESS(f"Cleaned up {count} expired RSVPs"))
