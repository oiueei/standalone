"""
Reservation views for OIUEEI.

All reservations now use the unified BookingPeriod model.
Email links use RSVP codes as intermediaries to avoid exposing
real codes (booking_code, thing_code) in URLs.
"""

from django.conf import settings
from django.core.mail import send_mail
from rest_framework import status
from rest_framework.permissions import IsAuthenticated
from rest_framework.response import Response
from rest_framework.views import APIView

from core.models import RSVP, Thing, User
from core.models.booking import DATE_BASED_TYPES, REPEATABLE_TYPES, BookingPeriod
from core.serializers.booking import ThingOrderSerializer, ThingRequestWithDatesSerializer


class ThingRequestView(APIView):
    """
    POST /api/v1/things/{thing_code}/request/
    Request a reservation/booking for a thing.

    All thing types now use BookingPeriod:
    - LEND/RENT/SHARE: requires start_date and end_date
    - ORDER: requires delivery_date and quantity
    - GIFT/SELL: no extra fields required
    """

    permission_classes = [IsAuthenticated]

    def post(self, request, thing_code):
        try:
            thing = Thing.objects.get(code=thing_code)
        except Thing.DoesNotExist:
            return Response(
                {"error": "Thing not found"},
                status=status.HTTP_404_NOT_FOUND,
            )

        # Check if user can view this thing (is invited to collection)
        if not thing.can_view(request.user.code):
            return Response(
                {"error": "Not authorized to request this thing"},
                status=status.HTTP_403_FORBIDDEN,
            )

        # Owner cannot request their own thing
        if thing.is_owner(request.user.code):
            return Response(
                {"error": "Cannot request your own thing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Check if thing is available
        if thing.status != "ACTIVE":
            return Response(
                {"error": "Thing is not available for reservation"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Route based on thing type
        if thing.type in DATE_BASED_TYPES:
            return self._handle_date_based_request(request, thing)
        elif thing.type in REPEATABLE_TYPES:
            return self._handle_order_request(request, thing)
        else:
            return self._handle_standard_request(request, thing)

    def _handle_date_based_request(self, request, thing):
        """Handle LEND/RENT/SHARE requests with date-based booking."""
        # Validate dates
        serializer = ThingRequestWithDatesSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        start_date = serializer.validated_data["start_date"]
        end_date = serializer.validated_data["end_date"]

        # Check for overlap with existing bookings
        if BookingPeriod.has_overlap(thing.code, start_date, end_date):
            return Response(
                {"error": "Selected dates overlap with existing booking"},
                status=status.HTTP_409_CONFLICT,
            )

        # Create booking period (status=PENDING, blocks dates for 72h)
        booking = BookingPeriod.objects.create(
            thing_code=thing.code,
            thing_type=thing.type,
            requester_code=request.user.code,
            requester_email=request.user.email,
            owner_code=thing.owner,
            start_date=start_date,
            end_date=end_date,
        )

        # Get owner info and send email
        owner_email = self._get_owner_email(thing.owner)
        if not owner_email:
            return Response(
                {"error": "Thing owner not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        self._send_booking_email(request.user, thing, booking, owner_email, with_dates=True)

        # NOTE: Do NOT change thing status - it stays ACTIVE for date-based types
        # Multiple bookings can exist for different date ranges

        return Response(
            {
                "message": "Booking request sent",
                "booking_code": booking.code,
                "start_date": str(start_date),
                "end_date": str(end_date),
            },
            status=status.HTTP_200_OK,
        )

    def _handle_order_request(self, request, thing):
        """Handle ORDER_THING requests (delivery_date + quantity)."""
        # Validate order data
        serializer = ThingOrderSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)

        delivery_date = serializer.validated_data["delivery_date"]
        quantity = serializer.validated_data["quantity"]

        # Create booking with order info
        booking = BookingPeriod.objects.create(
            thing_code=thing.code,
            thing_type=thing.type,
            requester_code=request.user.code,
            requester_email=request.user.email,
            owner_code=thing.owner,
            delivery_date=delivery_date,
            quantity=quantity,
        )

        # Get owner info and send email
        owner_email = self._get_owner_email(thing.owner)
        if not owner_email:
            return Response(
                {"error": "Thing owner not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        self._send_booking_email(request.user, thing, booking, owner_email, order_info=True)

        # NOTE: Thing stays ACTIVE - multiple orders allowed
        return Response(
            {
                "message": "Order request sent",
                "booking_code": booking.code,
                "delivery_date": str(delivery_date),
                "quantity": quantity,
            },
            status=status.HTTP_200_OK,
        )

    def _handle_standard_request(self, request, thing):
        """Handle GIFT/SELL requests (no dates)."""
        # Check if user already has a pending request
        existing = BookingPeriod.objects.filter(
            thing_code=thing.code,
            requester_code=request.user.code,
            status="PENDING",
        ).first()
        if existing:
            return Response(
                {"error": "You already have a pending request for this thing"},
                status=status.HTTP_400_BAD_REQUEST,
            )

        # Create booking (no dates for standard requests)
        booking = BookingPeriod.objects.create(
            thing_code=thing.code,
            thing_type=thing.type,
            requester_code=request.user.code,
            requester_email=request.user.email,
            owner_code=thing.owner,
        )

        # Update thing status to TAKEN (blocks other requests)
        thing.status = "TAKEN"
        thing.save(update_fields=["status"])

        # Get owner info and send email
        owner_email = self._get_owner_email(thing.owner)
        if not owner_email:
            return Response(
                {"error": "Thing owner not found"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR,
            )

        self._send_booking_email(request.user, thing, booking, owner_email)

        return Response(
            {
                "message": "Booking request sent",
                "booking_code": booking.code,
            },
            status=status.HTTP_200_OK,
        )

    def _get_owner_email(self, owner_code):
        """Get owner's email address."""
        try:
            owner = User.objects.get(code=owner_code)
            return owner.email
        except User.DoesNotExist:
            return None

    def _send_booking_email(
        self, requester, thing, booking, owner_email, with_dates=False, order_info=False
    ):
        """Send booking request email to owner with RSVP-protected links."""
        # Create RSVP tokens for accept/reject links
        rsvp_accept = RSVP.create_for_booking("BOOKING_ACCEPT", booking, owner_email)
        rsvp_reject = RSVP.create_for_booking("BOOKING_REJECT", booking, owner_email)

        # Build links
        base_url = getattr(settings, "RSVP_BASE_URL", "http://localhost:3000/rsvp")
        accept_link = f"{base_url}/{rsvp_accept.code}"
        reject_link = f"{base_url}/{rsvp_reject.code}"

        requester_name = requester.name or requester.email

        # Build email content based on booking type
        if with_dates:
            message = (
                f"{requester_name} ha solicitado reservar '{thing.headline}' "
                f"del {booking.start_date} al {booking.end_date}. "
                f"Aceptar: {accept_link} | Rechazar: {reject_link}"
            )
            html_extra = f"<p>Fechas: {booking.start_date} - {booking.end_date}</p>"
            subject = f"{requester_name} quiere reservar: {thing.headline}"
        elif order_info:
            message = (
                f"{requester_name} ha solicitado {booking.quantity}x '{thing.headline}' "
                f"para el {booking.delivery_date}. "
                f"Aceptar: {accept_link} | Rechazar: {reject_link}"
            )
            html_extra = (
                f"<p>Cantidad: {booking.quantity}</p>"
                f"<p>Fecha de entrega: {booking.delivery_date}</p>"
            )
            subject = f"{requester_name} quiere pedir: {thing.headline}"
        else:
            message = (
                f"{requester_name} ha solicitado reservar '{thing.headline}'. "
                f"Aceptar: {accept_link} | Rechazar: {reject_link}"
            )
            html_extra = ""
            subject = f"{requester_name} quiere reservar: {thing.headline}"

        send_mail(
            subject=subject,
            message=message,
            from_email=None,
            recipient_list=[owner_email],
            html_message=f"""
            <html>
            <p><strong>{requester_name}</strong> ha solicitado:</p>
            <p><strong>{thing.headline}</strong></p>
            {html_extra}
            <p>
                <a href="{accept_link}">Aceptar</a> |
                <a href="{reject_link}">Rechazar</a>
            </p>
            </html>
            """,
        )
