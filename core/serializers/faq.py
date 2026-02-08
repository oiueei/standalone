"""
FAQ serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import FAQ


class FAQSerializer(serializers.ModelSerializer):
    """Full FAQ serializer."""

    class Meta:
        model = FAQ
        fields = [
            "code",
            "thing",
            "created",
            "questioner",
            "question",
            "answer",
            "is_visible",
        ]
        read_only_fields = [
            "code",
            "thing",
            "created",
            "questioner",
        ]


class FAQCreateSerializer(serializers.Serializer):
    """Serializer for creating a FAQ (asking a question)."""

    question = serializers.CharField(max_length=64)


class FAQAnswerSerializer(serializers.Serializer):
    """Serializer for answering a FAQ."""

    answer = serializers.CharField(max_length=256)
