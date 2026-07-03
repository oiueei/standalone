from django.db import models
from django.utils import timezone

from core.utils import generate_id

from .thing import Thing
from .user import User


class Report(models.Model):
    """A logged-in member's flag on a Thing.

    Anonymous **to the owner**: they only learn *that* one of their listings was
    reported (and which one, so they can go look) — never by whom. The
    `reporter` FK is kept server-side purely as a platform-moderation record, so
    we can see how many reports landed in a given period. Reporting requires
    authentication (no anonymous reports), and one member can report a given
    thing only once (`unique_report_per_reporter_thing`).
    """

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    # SET_NULL on both FKs so the moderation log survives the thing / reporter
    # being deleted later; the headline snapshot keeps the row readable.
    thing = models.ForeignKey(Thing, on_delete=models.SET_NULL, null=True, related_name="reports")
    thing_headline = models.CharField(max_length=64, blank=True)
    reporter = models.ForeignKey(
        User, on_delete=models.SET_NULL, null=True, related_name="reports_made"
    )
    created = models.DateTimeField(default=timezone.now, db_index=True)

    class Meta:
        db_table = "reports"
        ordering = ["-created"]
        constraints = [
            models.UniqueConstraint(
                fields=["thing", "reporter"], name="unique_report_per_reporter_thing"
            )
        ]

    def __str__(self):
        return f"Report {self.code} on {self.thing_headline or self.thing_id}"
