"""
Owner multilingual content (O6) end to end: the owner of a bilingual group writes
one text per language as inline JSON, and each member — on the page and in their
inbox — reads their own.

The unit side (parse, resolve, the field guards) lives in
``core/tests/unit/test_localized.py``; this is the API + email surface.
"""

import json

import pytest
from django.core import mail

from core.models import Collection, Language, Thing, User
from core.services.email_service import send_collection_invite_email, send_digest_email

BILINGUAL = json.dumps({"es": "Las cosas de mamá", "ca": "Les coses de mama"})


@pytest.fixture(autouse=True)
def english_deployment(settings):
    settings.EMAIL_LANGUAGE = "en"


@pytest.mark.django_db
class TestWritingLocalizedContent:
    def test_a_collection_headline_may_carry_one_text_per_language(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": BILINGUAL, "description": BILINGUAL},
            format="json",
        )

        assert res.status_code == 201
        # Stored as written — resolving is the reader's job, not the writer's.
        assert res.data["headline"] == BILINGUAL

    def test_a_thing_headline_may_too(self, authenticated_client, collection):
        res = authenticated_client.post(
            "/api/v1/things/",
            {"type": "GIFT_THING", "headline": BILINGUAL, "collection_code": collection.code},
            format="json",
        )

        assert res.status_code == 201
        assert Thing.objects.get(code=res.data["code"]).headline == BILINGUAL

    def test_a_tag_label_may_too(self, authenticated_client):
        label = json.dumps({"es": "Juguetes", "ca": "Joguines"})

        res = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": "Tagged", "tags": [label]},
            format="json",
        )

        assert res.status_code == 201
        assert res.data["tags"] == [label]

    def test_one_language_over_the_limit_is_rejected(self, authenticated_client):
        overflowing = json.dumps({"es": "corto", "ca": "c" * 65})

        res = authenticated_client.post(
            "/api/v1/collections/", {"headline": overflowing}, format="json"
        )

        assert res.status_code == 400

    def test_html_in_one_language_is_rejected(self, authenticated_client):
        res = authenticated_client.post(
            "/api/v1/collections/",
            {"headline": json.dumps({"es": "Hola", "ca": "<script>alert(1)</script>"})},
            format="json",
        )

        assert res.status_code == 400

    def test_a_headline_that_only_looks_like_json_is_kept_verbatim(self, authenticated_client):
        # An owner writing about JSON must not have their words swallowed.
        res = authenticated_client.post(
            "/api/v1/collections/", {"headline": '{"not": "a language"}'}, format="json"
        )

        assert res.status_code == 201
        assert res.data["headline"] == '{"not": "a language"}'


@pytest.mark.django_db
class TestReadingLocalizedContent:
    def test_an_invite_subject_speaks_the_recipients_language(self, user):
        collection = Collection.objects.create(
            code="LOC001", owner=user, headline=BILINGUAL, language=Language.ES
        )
        catalan = User.objects.create(email="ca@test.com", language=Language.CA)
        collection.invites.add(catalan)

        send_collection_invite_email(
            "Lala", collection.headline, catalan.email, "a", "r", collection=collection
        )

        subject = mail.outbox[0].subject
        assert "Les coses de mama" in subject
        assert "{" not in subject

    def test_a_bilingual_group_reads_one_digest_in_each_language(self, user):
        collection = Collection.objects.create(
            code="LOC002", owner=user, headline=BILINGUAL, language=Language.ES
        )
        catalan = User.objects.create(email="ca@test.com", language=Language.CA, notify_news=True)
        spanish = User.objects.create(email="es@test.com", notify_news=True)
        collection.invites.add(catalan, spanish)

        send_digest_email(
            collection.headline,
            collection.code,
            [json.dumps({"es": "Una silla", "ca": "Una cadira"})],
            [catalan.email, spanish.email],
            collection=collection,
        )

        by_recipient = {m.to[0]: m for m in mail.outbox}
        assert "Les coses de mama" in by_recipient["ca@test.com"].subject
        assert "Una cadira" in by_recipient["ca@test.com"].body
        assert "Las cosas de mamá" in by_recipient["es@test.com"].subject
        assert "Una silla" in by_recipient["es@test.com"].body

    def test_a_reader_whose_language_the_owner_skipped_still_gets_words(self, user):
        collection = Collection.objects.create(code="LOC003", owner=user, headline=BILINGUAL)
        english = User.objects.create(email="en@test.com", language=Language.EN)
        collection.invites.add(english)

        send_collection_invite_email(
            "Lala", collection.headline, english.email, "a", "r", collection=collection
        )

        # No English text was written, so Spanish answers — never the raw map.
        assert "Las cosas de mamá" in mail.outbox[0].subject
