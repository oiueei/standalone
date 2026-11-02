"""Shared view helpers for OIUEEI."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from core.models import Thing
from core.models.collection import KIND_THING_TYPES, derive_thing_type
from core.utils import Refusal


def body_dict(request):
    """``request.data`` when the body is a JSON object, else an empty dict.

    DRF parses a JSON *array* body into a ``list``, which has no ``.get`` — so a
    view that reads ``request.data.get(...)`` before any serializer has run
    raises ``AttributeError`` and answers 500 where it owes a 400. Every endpoint
    using this expects an object body, so anything else is simply "no fields
    given" and falls through to the view's own validation, which already has the
    right message for an empty request.
    """
    return request.data if isinstance(request.data, dict) else {}


def refusal_body(message, *, code=None, key="error", **params):
    """The body of a coded refusal: ``{key: <the English sentence>, "code", "params"}``.

    The same shape ``BookingRequestError.as_body`` and the co-curator ceiling use, so
    the SPA says the refusal in the reader's language (``requestErrors.<code>``) and a
    client that does not know the code still shows the sentence. ``key`` is the one the
    view always used (``"error"`` or ``"detail"``). A ``Refusal`` carries its own code and
    params (``capacity_violation``, the invitation quota): ``refusal_body(refusal)`` is
    enough. ``params`` is left out when the sentence interpolates nothing.
    """
    body = {key: str(message)}
    code = code or getattr(message, "code", None)
    if code:
        body["code"] = code
        params = params or dict(getattr(message, "params", {}))
        if params:
            body["params"] = params
    return body


# A refusal of an approval that is final, however long the owner waits: the suggestion stays
# pending (a curator closes it by declining) and the link is not consumed, but trying again
# changes nothing. Everything else that blocks an approval (the daily quota, the member
# ceiling) is "not now".
_FINAL_APPROVAL_REFUSALS = {"invite_already_asked"}


def approval_refusal_response(reason, http_status):
    """The answer to an approval that ``proposal_approval_blocked`` turned down.

    The one place that says whether it is worth coming back: ``retryable: true`` for a
    daily quota or a full group, nothing for an address already invited, which stays
    blocked for a year. Shared by the in-app approval and the emailed link.
    """
    body = refusal_body(reason)
    if getattr(reason, "code", None) not in _FINAL_APPROVAL_REFUSALS:
        body["retryable"] = True
    return Response(body, status=http_status)


def viewer_code(request):
    """The requesting user's code, or ``None`` for an anonymous visitor.

    The public-read endpoints accept anonymous callers, but ``request.user`` is
    then an ``AnonymousUser`` with no ``.code``. Centralise the guard so each
    view passes a real code — or ``None`` — straight into the ``can_view``
    helpers (which treat ``None`` as "anonymous": PUBLIC collections only).
    """
    user = request.user
    return user.code if user.is_authenticated else None


def deny_if_cannot_view(obj, user_code, message):
    """Return a 403 ``{"error": message}`` Response if ``user_code`` cannot view
    ``obj`` (a Thing), else ``None``.

    Centralises the ``can_view`` authorisation guard so every endpoint returns the
    same ``{"error": ...}`` shape (one endpoint previously used ``{"detail": ...}``).
    """
    if not obj.can_view(user_code):
        return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)
    return None


def get_viewable_thing(code, user_code, message):
    """``get_object_or_404(Thing, code=code)`` followed by the ``can_view`` guard.

    Returns ``(thing, None)`` on success, or ``(thing, Response)`` when the user
    cannot view it — callers do ``thing, denied = ...; if denied: return denied``.
    """
    thing = get_object_or_404(Thing, code=code)
    return thing, deny_if_cannot_view(thing, user_code, message)


_VERB_NAMES = {
    "STALL": ("sale", "gift"),
    "LIBRARY": ("rental", "loan"),
}


def verb_from_price(collection, fee, given_type=None):
    """``(thing_type, None)`` for a thing in ``collection`` priced at ``fee``, or
    ``(None, message)`` when the verb the client named contradicts its price.

    The server decides the verb (`derive_thing_type`); a client may still name one,
    and naming the wrong one is an error rather than something silently corrected,
    so a stale form never sells what its owner meant to give away.
    """
    derived = derive_thing_type(collection.kind, fee)
    if given_type is None or given_type == derived:
        return derived, None
    kind = collection.kind.lower()
    names = _VERB_NAMES.get(collection.kind)
    if names is None:
        return None, f"In a {kind} every thing is booked: its verb is always a reservation."
    return None, (
        f"In a {kind} the verb follows the price: with a price it's a {names[0]}, "
        f"without one a {names[1]}."
    )


def type_validity_error(thing_type, collection):
    """Error message if ``thing_type`` isn't valid for ``collection``, else None.

    Shared by thing create/update so the owner's per-collection allowlist can't
    be bypassed by any path. A thing is no longer created without a collection
    (``ThingViewSet.perform_create`` refuses it), so the ``collection is None``
    branches below are defence for rows from before that rule: a thing with no
    collection has no allowlist to answer to and is valid, except RESERVE_THING.

    RESERVE_THING is the one type with a rule of its own: it can *only* live in
    a reservations collection (a shed: ``is_reservations_collection()``), so
    a RESERVE thing with no collection — or one aimed at any other collection — is
    refused. A shed's verb list (``["RESERVE_THING"]``) already blocks the other
    verbs from it; this closes the other direction.
    """
    if thing_type == "RESERVE_THING":
        if collection is None or not collection.is_reservations_collection():
            return (
                "A reservation can only be added to a reservations collection "
                "(one that offers reservations and nothing else)."
            )
        return None
    if collection is None:
        return None
    # The list is never empty any more (it used to mean "no restriction"); the
    # truthiness guard stays as defence against a row edited by hand, as in
    # ``community_contribution_types``.
    if collection.allowed_thing_types and thing_type not in collection.allowed_thing_types:
        if thing_type in KIND_THING_TYPES[collection.kind][1:]:
            return Refusal("This group doesn't take prices.", "no_prices_here")
        return (
            f"This collection does not accept {thing_type.replace('_', ' ').title()}s."
            " The owner has restricted it to specific types."
        )
    return None


def require_network_founder(collection, user_code, message):
    """In a NETWORK, return a 403 for anyone but the founder; ``None`` elsewhere.

    The collection-level powers a co-curator has in every other mode are cut in a
    network (naming dinamizadores, editing the settings, removing members): what
    one entity does there reaches the others'. A coded body, so the SPA words it.
    """
    if collection.is_network() and not collection.is_owner(user_code):
        return Response(
            refusal_body(message, code="network_founder_only"), status=status.HTTP_403_FORBIDDEN
        )
    return None


def require_collection_curator(collection, user_code, message):
    """Return a 403 ``{"error": message}`` Response if ``user_code`` is neither
    the collection owner nor a co-owner, else ``None``.

    Used by every collection APIView that a co-curator shares with the founder
    (invite, share-link, broadcast, stats, export, proposal decisions, and
    promoting/demoting a co-curator) instead of the ``IsCollectionCurator``
    DRF permission, so each keeps its own specific ``{"error": ...}`` message
    rather than DRF's generic ``{"detail": ...}`` body. Deleting the
    collection is the one action still owner-only, and it uses the
    ``IsCollectionOwner`` permission class directly.
    """
    if not collection.is_curator(user_code):
        return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)
    return None
