"""
Collection views for OIUEEI.
"""

import csv
import logging
import threading
from collections import Counter
from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.db.models import Count, Prefetch
from django.http import HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import serializers, status
from rest_framework.decorators import action
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from core.models import RSVP, Collection, Thing, User
from core.models.booking import BookingPeriod
from core.models.collection import generate_share_token
from core.models.notification import InAppNotification
from core.models.transfer import ThingTransfer
from core.permissions import IsCollectionOwner
from core.serializers import (
    CollectionAddThingSerializer,
    CollectionBroadcastSerializer,
    CollectionCreateSerializer,
    CollectionInviteSerializer,
    CollectionRemoveInviteSerializer,
    CollectionRemoveThingSerializer,
    CollectionSerializer,
    CollectionUpdateSerializer,
)
from core.services.email_service import (
    send_broadcast_email,
    send_collection_invite_email,
    send_collection_revoke_email,
)
from core.validators import SafeHeadlineField
from core.views._helpers import require_collection_owner, type_validity_error, viewer_code

logger = logging.getLogger(__name__)


def _optimise_collection_queryset(queryset):
    """Add select/prefetch_related for nested serializer access on collections."""
    return queryset.select_related("owner").prefetch_related(
        "invites",
        Prefetch(
            "things",
            queryset=Thing.objects.select_related("owner")
            .annotate(_transfer_count=Count("transfers", distinct=True))
            .prefetch_related(
                "faq_set",
                "responses",
                "deal",
                Prefetch(
                    "bookings",
                    queryset=BookingPeriod.objects.filter(status=BookingPeriod.Status.PENDING),
                    to_attr="_pending_bookings",
                ),
                Prefetch(
                    "bookings",
                    queryset=BookingPeriod.objects.filter(
                        status__in=[
                            BookingPeriod.Status.PENDING,
                            BookingPeriod.Status.ACCEPTED,
                        ]
                    ).order_by("start_date"),
                    to_attr="_blocked_periods",
                ),
            ),
        ),
    )


class CollectionViewSet(ModelViewSet):
    """
    ViewSet for Collection CRUD operations.

    list:    GET /api/v1/collections/
    create:  POST /api/v1/collections/
    retrieve: GET /api/v1/collections/{code}/
    update:  PUT /api/v1/collections/{code}/
    destroy: DELETE /api/v1/collections/{code}/
    add_thing: POST /api/v1/collections/{code}/add-thing/
    """

    lookup_field = "code"

    def get_queryset(self):
        qs = Collection.objects.filter(owner=self.request.user).order_by("-created")
        if self.action in ("list", "retrieve"):
            return _optimise_collection_queryset(qs)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return CollectionCreateSerializer
        if self.action in ("update", "partial_update"):
            return CollectionUpdateSerializer
        if self.action == "add_thing":
            return CollectionAddThingSerializer
        return CollectionSerializer

    def get_permissions(self):
        # remove_thing is intentionally NOT gated by IsCollectionOwner here: its
        # rule is broader (in COMMUNITY mode a thing's own owner may remove it), so
        # it is enforced inline in the action. It also fetches via get_object_or_404,
        # so an object-level permission would never run for it anyway (the I3 footgun).
        if self.action in ("update", "partial_update", "destroy"):
            return [IsAuthenticated(), IsCollectionOwner()]
        # Anonymous read is allowed for retrieve; can_view() (below) still gates
        # it — only PUBLIC, ACTIVE collections are visible without membership.
        if self.action == "retrieve":
            return [AllowAny()]
        return [IsAuthenticated()]

    def get_object(self):
        if self.action == "retrieve":
            # Use the optimised queryset (prefetch + annotations) so nesting the
            # collection's things doesn't N+1. No owner filter — can_view() below
            # gates access so invited (non-owner) users can still retrieve.
            qs = _optimise_collection_queryset(Collection.objects.all())
            obj = get_object_or_404(qs, code=self.kwargs[self.lookup_field])
            if not obj.can_view(viewer_code(self.request)):
                self.permission_denied(self.request)
            return obj
        obj = get_object_or_404(Collection, code=self.kwargs[self.lookup_field])
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_destroy(self, instance):
        owner_name = instance.owner.display_name
        headline = instance.headline
        invitees = list(instance.invites.all())

        orphaned_things = instance.things.annotate(col_count=Count("collections")).filter(
            col_count=1
        )
        orphaned_things.delete()
        instance.delete()

        InAppNotification.objects.bulk_create(
            [
                InAppNotification(
                    user=invitee,
                    type=InAppNotification.Type.COLLECTION_DELETED,
                    payload={"collection_headline": headline, "owner_name": owner_name},
                )
                for invitee in invitees
            ]
        )

    def perform_create(self, serializer):
        validated_data = serializer.validated_data
        collection = Collection.objects.create(
            owner=self.request.user,
            **validated_data,
        )
        self._created_collection = collection

    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            CollectionSerializer(self._created_collection, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )

    @action(detail=True, methods=["post"], url_path="add-thing")
    def add_thing(self, request, code=None):
        """Add a thing to the collection.

        Owner can always add. Invited users can add their own things
        in COMMUNITY mode collections.
        """
        collection = get_object_or_404(Collection, code=self.kwargs[self.lookup_field])

        if not collection.can_add_thing(request.user.code):
            return Response(
                {"error": "You do not have permission to add things to this collection"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CollectionAddThingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        thing_code = serializer.validated_data["thing_code"]
        thing = get_object_or_404(Thing, code=thing_code)

        if not thing.is_owner(request.user.code):
            return Response(
                {"error": "You can only add your own things to collections"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if collection.things.filter(code=thing_code).exists():
            return Response(
                {"error": "Thing is already in this collection"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # The thing's type must be valid for this collection — same rules as
        # create/update, so add-thing can't smuggle in a forbidden type (L4).
        type_error = type_validity_error(thing.type, collection)
        if type_error:
            return Response({"error": type_error}, status=status.HTTP_400_BAD_REQUEST)

        collection.things.add(thing)

        return Response(
            {
                "message": "Thing added to collection",
                "collection": CollectionSerializer(collection, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )

    @action(detail=True, methods=["post"], url_path="remove-thing")
    def remove_thing(self, request, code=None):
        """Remove a thing from the collection (without deleting it).

        Owner can remove any thing. In COMMUNITY mode, thing owners
        can remove their own things.
        """
        collection = get_object_or_404(Collection, code=self.kwargs[self.lookup_field])

        serializer = CollectionRemoveThingSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        thing_code = serializer.validated_data["thing_code"]

        if not collection.things.filter(code=thing_code).exists():
            return Response(
                {"error": "Thing is not in this collection"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        thing = collection.things.get(code=thing_code)

        # Collection owner can always remove. In community mode,
        # thing owners can remove their own things.
        if not collection.is_owner(request.user.code):
            if not (collection.is_community() and thing.is_owner(request.user.code)):
                return Response(
                    {"error": "You do not have permission to remove this thing"},
                    status=status.HTTP_403_FORBIDDEN,
                )

        collection.things.remove(thing)

        return Response(
            {
                "message": "Thing removed from collection",
                "collection": CollectionSerializer(collection, context={"request": request}).data,
            },
            status=status.HTTP_200_OK,
        )


class CollectionInviteView(APIView):
    """
    POST /api/v1/collections/{collection_code}/invite/
    Invite a user to a collection.

    DELETE /api/v1/collections/{collection_code}/invite/
    Remove a user from the collection's invite list.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_owner(
            collection, request.user.code, "Only the owner can invite users"
        )
        if denied:
            return denied

        serializer = CollectionInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()

        invited_user, created = User.objects.get_or_create(
            email=email,
            defaults={"email": email},
        )

        if collection.is_invited(invited_user.code):
            return Response(
                {"detail": "This user is already invited to this collection."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Delete any old pending RSVPs for this user+collection (allows resend)
        RSVP.objects.filter(
            user_code=invited_user,
            target_code=collection_code,
            action__in=[RSVP.Action.COLLECTION_INVITE, RSVP.Action.COLLECTION_REJECT],
        ).delete()

        # Create RSVPs for accept and reject actions
        accept_rsvp = RSVP.objects.create(
            user_code=invited_user,
            user_email=email,
            action=RSVP.Action.COLLECTION_INVITE,
            target_code=collection_code,
        )
        reject_rsvp = RSVP.objects.create(
            user_code=invited_user,
            user_email=email,
            action=RSVP.Action.COLLECTION_REJECT,
            target_code=collection_code,
        )

        # Send invitation email with accept and reject links
        accept_link = accept_rsvp.action_link()
        reject_link = reject_rsvp.action_link()

        send_collection_invite_email(
            request.user.display_name,
            collection.headline,
            email,
            accept_link,
            reject_link,
        )

        return Response(
            {
                "message": "Invitation sent",
                "email": email,
                "user_code": invited_user.code,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_owner(
            collection, request.user.code, "Only the owner can remove invites"
        )
        if denied:
            return denied

        serializer = CollectionRemoveInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_code = serializer.validated_data["user_code"]

        # Check if user is a confirmed invite
        try:
            invited_user = collection.invites.get(code=user_code)
        except User.DoesNotExist:
            invited_user = None

        if invited_user:
            collection.invites.remove(invited_user)

            # Send notification email and in-app notification to removed user
            try:
                user = User.objects.get(code=user_code)
                owner_name = request.user.display_name
                send_collection_revoke_email(owner_name, collection.headline, user.email)
                InAppNotification.objects.create(
                    user=user,
                    type=InAppNotification.Type.COLLECTION_REVOKED,
                    payload={"collection_headline": collection.headline, "owner_name": owner_name},
                )
            except User.DoesNotExist:
                pass

            return Response(
                {
                    "message": "User removed from collection",
                    "user_code": user_code,
                },
                status=status.HTTP_200_OK,
            )

        # Check if user has a pending invite (RSVP)
        pending_rsvps = RSVP.objects.filter(
            user_code_id=user_code,
            target_code=collection_code,
            action__in=[RSVP.Action.COLLECTION_INVITE, RSVP.Action.COLLECTION_REJECT],
        )
        if pending_rsvps.exists():
            pending_rsvps.delete()
            return Response(
                {
                    "message": "Pending invitation cancelled",
                    "user_code": user_code,
                },
                status=status.HTTP_200_OK,
            )

        return Response(
            {"error": "User is not invited to this collection"},
            status=status.HTTP_400_BAD_REQUEST,
        )


def _send_bulk_invites(inviter_name, headline, recipients):
    """Send the collection-invite emails for a bulk invite without blocking.

    In production (``EMAIL_SEND_ASYNC``) the whole loop runs on a daemon thread so
    a large batch doesn't stall the response; elsewhere it sends synchronously to
    keep tests deterministic. Each send is best-effort and swallows its errors.
    """
    if not recipients:
        return

    def _run():
        for email, accept_link, reject_link in recipients:
            try:
                send_collection_invite_email(
                    inviter_name, headline, email, accept_link, reject_link
                )
            except Exception:
                pass

    if getattr(settings, "EMAIL_SEND_ASYNC", False):
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()


class CollectionBulkInviteView(APIView):
    """
    POST /api/v1/collections/{collection_code}/invite/bulk/

    Invite many guests at once from a client-parsed CSV
    (``{"invites": [{"email": ..., "name": ...?}, ...]}``). Best-effort: valid,
    new addresses are invited and emailed; the rest are reported as skipped with a
    reason (invalid / duplicate / already_member / already_invited) — one bad row
    never fails the batch. Owner-only, capped at ``MAX_ROWS`` and rate-limited.
    """

    permission_classes = [IsAuthenticated]
    MAX_ROWS = 100

    @method_decorator(ratelimit(key="user", rate="5/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_owner(
            collection, request.user.code, "Only the owner can invite users"
        )
        if denied:
            return denied

        rows = request.data.get("invites") if isinstance(request.data, dict) else None
        if not isinstance(rows, list) or not rows:
            return Response({"error": "No emails to invite."}, status=status.HTTP_400_BAD_REQUEST)
        if len(rows) > self.MAX_ROWS:
            return Response(
                {"error": f"At most {self.MAX_ROWS} invitations can be sent at once."},
                status=status.HTTP_400_BAD_REQUEST,
            )

        email_field = serializers.EmailField(max_length=64)
        name_field = SafeHeadlineField(max_length=32, required=False, allow_blank=True)

        skipped = []
        seen = set()
        candidates = []  # (email, name) — well-formed and unique within the batch
        for row in rows:
            raw_email = (row.get("email") if isinstance(row, dict) else "") or ""
            try:
                email = email_field.run_validation(str(raw_email).strip()).lower()
            except serializers.ValidationError:
                skipped.append({"email": str(raw_email).strip()[:64], "reason": "invalid"})
                continue
            if email in seen:
                skipped.append({"email": email, "reason": "duplicate"})
                continue
            seen.add(email)
            raw_name = str((row.get("name") if isinstance(row, dict) else "") or "").strip()
            try:
                # A malformed name (e.g. HTML) is dropped, not a reason to skip.
                name = name_field.run_validation(raw_name) if raw_name else ""
            except serializers.ValidationError:
                name = ""
            candidates.append((email, name))

        inviter_name = request.user.display_name
        invited = []
        recipients = []  # (email, accept_link, reject_link)
        with transaction.atomic():
            for email, name in candidates:
                defaults = {"email": email}
                if name:
                    defaults["name"] = name
                invited_user, _ = User.objects.get_or_create(email=email, defaults=defaults)

                if collection.is_invited(invited_user.code):
                    skipped.append({"email": email, "reason": "already_member"})
                    continue
                if RSVP.objects.filter(
                    user_code=invited_user,
                    target_code=collection_code,
                    action=RSVP.Action.COLLECTION_INVITE,
                ).exists():
                    skipped.append({"email": email, "reason": "already_invited"})
                    continue

                accept_rsvp = RSVP.objects.create(
                    user_code=invited_user,
                    user_email=email,
                    action=RSVP.Action.COLLECTION_INVITE,
                    target_code=collection_code,
                )
                reject_rsvp = RSVP.objects.create(
                    user_code=invited_user,
                    user_email=email,
                    action=RSVP.Action.COLLECTION_REJECT,
                    target_code=collection_code,
                )
                invited.append(email)
                recipients.append((email, accept_rsvp.action_link(), reject_rsvp.action_link()))

        _send_bulk_invites(inviter_name, collection.headline, recipients)

        logger.info(
            "Bulk invite: user=%s collection=%s invited=%d skipped=%d",
            request.user.code,
            collection_code,
            len(invited),
            len(skipped),
        )

        return Response(
            {"invited": len(invited), "skipped": skipped, "total": len(rows)},
            status=status.HTTP_200_OK,
        )


class CollectionStatsView(APIView):
    """
    GET /api/v1/collections/{collection_code}/stats/

    Owner-only usage statistics for any collection, returned as a CSV
    download (metric,value): a snapshot plus a 90-day window, and — since the
    optional member demographics exist — an aggregate age-range and postal-code
    breakdown. Aggregate only; the per-member values live on the guests page
    (and stay COMMUNITY-only there).
    """

    permission_classes = [IsAuthenticated]
    WINDOW_DAYS = 90

    def get(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)
        denied = require_collection_owner(
            collection, request.user.code, "Only the owner can view stats"
        )
        if denied:
            return denied

        win = self.WINDOW_DAYS
        since = timezone.now() - timedelta(days=win)
        since_date = since.date()
        members = list(collection.invites.all())
        member_codes = [u.code for u in members]

        rows = [["metric", "value"]]
        rows.append(["Members", len(members)])
        rows.append(
            [
                "Pending invitations",
                RSVP.objects.filter(
                    action=RSVP.Action.COLLECTION_INVITE, target_code=collection_code
                ).count(),
            ]
        )
        rows.append(["Things total", collection.things.count()])
        rows.append(["Things active", collection.things.filter(status=Thing.Status.ACTIVE).count()])
        rows.append(
            ["Things reserved", collection.things.filter(status=Thing.Status.TAKEN).count()]
        )
        rows.append(
            [f"Things added ({win}d)", collection.things.filter(created__gte=since).count()]
        )
        rows.append(
            [
                f"Bookings ({win}d)",
                BookingPeriod.objects.filter(thing_code__collections=collection, created__gte=since)
                .distinct()
                .count(),
            ]
        )
        rows.append(
            [
                f"Handovers ({win}d)",
                ThingTransfer.objects.filter(
                    thing__collections=collection, lent_date__gte=since_date
                )
                .distinct()
                .count(),
            ]
        )
        rows.append(
            [
                f"Invitations sent ({win}d)",
                RSVP.objects.filter(
                    action=RSVP.Action.COLLECTION_INVITE,
                    target_code=collection_code,
                    created__gte=since,
                ).count(),
            ]
        )
        active = set(
            Thing.objects.filter(
                collections=collection, created__gte=since, owner_id__in=member_codes
            ).values_list("owner_id", flat=True)
        ) | set(
            BookingPeriod.objects.filter(
                thing_code__collections=collection,
                created__gte=since,
                requester_code_id__in=member_codes,
            ).values_list("requester_code_id", flat=True)
        )
        rows.append([f"Active members ({win}d)", len(active)])

        age_labels = {
            "UP_TO_21": "Age 21 or under",
            "22_35": "Age 22-35",
            "36_55": "Age 36-55",
            "56_PLUS": "Age 56 or over",
        }
        age_counts = Counter(u.age_range for u in members if u.age_range)
        for age_code, label in age_labels.items():
            rows.append([label, age_counts.get(age_code, 0)])
        rows.append(["Age not specified", sum(1 for u in members if not u.age_range)])

        postal_counts = Counter(u.postal_code for u in members if u.postal_code)
        for postal, count in postal_counts.most_common(10):
            # The code follows the literal "Postal " label, so the cell never
            # starts with =, +, - or @ — no spreadsheet-formula injection.
            rows.append([f"Postal {postal}", count])
        rows.append(["Postal not specified", sum(1 for u in members if not u.postal_code)])

        response = HttpResponse(content_type="text/csv")
        response["Content-Disposition"] = f'attachment; filename="{collection_code}-stats.csv"'
        csv.writer(response).writerows(rows)
        return response


class InvitedCollectionsView(APIView):
    """
    GET /api/v1/invited-collections/
    List collections where the current user is in invites.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        invited_collections = _optimise_collection_queryset(
            request.user.invited_to_collections.filter(status=Collection.Status.ACTIVE)
        )
        serializer = CollectionSerializer(
            invited_collections, many=True, context={"request": request}
        )
        return Response(serializer.data)


class MyPendingInvitationsView(APIView):
    """
    GET /api/v1/my-invitations/
    List pending (not yet accepted) collection invitations for the current user.
    Returns accept + reject RSVP codes, collection headline and owner name.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        accept_rsvps = list(
            RSVP.objects.filter(user_code=request.user, action=RSVP.Action.COLLECTION_INVITE)
        )

        if not accept_rsvps:
            return Response([])

        target_codes = [r.target_code for r in accept_rsvps]

        # Fetch all related collections and reject RSVPs in two queries
        collections_by_code = {
            c.code: c
            for c in Collection.objects.filter(code__in=target_codes).select_related("owner")
        }
        reject_rsvps_by_target = {
            r.target_code: r
            for r in RSVP.objects.filter(
                user_code=request.user,
                action=RSVP.Action.COLLECTION_REJECT,
                target_code__in=target_codes,
            )
        }

        result = []
        for accept_rsvp in accept_rsvps:
            collection = collections_by_code.get(accept_rsvp.target_code)
            if collection is None:
                continue
            reject_rsvp = reject_rsvps_by_target.get(accept_rsvp.target_code)
            result.append(
                {
                    # The high-entropy token, not the 6-char PK — the frontend
                    # feeds these straight to /verify/<value>/, which now resolves
                    # RSVPs by token only.
                    "accept_code": accept_rsvp.token,
                    "reject_code": reject_rsvp.token if reject_rsvp else None,
                    "collection_code": collection.code,
                    "collection_headline": collection.headline,
                    "owner_name": collection.owner.display_name,
                }
            )

        return Response(result)


class CollectionShareLinkView(APIView):
    """
    POST /api/v1/collections/{collection_code}/share-link/
    Generate (or rotate) a public share token. Returns the full public URL.

    DELETE /api/v1/collections/{collection_code}/share-link/
    Revoke the share token. The link becomes invalid for everyone.

    Owner only. Token is a 22-char URL-safe bearer credential — anyone with
    the link can join the collection via /share/{token}, so the token must
    not appear in any read endpoint.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_owner(
            collection, request.user.code, "Only the owner can manage the share link"
        )
        if denied:
            return denied

        rotate = bool(request.data.get("rotate"))

        if rotate or not collection.share_token:
            collection.share_token = generate_share_token()
            collection.save(update_fields=["share_token"])

        share_base = getattr(settings, "SHARE_LINK_BASE_URL", "http://localhost:3000/share")
        share_url = f"{share_base}/{collection.share_token}"

        return Response(
            {
                "share_url": share_url,
                "share_token": collection.share_token,
            },
            status=status.HTTP_200_OK,
        )

    def delete(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_owner(
            collection, request.user.code, "Only the owner can manage the share link"
        )
        if denied:
            return denied

        if collection.share_token:
            collection.share_token = None
            collection.save(update_fields=["share_token"])

        return Response(
            {"message": "Share link revoked"},
            status=status.HTTP_200_OK,
        )


class CollectionBroadcastView(APIView):
    """
    POST /api/v1/collections/{collection_code}/broadcast/
    Send a broadcast email from the collection owner to all invitees.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="5/d", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_owner(
            collection, request.user.code, "Only the owner can send broadcasts"
        )
        if denied:
            return denied

        serializer = CollectionBroadcastSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        message = serializer.validated_data["message"]

        # Gather invitee emails
        invitee_emails = list(collection.invites.values_list("email", flat=True))

        if not invitee_emails:
            return Response(
                {"error": "No invitees to broadcast to"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        owner_name = request.user.display_name

        send_broadcast_email(
            owner_name=owner_name,
            owner_email=request.user.email,
            collection_headline=collection.headline,
            collection_code=collection.code,
            message=message,
            emails=invitee_emails,
        )

        InAppNotification.objects.bulk_create(
            [
                InAppNotification(
                    user=invitee,
                    type=InAppNotification.Type.BROADCAST,
                    payload={
                        "collection_headline": collection.headline,
                        "owner_name": owner_name,
                        "message": message,
                        "collection_code": collection.code,
                    },
                )
                for invitee in collection.invites.all()
            ]
        )

        return Response(
            {
                "message": "Broadcast sent",
                "recipients": len(invitee_emails),
            },
            status=status.HTTP_200_OK,
        )
