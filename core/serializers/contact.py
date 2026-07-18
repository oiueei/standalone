"""
Contact-form serializer (the support channel).

Anonymous-capable by design: the person who most needs this form is the one
who can't log in. The reply address is therefore asked for explicitly — there
is no authenticated user to read it from.
"""

from rest_framework import serializers

from core.validators import SafeHeadlineField, SafeTextField


class ContactSerializer(serializers.Serializer):
    """One message through the contact form.

    ``kind`` labels the operator's inbox: ``support`` (default — the contact
    page) or ``collab`` (the collaborate page). Same pipe, different subject.
    """

    name = SafeHeadlineField(max_length=32, required=False, allow_blank=True, default="")
    email = serializers.EmailField(max_length=64)
    message = SafeTextField(max_length=2000)
    kind = serializers.ChoiceField(choices=["support", "collab"], required=False, default="support")
