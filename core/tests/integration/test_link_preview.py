"""The ``<head>`` of a shared link: what a preview card may say, and what it must not.

A chat app reads the HTML the server sends and runs no JavaScript. These tests hold
the two halves of ``core.services.link_preview``: a public collection, a thing in
one and a share link get a filled ``<head>``; everything a stranger could not read
on the page is answered with the **same bytes** as a neutral route, so a private
collection cannot be told from a code that does not exist.
"""

import pytest
from django.test import Client, override_settings
from django.utils.html import escape

from core.models import Collection, Thing, User
from core.services.email_texts import T
from core.services.link_preview import inject_preview, plain_description

HEAD = "<!doctype html><html><head><title>OIUEEI</title></head><body></body></html>"
TOKEN = "tok_preview_group_0123"
MEDIA = "https://media.your-domain.test"


@pytest.fixture
def built(tmp_path, db):
    dist = tmp_path / "frontend" / "dist"
    dist.mkdir(parents=True)
    (dist / "index.html").write_text(HEAD, encoding="utf-8")
    with override_settings(BASE_DIR=tmp_path):
        yield tmp_path


@pytest.fixture
def owner(db):
    return User.objects.create(code="PRVOW1", email="lele14@your-domain.test", name="Owner")


def _collection(owner, code="PUB001", **fields):
    fields.setdefault("headline", "The street")
    fields.setdefault("description", "Things we share")
    fields.setdefault("status", Collection.Status.ACTIVE)
    fields.setdefault("visibility", Collection.Visibility.PUBLIC)
    return Collection.objects.create(code=code, owner=owner, **fields)


def _thing(owner, collection, code="THG001", **fields):
    fields.setdefault("headline", "Drill")
    thing = Thing.objects.create(code=code, owner=owner, **fields)
    collection.things.add(thing)
    return thing


def _body(path):
    return Client().get(path).content.decode()


def _neutral():
    """The site's card: what a page with no preview of its own is answered with."""
    return _body("/me")


class TestACollection:
    def test_a_public_collection_names_itself(self, built, owner):
        _collection(owner)

        body = Client().get("/stall/PUB001", HTTP_HOST="testserver").content.decode()

        assert "<title>The street — OIUEEI</title>" in body
        assert '<meta property="og:title" content="The street">' in body
        assert '<meta property="og:description" content="Things we share">' in body
        assert '<meta name="description" content="Things we share">' in body
        assert '<meta property="og:url" content="http://testserver/stall/PUB001">' in body
        assert '<meta property="og:site_name" content="OIUEEI">' in body

    @override_settings(MEDIA_PUBLIC_BASE_URL=MEDIA)
    def test_a_photo_becomes_the_card_image(self, built, owner):
        _collection(owner, thumbnail="oiueei/u/cover.webp")

        body = _body("/stall/PUB001")

        assert f'<meta property="og:image" content="{MEDIA}/oiueei/u/cover.webp">' in body
        assert "summary_large_image" in body

    @override_settings(MEDIA_PUBLIC_BASE_URL=MEDIA)
    def test_without_a_photo_there_is_no_image_at_all(self, built, owner):
        _collection(owner)

        body = _body("/stall/PUB001")

        assert "og:image" not in body
        assert "summary_large_image" not in body
        assert '<meta name="twitter:card" content="summary">' in body

    def test_the_join_page_carries_the_same_preview(self, built, owner):
        _collection(owner)

        assert "<title>The street — OIUEEI</title>" in _body("/stall/PUB001/join")
        assert "<title>The street — OIUEEI</title>" in _body("/stall/PUB001/join/")

    @pytest.mark.parametrize("kind", ["STALL", "LIBRARY", "SHED"])
    def test_a_description_less_collection_is_described_by_its_kind(self, built, owner, kind):
        _collection(owner, description="", kind=kind)
        sentence = T(f"kind_what_{kind}", "en")

        body = _body(f"/{kind.lower()}/PUB001")

        assert f'<meta property="og:description" content="{escape(sentence)}">' in body
        assert f'<meta name="description" content="{escape(sentence)}">' in body

    def test_the_sentence_of_the_kind_speaks_the_collections_language(self, built, owner):
        _collection(owner, description="", kind="LIBRARY", language="es")

        body = _body("/library/PUB001")

        assert f'content="{escape(T("kind_what_LIBRARY", "es"))}"' in body

    def test_with_a_description_of_its_own_the_kind_says_nothing(self, built, owner):
        _collection(owner, kind="LIBRARY")

        body = _body("/library/PUB001")

        assert '<meta name="description" content="Things we share">' in body
        assert T("kind_what_LIBRARY", "en") not in body

    @pytest.mark.parametrize(
        "language,expected",
        [("ca", "Els carrers"), ("", "Las calles"), ("en", "Las calles")],
    )
    def test_the_collections_own_language_picks_the_text(self, built, owner, language, expected):
        _collection(owner, headline='{"es": "Las calles", "ca": "Els carrers"}', language=language)

        assert f"<title>{expected} — OIUEEI</title>" in _body("/stall/PUB001")


class TestAShareLinkWithNoDescription:
    def test_it_is_described_by_its_kind_and_carries_no_photo(self, built, owner):
        _collection(
            owner, description="", kind="SHED", share_token=TOKEN, thumbnail="oiueei/u/cover.webp"
        )

        body = _body(f"/share/{TOKEN}")

        assert f'<meta name="description" content="{escape(T("kind_what_SHED", "en"))}">' in body
        assert "og:image" not in body


class TestEveryOtherPageCarriesTheSitesCard:
    """A page with no preview of its own is not left bare: whoever shares the
    address of the instance (`/`, `/login`) gets a card that says what OIUEEI is."""

    @pytest.mark.parametrize("path", ["/", "/login", "/me"])
    def test_the_front_door_and_the_other_pages_say_what_oiueei_is(self, built, db, path):
        body = _body(path)

        pitch = escape(T("generic_parent_pitch", "en"))
        assert f'<meta property="og:description" content="{pitch}">' in body
        assert f'<meta name="description" content="{pitch}">' in body
        assert '<meta property="og:title" content="OIUEEI">' in body
        assert "<title>OIUEEI</title>" in body
        assert "og:image" not in body

    def test_a_libraries_donate_page_is_served_with_the_sites_card(self, built, owner):
        """The "Donate things" page is a route of the SPA: a cold load answers it, and the
        card is the site's, never the collection's (it is no page a preview describes)."""
        _collection(owner, kind=Collection.Kind.LIBRARY)

        response = Client().get("/library/PUB001/donate")

        assert response.status_code == 200
        assert response.content.decode() == _neutral()

    @pytest.mark.parametrize("prefix", ["stall", "shed", "collections"])
    def test_the_donate_page_at_another_kinds_prefix_is_moved_to_the_libraries(
        self, built, owner, prefix
    ):
        _collection(owner, kind=Collection.Kind.LIBRARY)

        response = Client().get(f"/{prefix}/PUB001/donate")

        assert response.status_code == 301
        assert response["Location"] == "/library/PUB001/donate"

    @override_settings(EMAIL_LANGUAGE="es")
    def test_it_speaks_the_deployments_language(self, built, db):
        body = _body("/login")

        assert f'content="{escape(T("generic_parent_pitch", "es"))}"' in body

    def test_it_asks_the_database_nothing(self, built, django_assert_num_queries):
        with django_assert_num_queries(0):
            Client().get("/login")

    def test_a_private_collection_and_a_code_that_names_nothing_are_the_same_answer(
        self, built, owner
    ):
        _collection(owner, visibility=Collection.Visibility.PRIVATE)

        assert _body("/stall/PUB001") == _body("/stall/NOPE00")
        assert _body("/stall/PUB001").count("og:title") == 1

    def test_a_private_thing_and_a_share_link_that_name_nothing_are_too(self, built, owner):
        group = _collection(owner, visibility=Collection.Visibility.PRIVATE)
        _thing(owner, group)

        assert _body("/things/THG001") == _body("/things/NOPE00")
        assert _body("/share/nope") == _body("/login")


class TestWhatAStrangerCannotSee:
    def test_a_private_collection_gets_the_same_page_as_a_code_that_names_nothing(
        self, built, owner
    ):
        _collection(owner, visibility=Collection.Visibility.PRIVATE)

        # The same bytes as a code that names nothing: not a hint of the group.
        assert _body("/stall/PUB001") == _body("/stall/NOPE00") == _neutral()
        assert _body("/stall/PUB001/join") == _body("/stall/NOPE00/join")
        assert "The street" not in _body("/stall/PUB001")
        assert "Things we share" not in _body("/stall/PUB001")

    def test_an_inactive_public_collection_gets_the_same_page_as_a_neutral_route(
        self, built, owner
    ):
        _collection(owner, status=Collection.Status.INACTIVE)

        assert _body("/stall/PUB001") == _neutral()

    def test_an_unknown_code_gets_the_sites_card(self, built, db):
        assert _body("/collections/NOPE00") == _neutral()
        assert _body("/things/NOPE00") == _neutral()
        assert _body("/share/nope") == _neutral()


class TestEveryKindHasItsOwnPrefix:
    @pytest.mark.parametrize("kind", ["STALL", "LIBRARY", "SHED"])
    def test_a_collection_and_its_thing_are_previewed_under_their_kinds_prefix(
        self, built, owner, kind
    ):
        group = _collection(owner, kind=kind)
        _thing(owner, group)
        prefix = kind.lower()

        assert "<title>The street — OIUEEI</title>" in _body(f"/{prefix}/PUB001")
        assert "<title>The street — OIUEEI</title>" in _body(f"/{prefix}/PUB001/join")
        assert "<title>Drill — OIUEEI</title>" in _body(f"/{prefix}/PUB001/things/THG001")

    @pytest.mark.parametrize("kind", ["STALL", "LIBRARY", "SHED"])
    def test_a_private_one_gets_the_sites_card_under_every_prefix(self, built, owner, kind):
        _collection(owner, kind=kind, visibility=Collection.Visibility.PRIVATE)

        assert _body(f"/{kind.lower()}/PUB001") == _neutral()

    def test_the_old_prefix_reaches_the_preview_only_for_a_code_that_exists_nowhere(
        self, built, db
    ):
        assert _body("/collections/NOPE00") == _neutral()


class TestAThing:
    def test_both_routes_carry_the_things_own_data(self, built, owner):
        _thing(
            owner, _collection(owner, language="ca"), headline='{"es": "Taladro", "ca": "Trepant"}'
        )

        for path in ("/things/THG001", "/stall/PUB001/things/THG001"):
            body = _body(path)
            assert "<title>Trepant — OIUEEI</title>" in body, path
            assert '<meta property="og:title" content="Trepant">' in body, path

    def test_an_inactive_thing_gets_the_sites_card(self, built, owner):
        _thing(owner, _collection(owner), status=Thing.Status.INACTIVE)

        assert _body("/things/THG001") == _neutral()
        assert _body("/stall/PUB001/things/THG001") == _neutral()

    def test_a_thing_of_a_private_collection_gets_the_sites_card(self, built, owner):
        _thing(owner, _collection(owner, visibility=Collection.Visibility.PRIVATE))

        assert _body("/things/THG001") == _neutral()

    def test_the_things_other_pages_are_not_previewed(self, built, owner):
        _thing(owner, _collection(owner))

        assert _body("/things/THG001/request") == _neutral()


class TestAShareLink:
    @override_settings(MEDIA_PUBLIC_BASE_URL=MEDIA)
    def test_a_private_group_gives_name_and_description_but_never_the_photo(self, built, owner):
        _collection(
            owner,
            visibility=Collection.Visibility.PRIVATE,
            share_token=TOKEN,
            thumbnail="oiueei/u/cover.webp",
        )

        body = _body(f"/share/{TOKEN}")

        assert "<title>The street — OIUEEI</title>" in body
        assert '<meta property="og:description" content="Things we share">' in body
        assert "og:image" not in body
        assert "summary_large_image" not in body

    def test_a_revoked_or_unknown_token_or_an_inactive_group_gets_the_sites_card(
        self, built, owner
    ):
        _collection(owner, code="REV001", share_token=None)
        _collection(owner, code="OFF001", share_token=TOKEN, status=Collection.Status.INACTIVE)

        for token in ("never-issued", TOKEN):
            assert _body(f"/share/{token}") == _neutral(), token


class TestEscaping:
    def test_an_owners_markup_never_reaches_the_page_as_markup(self, built, owner):
        _collection(owner, headline='"><script>alert(1)</script>')

        body = _body("/stall/PUB001")

        assert "<script>alert" not in body
        assert "&quot;" in body

    def test_a_page_without_head_or_title_is_returned_as_it_was(self):
        preview = {"title": "T", "description": "d", "image": None}

        assert inject_preview("<p>x</p>", preview, "http://x/") == "<p>x</p>"
        assert inject_preview("<title>a</title>", preview, "http://x/") == "<title>a</title>"


class TestPlainDescription:
    @pytest.mark.parametrize(
        "markdown,expected",
        [
            ("see [the rules](https://x.test/r) now", "see the rules now"),
            ("a **bold** word", "a bold word"),
            ("an *italic* word", "an italic word"),
            ("# Title\ntext", "Title text"),
            ("- one\n* two\n+ three\n1. four", "one two three four"),
            ("| a | b |\n|---|---|", "a b"),
            ("line one\n\n\nline   two", "line one line two"),
            ("snake_case and _slant_", "snake_case and slant"),
            ("", ""),
            (None, ""),
        ],
    )
    def test_markup_goes_and_whitespace_collapses(self, markdown, expected):
        assert plain_description(markdown) == expected

    def test_a_long_text_is_cut_at_a_word_with_an_ellipsis(self):
        text = " ".join(["palabra"] * 60)

        out = plain_description(text)

        assert out.endswith("…")
        assert len(out) <= 201
        assert out[:-1].split(" ")[-1] == "palabra"

    def test_a_text_at_the_limit_is_kept_whole(self):
        assert plain_description("a" * 200) == "a" * 200


class TestQueryBudget:
    @pytest.mark.parametrize("path", ["/", "/me", "/login", "/things/THG001/request"])
    def test_neutral_routes_ask_the_database_nothing(self, built, django_assert_num_queries, path):
        with django_assert_num_queries(0):
            Client().get(path)

    def test_a_collection_costs_two_queries(self, built, owner, django_assert_max_num_queries):
        """One to see which kind's address it was asked at, one for the preview."""
        _collection(owner)

        with django_assert_max_num_queries(2):
            Client().get("/stall/PUB001")

    def test_the_donate_page_costs_the_one_query_of_the_kinds_address(
        self, built, owner, django_assert_max_num_queries
    ):
        _collection(owner, kind=Collection.Kind.LIBRARY)

        with django_assert_max_num_queries(1):
            Client().get("/library/PUB001/donate")

    def test_a_thing_costs_a_few(self, built, owner, django_assert_max_num_queries):
        _thing(owner, _collection(owner))

        with django_assert_max_num_queries(3):
            Client().get("/things/THG001")
