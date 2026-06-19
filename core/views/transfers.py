"""
Transfer views for OIUEEI — thing journey/lending history.
"""

from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import Collection, Thing
from core.models.transfer import ThingTransfer
from core.serializers.transfer import ThingTransferStatsSerializer
from core.views._helpers import get_viewable_thing


class ThingTransferView(APIView):
    """
    GET /api/v1/things/{thing_code}/transfers/

    Returns the transfer history and stats for a thing.
    Permission: must be able to view the thing (owner or invited).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, thing_code):
        thing, denied = get_viewable_thing(thing_code, request.user.code, "Not authorised.")
        if denied:
            return denied

        # Materialise once (ordered most-recent first) and derive every stat in
        # Python — re-querying with .count()/.filter()/.order_by() on the same
        # rows would issue three extra round-trips for no benefit.
        transfers = list(
            ThingTransfer.objects.filter(thing=thing)
            .select_related("from_user", "to_user")
            .order_by("-lent_date")
        )

        total_transfers = len(transfers)

        # Unique homes = unique users who have held the item (both from and to)
        user_codes = set()
        for t in transfers:
            user_codes.add(t.from_user_id)
            user_codes.add(t.to_user_id)
        unique_homes = len(user_codes)

        # Current holder = most recent unreturned transfer's to_user (the list is
        # ordered -lent_date, so the first unreturned row is the most recent).
        current_transfer = next((t for t in transfers if t.returned_date is None), None)
        current_holder = None
        current_holder_name = None
        if current_transfer:
            current_holder = current_transfer.to_user_id
            # Bare name, not display_name — shown community-wide in the journey,
            # so the email fallback would leak addresses (L2).
            current_holder_name = current_transfer.to_user.name

        # Original owner = from_user of the oldest transfer (last in -lent_date order)
        oldest = transfers[-1] if transfers else None
        original_owner = oldest.from_user_id if oldest else None
        original_owner_name = (oldest.from_user.name) if oldest else None

        # Is this a SHARE_THING in a COMMUNITY collection?
        is_share_in_community = (
            thing.type == Thing.Type.SHARE_THING
            and thing.collections.filter(mode=Collection.Mode.COMMUNITY).exists()
        )

        stats_data = {
            "total_transfers": total_transfers,
            "unique_homes": unique_homes,
            "current_holder": current_holder,
            "current_holder_name": current_holder_name,
            "original_owner": original_owner,
            "original_owner_name": original_owner_name,
            "is_share_in_community": is_share_in_community,
            "transfers": transfers,
        }

        serializer = ThingTransferStatsSerializer(stats_data)
        return Response(serializer.data)
