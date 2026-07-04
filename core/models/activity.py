"""First-party daily-activity record — one row per user per day they were active.

The app keeps no session/analytics concept, so returns and retention are otherwise
unanswerable. This is deliberately the smallest thing that answers them: a
``(user, date)`` row, written at most once per user per day by
``core.middleware.DailyActivityMiddleware`` (guarded by a cache key so it's one DB
write per user per day, not per request).

Powers WAU/MAU per role, creator/guest return counts, and "guests who never come
back after their first visit". It records *less* than the web server logs already
hold and never leaves our DB (DESIGN §9).
"""

from django.db import models

from core.utils import generate_id

from .user import User


class DailyActivity(models.Model):
    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="daily_activity")
    date = models.DateField()

    class Meta:
        db_table = "daily_activity"
        ordering = ["-date"]
        constraints = [
            models.UniqueConstraint(fields=["user", "date"], name="unique_daily_activity_per_day")
        ]
        # Range scans over "everyone active since <cutoff>" (WAU/MAU) filter by date.
        indexes = [models.Index(fields=["date"])]

    def __str__(self):
        return f"{self.user_id} active {self.date}"
