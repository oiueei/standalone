"""
Theeeme views for OIUEEI.
"""

from rest_framework.generics import ListAPIView
from rest_framework.permissions import IsAuthenticated

from core.models import Theeeme
from core.serializers.theeeme import TheeemeSerializer


class TheeemeListView(ListAPIView):
    """List all available theeemes."""

    permission_classes = [IsAuthenticated]
    serializer_class = TheeemeSerializer
    queryset = Theeeme.objects.all()
