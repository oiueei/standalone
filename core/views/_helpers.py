"""Shared view helpers for OIUEEI."""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.response import Response

from core.models import Thing


def deny_if_cannot_view(obj, user_code, message):
    """Return a 403 ``{"error": message}`` Response if ``user_code`` cannot view
    ``obj`` (a Thing, including a wish), else ``None``.

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


def type_validity_error(thing_type, collection):
    """Error message if ``thing_type`` isn't valid for ``collection`` (or for no
    collection, when None), else None.

    Shared by thing create/update AND the collection add-thing endpoint so the
    type rules (community-only types, swap/share/album restrictions, per-collection
    allowlist) can't be bypassed by any path (L4).
    """
    if collection is None:
        if thing_type in (Thing.Type.WISH_THING, Thing.Type.SHARE_THING):
            return (
                f"{thing_type.replace('_', ' ').title()}s can only be created"
                " in community collections"
            )
        if thing_type == Thing.Type.SWAP_THING:
            return "Swap things can only be created in swap collections"
        return None
    if (
        thing_type in (Thing.Type.WISH_THING, Thing.Type.SHARE_THING)
        and not collection.is_community()
    ):
        return (
            f"{thing_type.replace('_', ' ').title()}s can only be created"
            " in community collections"
        )
    if collection.is_swap and thing_type != Thing.Type.SWAP_THING:
        return "Only swap things can be added to a swap collection"
    if thing_type == Thing.Type.SWAP_THING and not collection.is_swap:
        return "Swap things can only be created in swap collections"
    if collection.is_share and thing_type != Thing.Type.SHARE_THING:
        return "Only share things can be added to a share collection"
    if collection.is_minimalist and thing_type not in (
        Thing.Type.GIFT_THING,
        Thing.Type.SHARE_THING,
        Thing.Type.SWAP_THING,
    ):
        return "Only gift, share, and swap things can be added to a minimalist collection"
    if collection.allowed_thing_types and thing_type not in collection.allowed_thing_types:
        return (
            f"This collection does not accept {thing_type.replace('_', ' ').title()}s."
            " The owner has restricted it to specific types."
        )
    return None


def require_collection_owner(collection, user_code, message):
    """Return a 403 ``{"error": message}`` Response if ``user_code`` is not the
    collection owner, else ``None``.

    Used by the collection APIViews (invite, share-link, broadcast) instead of the
    ``IsCollectionOwner`` DRF permission so each keeps its own specific ``{"error":
    ...}`` message rather than DRF's generic ``{"detail": ...}`` body.
    """
    if not collection.is_owner(user_code):
        return Response({"error": message}, status=status.HTTP_403_FORBIDDEN)
    return None
