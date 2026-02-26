"""
DRF permission classes for OIUEEI.

Object-level permissions for Things and Collections.
"""

from rest_framework.permissions import BasePermission


class IsThingOwner(BasePermission):
    """Object-level: request user is the Thing owner."""

    def has_object_permission(self, request, view, obj):
        return obj.is_owner(request.user.code)


class IsCollectionOwner(BasePermission):
    """Object-level: request user is the Collection owner."""

    def has_object_permission(self, request, view, obj):
        return obj.is_owner(request.user.code)
