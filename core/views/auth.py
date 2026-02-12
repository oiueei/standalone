"""
Authentication views for OIUEEI.

Handles magic link authentication and RSVP-based actions.
RSVP serves as an intermediary for ALL email communications to avoid
exposing real codes (booking_code, thing_code, etc.) in URLs.
"""

import logging

from django.conf import settings
from django.contrib.auth import login
from django.utils.decorators import method_decorator
from django_ratelimit.decorators import ratelimit
from rest_framework import status
from rest_framework.permissions import AllowAny, IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.tokens import RefreshToken

from core.models import RSVP, Collection, User
from core.models.booking import BookingPeriod
from core.serializers import RequestLinkSerializer, UserSerializer
from core.services.booking_service import accept_booking, reject_booking
from core.services.email_service import (
    send_booking_decision_email,
    send_invite_rejected_email,
    send_magic_link_email,
)
from core.utils import get_client_ip

security_logger = logging.getLogger("security")


class RequestLinkView(APIView):
    """
    POST /api/v1/auth/request-link/
    Request a magic link for authentication.
    """

    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="5/m", method="POST", block=True))
    def post(self, request):
        serializer = RequestLinkSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)

        email = serializer.validated_data["email"].lower()
        ip = get_client_ip(request)

        # INVITE-ONLY: Only existing users can request magic links
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            security_logger.warning(
                f"Magic link request denied for non-existent user: {email} from IP {ip}"
            )
            return Response(
                {"error": "No account found. Please ask someone to invite you."},
                status=status.HTTP_404_NOT_FOUND,
            )

        security_logger.info(f"Magic link requested for {email} from IP {ip}")

        # Create RSVP
        rsvp = RSVP.objects.create(
            user_code=user,
            user_email=email,
        )

        # Send magic link email
        magic_link_base = getattr(
            settings, "MAGIC_LINK_BASE_URL", "http://localhost:3000/magic-link"
        )
        magic_link = f"{magic_link_base}/{rsvp.code}"

        send_magic_link_email(email, magic_link)

        return Response(
            {"message": "Magic link sent", "email": email},
            status=status.HTTP_200_OK,
        )


class VerifyLinkView(APIView):
    """
    GET /api/v1/auth/verify/{rsvp_code}/
    Process an RSVP action.

    Handles all RSVP-based actions:
    - MAGIC_LINK: Verify magic link and return JWT token
    - COLLECTION_INVITE: Accept collection invitation and return JWT token
    - BOOKING_ACCEPT: Accept a booking (all thing types)
    - BOOKING_REJECT: Reject a booking (all thing types)
    """

    permission_classes = [AllowAny]

    @method_decorator(ratelimit(key="ip", rate="10/m", method="GET", block=True))
    def get(self, request, rsvp_code):
        ip = get_client_ip(request)

        try:
            rsvp = RSVP.objects.get(code=rsvp_code)
        except RSVP.DoesNotExist:
            security_logger.warning(f"Invalid RSVP code attempted from IP {ip}")
            return Response(
                {"error": "Invalid or expired link"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        if not rsvp.is_valid():
            security_logger.warning(f"Expired RSVP code used from IP {ip}")
            rsvp.delete()
            return Response(
                {"error": "Link expired"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Route to appropriate handler based on action type
        action_handlers = {
            "MAGIC_LINK": self._handle_magic_link,
            "COLLECTION_INVITE": self._handle_collection_invite,
            "COLLECTION_REJECT": self._handle_collection_reject,
            "BOOKING_ACCEPT": self._handle_booking_accept,
            "BOOKING_REJECT": self._handle_booking_reject,
        }

        handler = action_handlers.get(rsvp.action, self._handle_magic_link)
        return handler(request, rsvp)

    def _handle_magic_link(self, request, rsvp):
        """Handle magic link authentication."""
        ip = get_client_ip(request)

        # Get user (rsvp.user_code is now a FK)
        user = rsvp.user_code
        if not user:
            rsvp.delete()
            return Response(
                {"error": "User not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Update last activity
        user.update_last_activity()

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        # Also login via session for browser access
        login(request, user)

        # Delete RSVP (one-time use)
        rsvp.delete()

        security_logger.info(f"User {user.email} logged in via magic link from IP {ip}")

        # Return token and user data
        user_data = UserSerializer(user).data

        return Response(
            {
                "action": "MAGIC_LINK",
                "token": str(refresh.access_token),
                "refresh": str(refresh),
                "user": user_data,
            },
            status=status.HTTP_200_OK,
        )

    def _handle_collection_invite(self, request, rsvp):
        """Handle collection invitation acceptance."""
        # Get user (rsvp.user_code is now a FK)
        user = rsvp.user_code
        if not user:
            rsvp.delete()
            return Response(
                {"error": "User not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Update last activity
        user.update_last_activity()

        # Process collection invitation
        invited_collection = None
        if rsvp.target_code:
            try:
                collection = Collection.objects.get(code=rsvp.target_code)
                # Add user to collection invites (M2M)
                collection.invites.add(user)
                invited_collection = rsvp.target_code
            except Collection.DoesNotExist:
                pass  # Collection was deleted, ignore

        # Generate JWT tokens
        refresh = RefreshToken.for_user(user)

        # Also login via session for browser access
        login(request, user)

        # Delete this RSVP and the sibling reject RSVP (invalidate both links)
        RSVP.objects.filter(
            user_code=user,
            action="COLLECTION_REJECT",
            target_code=rsvp.target_code,
        ).delete()
        rsvp.delete()

        # Return token and user data
        user_data = UserSerializer(user).data

        response_data = {
            "action": "COLLECTION_INVITE",
            "token": str(refresh.access_token),
            "refresh": str(refresh),
            "user": user_data,
        }

        if invited_collection:
            response_data["invited_collection"] = invited_collection

        return Response(response_data, status=status.HTTP_200_OK)

    def _handle_collection_reject(self, request, rsvp):
        """Handle collection invitation rejection."""
        user = rsvp.user_code
        if not user:
            rsvp.delete()
            return Response(
                {"error": "User not found"},
                status=status.HTTP_401_UNAUTHORIZED,
            )

        # Send rejection notification to collection owner
        if rsvp.target_code:
            try:
                collection = Collection.objects.get(code=rsvp.target_code)
                invitee_name = user.name or user.email
                send_invite_rejected_email(
                    invitee_name,
                    collection.headline,
                    collection.owner.email,
                )
            except Collection.DoesNotExist:
                pass  # Collection was deleted, ignore

        # Delete both accept and reject RSVPs to invalidate all links
        RSVP.objects.filter(
            user_code=user,
            action="COLLECTION_INVITE",
            target_code=rsvp.target_code,
        ).delete()
        rsvp.delete()

        return Response(
            {
                "action": "COLLECTION_REJECT",
                "message": "Invitation declined",
            },
            status=status.HTTP_200_OK,
        )

    def _handle_booking_accept(self, request, rsvp):
        """Handle booking accept action for all thing types."""
        booking_code = rsvp.target_code

        try:
            booking = BookingPeriod.objects.get(code=booking_code)
        except BookingPeriod.DoesNotExist:
            rsvp.delete()
            return Response(
                {"error": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not booking.is_valid():
            rsvp.delete()
            return Response(
                {"error": "Booking expired or already processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get thing (FK access)
        thing = booking.thing_code
        if not thing:
            rsvp.delete()
            return Response(
                {"error": "Thing not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Accept the booking and update thing status
        thing = accept_booking(booking)

        # Send confirmation email to requester
        send_booking_decision_email(booking, thing, accepted=True)

        # Delete RSVP (one-time use)
        rsvp.delete()

        # Build response
        response_data = {
            "action": "BOOKING_ACCEPT",
            "message": "Booking accepted",
            "thing_headline": thing.headline,
        }
        if booking.start_date:
            response_data["start_date"] = str(booking.start_date)
        if booking.end_date:
            response_data["end_date"] = str(booking.end_date)
        if booking.delivery_date:
            response_data["delivery_date"] = str(booking.delivery_date)
        if booking.quantity:
            response_data["quantity"] = booking.quantity

        return Response(response_data, status=status.HTTP_200_OK)

    def _handle_booking_reject(self, request, rsvp):
        """Handle booking reject action for all thing types."""
        booking_code = rsvp.target_code

        try:
            booking = BookingPeriod.objects.get(code=booking_code)
        except BookingPeriod.DoesNotExist:
            rsvp.delete()
            return Response(
                {"error": "Booking not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        if not booking.is_valid():
            rsvp.delete()
            return Response(
                {"error": "Booking expired or already processed"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Get thing (FK access)
        thing = booking.thing_code
        if not thing:
            rsvp.delete()
            return Response(
                {"error": "Thing not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Reject the booking and update thing status
        thing = reject_booking(booking)

        # Send rejection email to requester
        send_booking_decision_email(booking, thing, accepted=False)

        # Delete RSVP (one-time use)
        rsvp.delete()

        return Response(
            {
                "action": "BOOKING_REJECT",
                "message": "Booking rejected",
                "thing_headline": thing.headline,
            },
            status=status.HTTP_200_OK,
        )


class MeView(APIView):
    """
    GET /api/v1/auth/me/
    Get current authenticated user.
    """

    permission_classes = [IsAuthenticated]

    def get(self, request):
        user = request.user
        user.update_last_activity()
        serializer = UserSerializer(user)
        return Response(serializer.data)


class LogoutView(APIView):
    """
    POST /api/v1/auth/logout/
    Logout the current user.

    Optionally accepts a refresh token to blacklist it.
    """

    permission_classes = [IsAuthenticated]

    def post(self, request):
        from django.contrib.auth import logout

        # Try to blacklist the refresh token if provided
        refresh_token = request.data.get("refresh")
        if refresh_token:
            try:
                token = RefreshToken(refresh_token)
                token.blacklist()
            except Exception:
                # Blacklist might not be enabled or token invalid
                pass

        # Logout from Django session
        logout(request)

        return Response(
            {"message": "Successfully logged out"},
            status=status.HTTP_200_OK,
        )
