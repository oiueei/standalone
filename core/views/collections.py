"""
Collection views for OIUEEI.
"""

import csv
import logging
import threading
from datetime import timedelta

from django.conf import settings
from django.db import IntegrityError, transaction
from django.db.models import Exists, OuterRef, Prefetch, Q
from django.http import Http404, HttpResponse
from django.shortcuts import get_object_or_404
from django.utils import timezone
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import serializers, status
from rest_framework.exceptions import PermissionDenied
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework.viewsets import ModelViewSet

from core.models import RSVP, Collection, InvitationProposal, NetworkPoint, Thing, User
from core.models.collection import generate_share_token
from core.models.event import Event
from core.models.notification import InAppNotification
from core.permissions import IsCollectionCurator, IsCollectionOwner
from core.serializers import (
    CollectionBroadcastSerializer,
    CollectionCreateSerializer,
    CollectionInviteSerializer,
    CollectionProposeInviteSerializer,
    CollectionRemoveInviteSerializer,
    CollectionSerializer,
    CollectionUpdateSerializer,
    EmailNoteTestSerializer,
)
from core.serializers.network_point import (
    IDENTITY_FIELDS,
    NetworkPointSerializer,
    NetworkPointWriteSerializer,
)
from core.serializers.theeeme import theeeme_colors
from core.serializers.thing import optimise_thing_queryset
from core.services.creator_policy import (
    capabilities_for,
    co_owners_denial,
    collection_kind_denial,
    collection_mode_denial,
)
from core.services.deletion_events import deleting_as
from core.services.email_service import (
    send_broadcast_email,
    # Still used directly by the bulk-invite fan-out, which batches its RSVP
    # creation and then mails off the request thread — a different shape from
    # the one-at-a-time `deliver_invitation` path below.
    send_collection_invite_email,
    send_collection_revoke_email,
    send_email_note_test_email,
)
from core.services.export_service import collection_stats_rows
from core.services.invitation_service import (
    _ALREADY_ASKED_MESSAGE,
    _INVITE_QUOTA_MESSAGE,
    InvitationAlreadyAsked,
    ProposalAlreadyDecided,
    _consume_invite_quota,
    _invite_quota_left,
    approve_proposal,
    create_proposal,
    deliver_invitation,
    invitation_blocked,
    proposal_approval_blocked,
    record_invitation,
    reject_proposal,
)
from core.services.join_quota import consume_join_quota, join_quota_exhausted
from core.services.membership_service import (
    demote_curator,
    end_membership,
    network_exit_block,
    things_leaving_with,
)
from core.services.team import drop_team_notices_of
from core.utils import get_client_ip, redact_email
from core.validators import SafeHeadlineField
from core.views._helpers import (
    approval_refusal_response,
    body_dict,
    refusal_body,
    require_collection_curator,
    require_network_founder,
    viewer_code,
)

# The single funnel every join path goes through (invite acceptance, share
# token, public login-to-act, onboarding). Imported rather than reimplemented
# so this door cannot drift from the others on what a join means.
from core.views.auth import _join_collection

logger = logging.getLogger(__name__)
security_logger = logging.getLogger("security")


def _optimise_collection_queryset(queryset, viewer=None):
    """Add select/prefetch_related for nested serializer access on collections.

    ``viewer`` is the requesting user, when there is one. It buys the
    ``is_digest_muted`` prefetch, and only then: the field answers False without
    a lookup for anonymous readers and for owners, so prefetching unconditionally
    spends a query on the anonymous PUBLIC-collection read — the hot path that
    costs us the most and gains nothing (pinned by the query-budget tests).

    The prefetch is narrowed to the viewer's own row rather than pulling every
    muted member of the group: the serializer only ever asks "did *I* mute this?"
    """
    queryset = queryset.select_related("owner", "theeeme").prefetch_related(
        "invites",
        # Public, like `owner_name` — `get_co_owners` serves it to every
        # viewer, and `is_curator`/`is_member` read it via `.all()` for any
        # signed-in one, so it is prefetched unconditionally alongside
        # `invites` rather than gated behind `viewer` the way `digest_muted` is.
        "co_owners",
        # The curators' pages travel with every collection (public, in any mode), and
        # `point_for` / `card_for` read the same rows: one query for all of them.
        Prefetch("points", queryset=NetworkPoint.objects.select_related("user")),
        Prefetch("things", queryset=optimise_thing_queryset(Thing.objects.all())),
    )
    if viewer is not None and viewer.is_authenticated:
        queryset = queryset.prefetch_related(
            Prefetch("digest_muted", queryset=User.objects.filter(code=viewer.code)),
            # Owner-only in the serializer, but prefetched for any signed-in
            # viewer: the alternative is a query per collection on the owner's
            # own list (caught by the query-budget tests). The proposer is
            # joined because the card prints their name.
            Prefetch(
                "invitation_proposals",
                queryset=InvitationProposal.objects.filter(
                    status=InvitationProposal.Status.PENDING
                ).select_related("proposer"),
                to_attr="_pending_proposals",
            ),
        )
    return queryset


class CollectionViewSet(ModelViewSet):
    """
    ViewSet for Collection CRUD operations.

    list:    GET /api/v1/collections/
    create:  POST /api/v1/collections/
    retrieve: GET /api/v1/collections/{code}/
    update:  PUT /api/v1/collections/{code}/
    destroy: DELETE /api/v1/collections/{code}/
    """

    lookup_field = "code"

    def get_queryset(self):
        # "My collections" includes what this account curates, not only what
        # it owns — a co-owner's group belongs here, next to their own, rather
        # than only under "Shared with me" (InvitedCollectionsView).
        qs = (
            Collection.objects.filter(Q(owner=self.request.user) | Q(co_owners=self.request.user))
            .distinct()
            .order_by("-created")
        )
        if self.action in ("list", "retrieve"):
            # The viewer matters here even though this list is always their own:
            # `pending_proposals` is owner-only, so this is exactly the list that
            # needs its prefetch, and without it the field costs one query per
            # collection (caught by the query-budget tests).
            return _optimise_collection_queryset(qs, viewer=self.request.user)
        return qs

    def get_serializer_class(self):
        if self.action == "create":
            return CollectionCreateSerializer
        if self.action in ("update", "partial_update"):
            return CollectionUpdateSerializer
        return CollectionSerializer

    def get_permissions(self):
        # destroy stays owner-only — deleting the collection is deliberately not
        # a co-owner power. update/partial_update widen to the curator tier.
        if self.action == "destroy":
            return [IsAuthenticated(), IsCollectionOwner()]
        if self.action in ("update", "partial_update"):
            return [IsAuthenticated(), IsCollectionCurator()]
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
            qs = _optimise_collection_queryset(Collection.objects.all(), viewer=self.request.user)
            obj = get_object_or_404(qs, code=self.kwargs[self.lookup_field])
            if not obj.can_view(viewer_code(self.request)):
                self.permission_denied(self.request)
            return obj
        obj = get_object_or_404(Collection, code=self.kwargs[self.lookup_field])
        self.check_object_permissions(self.request, obj)
        return obj

    def perform_destroy(self, instance):
        # Bare name — this rides an in-app notification to every member, and a
        # member is never served their owner's address.
        owner_name = instance.owner.name
        headline = instance.headline
        invitees = list(instance.invites.all())

        # Only what lives nowhere else. Counting with `instance.things.annotate(
        # Count("collections"))` reuses the join the related manager already
        # filtered by this collection and always says 1, so a thing in another
        # collection too would go with this one.
        in_another = Collection.things.through.objects.filter(thing=OuterRef("pk")).exclude(
            collection=instance
        )
        orphaned_things = Thing.objects.filter(collections=instance).filter(~Exists(in_another))
        with transaction.atomic(), deleting_as(self.request.user):
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
        # Does this deployment let this person open a collection in that mode?
        # The default is checked too, not just an explicit one: a policy that
        # withholds every mode has to refuse a body that names none.
        capabilities = capabilities_for(self.request.user)
        denial = collection_mode_denial(
            self.request.user,
            validated_data.get("mode", Collection.Mode.PROPRIETARY),
            capabilities,
        ) or collection_kind_denial(self.request.user, validated_data["kind"], capabilities)
        if denial:
            raise PermissionDenied(denial)
        collection = Collection.objects.create(
            owner=self.request.user,
            **validated_data,
        )
        Event.log(Event.Kind.COLLECTION_CREATED, actor=self.request.user, collection=collection)
        self._created_collection = collection

    def perform_update(self, serializer):
        # The mode is editable, and switching one is how a collection would
        # otherwise walk around the gate at creation. Checked only when it
        # actually changes: a collection already in a mode the policy has since
        # stopped handing out stays fully editable by its owner — the gate is on
        # opening one, not on keeping one.
        collection = serializer.instance
        new_mode = serializer.validated_data.get("mode", collection.mode)
        if new_mode != collection.mode:
            denial = collection_mode_denial(self.request.user, new_mode)
            if denial:
                raise PermissionDenied(denial)
        serializer.save()

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def create(self, request, *args, **kwargs):
        serializer = self.get_serializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        self.perform_create(serializer)
        return Response(
            CollectionSerializer(self._created_collection, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


# Daily cap on invitation *emails* per account, shared by the single and bulk
# invite endpoints. The per-view rate limits count requests, and one bulk request
# fans out up to MAX_ROWS emails — 5/h x 100 rows is ~500 owner-authored emails
# an hour from one account, a spam/phishing vector riding the deployment's
# sending domain (and a cheap one wherever a deployment adds an open sign-up
# door of its own). This counts the emails themselves.
#
# **Operator policy, not a product rule.** The cap protects the deployment's own
# sending reputation, and only the operator knows what their provider tolerates,
# so the value lives in settings (`INVITE_EMAILS_PER_DAY`, read from the env in
# base.py) and the standalone ships it **unset = unlimited**: a self-hoster
# decides for their own instance. A deployment sets the config var.
#
# Coarse abuse prevention, not an exact quota: it also follows RATELIMIT_ENABLE
# (the same switch the django-ratelimit decorators read, so dev and tests stay
# consistent) and its DatabaseCache read-then-set shares base.py's
# non-atomicity note.
def _exit_blocked(code, headlines):
    """The 409 that holds a network's removal or demotion back while a loan is in hand."""
    sentences = {
        "curator_things_lent_out": (
            "Some of their things are lent out right now. It can be done once the loans end: "
            "{things}."
        ),
        "member_holds_loans": (
            "They have things in hand right now. It can be done once the loans end: {things}."
        ),
    }
    things = ", ".join(headlines)
    return Response(
        refusal_body(sentences[code].format(things=things), code=code, things=things),
        status=status.HTTP_409_CONFLICT,
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

        denied = require_collection_curator(
            collection, request.user.code, "Only the owner or a co-owner can invite users"
        )
        if denied:
            return denied

        # Checked before get_or_create so a quota-blocked request creates no User row.
        if _invite_quota_left(request.user.code) == 0:
            return Response(
                refusal_body(_INVITE_QUOTA_MESSAGE),
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        serializer = CollectionInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()

        # Member ceiling, enforced where invitations are SENT rather than where
        # they are accepted: refusing an invitee at the door would punish someone
        # who did nothing wrong. It counts current members, so invitations still
        # pending are not included — the daily email quota above is what caps a
        # fan-out of unaccepted invites.
        #
        # Someone who is already a member consumes no capacity — they are inside
        # the count the ceiling measures — so re-inviting them is never a ceiling
        # refusal: it falls through to the "already invited" 400 below, which is
        # the accurate answer. Checked by email so it still runs before
        # get_or_create, leaving a refused invite with no User row behind.
        if (
            collection.capacity_ceiling("invites")
            and not collection.invites.filter(email=email).exists()
        ):
            full = collection.capacity_violation("invites", adding=1)
            if full:
                return Response(refusal_body(full), status=status.HTTP_400_BAD_REQUEST)

        # One delivery path, shared with an owner approving a member's proposal
        # (invitation_service.deliver_invitation): the get_or_create, the RSVP
        # pair, the email and the quota all live there, so the two routes into an
        # invitation cannot drift.
        try:
            invited_user, already_invited = deliver_invitation(
                collection,
                email,
                # Bare name: this reaches somebody outside the group entirely.
                request.user.name,
                quota_user_code=request.user.code,
            )
        except InvitationAlreadyAsked:
            return Response(
                refusal_body(_ALREADY_ASKED_MESSAGE), status=status.HTTP_400_BAD_REQUEST
            )
        if already_invited:
            return Response(
                refusal_body(
                    "This user is already invited to this collection.",
                    code="already_invited",
                    key="detail",
                ),
                status=status.HTTP_400_BAD_REQUEST,
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

        denied = require_collection_curator(
            collection, request.user.code, "Only the owner or a co-owner can remove invites"
        )
        if denied:
            return denied

        serializer = CollectionRemoveInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        user_code = serializer.validated_data["user_code"]

        # The founder is an FK, never an ``invites`` row: refused before ``invites`` is
        # read, so a stray row can't turn this into the founder's own removal.
        if user_code == collection.owner_id:
            return Response(
                refusal_body(
                    "The owner can't be removed from their own collection.",
                    code="owner_cannot_be_removed",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user is a confirmed invite
        try:
            invited_user = collection.invites.get(code=user_code)
        except User.DoesNotExist:
            invited_user = None

        if invited_user:
            # Cancelling a pending invitation undoes what any dinamizador may do
            # (invite); removing a member is the founder's alone in a network.
            denied = require_network_founder(
                collection, request.user.code, "Only the founder of a network can remove members"
            )
            if denied:
                return denied
            blocked = network_exit_block(collection, invited_user, removing=True)
            if blocked:
                return _exit_blocked(*blocked)
            was_co_owner = collection.co_owners.filter(code=invited_user.code).exists()
            went_with_them = [t.headline for t in things_leaving_with(collection, invited_user)]
            things_deleted = end_membership(collection, invited_user, actor=request.user)
            if was_co_owner:
                # They stopped running the group: the requests and reservations it
                # sent them to decide are no longer theirs (same as a demotion).
                drop_team_notices_of(invited_user, collection)
            Event.log(Event.Kind.MEMBER_LEFT, actor=invited_user, collection=collection)

            # A co-curator's removal is told to the founder, who did not do it
            # (the same notice a member's own leaving writes, plus who removed them,
            # by bare name). The founder removing someone is told nothing. A removed
            # member with no name is named to the founder by their address
            # (``member_email``): the members list already shows it to them.
            if request.user.code != collection.owner_id:
                InAppNotification.objects.create(
                    user=collection.owner,
                    type=InAppNotification.Type.MEMBER_LEFT,
                    payload={
                        "collection_headline": collection.headline,
                        "collection_code": collection.code,
                        "member_name": invited_user.name,
                        **({} if invited_user.name else {"member_email": invited_user.email}),
                        "things_deleted": things_deleted,
                        "removed_by_name": request.user.name,
                    },
                )

            # Notify the removed user — invited_user is already in hand (fetched
            # above), so there's no need to re-query and no DoesNotExist to guard.
            # Bare name — the person being removed is the last reader who
            # should be handed the owner's address on the way out.
            owner_name = request.user.name
            send_collection_revoke_email(
                owner_name,
                collection.headline,
                invited_user.email,
                collection=collection,
                things=went_with_them,
            )
            InAppNotification.objects.create(
                user=invited_user,
                type=InAppNotification.Type.COLLECTION_REVOKED,
                payload={"collection_headline": collection.headline, "owner_name": owner_name},
            )

            return Response(
                {
                    "message": "User removed from collection",
                    "user_code": user_code,
                    "things_deleted": things_deleted,
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
            refusal_body("User is not invited to this collection", code="not_invited"),
            status=status.HTTP_400_BAD_REQUEST,
        )


class CollectionCoOwnerView(APIView):
    """
    POST /api/v1/collections/{collection_code}/co-owners/
    Promote an existing member to co-curator.

    DELETE /api/v1/collections/{collection_code}/co-owners/
    Demote a co-curator back to a plain member — they stay a member, they just
    lose the admin powers.

    Any curator may promote or demote another, in any mode: a co-curator has
    the founder's reach over everything except deleting the collection (the
    CASCADE-delete root, which stays ``IsCollectionOwner``), and appointing
    help is part of that reach. The founding ``owner`` is an FK, not a
    ``co_owners`` row, so this endpoint structurally cannot demote them — no
    guard needed; the accepted trade-off is that co-curators can ping-pong
    demotions and the founder is the circuit breaker. Promotion is still
    gated behind this deployment's ``CREATOR_POLICY`` the same way a mode or a
    verb is.
    """

    permission_classes = [IsAuthenticated]

    def _get_target(self, collection, request):
        """Shared validation for POST and DELETE: resolve and return the
        target ``User``, or a Response explaining why not.

        Checks membership only — a co-curator is promoted from ``invites``,
        never invited separately (``co_owners ⊆ invites``), and the
        collection's mode is not a factor in either direction.
        """
        serializer = CollectionRemoveInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        user_code = serializer.validated_data["user_code"]

        try:
            member = collection.invites.get(code=user_code)
        except User.DoesNotExist:
            return None, Response(
                refusal_body(
                    "Only an existing member can be promoted or demoted",
                    code="not_a_member_target",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        return member, None

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_curator(
            collection, request.user.code, "Only a curator can promote a co-curator"
        ) or require_network_founder(
            collection, request.user.code, "Only the founder of a network can name its team"
        )
        if denied:
            return denied

        denial = co_owners_denial(request.user)
        if denial:
            return Response({"error": denial}, status=status.HTTP_403_FORBIDDEN)

        member, denied = self._get_target(collection, request)
        if denied:
            return denied

        # Re-promoting someone who is already a co-curator stays idempotent and
        # never hits the ceiling — only growing the set does. The bound is the
        # abuse ceiling (`Collection.MAX_CO_OWNERS`), not the design intent of
        # 1–2: a compromised curator's credential must not be able to promote
        # the whole roster, since each promotion hands over the member list. The
        # check and the add are one locked step in the model, so promotions
        # running at once cannot all read the same count and overshoot it.
        result = collection.promote_co_owner(member)
        if result is Collection.Promotion.FULL:
            # Coded like a request's refusals (`BookingRequestError.as_body`): the
            # SPA says it in the reader's language from `requestErrors.co_owners_full`,
            # the English sentence stays as the fallback for a client that lacks it.
            return Response(
                {
                    "error": (
                        "This collection already has the maximum of "
                        f"{Collection.MAX_CO_OWNERS} co-curators"
                    ),
                    "code": "co_owners_full",
                    "params": {"max": Collection.MAX_CO_OWNERS},
                },
                status=status.HTTP_400_BAD_REQUEST,
            )
        if result is Collection.Promotion.ADDED:
            InAppNotification.objects.create(
                user=member,
                type=InAppNotification.Type.PROMOTED_CO_OWNER,
                payload={
                    "collection_headline": collection.headline,
                    "collection_code": collection.code,
                    # A dinamizador's reach is narrower in a network: the card says which.
                    **({"network": True} if collection.is_network() else {}),
                },
            )

        return Response(
            {"message": "Promoted to co-owner", "user_code": member.code},
            status=status.HTTP_200_OK,
        )

    # Same ceiling as promotion: without it a compromised curator could thrash
    # demotions (each one firing a DEMOTED notice) without any bound.
    @method_decorator(ratelimit(key="user", rate="30/h", method="DELETE", block=True))
    def delete(self, request, collection_code):
        # No `co_owners_denial()` check here, deliberately: the gate is on
        # *bringing this state into existence* (see `post`), not on living in
        # it — the same grandfathering `creator_policy` already applies to a
        # mode or a verb a deployment later withdraws. A curator must always be
        # able to demote, even on a deployment that has since disabled the
        # feature outright.
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_curator(
            collection, request.user.code, "Only a curator can demote a co-curator"
        ) or require_network_founder(
            collection, request.user.code, "Only the founder of a network can name its team"
        )
        if denied:
            return denied

        member, denied = self._get_target(collection, request)
        if denied:
            return denied

        was_co_owner = collection.co_owners.filter(code=member.code).exists()
        things_deleted = 0
        if was_co_owner and collection.is_network():
            # Stops being a dinamizador: the things they ran cannot stay (nobody else
            # may decide them), and not while someone has one in hand.
            blocked = network_exit_block(collection, member, removing=False)
            if blocked:
                return _exit_blocked(*blocked)
            things_deleted = demote_curator(collection, member, actor=request.user)
        else:
            collection.co_owners.remove(member)
            # Outside a network the role's page goes with it too (their things stay).
            if was_co_owner:
                collection.points.filter(user=member).delete()
        if was_co_owner:
            payload = {
                "collection_headline": collection.headline,
                "collection_code": collection.code,
            }
            if collection.is_network():
                payload["things_deleted"] = things_deleted
            InAppNotification.objects.create(
                user=member,
                type=InAppNotification.Type.DEMOTED_CO_OWNER,
                payload=payload,
            )
            # After the DEMOTED notice, so the one that tells them what happened is
            # never in the way: what goes is the team's requests and reservations of
            # this group, which they can no longer decide.
            drop_team_notices_of(member, collection)

        return Response(
            {"message": "Demoted to member", "user_code": member.code},
            status=status.HTTP_200_OK,
        )


class CollectionLeaveView(APIView):
    """
    POST /api/v1/collections/{collection_code}/leave/
    Lets an invited member remove themselves from a collection (self-unlink).
    A curator (the owner, or a co-owner) cannot leave this way — the owner
    deletes the collection instead, and a co-owner is staff, not a
    rank-and-file member, so the owner demotes them via the co-owners endpoint.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        if collection.is_owner(request.user.code):
            return Response(
                refusal_body(
                    "The owner can't leave their own collection.",
                    code="owner_cannot_leave",
                    key="detail",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        if collection.is_curator(request.user.code):
            return Response(
                refusal_body(
                    "A co-owner can't leave — ask the owner to demote you first.",
                    code="co_owner_cannot_leave",
                    key="detail",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not collection.invites.filter(code=request.user.code).exists():
            return Response(
                refusal_body(
                    "You are not a member of this collection.",
                    code="not_a_member_of_collection",
                    key="detail",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        things_deleted = end_membership(collection, request.user, actor=request.user)
        Event.log(Event.Kind.MEMBER_LEFT, actor=request.user, collection=collection)

        # Let the owner know a member left (in-app; symmetric to the revoke notice).
        InAppNotification.objects.create(
            user=collection.owner,
            type=InAppNotification.Type.MEMBER_LEFT,
            payload={
                "collection_headline": collection.headline,
                "member_name": request.user.name,
                **({} if request.user.name else {"member_email": request.user.email}),
                "collection_code": collection.code,
                "things_deleted": things_deleted,
            },
        )

        return Response(
            {"message": "You have left the collection", "things_deleted": things_deleted},
            status=status.HTTP_200_OK,
        )


def _log_joined(user, collection, door, ip):
    """The security-log line for a signed-in join, as ``JoinView`` writes for the
    anonymous one: who, into what, through which door."""
    security_logger.info(
        f"User {user.code} joined collection {collection.code} via {door} from IP {ip}"
    )


def _log_join_refused(user, collection, ip):
    """The operator's side of a refusal the visitor is told only as "tomorrow"."""
    security_logger.warning(
        f"Join refused for user {user.code} from IP {ip}: "
        f"collection {collection.code} is over COLLECTION_JOINS_PER_DAY"
    )


class CollectionJoinView(APIView):
    """
    POST /api/v1/collections/{collection_code}/join/
    Lets a signed-in visitor join a PUBLIC collection themselves.

    The mirror of ``CollectionLeaveView``, and it was the missing half. A
    PUBLIC collection is readable with no account, and the login-to-act funnel
    turns an **anonymous** reader into a member: they type an email at
    ``/collections/{code}/join``, ``POST /auth/join/`` adds them and mails a
    magic link. Someone who is *already signed in* fell through that funnel —
    the page assumes an anonymous visitor, and a magic link is no use to a
    session that already exists — so the one reader with an account and the
    most intent had no way in at all. In COMMUNITY mode the collection page
    then offered them "Add thing", which `Collection.can_add_thing` refuses:
    they filled the form, uploaded the photos, and collected a 403.

    Same door as the anonymous one, so the same rules: PUBLIC and ACTIVE only,
    the join funnel that logs MEMBER_JOINED once and sends the welcome document,
    and the operator's per-collection daily ceiling — a cap that only stopped
    strangers would be a cap anyone with an account could walk around.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        # Existence is answered by the same guard that decides whether they may
        # read it at all: a PRIVATE collection must not confirm it exists to
        # someone who cannot see it, and "you may not join" would do exactly
        # that.
        if not collection.can_view(request.user.code):
            raise Http404

        if collection.is_owner(request.user.code):
            return Response(
                refusal_body(
                    "You already own this collection.", code="already_owner", key="detail"
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Idempotent, like the funnel below: a double-tap, or a member who
        # somehow lands here, gets the same answer and nothing happens twice.
        if collection.invites.filter(code=request.user.code).exists():
            return Response({"message": "You are a member of this collection"})

        # Belt and braces, and **unreachable as the guards above stand**: a
        # non-owner only gets past `can_view` on a PUBLIC ACTIVE collection or
        # one they are invited to, and `is_invited` is the very query the
        # membership line just ran. So nothing can arrive here non-public, which
        # is why no test covers this branch and none can — the two that pin the
        # invariant instead are `test_a_private_collection_does_not_confirm_it_
        # exists` (404) and `test_a_member_of_a_private_collection_is_told_they_
        # are_already_in` (200).
        #
        # It stays because the invariant lives in another file: widen `can_view`
        # one day — a network of federated groups, a "readable by link" tier —
        # and this is what keeps a readable-but-not-public collection from being
        # joinable by anyone who can see it.
        if not collection.is_public():
            return Response(
                refusal_body(
                    "This collection is not open to join.", code="not_open_to_join", key="detail"
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

        ip = get_client_ip(request)
        if join_quota_exhausted(collection.code):
            _log_join_refused(request.user, collection, ip)
            return Response(
                refusal_body(
                    "This collection has taken today's joins. Try again tomorrow.",
                    code="joins_spent",
                    key="detail",
                ),
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        _join_collection(collection, request.user, source=Event.Source.PUBLIC)
        consume_join_quota(collection.code)
        _log_joined(request.user, collection, "public", ip)

        return Response({"message": "You have joined the collection"})


class CollectionProposeInviteView(APIView):
    """
    POST /api/v1/collections/{collection_code}/invite/propose/

    A **member** asks the owner to invite somebody. Nothing is sent to the
    proposed address here — see `invitation_service.create_proposal`.

    Members could not bring anyone in at all before this: every new person cost
    an owner action, so a group grew only as fast as one person worked at it. But
    an owner is not merely a bottleneck: the group may be closed, may run on
    subscriptions, papers or rules of admission the product knows nothing about.
    So the member proposes and the owner decides.

    Open in **both** modes. PROPRIETARY decides who may add a *thing*; it has
    never decided who may suggest a person, and the owner's approval is the gate
    either way.

    Rate limited 30/day per member — high on purpose. This is not expected to be
    abused, and if somebody does, the owner has a much better answer than a quota:
    removing them from the collection.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/d", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        if collection.is_curator(request.user.code):
            # A curator (owner or co-owner) has the real thing one endpoint over.
            return Response(
                refusal_body(
                    "You own this collection — invite them directly.",
                    code="owner_invites_directly",
                    key="detail",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not collection.invites.filter(code=request.user.code).exists():
            return Response(
                refusal_body(
                    "Only members can propose someone.", code="only_members_propose", key="detail"
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )
        if not collection.allow_member_proposals:
            # The owner has said they don't want to be asked. The frontend hides
            # the form, so reaching this means a stale page or a direct POST.
            return Response(
                refusal_body(
                    "This group doesn't take suggestions from members.",
                    code="proposals_off",
                    key="detail",
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = CollectionProposeInviteSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        email = serializer.validated_data["email"].lower()
        note = serializer.validated_data.get("note", "")

        # Answered here rather than by the owner: neither case needs a decision.
        #
        # **One message for both, deliberately.** Separately they read "they are
        # already part of this group" and "someone has already suggested them",
        # and the first of those is an email-membership oracle: a member could
        # test any address against the roster, 30 a day, and get a yes/no. The
        # roster a non-owner receives is `code` + `name` and no email precisely
        # so that co-members' addresses stay the owner's to see — this
        # endpoint handed the same fact back one guess at a time. Answering with
        # both possibilities keeps the proposer's real question answered ("do I
        # need to do anything? no") while confirming neither branch.
        already_member = (
            collection.invites.filter(email=email).exists()
            or collection.owner.email.lower() == email
        )
        already_proposed = InvitationProposal.objects.filter(
            collection=collection, email=email, status=InvitationProposal.Status.PENDING
        ).exists()
        if already_member or already_proposed:
            return Response(
                refusal_body(
                    "Nothing to do — either they are already in this group, "
                    "or someone has already suggested them and it's with the owner.",
                    code="proposal_nothing_to_do",
                    key="detail",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        create_proposal(collection, request.user, email, note)
        return Response(
            {"message": "Suggestion sent to whoever runs the group"},
            status=status.HTTP_200_OK,
        )


class CollectionProposalActionView(APIView):
    """
    POST /api/v1/proposals/{proposal_code}/{approve|reject}/

    The owner's or a co-owner's in-app answer to a member's suggestion; the
    email links reach the same decisions through `VerifyLinkView`. Curator
    only — the proposer must not be able to wave their own suggestion through.
    """

    permission_classes = [IsAuthenticated]

    @staticmethod
    def _not_pending():
        return Response(
            refusal_body(
                "This suggestion is no longer pending.",
                code="proposal_not_pending",
                key="detail",
            ),
            status=status.HTTP_400_BAD_REQUEST,
        )

    def post(self, request, proposal_code, action):
        proposal = get_object_or_404(InvitationProposal, code=proposal_code)

        denied = require_collection_curator(
            proposal.collection,
            request.user.code,
            "Only the owner or a co-owner can answer a suggestion",
        )
        if denied:
            return denied

        if not proposal.is_valid():
            return self._not_pending()

        if action == "approve":
            # The ceiling and the quota are the owner's, and are checked for the
            # same reason the direct invite checks them: an approval that can't
            # be delivered should say so rather than half-happen. Shared with the
            # emailed approve link, which must not be a way around either.
            blocked = proposal_approval_blocked(proposal)
            if blocked:
                reason, code = blocked
                # Same refusal, same shape as the emailed link's (see
                # ``VerifyLinkView._handle_proposal_action``): the suggestion
                # stays pending; whether the owner may answer later is decided
                # in ``approval_refusal_response``.
                return approval_refusal_response(reason, code)
            try:
                approve_proposal(proposal)
            except ProposalAlreadyDecided:
                return self._not_pending()
            except InvitationAlreadyAsked:
                # Another invitation got in between the check above and the send.
                # The decision's reservation was undone with the transaction.
                return approval_refusal_response(_ALREADY_ASKED_MESSAGE, 400)
            return Response({"message": "Invitation sent"}, status=status.HTTP_200_OK)

        try:
            reject_proposal(proposal)
        except ProposalAlreadyDecided:
            return self._not_pending()
        return Response({"message": "Suggestion declined"}, status=status.HTTP_200_OK)


class CollectionDigestPrefView(APIView):
    """
    POST /api/v1/collections/{collection_code}/digest/  {"muted": true|false}

    A member silences (or un-silences) this one group's digest. It is the narrow
    control that makes ``User.notify_news`` defaulting to True honest: leaving a
    chatty group's summaries costs nothing else, so nobody has to choose between
    a weekly digest they didn't ask for and the booking emails they need.

    Whoever receives the digest may mute it: a member (co-curators are members
    too) and the founder, who gets it with the rest of the team. Anyone else is a
    400.

    Idempotent: ``add``/``remove`` on the M2M, so a double POST is harmless and
    the email footer's one-click link can be followed twice without an error.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        if not (
            collection.is_owner(request.user.code)
            or collection.invites.filter(code=request.user.code).exists()
        ):
            return Response(
                refusal_body(
                    "You are not a member of this collection.",
                    code="not_a_member_of_collection",
                    key="detail",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        muted = body_dict(request).get("muted")
        if not isinstance(muted, bool):
            return Response(
                {"muted": ["This field is required and must be true or false."]},
                status=status.HTTP_400_BAD_REQUEST,
            )

        if muted:
            collection.digest_muted.add(request.user)
        else:
            collection.digest_muted.remove(request.user)

        return Response({"muted": muted}, status=status.HTTP_200_OK)


def _send_bulk_invites(inviter_name, headline, recipients, collection=None):
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
                    inviter_name, headline, email, accept_link, reject_link, collection=collection
                )
            except Exception:
                # Per-email SMTP failures are already handled inside _send; anything
                # reaching here is unexpected (e.g. a template/programming error).
                # Log it (redacted) instead of silently dropping the invite,
                # but keep going so one bad row can't abort the rest of the batch.
                logger.warning(
                    "Bulk invite email failed for %s", redact_email(email), exc_info=True
                )

    if getattr(settings, "EMAIL_SEND_ASYNC", False):
        threading.Thread(target=_run, daemon=True).start()
    else:
        _run()


def _send_broadcast(
    owner_name, owner_email, headline, collection_code, message, emails, collection=None
):
    """Send a collection broadcast without blocking the request.

    ``send_broadcast_email`` loops over every invitee with a sequential SMTP call
    (10s timeout each), so a large group could exhaust the Heroku 30s request
    window (H12). In production (``EMAIL_SEND_ASYNC``) run it on a daemon thread so
    the owner's response returns immediately; elsewhere send synchronously to keep
    tests deterministic. It already swallows per-recipient send errors.
    """

    def _run():
        send_broadcast_email(
            owner_name=owner_name,
            owner_email=owner_email,
            collection_headline=headline,
            collection_code=collection_code,
            message=message,
            emails=emails,
            collection=collection,
        )

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
    reason (invalid / duplicate / already_member / already_asked / already_invited) — one bad row
    never fails the batch. Owner or co-owner, capped at ``MAX_ROWS`` and
    rate-limited.
    """

    permission_classes = [IsAuthenticated]
    MAX_ROWS = 100

    @method_decorator(ratelimit(key="user", rate="5/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_curator(
            collection, request.user.code, "Only the owner or a co-owner can invite users"
        )
        if denied:
            return denied

        # None = unlimited (RATELIMIT_ENABLE off in dev/tests). Exhausted → 429
        # outright; a partially-available quota lets the batch run and reports the
        # overflow per row below, so the owner sees exactly which addresses wait.
        quota_left = _invite_quota_left(request.user.code)
        if quota_left == 0:
            return Response(
                refusal_body(_INVITE_QUOTA_MESSAGE),
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        rows = body_dict(request).get("invites")
        if not isinstance(rows, list) or not rows:
            return Response(
                refusal_body("No emails to invite.", code="no_emails_to_invite"),
                status=status.HTTP_400_BAD_REQUEST,
            )
        if len(rows) > self.MAX_ROWS:
            return Response(
                refusal_body(
                    f"At most {self.MAX_ROWS} invitations can be sent at once.",
                    code="too_many_invites",
                    max=self.MAX_ROWS,
                ),
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

        # Member ceiling for the whole batch — same reasoning as the single
        # endpoint, and checked against the batch so a bulk invite cannot step
        # over the line 100 rows at a time. Counted AFTER validation and dedup,
        # and excluding addresses that are ALREADY members: those sit inside the
        # count the ceiling is measured against, so counting them again would
        # refuse a batch that adds nobody. With no ceiling set — the standalone
        # default — none of this runs and the guard costs no query.
        #
        # No row lock here, unlike the thing ceiling: this endpoint sends
        # invitations, it does not add members. The count it reads only moves
        # when someone accepts, which is deliberately never refused, so two
        # concurrent batches have nothing to race over.
        if collection.capacity_ceiling("invites"):
            emails = [email for email, _ in candidates]
            already = set(
                collection.invites.filter(email__in=emails).values_list("email", flat=True)
            )
            already.add(collection.owner.email.lower())
            full = collection.capacity_violation(
                "invites", adding=sum(1 for email in emails if email not in already)
            )
            if full:
                return Response(refusal_body(full), status=status.HTTP_400_BAD_REQUEST)

        inviter_name = request.user.name  # bare name — invitees are third parties
        invited = []
        recipients = []  # (email, accept_link, reject_link)
        with transaction.atomic():
            for email, name in candidates:
                # Past today's cap: report the rest of the batch per row (the
                # frontend shows the reason) rather than silently dropping it.
                # Before get_or_create, so a quota-skipped row creates no User.
                if quota_left is not None and len(invited) >= quota_left:
                    skipped.append({"email": email, "reason": "daily_limit"})
                    continue
                # Both answers come before get_or_create, so a row skipped here
                # creates no User. Somebody inside is a member whatever their
                # record says; an address already invited is not mailed again.
                inside = User.objects.filter(email=email).first()
                if inside is not None and (
                    collection.is_owner(inside.code) or collection.is_invited(inside.code)
                ):
                    skipped.append({"email": email, "reason": "already_member"})
                    continue
                if invitation_blocked(collection, email, request.user.code):
                    skipped.append({"email": email, "reason": "already_asked"})
                    continue
                defaults = {"email": email}
                if name:
                    defaults["name"] = name
                invited_user, created = User.objects.get_or_create(email=email, defaults=defaults)
                if created:
                    Event.log(Event.Kind.USER_JOINED, actor=invited_user)

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
                record_invitation(collection, email, request.user.code)
                invited.append(email)
                recipients.append((email, accept_rsvp.action_link(), reject_rsvp.action_link()))

        _consume_invite_quota(request.user.code, len(invited))
        _send_bulk_invites(inviter_name, collection.headline, recipients, collection=collection)

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

    Owner-or-co-owner usage statistics for any collection, returned as a CSV
    download (metric,value): a snapshot plus a 90-day window, and — since the
    optional member demographics exist — an aggregate age-range and postal-code
    breakdown. Aggregate only; the per-member values live on the guests page
    (and stay COMMUNITY-only there).
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)
        denied = require_collection_curator(
            collection, request.user.code, "Only the owner or a co-owner can view stats"
        )
        if denied:
            return denied

        # Every metric is defined once, in the service: this renders it as a CSV,
        # the collection export carries the same rows as a dict.
        rows = [["metric", "value"], *collection_stats_rows(collection, request.user)]
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
            request.user.invited_to_collections.filter(status=Collection.Status.ACTIVE),
            viewer=request.user,
        ).order_by("owner__name", "created")
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
        # Only surface invitations whose link is still valid (matches the per-action
        # expiry in RSVP.is_valid / cleanup_rsvps), so a stale invite never shows a
        # link that would 401 on click.
        cutoff = timezone.now() - timedelta(
            hours=RSVP.expiry_hours_for(RSVP.Action.COLLECTION_INVITE)
        )
        accept_rsvps = list(
            RSVP.objects.filter(
                user_code=request.user,
                action=RSVP.Action.COLLECTION_INVITE,
                created__gte=cutoff,
            )
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
                    # Bare name: the reader is an invitee, not a member yet.
                    "owner_name": collection.owner.name,
                }
            )

        return Response(result)


class CollectionShareLinkView(APIView):
    """
    POST /api/v1/collections/{collection_code}/share-link/
    Generate (or rotate) a public share token. Returns the full public URL.

    DELETE /api/v1/collections/{collection_code}/share-link/
    Revoke the share token. The link becomes invalid for everyone.

    Owner or co-owner. Token is a 22-char URL-safe bearer credential — anyone
    with the link can join the collection via /share/{token}, so the token
    must not appear in any read endpoint.

    In a NETWORK, generating the link the first time and reading the existing one
    stay any dinamizador's (inviting is theirs), but rotating or revoking it is the
    founder's alone: it would kill the links and QR codes everyone else handed out.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_curator(
            collection, request.user.code, "Only the owner or a co-owner can manage the share link"
        )
        if denied:
            return denied

        rotate = bool(body_dict(request).get("rotate"))

        if rotate and collection.share_token:
            denied = require_network_founder(
                collection,
                request.user.code,
                "Only the founder of a network can take back its share link",
            )
            if denied:
                return denied

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

        denied = require_collection_curator(
            collection, request.user.code, "Only the owner or a co-owner can manage the share link"
        )
        if denied:
            return denied

        denied = require_network_founder(
            collection,
            request.user.code,
            "Only the founder of a network can take back its share link",
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


class SharePreviewView(APIView):
    """
    GET /api/v1/share/{token}/preview/

    The name and description of the collection a ``/share/{token}`` link opens,
    so the join page can say "Join the Chalmercadillo" instead of "Join us on
    OIUEEI" — a stranger handed the link on WhatsApp has no idea what OIUEEI is.

    Public and unauthenticated: the 22-char token **is** the credential, and
    whoever holds it already knows a real collection sits behind it. It returns
    **only** ``headline``, ``description``, ``language``, ``kind`` and the palette — never
    the owner, the roster or a member count — and a generic **404** for an unknown,
    revoked or inactive token, so it reveals nothing the link itself does not.
    ``language``, ``kind`` and the palette (``theeeme_colors``, ``koro``: the join page
    is the door of that group and wears its colours) are no more sensitive than the other
    two: they are exactly what
    `CollectionSerializer` already serves any signed-in member.

    ``headline``/``description`` are returned raw: either may be a
    ``{lang: text}`` map the SPA resolves against the reader's language,
    exactly like every other collection read. ``language`` powers the SPA's
    `useCollectionLanguage` — this is the one join door (`/share/{token}`)
    reached before a stranger is a member of anything, so the collection's own
    language is the only signal available yet.
    """

    permission_classes = [AllowAny]
    authentication_classes = []

    @method_decorator(ratelimit(key="ip", rate="30/m", method="GET", block=True))
    def get(self, request, token):
        collection = (
            Collection.objects.filter(share_token=token, status=Collection.Status.ACTIVE)
            .select_related("theeeme")
            .first()
        )
        if collection is None:
            raise Http404
        return Response(
            {
                "headline": collection.headline,
                "description": collection.description,
                "language": collection.language,
                "kind": collection.kind,
                "theeeme_colors": theeeme_colors(collection.theeeme),
                "koro": collection.koro,
            }
        )


class ShareJoinView(APIView):
    """
    POST /api/v1/share/{token}/join/

    Lets a **signed-in** reader accept a ``/share/{token}`` invitation with a
    click. ``SharePage`` used to ask for an email even when there was a session —
    email, inbox, link, back — and in a neighbourhood the same people belong to
    several groups, so this link (the main viral route) was a round trip for
    exactly the people who use it most. It is the token's twin of
    ``CollectionJoinView``, which joins a PUBLIC collection by its code: there
    the credential is the collection's own publicness, here it is the token.

    **The token is the whole credential, and it is looked up exactly like
    ``SharePreviewView`` does**: ``share_token=token``, ACTIVE only. An unknown,
    revoked or INACTIVE token is one generic ``404`` (``Http404``), so this reveals
    nothing the preview does not — that endpoint already answers a bad token with
    the same 404, to anyone, unauthenticated, so an account holder gets no new
    oracle from asking here (and 30 an hour per user, on top). It never returns
    or touches the token, creates no user and no RSVP (there is a session), and
    answers with the collection's code, which the joined member is about to read
    on every page anyway.

    Idempotent: the owner and any member — co-curators are in ``invites`` — get a
    ``200`` with ``joined: false`` and nothing else happens, so a curator trying
    their own link lands on their collection instead of an error, and a double
    tap logs one ``MEMBER_JOINED``. A new member goes through ``_join_collection``
    like every other door (one event with ``source=SHARE``, the welcome document
    if the owner set one), after the operator's per-collection daily ceiling has
    been asked — the same cap and the same ``detail`` as ``CollectionJoinView``:
    a ceiling that only stopped strangers would be one anyone with an account
    could walk around.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="30/h", method="POST", block=True))
    def post(self, request, token):
        collection = Collection.objects.filter(
            share_token=token, status=Collection.Status.ACTIVE
        ).first()
        if collection is None:
            raise Http404

        user_code = request.user.code
        if collection.is_owner(user_code) or collection.invites.filter(code=user_code).exists():
            return Response(
                {"collection": collection.code, "collection_kind": collection.kind, "joined": False}
            )

        ip = get_client_ip(request)
        if join_quota_exhausted(collection.code):
            _log_join_refused(request.user, collection, ip)
            return Response(
                refusal_body(
                    "This collection has taken today's joins. Try again tomorrow.",
                    code="joins_spent",
                    key="detail",
                ),
                status=status.HTTP_429_TOO_MANY_REQUESTS,
            )

        _join_collection(collection, request.user, source=Event.Source.SHARE)
        consume_join_quota(collection.code)
        _log_joined(request.user, collection, "share", ip)

        return Response(
            {"collection": collection.code, "collection_kind": collection.kind, "joined": True}
        )


class CollectionEmailNoteTestView(APIView):
    """
    POST /api/v1/collections/{collection_code}/email-note/test/
    Email the acting curator their ``email_note`` draft, rendered exactly as it
    will reach a member (``send_email_note_test_email``). Curators only; the
    draft needn't be saved. It goes to the requester's own address and nobody
    else's, so the only thing to limit is how often.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="10/h", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)
        denied = require_collection_curator(
            collection, request.user.code, "Only the owner or a co-owner can test the email note"
        )
        if denied:
            return denied
        serializer = EmailNoteTestSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        send_email_note_test_email(
            request.user, collection, serializer.validated_data["email_note"]
        )
        return Response({"status": "sent"}, status=status.HTTP_200_OK)


class CollectionBroadcastView(APIView):
    """
    POST /api/v1/collections/{collection_code}/broadcast/
    Send a broadcast email from the collection owner or a co-owner to all
    invitees.
    """

    permission_classes = [IsAuthenticated]

    @method_decorator(ratelimit(key="user", rate="5/d", method="POST", block=True))
    def post(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)

        denied = require_collection_curator(
            collection, request.user.code, "Only the owner or a co-owner can send broadcasts"
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
                refusal_body("No invitees to broadcast to", code="no_invitees_to_broadcast"),
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Bare name. The broadcast discloses the owner's address anyway, by
        # design — it carries a Reply-To so a group message can be answered, and
        # the compose box says so before it is sent. That is a disclosure the
        # owner makes knowingly; rendering it as their *name* in the body and in
        # every member's inbox is not the same thing, and is not what it means.
        owner_name = request.user.name
        # In a network a dinamizador speaks for their entity: the message is signed
        # with the name of their pickup point (its entity's, else their own).
        point = collection.point_for(request.user.code)
        if point is not None:
            owner_name = point.display_name

        _send_broadcast(
            owner_name=owner_name,
            owner_email=request.user.email,
            headline=collection.headline,
            collection_code=collection.code,
            message=message,
            emails=invitee_emails,
            collection=collection,
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


class CollectionPointView(APIView):
    """
    GET / PUT /api/v1/collections/{collection_code}/point/

    The page the curator asking has in this group, in any collection: the entity they
    answer for (name, logo, about, contact). In a **network** it is also their pickup
    point (address, hours, days, closures) and the conditions of their own loans. Each
    curator (the founder included) reads and edits **only their own**; the others' are
    in the collection's payload, public with it.

    Outside a network a PUT keeps only the identity fields and ignores the rest without
    error, and a GET serves the network's fields empty. No row yet is a 200 with the
    empty fields: setting one up is a first PUT. A member who is not a curator gets 403.
    """

    permission_classes = [IsAuthenticated]

    def _resolve(self, request, collection_code):
        collection = get_object_or_404(Collection, code=collection_code)
        denied = require_collection_curator(
            collection, request.user.code, "Only a curator can set up their page in a group"
        )
        return collection, denied

    def get(self, request, collection_code):
        collection, denied = self._resolve(request, collection_code)
        if denied:
            return denied
        point = collection.points.filter(user=request.user).first()
        if point is None:
            point = NetworkPoint(collection=collection, user=request.user)
        return Response(NetworkPointSerializer(point, context={"request": request}).data)

    @method_decorator(ratelimit(key="user", rate="30/h", method="PUT", block=True))
    def put(self, request, collection_code):
        collection, denied = self._resolve(request, collection_code)
        if denied:
            return denied
        point = collection.points.filter(user=request.user).first() or NetworkPoint(
            collection=collection, user=request.user
        )
        data = body_dict(request)
        if not collection.is_network():
            data = {key: value for key, value in data.items() if key in IDENTITY_FIELDS}
        serializer = NetworkPointWriteSerializer(point, data=data, partial=True)
        serializer.is_valid(raise_exception=True)
        try:
            with transaction.atomic():
                point = serializer.save()
        except IntegrityError:
            # Two first PUTs of the same curator raced: both saw no row and both
            # created one, and the second met `one_point_per_curator`. The row that
            # won is theirs, so the PUT applies to it instead.
            point = collection.points.filter(user=request.user).first()
            if point is None:
                raise
            serializer = NetworkPointWriteSerializer(point, data=data, partial=True)
            serializer.is_valid(raise_exception=True)
            point = serializer.save()
        return Response(NetworkPointSerializer(point, context={"request": request}).data)
