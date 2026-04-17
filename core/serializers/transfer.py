"""
Transfer serializers for OIUEEI.
"""

from rest_framework import serializers

from core.models.transfer import ThingTransfer


class ThingTransferSerializer(serializers.ModelSerializer):
    """Individual transfer record."""

    from_user = serializers.CharField(source="from_user_id")
    from_user_name = serializers.SerializerMethodField()
    to_user = serializers.CharField(source="to_user_id")
    to_user_name = serializers.SerializerMethodField()

    class Meta:
        model = ThingTransfer
        fields = [
            "code",
            "from_user",
            "from_user_name",
            "to_user",
            "to_user_name",
            "lent_date",
            "returned_date",
        ]

    def get_from_user_name(self, obj):
        return obj.from_user.name or obj.from_user.email

    def get_to_user_name(self, obj):
        return obj.to_user.name or obj.to_user.email


class ThingTransferStatsSerializer(serializers.Serializer):
    """Aggregated transfer stats for a thing."""

    total_transfers = serializers.IntegerField()
    unique_homes = serializers.IntegerField()
    current_holder = serializers.CharField(allow_null=True)
    current_holder_name = serializers.CharField(allow_null=True)
    transfers = ThingTransferSerializer(many=True)
