"""
Authentication serializers for OIUEEI.
"""

from rest_framework import serializers


class RequestLinkSerializer(serializers.Serializer):
    """Serializer for magic link request."""

    email = serializers.EmailField(max_length=64)
