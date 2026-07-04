"""
Bootstrap a TOTP (authenticator app) device for a Django admin user.

django-otp's OTPAdminSite (config/urls.py) requires every staff login to be
verified by a registered device, but django-otp only lets you *add* a device
through the admin's own config page — which itself requires an already
verified login. This command breaks that bootstrap deadlock: it creates a
confirmed device from the CLI and prints the otpauth:// provisioning URI to
scan into an authenticator app (Google Authenticator, Authy, etc.).

Usage:
    python manage.py add_totp_device owner@example.com
    python manage.py add_totp_device owner@example.com --replace
    heroku run --app <app> "python manage.py add_totp_device owner@example.com"
"""

from django.core.management.base import BaseCommand, CommandError
from django_otp.plugins.otp_totp.models import TOTPDevice

from core.models import User


class Command(BaseCommand):
    help = "Create a confirmed TOTP device for a staff user and print its provisioning URI."

    def add_arguments(self, parser):
        parser.add_argument("email", help="Email of the staff user to bootstrap 2FA for.")
        parser.add_argument(
            "--replace",
            action="store_true",
            help="Delete this user's existing TOTP devices before creating a new one.",
        )

    def handle(self, *args, **options):
        email = options["email"]
        try:
            user = User.objects.get(email=email)
        except User.DoesNotExist:
            raise CommandError(f"No user with email {email!r}")

        if not user.is_staff:
            raise CommandError(f"{email} is not a staff user — admin 2FA only applies to staff.")

        if options["replace"]:
            TOTPDevice.objects.filter(user=user).delete()
        elif TOTPDevice.objects.filter(user=user).exists():
            raise CommandError(
                f"{email} already has a TOTP device. Re-run with --replace to regenerate it."
            )

        device = TOTPDevice.objects.create(user=user, name="default", confirmed=True)
        self.stdout.write(self.style.SUCCESS(f"Created TOTP device for {email}."))
        self.stdout.write("Scan this URI into an authenticator app (Google Authenticator, etc.):")
        self.stdout.write(device.config_url)
