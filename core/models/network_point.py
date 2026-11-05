from django.db import models

from core.utils import generate_id

from .collection import Collection
from .user import User


class NetworkPoint(models.Model):
    """The page one curator has in one group: the entity they answer for.

    In **any** collection a curator (founder or co-curator) may set the identity half:
    ``entity_name``, ``logo``, ``about`` and ``contact``. Only in a **network** the row
    is also a pickup point (address, hours, days, closures and the loan conditions);
    elsewhere those columns stay empty and the place belongs to the group. The model
    keeps its name, and the table, from the network that came first.

    In a network, each dinamizador of a NETWORK runs their own things on behalf of an entity (a
    cooperative, a neighbourhood association, a shop, a union), not from their home:
    its name, where members collect and return, when, and the conditions of its own
    loans. Public with the collection, address included.

    One row per (collection, dinamizador). It is not required: a dinamizador with no
    point lends under the collection's own rules, and each condition left empty falls
    back to the collection's own, field by field (``Collection.effective_*``). It
    goes when the dinamizador stops being one, with their things.

    The conditions reuse the collection's columns, widths and serializers: the
    visible limit is per language and the column holds all three plus the JSON
    scaffolding (see ``Collection.deposit_policy`` / ``request_info`` / ``email_note``).
    """

    code = models.CharField(max_length=6, primary_key=True, default=generate_id)
    collection = models.ForeignKey(Collection, on_delete=models.CASCADE, related_name="points")
    user = models.ForeignKey(User, on_delete=models.CASCADE, related_name="network_points")
    # A proper name, plain text, not localized.
    entity_name = models.CharField(max_length=64, blank=True, default="")
    # Same width as ``Thing.location``, which it replaces in a network.
    address = models.CharField(max_length=64, blank=True, default="")
    hours_note = models.CharField(max_length=128, blank=True, default="")
    # A web or a phone of the entity; shown as typed, escaped, never made a link.
    contact = models.CharField(max_length=64, blank=True, default="")
    # The entity's logo: a storage key in the collections' folder, like
    # ``Collection.thumbnail`` (same width). ``db_default`` because the previous
    # release's dynos insert without naming the column while the release phase runs.
    logo = models.CharField(max_length=255, blank=True, default="", db_default="")
    # Markdown about the entity, one text per language like ``Collection.description``
    # (a ``TextField``: the serializer holds the visible limit). ``db_default`` for the
    # same reason as ``logo``.
    about = models.TextField(blank=True, default="", db_default="")
    # One set for pickup and return, like ``Collection.rental_weekdays`` (0=Mon…6=Sun).
    # Empty = the collection's days.
    weekdays = models.JSONField(default=list, blank=True)
    # The entity's own holidays, ISO strings cleaned like ``Collection.closed_dates``.
    closed_dates = models.JSONField(default=list, blank=True)
    deposit_policy = models.CharField(max_length=1024, blank=True, default="")
    request_info = models.CharField(max_length=2048, blank=True, default="")
    email_note = models.CharField(max_length=2048, blank=True, default="")

    class Meta:
        app_label = "core"
        db_table = "network_points"
        constraints = [
            models.UniqueConstraint(fields=["collection", "user"], name="one_point_per_curator")
        ]

    def __str__(self):
        return f"{self.code}: {self.entity_name or self.user_id} @ {self.collection_id}"

    @property
    def display_name(self):
        """The name the point goes by: its entity's, else the dinamizador's own (bare
        ``name``, never the address ``User.display_name`` falls back to)."""
        return self.entity_name or self.user.name

    def closed_date_set(self):
        """``closed_dates`` as ``date`` objects; a bad string is skipped."""
        from datetime import date as _date

        out = set()
        for raw in self.closed_dates or []:
            try:
                out.add(_date.fromisoformat(raw))
            except (TypeError, ValueError):
                continue
        return out
