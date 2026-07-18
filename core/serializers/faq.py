"""
FAQ serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models import FAQ
from core.validators import SafeHeadlineField, SafeTextField


class FAQSerializer(serializers.ModelSerializer):
    """Full FAQ serializer."""

    thing = serializers.CharField(source="thing_id")
    questioner = serializers.CharField(source="questioner_id", allow_null=True)
    questioner_name = serializers.SerializerMethodField()

    class Meta:
        model = FAQ
        fields = [
            "code",
            "thing",
            "created",
            "questioner",
            "questioner_name",
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

    def get_questioner_name(self, obj):
        # A deleted account keeps its questions but sheds its name (right to
        # erasure — FAQ.questioner is SET_NULL); the frontend renders its own
        # "former member" label for the empty value.
        return obj.questioner.name if obj.questioner else ""


class FAQCreateSerializer(serializers.Serializer):
    """Serializer for creating a FAQ (asking a question)."""

    question = SafeHeadlineField(max_length=64)


class FAQAnswerSerializer(serializers.Serializer):
    """Serializer for answering a FAQ."""

    answer = SafeTextField(max_length=256)
