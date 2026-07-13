"""Django admin: User.about renders as a Textarea, not a single-line input (S8).

A CharField renders in the admin as <input type="text"> by default. Pasting a
multi-line Markdown bio into that widget silently strips every newline in the
browser before the value is even submitted — a server-side round-trip test
can't reproduce the browser's paste-time collapsing (Django never sees the
pre-paste text), so what's verifiable here is (a) the admin's generated form
uses a real Textarea for this field, and (b) once Django *does* receive a
multi-line value, saving it through that form preserves the newlines
end-to-end. (The full HTTP change-form view sits behind django-otp 2FA —
config/urls.py's OTPAdminSite — so these go through the ModelAdmin/form layer
directly rather than fighting that gate for marginal extra coverage.)
"""

import pytest
from django import forms
from django.contrib import admin
from django.forms.models import model_to_dict

from core.admin import UserAdmin
from core.models import User


@pytest.mark.django_db
class TestUserAdminAboutField:
    def _superuser(self):
        return User.objects.create(
            code="ADMIN1", email="admin@test.com", name="Admin", is_staff=True, is_superuser=True
        )

    def _form_class(self, obj=None):
        request = type("FakeRequest", (), {"user": self._superuser()})()
        return UserAdmin(User, admin.site).get_form(request, obj=obj)

    def test_get_form_uses_a_textarea_widget_for_about(self):
        assert isinstance(self._form_class().base_fields["about"].widget, forms.Textarea)

    def test_a_multiline_bio_round_trips_through_the_admin_form(self):
        target = User.objects.create(code="BIOUSR", email="bio@test.com")
        multiline = "# Comuna Llum\n\nUna colla de coses per compartir.\n\nGràcies!"
        # password has no admin-facing validation here (plain CharField, not
        # the special ReadOnlyPasswordHashField) — model_to_dict returns '' for
        # this passwordless-auth model's unset field, which a required
        # CharField rejects, so give it a placeholder like the admin form would.
        data = {**model_to_dict(target), "about": multiline, "password": "unused-hash"}

        form = self._form_class(obj=target)(data=data, instance=target)
        assert form.is_valid(), form.errors
        form.save()

        target.refresh_from_db()
        assert target.about == multiline
