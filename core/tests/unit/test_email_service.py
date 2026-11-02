"""Unit tests for the email service: resilience and legally-required content.

A failing/slow SMTP provider must never propagate out of the email layer:
user actions whose DB work has already committed must not 500, and
multi-recipient loops must not abort on one bad recipient.

The MIME-structure and legal-footer tests below protect obligations that no
other test in the suite would notice going missing: nothing else renders a
real message and inspects it, so a regression here is silent everywhere else.
"""

import re
import smtplib
from html.parser import HTMLParser
from unittest.mock import patch

import pytest
from django.core import mail
from django.test import override_settings

from core.services import email_service
from core.tests.factories import also_in


def test_send_returns_false_on_smtp_error():
    """_send swallows an SMTP error and reports failure instead of raising."""
    with patch(
        "core.services.email_service.EmailMultiAlternatives.send",
        side_effect=smtplib.SMTPException("provider down"),
    ):
        result = email_service._send(
            "lolo9@your-domain.test",
            "Subject",
            "plain",
            "<p>html</p>",
            email_service.CATEGORY_MANDATORY,
            include_viral=False,
        )
    assert result is False


def test_send_returns_false_on_socket_error():
    """A socket-level error (timeout/connection) is also swallowed."""
    with patch(
        "core.services.email_service.EmailMultiAlternatives.send",
        side_effect=OSError("connection refused"),
    ):
        result = email_service._send(
            "lolo9@your-domain.test",
            "Subject",
            "plain",
            "<p>html</p>",
            email_service.CATEGORY_MANDATORY,
            include_viral=False,
        )
    assert result is False


@pytest.mark.django_db
def test_public_send_does_not_raise_when_provider_is_down():
    """A mandatory email (magic link) must not raise when SMTP fails — the
    sign-in action it backs must not 500 because mail is temporarily down.
    Needs DB access: the viral-line gate looks the recipient up."""
    with patch(
        "core.services.email_service.EmailMultiAlternatives.send",
        side_effect=smtplib.SMTPException("down"),
    ) as mock_send:
        email_service.send_magic_link_email("lolo9@your-domain.test", "https://x/verify/ABC123")
    # The send must have been ATTEMPTED — otherwise this test would also pass
    # if the function silently skipped sending, which is a different bug.
    mock_send.assert_called_once()


@pytest.mark.django_db
def test_html_email_embeds_logo_inline():
    """An activity email carries the OIUEEI logo as a CID attachment: one
    inline image attachment on the message, referenced from the HTML
    alternative, plain-text body untouched."""
    email_service.send_invite_rejected_email("Ana", "Ropa de invierno", "lala1@your-domain.test")

    assert len(mail.outbox) == 1
    msg = mail.outbox[0]
    assert len(msg.attachments) == 1
    assert msg.attachments[0]["Content-ID"] == "<oiueei-logo>"
    assert msg.attachments[0]["Content-Disposition"].startswith("inline")
    html_body = msg.alternatives[0][0]
    assert "cid:oiueei-logo" in html_body
    assert "cid:oiueei-logo" not in msg.body


@pytest.mark.django_db
def test_logo_send_uses_multipart_related():
    """The CID logo rides in multipart/related, not the default multipart/mixed,
    so Apple Mail renders it once inline instead of also appending a full-size
    copy with a paperclip. The multipart/alternative (plain + html) stays
    nested inside, and the logo keeps its Content-ID."""
    email_service.send_invite_rejected_email("Ana", "Ropa de invierno", "lala1@your-domain.test")

    assert len(mail.outbox) == 1
    msg = mail.outbox[0].message()
    assert msg.get_content_type() == "multipart/related"

    # The alternative (plain + html) is nested inside the related wrapper.
    alternative = next(
        part for part in msg.get_payload() if part.get_content_type() == "multipart/alternative"
    )
    subtypes = {part.get_content_type() for part in alternative.get_payload()}
    assert subtypes == {"text/plain", "text/html"}

    # The logo is still inline by CID, now a related sibling of the alternative.
    logo = next(part for part in msg.get_payload() if part["Content-ID"] == "<oiueei-logo>")
    assert logo.get_content_type() == "image/png"


@pytest.mark.django_db
def test_every_email_links_to_the_legal_page():
    """Art. 14 GDPR: every email carries a link to /legal, mandatory ones
    included — this is a disclosure duty, not an opt-out preference, so it
    can't live behind the same category gate as the "manage your emails"
    footer. Proven on a mandatory-category send (the magic link) precisely
    because that is the one category the preferences footer skips."""
    email_service.send_magic_link_email(
        "lele8@your-domain.test", "http://localhost:3000/verify/tok"
    )

    html = mail.outbox[0].alternatives[0][0]
    assert 'href="http://localhost:3000/legal"' in html


@pytest.mark.django_db
def test_the_legal_link_sits_inside_the_one_html_document():
    """The template renders only the top half of the card and `_bottom()` adds
    the footer after it, so the document must close exactly once, at the very
    end. Mandatory mail (the magic link) is the case with the shortest footer:
    a rule, the mark and the legal link, and nothing else to hide behind."""
    email_service.send_magic_link_email(
        "lele8@your-domain.test", "http://localhost:3000/verify/tok"
    )

    html = mail.outbox[0].alternatives[0][0]
    assert html.count("</html>") == 1
    assert html.index('href="http://localhost:3000/legal"') < html.index("</html>")
    assert html.rstrip().endswith("</html>")


@pytest.mark.django_db
def test_the_legal_link_follows_the_deployments_own_frontend_url():
    """Not hardcoded to localhost: a deployment sets MAGIC_LINK_BASE_URL to its
    real domain, and every derived link — this one included — has to follow."""
    with override_settings(MAGIC_LINK_BASE_URL="https://oiueei.example/verify"):
        email_service.send_magic_link_email(
            "lele8@your-domain.test", "https://oiueei.example/verify/x"
        )

    html = mail.outbox[0].alternatives[0][0]
    assert 'href="https://oiueei.example/legal"' in html


@pytest.mark.django_db
def test_the_legal_link_label_is_translated():
    with override_settings(EMAIL_LANGUAGE="es"):
        email_service.send_magic_link_email(
            "lele8@your-domain.test", "http://localhost:3000/verify/tok"
        )

    html = mail.outbox[0].alternatives[0][0]
    assert ">Legal y privacidad<" in html


# --- The magic link: greeting, button, fallback --------------


@pytest.mark.django_db
def test_magic_link_repeats_the_subjects_greeting_in_the_body():
    """The subject names the collection being joined, but an inbox preview
    shows only the subject — the body opens with the same greeting, so the
    message stands on its own once opened (and says *what* was joined before
    asking for the click). The collection is also this email's <h1> parent
    now, so the name appears twice — once as the title, once
    in the sentence beneath it."""
    email_service.send_magic_link_email(
        "lele8@your-domain.test",
        "http://localhost:3000/verify/tok",
        collection_headline="Chalmercadillo",
    )
    msg = mail.outbox[0]
    assert "welcome to 'Chalmercadillo'" in msg.subject
    assert "welcome to 'Chalmercadillo'" in msg.body
    html = msg.alternatives[0][0]
    # Django's autoescape turns the quotes around the name into &#x27; — assert
    # the escaped form, that IS what the reader's client will decode back into
    # 'Chalmercadillo'.
    assert "<h1" in html and ">Chalmercadillo</h1>" in html
    assert "Hello, welcome to &#x27;Chalmercadillo&#x27;!" in html
    assert html.index(">Chalmercadillo</h1>") < html.index("Hello, welcome")
    # The generic /login variant has no collection to be its parent: OIUEEI is,
    # with its own one-line pitch as the intro.
    mail.outbox.clear()
    email_service.send_magic_link_email("lele8@your-domain.test", "http://x/verify/t")
    generic_html = mail.outbox[0].alternatives[0][0]
    # No collection to be the parent: the mark itself leads as the <h1>,
    # not the literal word "OIUEEI".
    assert GENERIC_H1_LOGO_IMG in generic_html
    assert email_service.T("generic_parent_pitch", lang="en") in generic_html
    assert "Hello, welcome to OIUEEI!" in generic_html
    assert generic_html.index(GENERIC_H1_LOGO_IMG) < generic_html.index(
        email_service.T("generic_parent_pitch", lang="en")
    )


@pytest.mark.django_db
def test_magic_link_action_is_a_button_with_the_link_spelled_out():
    """Email clients strip <form>/<button> and ignore CSS custom properties,
    so the CTA is an inline-styled anchor in the app's literal bus blue — and
    the raw link follows as text, because the one click this email exists for
    is exactly what some clients refuse."""
    link = "http://localhost:3000/verify/tok"
    email_service.send_magic_link_email("lele8@your-domain.test", link)
    html = mail.outbox[0].alternatives[0][0]
    # The button: the magic link behind a bus-blue, white-text inline-styled
    # anchor — the token styles travel inline or not at all.
    assert (
        f'<a href="{link}" '
        'style="display:inline-block;background-color:#191919;color:#fafafa;' in html
    )
    # The fallback sentence, and the URL again as plain copy-pastable text.
    assert "copy and paste this link into your browser" in html
    assert f">{link}</a>" in html
    # The plain-text half never stopped carrying the raw link.
    assert link in mail.outbox[0].body


@pytest.mark.django_db
def test_the_invitation_email_tells_the_recipient_where_their_address_came_from():
    """Art. 14: this address was given to us by the inviter, not by its owner,
    so the invitation — the recipient's first contact with OIUEEI — has to say
    where it came from, what it's for, and that doing nothing ends it. Checked
    in both formats: a client that renders the plain body must not lose it."""
    email_service.send_collection_invite_email(
        "Lala",
        "Tools for the block",
        "lele14@your-domain.test",
        "http://localhost:3000/rsvp/accept",
        "http://localhost:3000/rsvp/reject",
    )

    msg = mail.outbox[0]
    note = "someone invited you"
    assert note in msg.body
    assert note in msg.alternatives[0][0]


@pytest.mark.django_db
def test_the_invitation_source_note_is_translated_too():
    with override_settings(EMAIL_LANGUAGE="ca"):
        email_service.send_collection_invite_email(
            "Lala",
            "Coses del barri",
            "lele14@your-domain.test",
            "http://localhost:3000/rsvp/accept",
            "http://localhost:3000/rsvp/reject",
        )

    assert "no et podrà tornar a convidar per correu durant un any" in mail.outbox[0].body


# The OIUEEI mark as the footer draws it (60x17) — the small size, wherever a
# non-generic email's footer still carries it. The generic "OIUEEI" parent case
# is different: the mark moves to the <h1>, bigger (see GENERIC_H1_LOGO_IMG /
# test_a_no_parent_email_...), and the footer carries none.
LOGO_IMG = (
    '<img src="cid:oiueei-logo" alt="OIUEEI" height="17" width="60" '
    'style="display:block;width:60px;height:17px;margin-bottom:15px;border:0;">'
)

# The mark as the <h1> draws it for a GENERIC_PARENT ("OIUEEI") email — 162x46,
# since the mark itself is the title there.
GENERIC_H1_LOGO_IMG = (
    '<img src="cid:oiueei-logo" alt="OIUEEI" height="46" width="162" '
    'style="display:block;width:162px;height:46px;border:0;">'
)


def _assert_the_footer_order(html, generic=False):
    """The bottom of every message, in one fixed order: a
    rule, the OIUEEI mark, then whatever else applies (viral line, "manage
    your preferences", a sender-specific extra line), and always last the
    legal link. Checks the two fixed points — mark right after the rule,
    legal genuinely last — since what sits between them varies per email.

    ``generic=True`` is the GENERIC_PARENT ("OIUEEI") case: the mark already
    led the message as its <h1>, at double size, so the footer carries none
    — the rule goes straight to whatever comes next (or to the legal link)."""
    if generic:
        assert LOGO_IMG not in html
    else:
        assert html.count(LOGO_IMG) == 1
    hr = '<hr style="border:none;border-top:1px solid #ddd;margin-top:24px;">'
    assert html.count(hr) == 1
    if not generic:
        assert html.index(hr) < html.index(LOGO_IMG)
        assert html.index(LOGO_IMG) < html.index("Legal")
    # Nothing after "Legal & privacy" but the card's own closing tags.
    tail = html[html.index("</a></p>", html.index("Legal")) :]
    assert tail.strip() == "</a></p></div></div></html>"


# --- The invitation: accept / decline as buttons -------------

INVITE_ACCEPT = "http://localhost:3000/rsvp/accept"
INVITE_REJECT = "http://localhost:3000/rsvp/reject"


def _invitation_html():
    email_service.send_collection_invite_email(
        "Lala", "Tools for the block", "lele14@your-domain.test", INVITE_ACCEPT, INVITE_REJECT
    )
    return mail.outbox[0].alternatives[0][0]


@pytest.mark.django_db
def test_the_invitation_answers_are_a_primary_and_a_secondary_button():
    """Accepting is the filled bus-blue button and declining the outlined one —
    the app's own primary/secondary split, as inline-styled anchors because
    email clients strip <button> and ignore CSS custom properties. They used
    to be two text links on one line, "Accept | Decline", equal in weight."""
    html = _invitation_html()

    primary = (
        f'<a href="{INVITE_ACCEPT}" '
        'style="display:inline-block;background-color:#191919;color:#fafafa;'
    )
    secondary = (
        f'<a href="{INVITE_REJECT}" '
        'style="display:inline-block;background-color:#ffffff;color:#191919;'
        "border:2px solid #191919;"
    )
    assert primary in html
    assert secondary in html
    # Each label sits inside its own button, accept first.
    assert ">Accept invitation</a>" in html
    assert ">Decline invitation</a>" in html
    assert html.index(primary) < html.index(secondary)
    # The old equal-weight "Accept | Decline" row is gone.
    assert f'<a href="{INVITE_ACCEPT}">Accept invitation</a>' not in html


@pytest.mark.django_db
def test_the_invitation_spells_both_links_out_under_the_buttons():
    """A button some clients will not draw is a dead end, and this email's whole
    job is one of two clicks. Both raw links follow as copy-pastable text —
    accept first, after a sentence saying why — and still before the art. 14
    note, which stays the last thing said."""
    email_service.send_collection_invite_email(
        "Lala", "Tools for the block", "lele14@your-domain.test", INVITE_ACCEPT, INVITE_REJECT
    )
    msg = mail.outbox[0]
    html = msg.alternatives[0][0]

    assert "copy and paste these links into your browser" in html
    accept_text = f">{INVITE_ACCEPT}</a>"
    reject_text = f">{INVITE_REJECT}</a>"
    assert accept_text in html
    assert reject_text in html
    assert html.index("Decline invitation</a>") < html.index("copy and paste these links")
    assert html.index(accept_text) < html.index(reject_text)
    assert html.index(reject_text) < html.index("someone invited you")
    # The plain-text half never stopped carrying both.
    assert INVITE_ACCEPT in msg.body
    assert INVITE_REJECT in msg.body


@pytest.mark.django_db
@pytest.mark.parametrize(
    "lang, phrase",
    [("es", "copia y pega estos enlaces"), ("ca", "copia i enganxa aquests enllaços")],
)
def test_the_invitation_link_fallback_is_translated_too(lang, phrase):
    with override_settings(EMAIL_LANGUAGE=lang):
        html = _invitation_html()

    assert phrase in html


# --- The hold request: confirm / cancel as buttons ----------

HOLD_ACCEPT = "http://localhost:3000/rsvp/confirm"
HOLD_REJECT = "http://localhost:3000/rsvp/cancel"


def _hold_request(user, user2, thing):
    """Send the owner's "someone asked for your thing" email; return the message."""
    from core.models import BookingPeriod

    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        status=BookingPeriod.Status.PENDING,
    )
    email_service.send_booking_request_email(
        user2, thing, booking, user.email, HOLD_ACCEPT, HOLD_REJECT
    )
    return mail.outbox[0]


@pytest.mark.django_db
def test_the_hold_request_answers_are_a_primary_and_a_secondary_button(user, user2, thing):
    """The owner's whole job in this email is one of two clicks, so it gets the
    invitation's shape: confirming is the filled bus-blue button and cancelling
    the outlined one, as inline-styled anchors (email clients strip <button>).
    They used to be two equal text links side by side."""
    html = _hold_request(user, user2, thing).alternatives[0][0]

    primary = (
        f'<a href="{HOLD_ACCEPT}" '
        'style="display:inline-block;background-color:#191919;color:#fafafa;'
    )
    secondary = (
        f'<a href="{HOLD_REJECT}" '
        'style="display:inline-block;background-color:#ffffff;color:#191919;'
        "border:2px solid #191919;"
    )
    assert primary in html
    assert secondary in html
    assert ">Confirm request</a>" in html
    assert ">Decline request</a>" in html
    assert html.index(primary) < html.index(secondary)
    # The old equal-weight row is gone.
    assert f'<a href="{HOLD_ACCEPT}">Confirm request</a>' not in html


@pytest.mark.django_db
def test_the_hold_request_spells_both_links_out_under_the_buttons(user, user2, thing):
    """A button some clients will not draw must not strand the owner: both raw
    links follow as copy-pastable text, confirm first, after a sentence saying
    why. The plain-text half never stopped carrying both."""
    msg = _hold_request(user, user2, thing)
    html = msg.alternatives[0][0]

    assert "copy and paste these links into your browser" in html
    accept_text = f">{HOLD_ACCEPT}</a>"
    reject_text = f">{HOLD_REJECT}</a>"
    assert accept_text in html
    assert reject_text in html
    assert html.index("Decline request</a>") < html.index("copy and paste these links")
    assert html.index(accept_text) < html.index(reject_text)
    assert HOLD_ACCEPT in msg.body
    assert HOLD_REJECT in msg.body


@pytest.mark.django_db
@pytest.mark.parametrize(
    "lang, label, phrase",
    [
        ("es", "Confirmar la solicitud", "copia y pega estos enlaces"),
        ("ca", "Rebutjar la sol·licitud", "copia i enganxa aquests enllaços"),
    ],
)
def test_the_hold_request_buttons_and_fallback_are_translated(
    user, user2, thing, lang, label, phrase
):
    with override_settings(EMAIL_LANGUAGE=lang):
        html = _hold_request(user, user2, thing).alternatives[0][0]

    assert f">{label}</a>" in html
    assert phrase in html


@pytest.mark.django_db
@pytest.mark.parametrize(
    "lang, confirm, decline, never",
    [
        ("es", "Confirmar la solicitud", "Rechazar la solicitud", "reserva"),
        ("ca", "Confirmar la sol·licitud", "Rebutjar la sol·licitud", "reserva"),
        ("en", "Confirm request", "Decline request", "Cancel"),
    ],
)
def test_the_hold_request_buttons_say_request_and_decline_never_reservation_or_cancel(
    user, user2, thing, lang, confirm, decline, never
):
    """A hold on a loan is a **request** ("reservation" is only RESERVE_THING, which
    confirms itself and never comes through here), and the second button *declines* it:
    it cancels nothing. The email used to say "Confirmar la reserva / Cancelar la
    reserva", where the app's own button said "Reject request". The buttons and the
    plain-text line that repeats them say the same."""
    with override_settings(EMAIL_LANGUAGE=lang):
        msg = _hold_request(user, user2, thing)
    html = msg.alternatives[0][0]

    assert f">{confirm}</a>" in html
    assert f">{decline}</a>" in html
    assert f"{confirm}: {HOLD_ACCEPT}" in msg.body
    assert f"{decline}: {HOLD_REJECT}" in msg.body
    for text in (html, msg.body):
        assert never not in text.replace(thing.headline, "")


# --- The house rule for action buttons ------------------------
#
# The primary action of an email — sign in, open the group, look at the thing —
# is a primary button, never a bare text link. Where an email asks a yes/no
# question, the positive answer is the primary button and the negative the
# secondary one. `_links` is the bare-text-link row; the rule says almost
# nothing may use it.

BUTTON_PRIMARY_START = 'style="display:inline-block;background-color:#191919;color:#fafafa;'


def _first_button(url):
    """The `<a>` anchor pointing at `url` that carries the primary button style."""
    return f'<a href="{url}" {BUTTON_PRIMARY_START}'


def test_no_email_action_is_ever_a_bare_text_link():
    """The rule, enforced on the source so a NEW email cannot quietly break it.

    `_links` draws a row of plain text links. It used to have one allowed
    caller — the account-erasure confirmation, kept a text link on the
    reasoning that a destructive step was not obviously the place for the
    app's friendliest control — until it was made a button too.
    `_links` now has NO callers left in
    the module; this fails the moment a new email reaches for it instead of
    `_cta` (one action) or `_ctas` (a yes/no pair)."""
    import ast
    import inspect

    tree = ast.parse(inspect.getsource(email_service))
    callers = set()
    for fn in ast.walk(tree):
        if isinstance(fn, ast.FunctionDef):
            for node in ast.walk(fn):
                if (
                    isinstance(node, ast.Call)
                    and isinstance(node.func, ast.Name)
                    and node.func.id == "_links"
                ):
                    callers.add(fn.name)
    assert callers == set(), (
        f"{sorted(callers)} draw a bare text link. "
        "An email's primary action is a primary button (_cta); a yes/no pair is "
        "_ctas (primary + secondary)."
    )


def test_the_light_no_fallback_button_is_gone():
    """`_button` used to be a lighter `_cta`: a bare button, no "copy and paste
    this link" sentence, no raw URL under it. The house rule grew a second
    clause: EVERY CTA repeats its link as plain text now, not
    only the ones whose whole job is one click — so the light variant has
    nothing left to be lighter than, and is deleted rather than kept unused."""
    assert not hasattr(email_service, "_button")


def test_every_single_action_cta_spells_its_own_link_out_below_it():
    """The single-button case, generically: whatever URL and label a caller
    gives `_cta`, both the fallback sentence and the raw link follow — this is
    what `_button` no longer existing has to mean in practice."""
    html = email_service._render_email(
        [email_service._cta("http://x/go", "Go there", "Trouble clicking?")], lang="en"
    )

    assert _first_button("http://x/go") in html
    assert ">Go there</a>" in html
    assert "Trouble clicking?" in html
    assert (
        '<a href="http://x/go" style="color:#191919 !important;text-decoration:underline !important;">http://x/go</a>'
        in html
    )


@pytest.mark.django_db
def test_signing_back_in_from_the_inactivity_email_is_a_primary_button(user):
    email_service.send_inactivity_warning_email(user, months=24, days=30, will_delete=True)

    html = mail.outbox[0].alternatives[0][0]
    assert _first_button("http://localhost:3000/login") in html


@pytest.mark.django_db
def test_opening_the_group_from_a_digest_is_a_primary_button(user):
    from core.models import Collection

    Collection.objects.create(code="COL001", owner=user, headline="C", kind="LIBRARY")
    email_service.send_digest_email(
        "Chalmercadillo", "COL001", ["A chair"], ["lili@your-domain.test"]
    )

    html = mail.outbox[0].alternatives[0][0]
    assert _first_button("http://localhost:3000/library/COL001") in html
    assert f">{email_service.T('view_collection_cta', lang='en')}</a>" in html


@pytest.mark.django_db
def test_opening_the_welcome_document_is_a_primary_button():
    email_service.send_collection_welcome_doc_email(
        "Chalmercadillo", "http://localhost:3000/doc.pdf", "lili@your-domain.test"
    )

    html = mail.outbox[0].alternatives[0][0]
    assert _first_button("http://localhost:3000/doc.pdf") in html


@pytest.mark.django_db
def test_the_proposal_answers_are_a_primary_and_a_secondary_button():
    """The owner deciding on a member's suggested guest is the same yes/no as
    the invitation and the hold request: approving is primary, rejecting the
    outlined secondary, both links spelled out after a sentence."""
    approve, reject = "http://localhost:3000/rsvp/yes", "http://localhost:3000/rsvp/no"
    email_service.send_invitation_proposal_email(
        "lala1@your-domain.test",
        "Lala",
        "Chalmercadillo",
        "lele4@your-domain.test",
        "",
        approve,
        reject,
    )

    html = mail.outbox[0].alternatives[0][0]
    assert _first_button(approve) in html
    secondary = (
        f'<a href="{reject}" style="display:inline-block;background-color:#ffffff;'
        "color:#191919;border:2px solid #191919;"
    )
    assert secondary in html
    assert html.index(_first_button(approve)) < html.index(secondary)
    assert "copy and paste these links into your browser" in html
    assert f">{approve}</a>" in html and f">{reject}</a>" in html


# --- Email addresses shown as data -----
#
# An address the reader should notice but not click as an action — a proposed
# guest, a contact form's sender, an operator alert's Owner — is bus blue,
# underlined, and now a real `mailto:` link: a client's own auto-linkification
# (Gmail, iOS/Android "data detectors") wraps a bare address that LOOKS like
# one in its own default blue regardless of any inline style on a non-anchor
# element around it, which kept happening after `!important` was added
# everywhere else. Making it a real anchor, in our colour, up
# front removes the client's opening to re-wrap it its own way. None is bold —
# `_email()` used to be, which was a second, unexplained treatment for
# the same kind of value `_field(email=True)` already rendered plainly.


def test_an_email_shown_as_its_own_value_is_a_plain_mailto_link():
    """`_email()` — the proposed guest's address on an invitation proposal,
    the declined proposal's own."""
    html = email_service._render_email([email_service._email("lele4@your-domain.test")], lang="en")

    assert (
        '<p><a href="mailto:lele4@your-domain.test" '
        'style="color:#191919 !important;text-decoration:underline !important;">'
        "lele4@your-domain.test</a></p>" in html
    )
    assert "<strong" not in html


def test_a_field_shown_as_an_address_is_a_plain_mailto_link():
    """`_field(label, value, email=True)` — the contact form's sender address."""
    html = email_service._render_email(
        [email_service._field("Email", "lili1@your-domain.test", email=True)], lang="en"
    )

    assert (
        '<p>Email: <a href="mailto:lili1@your-domain.test" '
        'style="color:#191919 !important;text-decoration:underline !important;">'
        "lili1@your-domain.test</a></p>" in html
    )
    assert "<strong" not in html


def test_a_named_email_field_keeps_the_name_plain_and_links_only_the_address():
    """`_named_email_field()` — the capacity alarm's Owner row: the person's name is not itself a
    link, only their parenthesised address is."""
    html = email_service._render_email(
        [email_service._named_email_field("Owner", "Lala", "lala14@your-domain.test")], lang="en"
    )

    assert (
        '<p>Owner: Lala (<a href="mailto:lala14@your-domain.test" '
        'style="color:#191919 !important;text-decoration:underline !important;">'
        "lala14@your-domain.test</a>)</p>" in html
    )


@pytest.mark.django_db
def test_the_capacity_alarms_owner_row_has_no_angle_brackets():
    """'Owner: Lala <lala6@your-domain.test>' read as
    a stray, unstyled HTML tag next to the name — parentheses instead, and
    only the address itself is a link (the two rows above)."""
    from core.models import Collection, User

    owner = User.objects.create(code="ALRMO2", email="lala@your-domain.test", name="Lala")
    collection = Collection.objects.create(
        code="ALRMC2", owner=owner, headline="Busy", status="ACTIVE"
    )
    User.objects.create(code="ALRMS2", email="lala2@your-domain.test", is_superuser=True)
    mail.outbox.clear()

    email_service.send_collection_capacity_alarm(collection, "things", 501, 500)

    html = mail.outbox[0].alternatives[0][0]
    assert f"<{owner.email}>" not in html
    assert (
        f"Owner: {owner.display_name} "
        f'(<a href="mailto:{owner.email}" '
        'style="color:#191919 !important;text-decoration:underline !important;">'
        f"{owner.email}</a>)" in html
    )
    plain = mail.outbox[0].body
    assert f"Owner: {owner.display_name} ({owner.email})" in plain


@pytest.mark.django_db
def test_every_email_declares_its_language_on_the_html_tag():
    """A4: a screen reader picks its pronunciation from `<html lang>`, and
    every email already speaks a specific, known language
    (`resolve_email_language`) — leaving the attribute blank was never
    "unknown", only unstated."""
    email_service.send_magic_link_email(
        "lele8@your-domain.test", "http://localhost:3000/verify/tok"
    )

    html = mail.outbox[0].alternatives[0][0]
    assert '<html lang="en">' in html


@pytest.mark.django_db
def test_the_html_lang_attribute_follows_the_recipients_own_language():
    email_service.send_magic_link_email(
        "lele8@your-domain.test", "http://localhost:3000/verify/tok", lang="ca"
    )

    html = mail.outbox[0].alternatives[0][0]
    assert '<html lang="ca">' in html


@pytest.mark.django_db
def test_a_sender_with_no_lang_in_scope_still_declares_the_deployment_default():
    # `lang` unset here reaches `_render_email(blocks, lang=None)` for real —
    # the same path an operator-only sender like send_collection_capacity_alarm
    # takes on purpose (no recipient to speak for) — and the tag still has to
    # name a real language, not render lang="".
    with override_settings(EMAIL_LANGUAGE="es"):
        email_service.send_magic_link_email("lele8@your-domain.test", "http://localhost:3000/x")

    html = mail.outbox[0].alternatives[0][0]
    assert '<html lang="es">' in html


# --- The viral line is a highlighted callout ----------------


@pytest.mark.django_db
def test_the_viral_line_is_a_pale_yellow_callout_with_black_text():
    """In the real message the growth line reads as one more grey
    footer sentence otherwise. A pale-yellow background + padding sets it
    apart; its own text is black, not the footer's muted grey — only the CTA
    link inside keeps the accent-coloured link style."""
    email_service.send_magic_link_email(
        "lele8@your-domain.test", "http://localhost:3000/verify/tok"
    )

    html = mail.outbox[0].alternatives[0][0]
    assert (
        f'<p style="font-size:{email_service.EMAIL_FOOTER_SIZE};color:#000000;'
        'background-color:#fff1a8;padding:10px;margin-top:16px;">' in html
    )


# --- The growth line leads to the form of the kind it names ----------


def _viral(line, monkeypatch, lang="en"):
    """Send the magic link with the growth line pinned to ``line``, and return the
    message and its HTML."""
    monkeypatch.setattr(email_service, "viral_lines", lambda lang=None: [line])
    email_service.send_magic_link_email(
        "lele8@your-domain.test", "http://localhost:3000/verify/tok", lang=lang
    )
    return mail.outbox[0], mail.outbox[0].alternatives[0][0]


@pytest.mark.django_db
def test_the_line_about_a_library_leads_to_the_form_of_a_library(monkeypatch):
    line = {"text": "A drill?", "cta": "Open your library", "path": "/library/new"}

    message, html = _viral(line, monkeypatch)

    assert 'href="http://localhost:3000/library/new"' in html
    assert "Open your library: http://localhost:3000/library/new" in message.body


@pytest.mark.django_db
def test_a_line_with_no_path_still_leads_to_the_chooser(monkeypatch):
    line = {"text": "Moving?", "cta": "Start here"}

    message, html = _viral(line, monkeypatch)

    assert 'href="http://localhost:3000/new"' in html
    assert "Start here: http://localhost:3000/new" in message.body


# --- The card gives up its own framing on a phone -----------


def test_the_card_and_page_shed_their_padding_below_480px():
    """Opening a real message in the Gmail iOS app: the page's 40px
    padding plus the card's own 24px stack to ~64px lost from each side on a
    phone-width screen, shrinking the reading column to almost nothing. Below
    480px both containers give up their framing (no grey/white split, no
    border, no radius) and the page div becomes the only, much smaller,
    source of padding."""
    html = email_service._render_email([email_service._para("Hi")], lang="en")

    assert 'class="oiueei-email-page" style="background-color:#f9fafb;padding:40px;"' in html
    assert 'class="oiueei-email-card" style="max-width:600px;' in html
    assert "@media only screen and (max-width: 480px) {" in html
    assert (
        ".oiueei-email-page { background-color: #ffffff !important; padding: 16px !important; }"
        in html
    )
    assert (
        ".oiueei-email-card { max-width: 100% !important; border: none !important; "
        "border-radius: 0 !important; padding: 0 !important; }" in html
    )


class _Page(HTMLParser):
    """One email's anchors (their attributes) and its `<style>` text, read with a
    real HTML parser rather than a regex over the markup."""

    def __init__(self, html):
        super().__init__()
        self.anchors = []
        self.css = ""
        self._in_style = False
        self.feed(html)
        self.close()

    def handle_starttag(self, tag, attrs):
        if tag == "a":
            self.anchors.append(dict(attrs))
        elif tag == "style":
            self._in_style = True

    def handle_endtag(self, tag):
        if tag == "style":
            self._in_style = False

    def handle_data(self, data):
        if self._in_style:
            self.css += data


def _phone_rules(css):
    """The rules inside the phone `@media` block of `css` (whitespace already
    normalised), as {selector: [declarations]} — read up to the brace that closes
    the block, so neither indentation nor line breaks matter."""
    query = "@media only screen and (max-width: 480px) {"
    assert query in css, "the phone media query is gone"
    start = css.index(query) + len(query)
    depth = 1
    end = start
    while depth:
        depth += {"{": 1, "}": -1}.get(css[end], 0)
        end += 1
    return {
        selector.strip(): [d.strip() for d in body.split(";") if d.strip()]
        for selector, body in re.findall(r"([^{}]+)\{([^{}]*)\}", css[start : end - 1])
    }


def test_buttons_go_full_width_below_480px():
    """Every button carries the class its phone and hover rules are written against,
    so on a phone all of them fill the width of the text column. In the same
    real message, a button sized to its own label sits
    narrower than the paragraphs around it once the card's own padding is gone
    too — full width, centred, aligned with the text column either side. The
    `ctas` pair's side margin (for the desktop side-by-side layout) has to be
    zeroed here too, or a 100%-wide box plus that margin would overflow past the
    text's own right edge.

    Read from a message that has a real button, and by declaration rather than by
    the stylesheet's layout: the rule is inert unless the anchor carries the class."""
    html = email_service._render_email(
        [email_service._cta("https://x.test/a", "Go", "Or open:")], lang="en"
    )
    page = _Page(html)

    rules = _phone_rules(" ".join(page.css.split()))

    selector = ".btn-primary, .btn-secondary"
    assert selector in rules, sorted(rules)
    assert set(rules[selector]) == {
        "display: block !important",
        "width: 100% !important",
        "box-sizing: border-box !important",
        "text-align: center !important",
        "margin: 0 0 12px 0 !important",
    }
    # The button, not the plain fallback link under it (same href, no class).
    [button] = [
        a
        for a in page.anchors
        if (a.get("style") or "").startswith(email_service.email_style()["btn_primary"])
    ]
    assert (button.get("class") or "").split() == ["btn-primary"]


# --- Dates in emails render DD/MM/YYYY, not ISO ------------------------------


def test_fmt_date_renders_ddmmyyyy_and_tolerates_junk():
    from datetime import date, datetime

    assert email_service._fmt_date(date(2026, 3, 5)) == "05/03/2026"
    assert email_service._fmt_date(datetime(2026, 3, 5, 9, 30)) == "05/03/2026"
    assert email_service._fmt_date("2026-03-05") == "05/03/2026"
    assert email_service._fmt_date("2026-03-05T09:30:00Z") == "05/03/2026"
    assert email_service._fmt_date(None) == ""
    assert email_service._fmt_date("") == ""
    assert email_service._fmt_date("whenever") == "whenever"  # passed through, not dropped


@pytest.mark.django_db
def test_a_dated_booking_email_shows_the_dates_ddmmyyyy(user, user2, thing):
    """The SPA and the date pickers speak DD/MM/YYYY; the emails must match, so
    a member never sees the same booking two ways."""
    from datetime import date

    from core.models import BookingPeriod

    thing.type = "LEND_THING"
    thing.save(update_fields=["type"])
    start, end = date(2026, 3, 5), date(2026, 3, 12)
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=start,
        end_date=end,
        status=BookingPeriod.Status.PENDING,
    )

    email_service.send_booking_request_email(
        user2, thing, booking, user.email, "http://x/a", "http://x/r"
    )

    body = mail.outbox[0].body
    html = mail.outbox[0].alternatives[0][0]
    assert "05/03/2026" in body and "12/03/2026" in body
    assert "05/03/2026" in html
    assert "2026-03-05" not in body and "2026-03-05" not in html


# --- "We've let the person who runs it know" ---
#
# The "Your request was sent" email named the thing's owner ("Hemos avisado a
# Lala"), but with a team the request reaches everyone who runs the thing. It now
# says who was told by number — the person who runs it, or the people who run it — and
# the verb follows ("responderá" / "responderán"), in the HTML paragraph and in both
# plain-text sentences. How many were told is the request's fan-out: the thing's
# managers bar the requester. It does not say "dinamizador" / "curator" (untrue in
# a COMMUNITY, where whoever runs a thing is its owner) and uses the request page's own
# words, letter by letter.

TOLD = {
    "es": (
        "Hemos avisado a quien gestiona esta cosa — te responderá pronto.",
        "Hemos avisado a quienes gestionan esta cosa — te responderán pronto.",
    ),
    "ca": (
        "Hem avisat qui gestiona aquesta cosa — aviat et respondrà.",
        "Hem avisat les persones que gestionen aquesta cosa — aviat et respondran.",
    ),
    "en": (
        "We've let the person who runs it know — they'll get back to you soon.",
        "We've let the people who run it know — they'll get back to you soon.",
    ),
}


def _told_by(user, user2, thing, lang, informed, dates):
    from datetime import date

    user2.language = lang
    user2.save(update_fields=["language"])
    if dates:
        booking = _loan(user, user2, thing, date(2026, 10, 13), date(2026, 10, 15))
    else:
        booking = _loan(user, user2, thing, None, None)
    mail.outbox.clear()
    email_service.send_booking_confirmation_email(user2, thing, booking, informed=informed)
    return mail.outbox[0]


@pytest.mark.django_db
@pytest.mark.parametrize("dates", [True, False], ids=["dated", "undated"])
@pytest.mark.parametrize("informed, which", [(1, 0), (2, 1), (5, 1)])
@pytest.mark.parametrize("lang", ["en", "es", "ca"])
def test_the_confirmation_says_who_runs_it_by_how_many_were_told(
    user, user2, thing, lang, informed, which, dates
):
    msg = _told_by(user, user2, thing, lang, informed, dates)

    from django.utils.html import escape

    said, other = TOLD[lang][which], TOLD[lang][1 - which]
    html = msg.alternatives[0][0]
    # The whole sentence, in the HTML paragraph (escaped, as the email escapes it)
    # and in the plain-text body…
    assert escape(said) in html
    assert said in msg.body
    # …never the other number's, and never the owner's name.
    assert escape(other) not in html
    assert other not in msg.body
    assert user.name not in html
    assert user.name not in msg.body


@pytest.mark.django_db
def test_without_being_told_how_many_the_confirmation_counts_them_itself(
    user, user2, thing, collection
):
    """The request's fan-out passes the number; called without it (the sample
    command, an older caller) the email works it out the same way: the thing's
    managers, bar the requester."""
    from datetime import date

    from core.models import Collection, User

    co_curator = User.objects.create(code="CURA01", email="lele10@your-domain.test", name="Cura")
    collection.mode = Collection.Mode.PROPRIETARY
    collection.save(update_fields=["mode"])
    collection.invites.add(co_curator, user2)
    collection.co_owners.add(co_curator)
    booking = _loan(user, user2, thing, date(2026, 10, 13), date(2026, 10, 15))
    mail.outbox.clear()

    email_service.send_booking_confirmation_email(user2, thing, booking)
    assert TOLD["en"][1] in mail.outbox[0].body  # the founder and the co-curator

    # Now the one asking is the co-curator: only the founder is left to warn.
    booking_by_curator = _loan(user, co_curator, thing, date(2026, 10, 13), date(2026, 10, 15))
    mail.outbox.clear()
    email_service.send_booking_confirmation_email(co_curator, thing, booking_by_curator)
    assert TOLD["en"][0] in mail.outbox[0].body


# --- A declined request is "declined", not "cancelled" ----------
#
# The manager presses "Decline request" and the requester's app says "Request
# declined — X declined your request", but their email said the request "has been
# cancelled", which reads as though they had cancelled it themselves. The word is
# one catalogue value interpolated into the intro and into both plain-text
# sentences, so it has to be right in all of them. The subject ("didn't go
# through") never named it.

DECLINED = {
    "en": ("declined", "cancelled", "Your request didn't go through"),
    "es": ("rechazada", "cancelada", "Tu solicitud no ha salido adelante"),
    "ca": ("rebutjada", "cancel·lada", "La teva sol·licitud no ha tirat endavant"),
}
CONFIRMED = {"en": "confirmed", "es": "confirmada", "ca": "confirmada"}


@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["en", "es", "ca"])
def test_a_declined_request_email_says_declined_never_cancelled(user, user2, thing, lang):
    from datetime import date

    user2.language = lang
    user2.save(update_fields=["language"])
    booking = _loan(user, user2, thing, date(2026, 10, 13), date(2026, 10, 15))
    mail.outbox.clear()

    email_service.send_booking_decision_email(booking, thing, accepted=False)

    msg = mail.outbox[0]
    html = msg.alternatives[0][0]
    word, old_word, subject = DECLINED[lang]
    assert msg.subject == subject  # the subject did not change
    # The plain-text sentence and the HTML introduction both carry the word.
    assert word in msg.body
    assert word in html
    assert old_word not in msg.body.lower()
    assert old_word not in html.lower()


@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["en", "es", "ca"])
def test_a_confirmed_request_email_still_says_confirmed(user, user2, thing, lang):
    from datetime import date

    user2.language = lang
    user2.save(update_fields=["language"])
    booking = _loan(user, user2, thing, date(2026, 10, 13), date(2026, 10, 15))
    mail.outbox.clear()

    email_service.send_booking_decision_email(booking, thing, accepted=True)

    msg = mail.outbox[0]
    assert CONFIRMED[lang] in msg.body
    assert DECLINED[lang][0] not in msg.body


# --- A booking for a single day says the day once ---------------
#
# "Tu solicitud está confirmada — Fechas: 13/10/2026 - 13/10/2026": a loan or a
# rental that starts and ends the same day printed it twice, in the "Dates" line
# and again in the plain-text sentence ("from the 13th to the 13th"). The same
# rule as the inbox: one day, one date; a longer booking is still a range.

# What each language says for "one day" and for a range, in the plain text.
ONE_DAY = {"en": "on 13/10/2026", "es": "el 13/10/2026", "ca": "el 13/10/2026"}
A_RANGE = {
    "en": "from 13/10/2026 to 15/10/2026",
    "es": "del 13/10/2026 al 15/10/2026",
    "ca": "del 13/10/2026 al 15/10/2026",
}


def _loan(user, user2, thing, start, end):
    from core.models import BookingPeriod

    thing.type = "LEND_THING"
    thing.save(update_fields=["type"])
    return BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=start,
        end_date=end,
        status=BookingPeriod.Status.PENDING,
    )


def _send_each_booking_email(user, user2, thing, booking):
    """The three emails that carry a booking's dates: the request to the owner, the
    answer to the requester, and the requester's own confirmation."""
    email_service.send_booking_request_email(
        user2, thing, booking, user.email, "http://x/a", "http://x/r"
    )
    email_service.send_booking_decision_email(booking, thing, accepted=True)
    email_service.send_booking_confirmation_email(user2, thing, booking)
    return {m.subject: m for m in mail.outbox}.values()


@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["en", "es", "ca"])
def test_a_single_day_loan_says_its_date_once_in_every_booking_email(user, user2, thing, lang):
    from datetime import date

    user.language = user2.language = lang
    user.save(update_fields=["language"])
    user2.save(update_fields=["language"])
    booking = _loan(user, user2, thing, date(2026, 10, 13), date(2026, 10, 13))
    mail.outbox.clear()

    emails = list(_send_each_booking_email(user, user2, thing, booking))

    assert len(emails) == 3
    for msg in emails:
        html = msg.alternatives[0][0]
        # The "Dates" line carries the day once…
        assert html.count("13/10/2026") == 1, msg.subject
        assert "13/10/2026 - 13/10/2026" not in html
        # …and so does the sentence, said as one day and not as a range.
        assert ONE_DAY[lang] in msg.body, msg.subject
        assert msg.body.count("13/10/2026") == 1, msg.subject


@pytest.mark.django_db
@pytest.mark.parametrize("lang", ["en", "es", "ca"])
def test_a_loan_over_several_days_is_still_a_range_in_every_booking_email(user, user2, thing, lang):
    from datetime import date

    user.language = user2.language = lang
    user.save(update_fields=["language"])
    user2.save(update_fields=["language"])
    booking = _loan(user, user2, thing, date(2026, 10, 13), date(2026, 10, 15))
    mail.outbox.clear()

    for msg in _send_each_booking_email(user, user2, thing, booking):
        assert "13/10/2026 - 15/10/2026" in msg.alternatives[0][0], msg.subject
        assert A_RANGE[lang] in msg.body, msg.subject


@pytest.mark.django_db
def test_a_one_day_reservation_says_its_day_once_in_the_dates_line(user, user2, thing):
    """A whole-day reservation prints its last day inclusive, so a one-day one has
    the same start and end — the same single date as the loan above."""
    from datetime import date

    from core.models import BookingPeriod

    thing.type = "RESERVE_THING"
    thing.save(update_fields=["type"])
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=date(2026, 10, 13),
        end_date=date(2026, 10, 14),  # the day the space is free again
        status=BookingPeriod.Status.ACCEPTED,
    )
    mail.outbox.clear()

    email_service.send_reservation_notice_email(user.email, user2, thing, booking, None)

    html = mail.outbox[0].alternatives[0][0]
    assert html.count("13/10/2026") == 1
    assert "13/10/2026 - 13/10/2026" not in html


# --- Every email names one parent, as its <h1> -------------
#
# A thing's own headline for thing-scoped mail (people recognise the drill,
# the room, the listing — not a group name they may belong to several of), a
# collection's for collection-scoped mail, the FAQ question itself for the
# three FAQ emails, "OIUEEI" for the rest. It replaced an earlier rule where
# every thing-scoped email named its *collection* at the top instead.


@pytest.mark.django_db
def test_a_collection_scoped_email_leads_with_the_collection_name(user):
    """A genuinely collection-scoped email (no thing, no FAQ question involved)
    still takes the collection's name as its <h1>, as it always did —
    the invitation is one of these."""
    email_service.send_collection_invite_email(
        "Lala", "Chalmercadillo", "lele14@your-domain.test", "http://x/a", "http://x/r"
    )

    msg = mail.outbox[0]
    html = msg.alternatives[0][0]
    assert "<h1" in html and ">Chalmercadillo</h1>" in html
    assert html.index(">Chalmercadillo</h1>") < html.index("Legal")
    _assert_the_footer_order(html)
    # Plain-text body opens with the collection name too.
    assert msg.body.startswith("Chalmercadillo")


@pytest.mark.django_db
def test_a_thing_scoped_email_names_the_thing_not_its_collection(user, user2, thing):
    """The `thing` fixture ("Test Thing") lives in "Test Collection" — a
    reservation-style email about it now names the THING at the top, not the
    group it happens to be in (it used to be the collection's
    name). The wordmark still closes the message, after the rule."""
    from datetime import date

    from core.models import BookingPeriod

    thing.type = "RESERVE_THING"
    thing.save(update_fields=["type"])
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=date(2026, 3, 5),
        end_date=date(2026, 3, 6),
        status=BookingPeriod.Status.ACCEPTED,
    )

    email_service.send_reservation_notice_email(user.email, user2, thing, booking)

    msg = mail.outbox[0]
    html = msg.alternatives[0][0]
    assert "<h1" in html and ">Test Thing</h1>" in html
    assert html.index(">Test Thing</h1>") < html.index("Legal")
    assert "Test Collection" not in html
    _assert_the_footer_order(html)
    assert html.index(">Test Thing</h1>") < html.index(LOGO_IMG)
    assert msg.body.startswith("Test Thing")


@pytest.mark.django_db
def test_the_reservation_notice_names_the_requesters_email(user, user2, thing):
    """The notice used to name who reserved but not how to reach
    them, leaving the owner with nothing to act on. The requester's address
    is a legitimate one to show here (the exception to never naming anyone by
    their address — the reader already holds it, via
    BookingPeriodSerializer.requester_email in the app), so it now rides the
    notice too, as a bus-blue mailto: link."""
    from datetime import date

    from core.models import BookingPeriod

    thing.type = "RESERVE_THING"
    thing.save(update_fields=["type"])
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=date(2026, 3, 5),
        end_date=date(2026, 3, 6),
        status=BookingPeriod.Status.ACCEPTED,
    )

    email_service.send_reservation_notice_email(user.email, user2, thing, booking)

    msg = mail.outbox[0]
    html = msg.alternatives[0][0]
    assert (
        f'Email: <a href="mailto:{user2.email}" '
        'style="color:#191919 !important;text-decoration:underline !important;">'
        f"{user2.email}</a>" in html
    )
    assert f"Email: {user2.email}" in msg.body


@pytest.mark.django_db
def test_a_standalone_things_email_names_the_thing_too(user, user2):
    """A thing in no collection has no group to name either way — it was
    always the thing (or nothing) for a standalone one; unchanged here, this
    just confirms the new footer order still holds for it."""
    from datetime import date

    from core.models import BookingPeriod, Thing

    loner = Thing.objects.create(code="LONER1", type="LEND_THING", owner=user, headline="Ladder")
    booking = BookingPeriod.objects.create(
        thing_code=loner,
        thing_type=loner.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=date(2026, 3, 5),
        end_date=date(2026, 3, 12),
        status=BookingPeriod.Status.PENDING,
    )

    email_service.send_booking_request_email(
        user2, loner, booking, user.email, "http://x/a", "http://x/r"
    )

    html = mail.outbox[0].alternatives[0][0]
    assert ">Ladder</h1>" in html
    _assert_the_footer_order(html)
    assert html.index(">Ladder</h1>") < html.index(LOGO_IMG)
    assert mail.outbox[0].body.startswith("Ladder")


@pytest.mark.django_db
def test_a_no_parent_email_still_gets_oiueei_as_its_h1(user):
    """Account-lifecycle mail (here: the erasure link) has no thing, no
    collection, no question — "OIUEEI" is its <h1> (it used to
    grow no header at all), without the generic pitch (a destructive step is
    not a pitch moment — see GENERIC_PARENT's own docstring)."""
    email_service.send_account_delete_email(user, "http://x/confirm")

    html = mail.outbox[0].alternatives[0][0]
    # The mark itself is the <h1> now — double the footer size, no literal
    # "OIUEEI" text ("OIUEEI is the protagonist" of this kind
    # of email — the mark moves up rather than appearing twice).
    assert GENERIC_H1_LOGO_IMG in html
    assert html.count("cid:oiueei-logo") == 1  # once total: h1 only, footer none
    assert ">OIUEEI</h1>" not in html
    assert email_service.T("generic_parent_pitch", lang="en") not in html
    _assert_the_footer_order(html, generic=True)


@pytest.mark.django_db
def test_every_logo_is_the_small_mark_and_the_file_cannot_be_drawn_giant(user):
    """The OIUEEI mark is 60x17 in the footer (up from 53x15)
    wherever the parent is a real
    thing/collection/question — the erasure email now being a GENERIC_PARENT
    case (its mark leads as a bigger <h1> instead, see the test below), a
    collection-scoped send is what still exercises the small footer mark.
    Apple Mail ignored the width/height attributes and drew the old 212x60
    file at its natural size while Gmail honoured them, so the size is also
    declared as inline CSS regardless of the file's own pixels.
    **The file itself is 1944x552** (a second Figma export, with a lighter font weight and
    the same display sizes), replacing
    the earlier 106x30 (2x) and then 846x240 versions, both reported pixelated
    on a real screen: a client honouring the displayed 60x17 draws crisp,
    heavily-oversampled art; one that ignores both attributes and CSS — Apple
    Mail's old behaviour — draws it at its full file size, big rather than
    giant, and still not garbled. The PNG stays small on disk despite the
    resolution because it is flat two-colour line art."""
    import struct

    email_service.send_collection_revoke_email("Lala", "Chalmercadillo", user.email)

    msg = mail.outbox[0]
    html = msg.alternatives[0][0]
    assert 'height="17" width="60"' in html
    assert "width:60px;height:17px" in html
    assert 'height="46"' not in html
    logo = next(p for p in msg.attachments if p["Content-ID"] == "<oiueei-logo>")
    png = logo.get_payload(decode=True)
    width, height = struct.unpack(">II", png[16:24])
    assert (width, height) == (1944, 552)


@pytest.mark.django_db
def test_a_generic_parent_emails_mark_is_the_h1_bigger_than_the_footer(user):
    """The one exception: when "OIUEEI" is the parent, its own mark leads the
    message as the <h1> — 162x46, bigger than the footer's
    60x17 — and the footer carries none, so the mark never appears twice."""
    email_service.send_account_delete_email(user, "http://x/confirm")

    html = mail.outbox[0].alternatives[0][0]
    assert GENERIC_H1_LOGO_IMG in html
    assert html.count("cid:oiueei-logo") == 1
    assert LOGO_IMG not in html


@pytest.mark.django_db
def test_the_header_speaks_the_readers_language(user):
    """A bilingual collection headline resolves to the reader's own language in
    the header, like every other owner-written value in an email."""
    import json

    from core.models import Collection, User

    catalan = User.objects.create(email="lele@your-domain.test", language="ca")
    collection = Collection.objects.create(
        code="BILN01",
        owner=user,
        headline=json.dumps({"es": "Cosas de casa", "ca": "Coses de casa"}),
    )
    collection.invites.add(catalan)

    email_service.send_collection_revoke_email(
        "Owner", collection.headline, catalan.email, collection=collection
    )

    html = mail.outbox[0].alternatives[0][0]
    assert "Coses de casa" in html and "Cosas de casa" not in html
    # No bold repeat of the name in the body — the header carries it now.
    assert "<strong>Coses de casa</strong>" not in html


# --- _fmt_when: HOUR-unit reservations in the four reservation emails -------
#
# The four RESERVE_THING senders already read "{start} to {end}" / "del
# {start} al {end}" in all three catalogues — no template changed. What
# changed is what `start`/`end` are for an HOUR-unit booking (start_time set):
# the date once, on `start`, then both HH:MM times, so "05/10/2026 10:00 to
# 13:00" reads correctly with no catalogue edits.


def test_fmt_when_a_one_day_reservation_ends_on_that_day():
    """A DAY-unit reservation stores ``end_date = start + duration`` — the day the
    space is free again. The emails used to print it as the end, so a one-day
    reservation on the 5th was "confirmed for 05/10 to 06/10": a day the member
    never booked, and possibly somebody else's."""
    from datetime import date

    from core.models import BookingPeriod

    booking = BookingPeriod(start_date=date(2026, 10, 5), end_date=date(2026, 10, 6))

    assert email_service._fmt_when(booking) == ("05/10/2026", "05/10/2026")


def test_fmt_when_a_multi_day_reservation_ends_on_its_last_day():
    from datetime import date

    from core.models import BookingPeriod

    # Three days from Monday the 5th: the 5th, 6th and 7th.
    booking = BookingPeriod(start_date=date(2026, 10, 5), end_date=date(2026, 10, 8))

    assert email_service._fmt_when(booking) == ("05/10/2026", "07/10/2026")


def test_fmt_when_an_hourly_booking_names_the_date_once_and_two_times():
    from datetime import date, time

    from core.models import BookingPeriod

    booking = BookingPeriod(
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 6),  # the day-based "free again" marker, unused here
        start_time=time(10, 0),
        end_time=time(13, 0),
    )

    assert email_service._fmt_when(booking) == ("05/10/2026 10:00", "13:00")


@pytest.mark.django_db
def test_an_hourly_reservation_confirmation_reads_correctly_in_all_three_languages(
    user, user2, thing
):
    from datetime import date, time

    from core.models import BookingPeriod

    thing.type = "RESERVE_THING"
    thing.save(update_fields=["type"])
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 6),
        start_time=time(10, 0),
        end_time=time(13, 0),
        status=BookingPeriod.Status.ACCEPTED,
    )

    expectations = {
        "en": "05/10/2026 10:00 to 13:00",
        "es": "del 05/10/2026 10:00 al 13:00",
        "ca": "del 05/10/2026 10:00 al 13:00",
    }
    for lang, phrase in expectations.items():
        mail.outbox.clear()
        with override_settings(EMAIL_LANGUAGE=lang):
            email_service.send_reservation_confirmed_email(user2, thing, booking)
        body = mail.outbox[0].body
        assert phrase in body, f"{lang}: {phrase!r} not in {body!r}"


@pytest.mark.django_db
def test_a_day_reservation_confirmation_names_the_days_booked_and_no_other(user, user2, thing):
    from datetime import date

    from core.models import BookingPeriod

    thing.type = "RESERVE_THING"
    thing.save(update_fields=["type"])
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 7),  # two days: the 5th and the 6th
        status=BookingPeriod.Status.ACCEPTED,
    )

    email_service.send_reservation_confirmed_email(user2, thing, booking)

    sent = mail.outbox[0]
    for part in (sent.body, sent.alternatives[0][0]):
        assert "06/10/2026" in part
        assert "07/10/2026" not in part


@pytest.mark.django_db
@pytest.mark.parametrize(
    ("lang", "one_day", "two_days"),
    [
        ("en", "on 05/10/2026", "from 05/10/2026 to 06/10/2026"),
        ("es", "el 05/10/2026", "del 05/10/2026 al 06/10/2026"),
        ("ca", "el 05/10/2026", "del 05/10/2026 al 06/10/2026"),
    ],
)
def test_the_plain_text_of_every_reservation_email_says_a_single_day_once(
    user, user2, thing, lang, one_day, two_days
):
    """A one-day reservation read "from 05/10/2026 to 05/10/2026" in the plain text of
    the reservation sentences, while the app and the HTML already said one date.
    A two-day one keeps its range."""
    from datetime import date

    from core.models import BookingPeriod

    thing.type = "RESERVE_THING"
    thing.save(update_fields=["type"])

    def booking(end):
        return BookingPeriod.objects.create(
            thing_code=thing,
            thing_type=thing.type,
            requester_code=user2,
            requester_email=user2.email,
            owner_code=user,
            start_date=date(2026, 10, 5),
            end_date=end,
            status=BookingPeriod.Status.ACCEPTED,
        )

    senders = [
        lambda b: email_service.send_reservation_confirmed_email(user2, thing, b),
        lambda b: email_service.send_reservation_notice_email(user.email, user2, thing, b),
        lambda b: email_service.send_reservation_cancelled_email(
            user2.email, "Lala", thing, b, cancelled_by_owner=True
        ),
        lambda b: email_service.send_reservation_cancelled_email(
            user.email, "Lele", thing, b, cancelled_by_owner=False
        ),
        lambda b: email_service.send_reservation_cancel_confirmation_email(
            user2.email, thing, b, is_own_reservation=True
        ),
        lambda b: email_service.send_reservation_cancel_confirmation_email(
            user.email, thing, b, is_own_reservation=False, member_name="Lele"
        ),
        lambda b: email_service.send_reservation_reminder_email(user2.email, thing, b),
    ]
    one, two = booking(date(2026, 10, 6)), booking(date(2026, 10, 7))
    with override_settings(EMAIL_LANGUAGE=lang):
        for send in senders:
            mail.outbox.clear()
            send(one)
            plain = mail.outbox[0].body
            assert one_day in plain, plain
            assert plain.count("05/10/2026") == 1, plain
            mail.outbox.clear()
            send(two)
            assert two_days in mail.outbox[0].body


# --- The owner's email note (Collection.email_note) ------------------------------


def test_note_blocks_renders_bold_links_lists_and_emojis():
    """The subset a 512-char note actually needs, rendered to one md block."""
    plain, blocks = email_service._note_blocks(
        "Hola! **Léenos** 🛠️\n"
        "\n"
        "- Trae tu [carnet](https://your-domain.test/reglas)\n"
        "- Planta 2\n"
        "\n"
        "1. Confirma\n"
        "2. Llega pronto"
    )
    # The plain half is the raw Markdown — the standard text/plain alternative.
    assert plain.startswith("Hola! **Léenos**")
    assert len(blocks) == 1 and blocks[0]["type"] == "md"
    html = str(blocks[0]["html"])
    assert "<p>Hola! <strong>Léenos</strong> 🛠️</p>" in html
    expected_list = (
        '<ul><li>Trae tu <a href="https://your-domain.test/reglas" '
        'style="color:#191919 !important;text-decoration:underline !important;">'
        "carnet</a> (your-domain.test)</li>"
        "<li>Planta 2</li></ul>"
    )
    assert expected_list in html
    assert "<ol><li>Confirma</li><li>Llega pronto</li></ol>" in html


def test_note_blocks_leaves_an_unsafe_url_as_literal_text():
    """A javascript: 'link' is not a link in the email — a dead href="#"
    would be worse than the raw text (the deliberate divergence from the
    frontend's sanitizeUrl)."""
    _, blocks = email_service._note_blocks("mira [esto](javascript:alert(1))")
    html = str(blocks[0]["html"])
    assert "<a " not in html
    assert "[esto](javascript:alert(1))" in html


def test_a_link_dressed_as_another_address_names_where_it_really_goes():
    """The owner picks both the text and the target, and the email leaves from
    the operator's own domain — so text that looks like the operator's sign-in
    link must not be all the reader sees."""
    _, blocks = email_service._note_blocks(
        "[https://www.your-domain.test/verify/abc](https://elsewhere.example/verify)"
    )
    html = str(blocks[0]["html"])
    assert html == (
        '<p><a href="https://elsewhere.example/verify" '
        'style="color:#191919 !important;text-decoration:underline !important;">https://www.your-domain.test/verify/abc</a>'
        " (elsewhere.example)</p>"
    )


def test_a_link_whose_text_is_its_own_url_needs_no_host():
    _, blocks = email_service._note_blocks(
        "[https://your-domain.test/a?b=1&c=2](https://your-domain.test/a?b=1&c=2)"
    )
    html = str(blocks[0]["html"])
    # Escaped once — the & survives as one &amp;, never &amp;amp; — and no
    # "(your-domain.test)" repeating what the text already says.
    assert html == (
        '<p><a href="https://your-domain.test/a?b=1&amp;c=2" '
        'style="color:#191919 !important;text-decoration:underline !important;">https://your-domain.test/a?b=1&amp;c=2</a></p>'
    )


def test_a_lookalike_host_is_named_in_punycode():
    # "еxample.com" with a Cyrillic е: shown as itself it would pass for the
    # real name; in ASCII it cannot.
    _, blocks = email_service._note_blocks("[rules](https://\u0435xample.com/rules)")
    html = str(blocks[0]["html"])
    assert "(xn--xample-2of.com)" in html
    assert "(\u0435xample.com)" not in html


def test_a_link_with_no_host_stays_literal_text():
    _, blocks = email_service._note_blocks("mira [esto](https://)")
    html = str(blocks[0]["html"])
    assert "<a " not in html
    assert "[esto](https://)" in html


@pytest.mark.parametrize(
    "url",
    [
        "https://[oops/normas",  # an unclosed IPv6 bracket: urlsplit raises ValueError
        "https://" + "a" * 64 + ".example/normas",  # a 64-char label: IDNA raises UnicodeError
    ],
)
def test_a_link_whose_host_cannot_be_read_stays_literal_text(url):
    """An owner can type either of these by accident. Both make the host
    lookup raise; the note must still render — as the literal text the owner
    wrote — or every email carrying it would fail to send."""
    _, blocks = email_service._note_blocks(f"Normas: [aquí]({url})")
    html = str(blocks[0]["html"])
    assert "<a " not in html
    assert f"[aquí]({url})" in html


def test_note_blocks_escapes_html_before_transforming(collection):
    """Raw HTML reaching the renderer (only possible bypassing the serializer,
    e.g. the admin) must render inert — and a typed NUL must not be able to
    forge an anchor placeholder. The NUL half never goes through the DB:
    PostgreSQL text columns cannot hold a NUL byte (CI runs Postgres; local
    SQLite would swallow it and the test would only ever prove the happy
    path), so it exercises the renderer directly instead."""
    collection.email_note = "<script>alert(1)</script> ok"
    collection.save(update_fields=["email_note"])
    _, blocks = email_service._note_blocks(collection.email_note)
    html = str(blocks[0]["html"])
    assert "<script>" not in html
    assert "&lt;script&gt;" in html

    # The NUL case needs no stored value — the stripping is the renderer's.
    _, blocks = email_service._note_blocks("<b>bold?</b> ok\x00")
    html = str(blocks[0]["html"])
    assert "\x00" not in html
    assert "&lt;b&gt;" in html


def test_note_blocks_is_empty_for_blank_text():
    assert email_service._note_blocks("") == ("", [])
    assert email_service._note_blocks(None) == ("", [])
    assert email_service._note_blocks("   \n  ") == ("", [])


@pytest.mark.django_db
def test_the_reservation_confirmation_embeds_the_note_after_the_listing_link(
    user, user2, thing, collection
):
    """With no note nothing is added; setting one inserts the rendered block
    after the listing link and the raw Markdown after the body — both before
    the appended viral line / footers, by construction of _send."""
    from datetime import date

    from core.models import BookingPeriod

    thing.type = "RESERVE_THING"
    thing.save(update_fields=["type"])
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 6),
        status=BookingPeriod.Status.ACCEPTED,
    )

    mail.outbox.clear()
    email_service.send_reservation_confirmed_email(user2, thing, booking, collection)
    plain_before = mail.outbox[0].body
    html_before = mail.outbox[0].alternatives[0][0]
    # No note: nothing appended to either half.
    assert "Trae el" not in plain_before
    assert "Trae el" not in html_before

    collection.email_note = "Trae el **carnet** 🛠️"
    collection.save(update_fields=["email_note"])
    mail.outbox.clear()
    email_service.send_reservation_confirmed_email(user2, thing, booking, collection)
    plain_after = mail.outbox[0].body
    html_after = mail.outbox[0].alternatives[0][0]

    assert "Trae el **carnet** 🛠️" in plain_after  # raw Markdown in text/plain
    note_html = "<p>Trae el <strong>carnet</strong> 🛠️</p>"
    assert note_html in html_after
    # Position, both halves: after the listing link, before the footers.
    thing_url = email_service._thing_url(thing, collection=collection)
    assert (
        plain_after.index(thing_url)
        < plain_after.index("Trae el **carnet** 🛠️")
        < plain_after.index("/me/notifications/")
    )
    assert html_after.index(thing_url) < html_after.index(note_html) < html_after.index("/legal")


@pytest.mark.django_db
def test_the_booking_confirmation_embeds_the_note_too(user, user2, thing, collection):
    """The LEND/RENT 'we've let the owner know' email carries the note of the
    collection the request was made through — the new `collection` param —
    while its language stays recipient-only (pinned in test_email_hierarchy)."""
    from core.models import BookingPeriod

    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        status=BookingPeriod.Status.PENDING,
    )

    collection.email_note = "Confirmamos en **48h**"
    collection.save(update_fields=["email_note"])
    mail.outbox.clear()
    email_service.send_booking_confirmation_email(user2, thing, booking, collection)

    html = mail.outbox[0].alternatives[0][0]
    note_html = "<p>Confirmamos en <strong>48h</strong></p>"
    assert note_html in html
    assert "Confirmamos en **48h**" in mail.outbox[0].body
    # The param is optional and defaults to no note — the pre-feature callers
    # (and any direct call without a collection) must keep working.
    mail.outbox.clear()
    email_service.send_booking_confirmation_email(user2, thing, booking)
    assert note_html not in mail.outbox[0].alternatives[0][0]


@pytest.mark.django_db
def test_the_note_is_resolved_per_recipient_language(user, user2, thing, collection):
    """A bilingual note reaches each member in their own language — the same
    `L` every other owner content goes through."""
    from datetime import date

    from core.models import BookingPeriod

    collection.email_note = '{"es": "Trae el carnet", "ca": "Porta el carnet"}'
    collection.save(update_fields=["email_note"])
    thing.type = "RESERVE_THING"
    thing.save(update_fields=["type"])
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 6),
        status=BookingPeriod.Status.ACCEPTED,
    )

    user2.language = "ca"
    user2.save(update_fields=["language"])
    mail.outbox.clear()
    email_service.send_reservation_confirmed_email(user2, thing, booking, collection)
    html = mail.outbox[0].alternatives[0][0]
    assert "Porta el carnet" in html
    assert "Trae el carnet" not in html


@pytest.mark.django_db
def test_the_acceptance_decision_carries_the_note_but_a_refusal_does_not(
    user, user2, thing, collection
):
    """An acceptance is the requester-facing confirmation for GIFT/SELL/LEND/
    RENT — the sibling of RESERVE's auto-confirm — so the note rides it. A
    refusal has no next steps for the note's prose to describe."""
    from core.models import BookingPeriod

    collection.email_note = "Recogida en **planta 2**"
    collection.save(update_fields=["email_note"])
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        status=BookingPeriod.Status.PENDING,
    )

    mail.outbox.clear()
    email_service.send_booking_decision_email(booking, thing, accepted=True, collection=collection)
    assert "Recogida en <strong>planta 2</strong>" in mail.outbox[0].alternatives[0][0]
    assert "Recogida en **planta 2**" in mail.outbox[0].body

    mail.outbox.clear()
    email_service.send_booking_decision_email(booking, thing, accepted=False, collection=collection)
    assert "Recogida en" not in mail.outbox[0].alternatives[0][0]
    assert "Recogida en" not in mail.outbox[0].body


@pytest.mark.django_db
def test_the_decision_takes_no_note_from_a_collection_it_was_not_given(
    user, user2, thing, collection
):
    """The note's collection is the caller's to resolve for this requester
    (`finalize_booking_decision`, among collections they may read). Given
    none, the email carries none — it no longer falls back to the thing's
    first collection, which can be a private group the requester isn't in."""
    from core.models import BookingPeriod

    collection.email_note = "Recogida en **planta 2**"
    collection.save(update_fields=["email_note"])
    booking = BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=user2,
        requester_email=user2.email,
        owner_code=user,
        status=BookingPeriod.Status.PENDING,
    )

    mail.outbox.clear()
    email_service.send_booking_decision_email(booking, thing, accepted=True)
    assert "Recogida en" not in mail.outbox[0].alternatives[0][0]
    assert "Recogida en" not in mail.outbox[0].body


# --------------------------------------------------------------------------- #
# The link in a thing-scoped email goes through a group its reader may open
# --------------------------------------------------------------------------- #


@pytest.fixture
def two_groups(user, user2, thing, collection):
    """``thing`` sits in COLL01, where ``user2`` is a member, and also in AAAAAA,
    a private group ``user2`` was never invited to — whose code sorts first, which
    is the one ``thing.collections.first()`` used to pick for everybody."""
    from core.models import Collection

    collection.invites.add(user2)
    hidden = Collection.objects.create(code="AAAAAA", owner=user, headline="Private circle")
    also_in(hidden, thing)
    return collection, hidden


def _a_booking(thing, requester, owner):
    from datetime import date

    from core.models import BookingPeriod

    return BookingPeriod.objects.create(
        thing_code=thing,
        thing_type=thing.type,
        requester_code=requester,
        requester_email=requester.email,
        owner_code=owner,
        start_date=date(2026, 10, 5),
        end_date=date(2026, 10, 6),
        status=BookingPeriod.Status.PENDING,
    )


def _both_halves(message):
    return message.body, message.alternatives[0][0]


@pytest.mark.django_db
def test_a_decision_email_links_a_group_its_reader_is_in_and_never_one_they_are_not(
    user, user2, thing, two_groups
):
    booking = _a_booking(thing, user2, user)

    mail.outbox.clear()
    email_service.send_booking_decision_email(booking, thing, accepted=True)

    for half in _both_halves(mail.outbox[0]):
        assert "/stall/COLL01/things/THNG01" in half
        assert "AAAAAA" not in half


@pytest.mark.django_db
def test_the_team_answer_email_links_a_group_its_reader_is_in_and_never_one_they_are_not(
    user, user2, thing, two_groups
):
    collection, _ = two_groups
    collection.co_owners.add(user2)  # a co-curator of the PROPRIETARY group, not of AAAAAA

    mail.outbox.clear()
    email_service.send_faq_answered_to_team_email(
        "Test User", thing, "Is it free?", "Yes", user2.email
    )

    for half in _both_halves(mail.outbox[0]):
        assert "/stall/COLL01/things/THNG01" in half
        assert "AAAAAA" not in half


@pytest.mark.django_db
def test_a_reader_in_none_of_the_things_groups_gets_the_bare_thing_link(
    user, thing, two_groups, django_user_model
):
    outsider = django_user_model.objects.create(code="OUTSD1", email="lolo4@your-domain.test")

    mail.outbox.clear()
    email_service.send_faq_answer_email("Test User", thing, "Is it free?", "Yes", outsider.email)

    for half in _both_halves(mail.outbox[0]):
        assert "/things/THNG01" in half
        # (the viral line's own "/new" is a different link)
        assert "/stall/COLL01" not in half
        assert "AAAAAA" not in half


@pytest.mark.django_db
def test_an_address_with_no_account_gets_the_bare_thing_link(thing, two_groups):
    mail.outbox.clear()
    email_service.send_faq_answer_email(
        "Test User", thing, "Is it free?", "Yes", "lele3@your-domain.test"
    )

    for half in _both_halves(mail.outbox[0]):
        assert "/things/THNG01" in half
        assert "/stall/COLL01" not in half
        assert "AAAAAA" not in half


@pytest.mark.django_db
def test_a_public_group_is_named_to_a_reader_who_is_not_in_it(
    user, thing, collection, django_user_model
):
    from core.models import Collection

    collection.visibility = Collection.Visibility.PUBLIC
    collection.save(update_fields=["visibility"])
    passer_by = django_user_model.objects.create(code="PASSBY", email="lili2@your-domain.test")

    mail.outbox.clear()
    email_service.send_faq_answer_email("Test User", thing, "Is it free?", "Yes", passer_by.email)

    for half in _both_halves(mail.outbox[0]):
        assert "/stall/COLL01/things/THNG01" in half


@pytest.mark.django_db
def test_the_collection_the_caller_resolved_wins_over_the_first_one_the_reader_can_open(
    user, user2, thing, two_groups
):
    collection, hidden = two_groups
    hidden.invites.add(user2)  # now both are readable, and AAAAAA sorts first
    booking = _a_booking(thing, user2, user)

    mail.outbox.clear()
    email_service.send_booking_decision_email(booking, thing, accepted=True)
    for half in _both_halves(mail.outbox[0]):
        assert "/stall/AAAAAA/things/THNG01" in half  # the rule, unprompted

    mail.outbox.clear()
    email_service.send_booking_decision_email(booking, thing, accepted=True, collection=collection)
    for half in _both_halves(mail.outbox[0]):
        assert "/stall/COLL01/things/THNG01" in half
        assert "AAAAAA" not in half


@pytest.mark.django_db
@pytest.mark.parametrize("sender", ["confirmation", "reservation_confirmed"])
def test_the_other_emails_that_receive_a_collection_link_that_one(
    user, user2, thing, two_groups, sender
):
    collection, hidden = two_groups
    hidden.invites.add(user2)
    booking = _a_booking(thing, user2, user)

    mail.outbox.clear()
    if sender == "confirmation":
        email_service.send_booking_confirmation_email(user2, thing, booking, collection)
    else:
        email_service.send_reservation_confirmed_email(user2, thing, booking, collection)

    for half in _both_halves(mail.outbox[0]):
        assert "/stall/COLL01/things/THNG01" in half
        assert "AAAAAA" not in half


def _send_to(sender, thing, reader, booking):
    """One call per thing-linking email, each addressed to ``reader``."""
    from datetime import date

    es = email_service
    address = reader.email
    calls = {
        "decision": lambda: es.send_booking_decision_email(booking, thing, accepted=True),
        "confirmation": lambda: es.send_booking_confirmation_email(reader, thing, booking),
        "faq_question": lambda: es.send_faq_question_email("Ana", thing, "Free?", address),
        "faq_answer": lambda: es.send_faq_answer_email("Ana", thing, "Free?", "Yes", address),
        "faq_answered_to_team": lambda: es.send_faq_answered_to_team_email(
            "Ana", thing, "Free?", "Yes", address
        ),
        "faq_hidden_to_team": lambda: es.send_faq_hidden_to_team_email(
            "Ana", thing, "Free?", address
        ),
        "thing_reported": lambda: es.send_thing_reported_email(thing, address),
        "return_due": lambda: es.send_return_due_email("Ana", thing, date(2026, 10, 6), address),
        "reservation_confirmed": lambda: es.send_reservation_confirmed_email(
            reader, thing, booking
        ),
        "reservation_reminder": lambda: es.send_reservation_reminder_email(address, thing, booking),
    }
    calls[sender]()


THING_LINKING_EMAILS = [
    "decision",
    "confirmation",
    "faq_question",
    "faq_answer",
    "faq_answered_to_team",
    "faq_hidden_to_team",
    "thing_reported",
    "return_due",
    "reservation_confirmed",
    "reservation_reminder",
]


@pytest.mark.django_db
@pytest.mark.parametrize("sender", THING_LINKING_EMAILS)
def test_every_email_that_links_a_thing_names_only_a_group_its_reader_may_open(
    user, user2, thing, two_groups, sender
):
    """The ten senders that link a thing, none of them handed a collection: each
    must ask ``_thing_url`` on behalf of the person it is addressed to."""
    booking = _a_booking(thing, user2, user)

    mail.outbox.clear()
    _send_to(sender, thing, user2, booking)

    assert len(mail.outbox) == 1
    plain, html = _both_halves(mail.outbox[0])
    # The return-due reminder's plain text has never carried the listing link
    # (its catalogue string has no {url}); the button in the HTML does.
    for half in (html,) if sender == "return_due" else (plain, html):
        assert "/stall/COLL01/things/THNG01" in half
    for half in (plain, html):
        assert "AAAAAA" not in half


@pytest.mark.django_db
def test_the_capacity_alarm_says_its_header_once_in_the_plain_text():
    """The alert's explanation is its parent line; `_send` already puts it on the first
    line of the plain text, so the body must not repeat it."""
    from core.models import Collection, User

    owner = User.objects.create(code="ALRMO3", email="lala3@your-domain.test", name="Lala")
    collection = Collection.objects.create(
        code="ALRMC3", owner=owner, headline="Busy", status="ACTIVE"
    )
    User.objects.create(code="ALRMS3", email="lala4@your-domain.test", is_superuser=True)
    mail.outbox.clear()

    email_service.send_collection_capacity_alarm(collection, "things", 501, 500)

    plain = mail.outbox[0].body
    assert plain.count("A collection has crossed the mass-upload alarm threshold.") == 1
    assert plain.startswith("A collection has crossed")
    assert "  Collection: Busy (ALRMC3)" in plain
