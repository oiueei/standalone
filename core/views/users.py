"""
User views for OIUEEI.
"""

from django.db.models import Q
from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Collection, User
from core.serializers import UserPublicSerializer, UserSerializer, UserUpdateSerializer
from core.views._helpers import refusal_body


def _inside(user_code):
    """Collections ``user_code`` is inside of: founds, or is invited to (co-curators included)."""
    return Q(owner_id=user_code) | Q(invites__code=user_code)


def can_view_user(viewer_user_code, target_user_code):
    """
    Check if viewer can see target user's profile.
    Returns True if:
    - viewer is target (own profile)
    - there is a collection both are inside of (founder, co-curator or member)

    Someone who is not in a group opens nobody's profile through it, even a public
    group's: a team is known to its group by the page of that group. What the other
    person sees is ``UserPublicSerializer``, never language, demographics or email
    preferences.

    One ``EXISTS`` query whatever the number of collections. The two ``filter()``
    calls are deliberate: each joins ``invites`` on its own.
    """
    if viewer_user_code == target_user_code:
        return True

    return (
        Collection.objects.filter(_inside(viewer_user_code))
        .filter(_inside(target_user_code))
        .exists()
    )


class UserDetailView(APIView):
    """
    GET /api/v1/users/{user_code}/
    Get a user's public profile.

    PUT /api/v1/users/{user_code}/
    Update own profile (authenticated user only).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, user_code):
        user = get_object_or_404(User, code=user_code)

        # Check if viewer can see this user's profile
        if not can_view_user(request.user.code, user_code):
            return Response(
                refusal_body(
                    "Not authorized to view this user's profile", code="profile_not_viewable"
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

        # If viewing own profile, return full data
        if request.user.code == user_code:
            serializer = UserSerializer(user)
            return Response(serializer.data)

        serializer = UserPublicSerializer(user)
        data = serializer.data

        # Only collections both are inside of (founder, co-curator or member):
        # a private group the target runs and the viewer cannot see never appears.
        viewer = request.user.code
        shared = list(
            Collection.objects.filter(_inside(viewer))
            .filter(_inside(user_code))
            .values("code", "headline", "kind")
            .distinct()
            .order_by("code")
        )
        data["shared_collections"] = shared

        return Response(data)

    def put(self, request, user_code):
        # Can only update own profile
        if request.user.code != user_code:
            return Response(
                refusal_body("Cannot update another user's profile", code="profile_not_yours"),
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(UserSerializer(request.user).data)
