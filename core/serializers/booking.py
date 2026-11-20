"""
Booking serializers for OIUEEI.
"""

import re
from datetime import date, timedelta

from django.utils import timezone
from rest_framework import serializers
from rest_framework.exceptions import ErrorDetail

from core.models.booking import BookingPeriod
from core.services.contact_seal import (
    CONTACT_PHONE_MIN_DIGITS,
    CONTACT_PHONE_PATTERN,
    unseal,
    unseal_phone,
)
from core.validators import SafeHeadlineField, SafeTextField

# Bookings/orders can't be placed more than ~3 months ahead — matches the
# frontend's today+90 cap and the availability horizon.
MAX_BOOKING_HORIZON_DAYS = 90

# The four details a library may ask a borrower for, in the order the form shows them. All
# four are required whenever the library asks.
LENDING_CONTACT_FIELDS = ("full_name", "address", "phone", "identity_document")
# An identity document is an ID card, a passport or another official paper: letters, digits,
# spaces, dots and hyphens, 4 to 32 of them.
IDENTITY_DOCUMENT_PATTERN = re.compile(r"^[A-Za-z0-9 .\-]{4,32}$")


def _check_phone(value):
    digits = sum(ch.isdigit() for ch in value)
    if not CONTACT_PHONE_PATTERN.match(value) or digits < CONTACT_PHONE_MIN_DIGITS:
        raise serializers.ValidationError(
            "Enter a phone number: digits, spaces and + ( ) . -, at least 6 digits."
        )
    return value


def _check_identity_document(value):
    if not IDENTITY_DOCUMENT_PATTERN.match(value):
        raise serializers.ValidationError(
            "Enter the number of your identity document: letters, digits, spaces, dots and "
            "hyphens, 4 to 32 characters."
        )
    return value


_LENDING_CONTACT_CHECKS = {
    "full_name": SafeHeadlineField(max_length=128).run_validation,
    "address": SafeTextField(max_length=256).run_validation,
    "phone": _check_phone,
    "identity_document": _check_identity_document,
}


def clean_lending_contact(raw):
    """The four contact details of a request to a library that asks for them, cleaned.

    All four are required: a missing or empty one is refused coded
    ``lending_contact_required``, one that does not pass its rule ``lending_contact_invalid``,
    each in its own field under ``lending_contact`` (``{"lending_contact": {"phone": [...]}}``);
    the exception handler lifts the code to the top of the body when every refusal shares one.
    Returns the details as a dict of trimmed text, ready to be sealed.
    """
    data = raw if isinstance(raw, dict) else {}
    cleaned, errors = {}, {}
    for name in LENDING_CONTACT_FIELDS:
        value = data.get(name)
        text = value.strip() if isinstance(value, str) else ""
        if not text:
            errors[name] = [ErrorDetail("This field is required.", code="lending_contact_required")]
            continue
        try:
            cleaned[name] = _LENDING_CONTACT_CHECKS[name](text)
        except serializers.ValidationError as exc:
            errors[name] = [ErrorDetail(str(exc.detail[0]), code="lending_contact_invalid")]
    if errors:
        raise serializers.ValidationError({"lending_contact": errors})
    return cleaned


def require_accepted_terms(raw):
    """A request to a library that asks borrowers to accept its terms must say it did:
    ``accepts_terms`` is exactly ``true``. Anything else (missing, ``false``, the string
    ``"true"``) is refused coded ``terms_required``, on the field."""
    if raw is not True:
        raise serializers.ValidationError(
            {
                "accepts_terms": [
                    ErrorDetail("Accept the lending terms to borrow.", code="terms_required")
                ]
            }
        )


class BookingPeriodSerializer(serializers.ModelSerializer):
    """Full booking period serializer (for owner view)."""

    thing_code = serializers.CharField(source="thing_code_id")
    thing_headline = serializers.CharField(source="thing_code.headline", read_only=True)
    requester_code = serializers.CharField(source="requester_code_id")
    requester_name = serializers.CharField(source="requester_code.name", read_only=True)
    owner_code = serializers.CharField(source="owner_code_id")
    # Whether accepting this request hands the thing over for good. `thing_type`
    # alone can't answer it: an endless GIFT is given away again and again and
    # transfers nothing, so a client deciding from the type would warn about a
    # transfer that isn't going to happen. The owner-requests page uses it to
    # decide whether accepting needs a confirmation first.
    thing_is_endless = serializers.BooleanField(source="thing_code.is_endless", read_only=True)
    # The group the request belongs to, for the /owner-bookings label: the page
    # now pools requests across every PROPRIETARY collection the viewer curates,
    # so a co-curator of two groups needs to see which one each row is about.
    collection_code = serializers.SerializerMethodField()
    collection_kind = serializers.SerializerMethodField()
    collection_headline = serializers.SerializerMethodField()
    # Whether the "remind them to return it" action is on offer for *this reader*
    # on this row: a manager of the thing, and the model's rule
    # (`BookingPeriod.can_be_return_reminded` — overdue, and not lent again
    # since). The once-a-day cap is not in it: `return_reminded_at` says when it
    # last went and the client greys the action out until tomorrow.
    can_remind_return = serializers.SerializerMethodField()
    # Whether this reader may say the loan came back (`BookingPeriod.can_be_marked_returned`
    # and the thing's manager): the same rule the endpoint judges again under its lock.
    can_mark_returned = serializers.SerializerMethodField()
    # The borrower's contact details a library asked for, opened — **only** for whoever manages
    # the thing (never the founder's rescue in a network), `None` for everyone else, without a
    # request, and when there are none. Never in MyBookingSerializer, the calendars, an email or
    # the group's export.
    lending_contact = serializers.SerializerMethodField()
    # Whether this reader may accept the request, or only reject it: the founder
    # of a network sees every entity's requests but decides none of them.
    can_decide = serializers.SerializerMethodField()
    # Served to whoever manages the reservation, like ``requester_email``, and only
    # until the reservation's last day has passed: the label on the request page
    # promises it is gone the day after, and the deletion runs later than that.
    contact_phone = serializers.SerializerMethodField()

    class Meta:
        model = BookingPeriod
        fields = [
            "code",
            "created",
            "thing_code",
            "thing_headline",
            "thing_type",
            "thing_is_endless",
            "collection_code",
            "collection_kind",
            "collection_headline",
            "requester_code",
            "requester_name",
            "requester_email",
            "owner_code",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "status",
            "quantity",
            "project_note",
            "contact_phone",
            "can_remind_return",
            "can_mark_returned",
            "can_decide",
            "return_reminded_at",
            "returned_at",
            "lending_contact",
        ]

    def get_contact_phone(self, obj):
        if not obj.contact_phone:
            return ""
        if obj.end_date is not None and obj.end_date <= timezone.localdate():
            return ""
        return unseal_phone(obj.contact_phone)

    def get_can_decide(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return obj.thing_code.can_manage(request.user.code)

    def get_can_remind_return(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return obj.thing_code.can_manage(request.user.code) and obj.can_be_return_reminded()

    def get_lending_contact(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated or not obj.lending_contact:
            return None
        if not obj.thing_code.can_manage(request.user.code):
            return None
        return unseal(obj.lending_contact)

    def get_can_mark_returned(self, obj):
        request = self.context.get("request")
        if request is None or not request.user.is_authenticated:
            return False
        return obj.thing_code.can_manage(request.user.code) and obj.can_be_marked_returned()

    def _collection(self, obj):
        # A thing lives in one collection; the list is read (the view prefetches
        # `thing_code__collections`, so it costs no extra query) and the first is
        # taken, which also covers a row from before that rule that sits in more.
        cols = obj.thing_code.collections_in_order()
        return cols[0] if cols else None

    def get_collection_code(self, obj):
        collection = self._collection(obj)
        return collection.code if collection else None

    def get_collection_kind(self, obj):
        collection = self._collection(obj)
        return collection.kind if collection else None

    def get_collection_headline(self, obj):
        collection = self._collection(obj)
        return collection.headline if collection else None


class BookingPeriodCalendarSerializer(serializers.ModelSerializer):
    """Calendar view serializer (limited info for guests)."""

    class Meta:
        model = BookingPeriod
        fields = [
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "status",
        ]


class BookingPeriodOwnerCalendarSerializer(serializers.ModelSerializer):
    """Calendar view serializer for owner (includes requester info)."""

    requester_code = serializers.CharField(source="requester_code_id")
    requester_name = serializers.SerializerMethodField()

    class Meta:
        model = BookingPeriod
        fields = [
            "code",
            "created",
            "requester_code",
            "requester_name",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "status",
            "quantity",
            "project_note",
        ]

    def get_requester_name(self, obj):
        return obj.requester_code.name or obj.requester_email


class ThingRequestWithDatesSerializer(serializers.Serializer):
    """Serializer for thing request with dates (LEND/RENT/SHARE)."""

    start_date = serializers.DateField()
    end_date = serializers.DateField()
    # How many of a thing's identical units. The range is the thing's (1 to
    # ``units``), judged by the service under its lock with a coded refusal.
    quantity = serializers.IntegerField(required=False, default=1)

    def validate_start_date(self, value):
        """Validate that start_date is today or in the future."""
        if value < date.today():
            raise serializers.ValidationError("Start date must be today or in the future")
        return value

    def validate(self, data):
        """Validate date range."""
        start_date = data.get("start_date")
        end_date = data.get("end_date")

        if start_date and end_date:
            if end_date < start_date:
                raise serializers.ValidationError(
                    {"end_date": "End date must be on or after start date"}
                )
            horizon = date.today() + timedelta(days=MAX_BOOKING_HORIZON_DAYS)
            if end_date > horizon:
                raise serializers.ValidationError(
                    {"end_date": "Dates can be at most 3 months ahead"}
                )
        return data


class ReservationRequestSerializer(serializers.Serializer):
    """RESERVE_THING request: a pickup date, plus either a length in days
    (DAY-unit collections) or a start/end time (HOUR-unit collections) — never
    both. Which shape applies is a property of the collection
    (``reservation_unit``), not of the request, so this serializer accepts
    either and ``request_reservation`` uses whichever one the collection is in.
    The real caps — day count, hour count, weekday/opening-hours rules — are
    checked in the service against the collection (``Collection.
    reservation_violation`` / ``reservation_hour_violation``). An optional
    project note rides along either way."""

    start_date = serializers.DateField()
    duration_days = serializers.IntegerField(min_value=1, max_value=7, required=False)
    start_time = serializers.TimeField(required=False)
    end_time = serializers.TimeField(required=False)
    project_note = SafeTextField(max_length=512, required=False, allow_blank=True)
    # Optional, always: whether the collection asks for it is the service's call, and
    # a number sent to a collection that does not ask is dropped there, not refused.
    contact_phone = serializers.CharField(required=False, allow_blank=True, trim_whitespace=True)

    def validate_contact_phone(self, value):
        value = value.strip()
        if not value:
            return ""
        return _check_phone(value)

    def validate_start_date(self, value):
        if value < date.today():
            raise serializers.ValidationError("Start date must be today or in the future")
        return value

    def validate(self, attrs):
        has_days = "duration_days" in attrs
        has_hours = "start_time" in attrs or "end_time" in attrs
        if has_days and has_hours:
            raise serializers.ValidationError(
                "Send either duration_days or start_time/end_time, not both."
            )
        if not has_days and not has_hours:
            raise serializers.ValidationError(
                "Send duration_days (day-based) or start_time and end_time (hour-based)."
            )
        if has_hours and ("start_time" not in attrs or "end_time" not in attrs):
            raise serializers.ValidationError("Send both start_time and end_time.")
        if has_hours and attrs["end_time"] <= attrs["start_time"]:
            raise serializers.ValidationError({"end_time": "Must be after start_time."})
        return attrs


class MyBookingSerializer(serializers.ModelSerializer):
    """Serializer for user's own booking requests."""

    thing_code = serializers.CharField(source="thing_code_id")
    thing_headline = serializers.CharField(source="thing_code.headline", read_only=True)
    owner_code = serializers.CharField(source="owner_code_id")
    owner_name = serializers.SerializerMethodField()

    class Meta:
        model = BookingPeriod
        fields = [
            "code",
            "created",
            "thing_code",
            "thing_headline",
            "thing_type",
            "owner_code",
            "owner_name",
            "start_date",
            "end_date",
            "start_time",
            "end_time",
            "status",
            "quantity",
            "project_note",
        ]

    def get_owner_name(self, obj):
        # Bare name only — never the email fallback (display_name): this is shown
        # to the requester, a co-member, and a member's email is never leaked.
        return obj.owner_code.name
