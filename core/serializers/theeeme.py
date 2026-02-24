"""
Theeeme serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import Theeeme


class TheeemeSerializer(serializers.ModelSerializer):
    """Read-only serializer for listing theeemes."""

    class Meta:
        model = Theeeme
        fields = ["code", "name"]
