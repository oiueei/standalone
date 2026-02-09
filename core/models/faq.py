"""
FAQ model for OIUEEI.
"""

from django.db import models
from django.utils import timezone

from core.utils import generate_id


class FAQ(models.Model):
    """
    A question and answer for a thing.
    """

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    thing = models.ForeignKey(
        "Thing",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="thing",
        related_name="faq_set",
    )
    created = models.DateTimeField(default=timezone.now)
    questioner = models.ForeignKey(
        "User",
        on_delete=models.CASCADE,
        to_field="code",
        db_column="questioner",
        related_name="asked_faqs",
    )
    question = models.CharField(max_length=64)
    answer = models.CharField(max_length=256, blank=True, default="")
    is_visible = models.BooleanField(default=True)

    class Meta:
        app_label = "core"
        db_table = "faqs"

    def __str__(self):
        return f"FAQ {self.code}: {self.question[:30]}..."

    def has_answer(self):
        """Check if this FAQ has been answered."""
        return bool(self.answer)

    def set_answer(self, answer_text):
        """Set the answer for this FAQ."""
        self.answer = answer_text
        self.save(update_fields=["answer"])
