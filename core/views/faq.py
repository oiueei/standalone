"""
FAQ views for OIUEEI.
"""

from django.shortcuts import get_object_or_404
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import FAQ, Thing
from core.pagination import StandardResultsPagination
from core.serializers import FAQAnswerSerializer, FAQCreateSerializer, FAQSerializer
from core.services.email_service import (
    send_faq_answer_email,
    send_faq_hide_email,
    send_faq_question_email,
)


class ThingFAQListView(APIView):
    """
    GET /api/v1/things/{thing_code}/faq/
    List FAQs for a thing.

    POST /api/v1/things/{thing_code}/faq/
    Ask a question about a thing.
    """

    permission_classes = [IsAuthenticated]

    def get_thing(self, thing_code):
        return get_object_or_404(Thing, code=thing_code)

    def get(self, request, thing_code):
        thing = self.get_thing(thing_code)

        # Check if user can view the thing
        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorized to view this thing's FAQs"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Get visible FAQs (or all if owner)
        if thing.is_owner(request.user.code):
            faqs = FAQ.objects.filter(thing=thing).order_by("-created")
        else:
            faqs = FAQ.objects.filter(thing=thing, is_visible=True).order_by("-created")

        paginator = StandardResultsPagination()
        page = paginator.paginate_queryset(faqs, request)
        if page is not None:
            serializer = FAQSerializer(page, many=True)
            return paginator.get_paginated_response(serializer.data)

        serializer = FAQSerializer(faqs, many=True)
        return Response(serializer.data)

    def post(self, request, thing_code):
        thing = self.get_thing(thing_code)

        # Owner cannot ask questions about their own thing
        if thing.is_owner(request.user.code):
            return Response(
                {"error": "Owner cannot ask questions about their own thing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if user can view the thing (must be invited to ask questions)
        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorized to ask questions about this thing"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = FAQCreateSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        faq = FAQ.objects.create(
            thing=thing,
            questioner=request.user,
            question=serializer.validated_data["question"],
        )

        # Notify owner by email
        try:
            owner = thing.owner
            questioner_name = request.user.name or request.user.email
            send_faq_question_email(questioner_name, thing.headline, faq.question, owner.email)
        except Exception:
            pass  # Owner not found, skip email

        return Response(
            FAQSerializer(faq).data,
            status=status.HTTP_201_CREATED,
        )


class FAQDetailView(APIView):
    """
    GET /api/v1/faq/{faq_code}/
    View a FAQ.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request, faq_code):
        faq = get_object_or_404(FAQ, code=faq_code)

        # Get the thing to check access
        thing = faq.thing

        # Check if user can view the thing
        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorized to view this FAQ"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Check visibility for non-owners
        if not faq.is_visible:
            # Only owner of thing or questioner can see hidden FAQs
            if not thing.is_owner(request.user.code) and faq.questioner_id != request.user.code:
                return Response(
                    {"error": "FAQ not found"},
                    status=status.HTTP_404_NOT_FOUND,
                )

        serializer = FAQSerializer(faq)
        return Response(serializer.data)


class FAQAnswerView(APIView):
    """
    POST /api/v1/faq/{faq_code}/answer/
    Answer a FAQ (thing owner only).
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, faq_code):
        faq = get_object_or_404(FAQ, code=faq_code)

        # Check if user is thing owner
        thing = faq.thing

        if not thing.is_owner(request.user.code):
            return Response(
                {"error": "Only the thing owner can answer questions"},
                status=status.HTTP_403_FORBIDDEN,
            )

        serializer = FAQAnswerSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        faq.set_answer(serializer.validated_data["answer"])

        # Notify questioner by email
        try:
            questioner = faq.questioner
            owner_name = request.user.name or request.user.email
            send_faq_answer_email(
                owner_name, thing.headline, faq.question, faq.answer, questioner.email
            )
        except Exception:
            pass  # Questioner not found, skip email

        return Response(FAQSerializer(faq).data)


class FAQVisibilityView(APIView):
    """
    POST /api/v1/faq/{faq_code}/hide/
    Hide a FAQ (thing owner only).

    POST /api/v1/faq/{faq_code}/show/
    Show a FAQ (thing owner only).
    """

    permission_classes = [IsAuthenticated]

    def _get_faq_and_thing(self, faq_code):
        faq = get_object_or_404(FAQ, code=faq_code)
        return faq, faq.thing

    def post(self, request, faq_code, action):
        faq, thing = self._get_faq_and_thing(faq_code)

        if not thing.is_owner(request.user.code):
            return Response(
                {"error": "Only the thing owner can change FAQ visibility"},
                status=status.HTTP_403_FORBIDDEN,
            )

        if action == "hide":
            faq.is_visible = False
            faq.save(update_fields=["is_visible"])

            # Notify questioner by email
            try:
                questioner = faq.questioner
                owner_name = request.user.name or request.user.email
                send_faq_hide_email(owner_name, thing.headline, faq.question, questioner.email)
            except Exception:
                pass  # Questioner not found, skip email

            return Response({"message": "FAQ hidden", "faq": FAQSerializer(faq).data})
        elif action == "show":
            faq.is_visible = True
            faq.save(update_fields=["is_visible"])
            return Response({"message": "FAQ shown", "faq": FAQSerializer(faq).data})
        else:
            return Response(
                {"error": "Invalid action"},
                status=status.HTTP_400_BAD_REQUEST,
            )
