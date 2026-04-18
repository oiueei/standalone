"""
User views for OIUEEI.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Collection, User
from core.serializers import UserPublicSerializer, UserSerializer, UserUpdateSerializer


def can_view_user(viewer_user_code, target_user_code):
    """
    Check if viewer can see target user's profile.
    Returns True if:
    - viewer is target (own profile)
    - target is in invites of any collection owned by viewer
    - viewer is in invites of any collection owned by target
    """
    if viewer_user_code == target_user_code:
        return True

    # Check if target is invited to any of viewer's collections
    if Collection.objects.filter(
        owner_id=viewer_user_code, invites__code=target_user_code
    ).exists():
        return True

    # Check if viewer is invited to any of target's collections
    if Collection.objects.filter(
        owner_id=target_user_code, invites__code=viewer_user_code
    ).exists():
        return True

    return False


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
                {"error": "Not authorized to view this user's profile"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # If viewing own profile, return full data
        if request.user.code == user_code:
            serializer = UserSerializer(user)
            return Response(serializer.data)

        serializer = UserPublicSerializer(user)
        data = serializer.data

        # Find shared collections (where both users are owner or invited)
        viewer = request.user.code
        # Collections owned by viewer where target is invited
        shared_qs = Collection.objects.filter(owner_id=viewer, invites__code=user_code).values(
            "code", "headline"
        )
        # Collections owned by target where viewer is invited
        shared_qs2 = Collection.objects.filter(owner_id=user_code, invites__code=viewer).values(
            "code", "headline"
        )
        shared = list(shared_qs.union(shared_qs2))
        data["shared_collections"] = shared

        return Response(data)

    def put(self, request, user_code):
        # Can only update own profile
        if request.user.code != user_code:
            return Response(
                {"error": "Cannot update another user's profile"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = UserUpdateSerializer(request.user, data=request.data, partial=True)
        serializer.is_valid(raise_exception=True)
        serializer.save()

        return Response(UserSerializer(request.user).data)
