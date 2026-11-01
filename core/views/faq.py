"""
FAQ views for OIUEEI.
"""

from django.db.models import Prefetch
from django.shortcuts import get_object_or_404
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import FAQ, Thing
from core.models.event import Event
from core.models.notification import InAppNotification
from core.pagination import StandardResultsPagination
from core.serializers import FAQAnswerSerializer, FAQCreateSerializer, FAQSerializer
from core.services.email_service import (
    send_faq_answer_email,
    send_faq_answered_to_team_email,
    send_faq_hidden_to_team_email,
    send_faq_hide_email,
    send_faq_question_email,
)
from core.services.team import managers_ready_collections
from core.views._helpers import deny_if_cannot_view, refusal_body, viewer_code


def _clear_faq_question_notifications(faq):
    """Drop every pending question notice for this FAQ, whoever holds it.

    A FAQ_QUESTION notification asks its reader to answer; one answer — or
    hiding the question — settles it for the whole team, so every copy goes,
    not just whoever acted (the ``_clear_request_notifications`` pattern from
    booking_service). Matched by ``payload__faq_code``: notifications created
    before that key existed carry only thing_headline/questioner_name, never
    match, and stay until dismissed by hand.
    """
    InAppNotification.objects.filter(
        type=InAppNotification.Type.FAQ_QUESTION,
        payload__faq_code=faq.code,
    ).delete()


class ThingFAQListView(APIView):
    """
    GET /api/v1/things/{thing_code}/faq/
    List FAQs for a thing.

    POST /api/v1/things/{thing_code}/faq/
    Ask a question about a thing.
    """

    def get_permissions(self):
        # Listing questions (GET) is part of the public "social layer" — anyone
        # who can view the thing may read them. Asking a question (POST) needs auth.
        if self.request.method == "POST":
            return [IsAuthenticated()]
        return [AllowAny()]

    def get_thing(self, thing_code):
        # Collections prefetched manager-ready (each with its owner selected
        # and its co-curators) so the manager set never costs a query per
        # collection: both `can_manage` (GET and POST) and the question
        # notice's `managers()` fan-out walk exactly that path.
        return get_object_or_404(
            Thing.objects.prefetch_related(
                Prefetch("collections", queryset=managers_ready_collections())
            ),
            code=thing_code,
        )

    def get(self, request, thing_code):
        thing = self.get_thing(thing_code)
        viewer = viewer_code(request)

        denied = deny_if_cannot_view(thing, viewer, "Not authorized to view this thing's FAQs")
        if denied:
            return denied

        # Get visible FAQs (or all for a manager — the owner, or a PROPRIETARY
        # collection's curator, who runs its FAQs)
        if thing.can_manage(viewer):
            faqs = FAQ.objects.filter(thing=thing).select_related("questioner").order_by("-created")
        else:
            faqs = (
                FAQ.objects.filter(thing=thing, is_visible=True)
                .select_related("questioner")
                .order_by("-created")
            )

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(faqs, request)
        if page is not None:
            serializer = FAQSerializer(page, many=True, context={"request": request})
            return paginator.get_paginated_response(serializer.data)

        serializer = FAQSerializer(faqs, many=True, context={"request": request})
        return Response(serializer.data)

    @method_decorator(ratelimit(key="user", rate="20/h", method="POST", block=True))
    def post(self, request, thing_code):
        thing = self.get_thing(thing_code)

        # A manager cannot ask questions about a thing they run — the owner, or
        # a curator of a PROPRIETARY collection it sits in (they answer, they
        # don't ask).
        if thing.can_manage(request.user.code):
            return Response(
                refusal_body(
                    "You manage this thing — you answer its questions, you don't ask them",
                    code="manager_cannot_ask",
                ),
                status=status.HTTP_400_BAD_REQUEST,
            )

        denied = deny_if_cannot_view(
            thing, request.user.code, "Not authorized to ask questions about this thing"
        )
        if denied:
            return denied

        serializer = FAQCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        faq = FAQ.objects.create(
            thing=thing,
            questioner=request.user,
            question=serializer.validated_data["question"],
        )
        Event.log(Event.Kind.FAQ_ASKED, actor=request.user, thing=thing)

        # Notify every manager — the thing owner, and the curators of a
        # PROPRIETARY collection it sits in, who answer questions shoulder to
        # shoulder with the founder. In COMMUNITY that set is just the owner (a
        # member owns what they contribute). Bare name only: nothing in the FAQ
        # API ever hands a co-member the asker's address, and this must not be
        # the one thing that does.
        questioner_name = request.user.name
        # A thing sits in one collection; read from the prefetch, so no query.
        collection = next(iter(thing.collections_in_order()), None)
        for manager in thing.managers():
            if manager.code == request.user.code:
                continue
            if manager.email:
                send_faq_question_email(questioner_name, thing, faq.question, manager.email)
            InAppNotification.objects.create(
                user=manager,
                type=InAppNotification.Type.FAQ_QUESTION,
                payload={
                    "thing_headline": thing.headline,
                    "questioner_name": questioner_name,
                    # Lets `drop_team_notices_of` find this notice when its reader
                    # stops running the collection.
                    "collection_code": collection.code if collection else "",
                    # What settles this notice (an answer or a hide) matches on.
                    "faq_code": faq.code,
                },
            )

        return Response(
            FAQSerializer(faq, context={"request": request}).data,
            status=status.HTTP_201_CREATED,
        )


class FAQDetailView(APIView):
    """
    GET /api/v1/faq/{faq_code}/
    View a FAQ.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, faq_code):
        faq = get_object_or_404(FAQ.objects.select_related("questioner", "thing"), code=faq_code)

        # Get the thing to check access
        thing = faq.thing

        denied = deny_if_cannot_view(thing, request.user.code, "Not authorized to view this FAQ")
        if denied:
            return denied

        # Check visibility for non-owners
        if not faq.is_visible:
            # Only a manager of the thing or the questioner can see hidden FAQs
            if not thing.can_manage(request.user.code) and faq.questioner_id != request.user.code:
                return Response(
                    refusal_body("FAQ not found", code="faq_not_found"),
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer = FAQSerializer(faq, context={"request": request})
        return Response(serializer.data)


def _faq_with_team():
    """FAQs with their thing's collections manager-ready: answering or hiding one
    fans a notice out to every manager (``thing.managers()``), and `can_manage`
    walks the same path, so neither may cost a query per collection."""
    return FAQ.objects.select_related("questioner", "thing").prefetch_related(
        Prefetch("thing__collections", queryset=managers_ready_collections())
    )


class FAQAnswerView(APIView):
    """
    POST /api/v1/faq/{faq_code}/answer/
    Answer a FAQ (a manager of the thing — its owner, or a PROPRIETARY
    collection's curator).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, faq_code):
        faq = get_object_or_404(_faq_with_team(), code=faq_code)

        thing = faq.thing

        if not thing.can_manage(request.user.code):
            return Response(
                refusal_body(
                    "Only a manager of this thing can answer questions",
                    code="only_managers_answer",
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = FAQAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        faq.set_answer(serializer.validated_data["answer"])

        # Notify questioner by email and in-app
        questioner = faq.questioner
        answerer_name = request.user.name  # bare name
        if questioner and questioner.email:
            send_faq_answer_email(answerer_name, thing, faq.question, faq.answer, questioner.email)
            InAppNotification.objects.create(
                user=questioner,
                type=InAppNotification.Type.FAQ_ANSWERED,
                payload={"thing_headline": thing.headline, "owner_name": answerer_name},
            )

        # The question asked every manager, so its answer is team news: the
        # others learn who answered (they were holding the same open question),
        # and the pending FAQ_QUESTION leaves every inbox — not just the
        # answerer's view of it. Whoever answered and whoever asked are skipped:
        # one already knows, the other has just been told.
        _clear_faq_question_notifications(faq)
        for manager in thing.managers():
            if manager.code in (request.user.code, faq.questioner_id):
                continue
            if manager.email:
                send_faq_answered_to_team_email(
                    answerer_name, thing, faq.question, faq.answer, manager.email
                )

        return Response(FAQSerializer(faq, context={"request": request}).data)


class FAQVisibilityView(APIView):
    """
    POST /api/v1/faq/{faq_code}/hide/
    Hide a FAQ (a manager of the thing).

    POST /api/v1/faq/{faq_code}/show/
    Show a FAQ (a manager of the thing).
    """

    permission_classes = [IsAuthenticated]

    def _get_faq_and_thing(self, faq_code):
        faq = get_object_or_404(_faq_with_team(), code=faq_code)
        return faq, faq.thing

    def post(self, request, faq_code, action):
        faq, thing = self._get_faq_and_thing(faq_code)

        if not thing.can_manage(request.user.code):
            return Response(
                refusal_body(
                    "Only a manager of this thing can change FAQ visibility",
                    code="only_managers_change_visibility",
                ),
                status=status.HTTP_403_FORBIDDEN,
            )

        if action == "hide":
            # Hiding a question that is already hidden changes nothing, so it
            # tells nobody: a double click, or a teammate hiding it a moment
            # after another, must not mail the asker and the whole team again.
            if not faq.is_visible:
                return Response(
                    {
                        "message": "FAQ hidden",
                        "faq": FAQSerializer(faq, context={"request": request}).data,
                    }
                )
            faq.is_visible = False
            faq.save(update_fields=["is_visible"])

            # Notify questioner by email and in-app
            questioner = faq.questioner
            hider_name = request.user.name  # bare name
            if questioner and questioner.email:
                send_faq_hide_email(hider_name, thing, faq.question, questioner.email)
                InAppNotification.objects.create(
                    user=questioner,
                    type=InAppNotification.Type.FAQ_HIDDEN,
                    payload={"thing_headline": thing.headline, "owner_name": hider_name},
                )

            # The same settling an answer gives: the other managers learn a
            # teammate retired the question deliberately, and the pending
            # FAQ_QUESTION leaves every inbox — an unanswered one stopped
            # owing anybody a reply the moment it was hidden.
            _clear_faq_question_notifications(faq)
            for manager in thing.managers():
                if manager.code in (request.user.code, faq.questioner_id):
                    continue
                if manager.email:
                    send_faq_hidden_to_team_email(hider_name, thing, faq.question, manager.email)

            return Response(
                {
                    "message": "FAQ hidden",
                    "faq": FAQSerializer(faq, context={"request": request}).data,
                }
            )
        elif action == "show":
            # No notice to anyone: putting a question back is not something
            # the team needs to hear about.
            faq.is_visible = True
            faq.save(update_fields=["is_visible"])
            return Response(
                {
                    "message": "FAQ shown",
                    "faq": FAQSerializer(faq, context={"request": request}).data,
                }
            )
        else:
            return Response(
                refusal_body("Invalid action", code="invalid_faq_action"),
                status=status.HTTP_400_BAD_REQUEST,
            )
