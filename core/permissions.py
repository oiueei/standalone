"""
DRF permission classes for OIUEEI.

Object-level permissions for Things and Collections.
"""

from rest_framework.permissions import BasePermission


class IsThingOwner(BasePermission):
    """Object-level: usuario es owner del Thing."""

    def has_object_permission(self, request, view, obj):
        return obj.is_owner(request.user.code)


class CanViewThing(BasePermission):
    """Object-level: usuario puede ver el Thing."""

    def has_object_permission(self, request, view, obj):
        return obj.can_view(request.user.code)


class IsCollectionOwner(BasePermission):
    """Object-level: usuario es owner de la Collection."""

    def has_object_permission(self, request, view, obj):
        return obj.is_owner(request.user.code)


class CanViewCollection(BasePermission):
    """Object-level: usuario puede ver la Collection."""

    def has_object_permission(self, request, view, obj):
        return obj.can_view(request.user.code)
