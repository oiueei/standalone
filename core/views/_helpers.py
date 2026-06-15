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
