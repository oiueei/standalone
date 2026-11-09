"""
DRF permission classes for OIUEEI.

Object-level permissions for Things and Collections.
"""

from rest_framework.permissions import BasePermission


class IsThingOwner(BasePermission):
    """Object-level: request user is the Thing owner."""

    def has_object_permission(self, request, view, obj):
        return obj.is_owner(request.user.code)


class IsThingManager(BasePermission):
    """Object-level: request user may manage the Thing — its owner, or a
    curator of a PROPRIETARY collection it sits in (`Thing.can_manage`).

    The mirror of `IsThingOwner`, one tier wider, for the catalogue actions
    a PROPRIETARY collection's curators run collectively (edit, hide,
    activate). Deleting keeps its own check (`Thing.can_delete`).
    """

    def has_object_permission(self, request, view, obj):
        return obj.can_manage(request.user.code)


class IsThingManagerOrRescuer(BasePermission):
    """Object-level: a manager of the Thing, or the founder of the network it sits in.

    For the one action the founder's rescue allows besides rejecting a request:
    hiding another entity's thing.
    """

    def has_object_permission(self, request, view, obj):
        return obj.can_manage(request.user.code) or obj.can_rescue(request.user.code)


class IsCollectionOwner(BasePermission):
    """Object-level: request user is the Collection owner."""

    def has_object_permission(self, request, view, obj):
        return obj.is_owner(request.user.code)


class IsCollectionCurator(BasePermission):
    """Object-level: request user is the Collection owner or a co-owner.

    The admin tier — everything except deleting the collection, which stays
    `IsCollectionOwner` (the CASCADE-delete root). Promoting and demoting a
    co-curator is curator-wide now (2026-09, co-curators in PROPRIETARY).
    """

    def has_object_permission(self, request, view, obj):
        # In a network the settings are the founder's alone: each dinamizador
        # edits only their own point, through its own endpoint.
        if obj.is_network():
            return obj.is_owner(request.user.code)
        return obj.is_curator(request.user.code)
