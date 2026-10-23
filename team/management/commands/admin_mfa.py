import base64

from axes.utils import reset as reset_lockouts
from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand, CommandError
from django_otp import devices_for_user
from django_otp.plugins.otp_totp.models import TOTPDevice

ATTEMPTS = 3


class Command(BaseCommand):
    help = (
        "Manage admin sign-in codes from the server shell: list who is enrolled, enroll an "
        "authenticator app, clear lockouts, or remove a lost authenticator."
    )

    def add_arguments(self, parser):
        actions = parser.add_subparsers(dest="action", required=True)
        actions.add_parser("status", help="List active staff users and whether each has an authenticator.")
        enroll = actions.add_parser("enroll", help="Add an authenticator app for a staff user.")
        enroll.add_argument("username")
        enroll.add_argument("--replace", action="store_true", help="Replace the user's existing authenticator.")
        unlock = actions.add_parser("unlock", help="Clear sign-in lockouts and code throttling for a user.")
        unlock.add_argument("username")
        reset = actions.add_parser("reset", help="Remove a user's authenticators (lost phone, departed admin).")
        reset.add_argument("username")

    def handle(self, *args, action, **options):
        if action == "status":
            return self.status()
        user = self.get_user(options["username"])
        if action == "enroll":
            return self.enroll(user, options["replace"])
        if action == "unlock":
            return self.unlock(user)
        return self.reset(user)

    def get_user(self, username):
        User = get_user_model()
        try:
            return User.objects.get(**{User.USERNAME_FIELD: username})
        except User.DoesNotExist:
            raise CommandError(f"No user named {username!r}.")

    def confirmed_devices(self, user):
        return TOTPDevice.objects.filter(user=user, confirmed=True)

    def status(self):
        User = get_user_model()
        staff = User.objects.filter(is_active=True, is_staff=True).order_by(User.USERNAME_FIELD)
        missing = 0
        for user in staff:
            enrolled = self.confirmed_devices(user).exists()
            missing += not enrolled
            self.stdout.write(f"{user.get_username():30} {'authenticator set up' if enrolled else 'NOT ENROLLED'}")
        if not staff:
            self.stdout.write("No active staff users.")
        elif missing:
            self.stdout.write(self.style.WARNING(
                f"{missing} active staff user(s) cannot sign in while codes are required. "
                "Run: python manage.py admin_mfa enroll <username>"
            ))
        else:
            self.stdout.write(self.style.SUCCESS("Every active staff user has an authenticator."))

    def enroll(self, user, replace):
        if not (user.is_active and user.is_staff):
            raise CommandError(f"{user.get_username()} is not an active staff user.")
        if self.confirmed_devices(user).exists() and not replace:
            raise CommandError(
                f"{user.get_username()} already has an authenticator. Use --replace to set up a new one."
            )
        device = TOTPDevice.objects.create(user=user, name="authenticator", confirmed=False)
        try:
            secret = base64.b32encode(device.bin_key).decode()
            self.stdout.write(f"Add this account to an authenticator app for {user.get_username()}:")
            self.stdout.write(f"  Setup key: {secret}")
            self.stdout.write(f"  Or open:   {device.config_url}")
            self.stdout.write("The key is a secret. Clear this terminal's scrollback when you are done.")
            for _ in range(ATTEMPTS):
                try:
                    token = input("Enter the 6-digit code the app shows: ").strip()
                except (EOFError, KeyboardInterrupt):
                    break
                device.throttle_reset()
                if device.verify_token(token):
                    device.confirmed = True
                    device.save()
                    if replace:
                        TOTPDevice.objects.filter(user=user).exclude(pk=device.pk).delete()
                    self.stdout.write(self.style.SUCCESS(f"Authenticator set up for {user.get_username()}."))
                    return
                self.stdout.write(self.style.ERROR("That code was not accepted."))
        finally:
            if not device.confirmed:
                device.delete()
        raise CommandError("No authenticator was set up.")

    def unlock(self, user):
        lockouts = reset_lockouts(username=user.get_username())
        devices = list(devices_for_user(user, confirmed=None))
        for device in devices:
            device.throttle_reset()
        self.stdout.write(
            f"Cleared {lockouts} sign-in lockout record(s) and code throttling on {len(devices)} device(s)."
        )

    def reset(self, user):
        devices = list(devices_for_user(user, confirmed=None))
        for device in devices:
            device.delete()
        reset_lockouts(username=user.get_username())
        self.stdout.write(
            f"Removed {len(devices)} authenticator(s) for {user.get_username()}. "
            "They cannot sign in again until you run: python manage.py admin_mfa enroll "
            f"{user.get_username()}"
        )
