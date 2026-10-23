import os
import secrets
import subprocess
import sys
from datetime import timedelta
from io import StringIO
from unittest import mock

from axes.models import AccessAttempt
from django.conf import settings
from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import RequestFactory, TestCase, override_settings
from django.utils import timezone
from django_otp.oath import TOTP
from django_otp.plugins.otp_totp.models import TOTPDevice

from fsae_site.admin_site import client_ip

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
PASSWORD = "correct-horse-battery-1"


def current_code(device):
    token = TOTP(device.bin_key, device.step, device.t0, device.digits, device.drift).token()
    return f"{token:0{device.digits}d}"


class AdminLoginTestCase(TestCase):
    @classmethod
    def setUpTestData(cls):
        cls.admin = get_user_model().objects.create_superuser("editor", "editor@example.com", PASSWORD)
        cls.device = TOTPDevice.objects.create(user=cls.admin, name="authenticator", confirmed=True)

    def login(self, password=PASSWORD, code=None, address="203.0.113.7", username="editor"):
        data = {"username": username, "password": password, "next": "/admin/"}
        if code is not None:
            data["otp_token"] = code
        return self.client.post("/admin/login/", data, HTTP_X_REAL_IP=address)


@override_settings(STORAGES=STORAGES, ADMIN_REQUIRE_OTP=True)
class OtpRequiredTests(AdminLoginTestCase):
    def test_password_alone_is_refused(self):
        response = self.login()
        self.assertEqual(response.status_code, 200)
        self.assertTrue(response.context["form"].errors)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_wrong_code_is_refused(self):
        response = self.login(code="000000" if current_code(self.device) != "000000" else "111111")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_password_and_current_code_sign_in_with_one_submission(self):
        response = self.login(code=current_code(self.device))
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/admin/").status_code, 200)

    def test_session_without_a_code_cannot_open_the_admin(self):
        self.client.force_login(self.admin)
        response = self.client.get("/admin/")
        self.assertEqual(response.status_code, 302)
        self.assertIn("/admin/login/", response["Location"])

    def test_wrong_codes_are_throttled_per_device_and_do_not_count_as_password_failures(self):
        wrong = "000000" if current_code(self.device) != "000000" else "111111"
        self.login(code=wrong)
        self.device.refresh_from_db()
        self.assertEqual(self.device.throttling_failure_count, 1)
        self.assertFalse(AccessAttempt.objects.exists())


@override_settings(STORAGES=STORAGES, ADMIN_REQUIRE_OTP=False)
class OtpOffTests(AdminLoginTestCase):
    def test_plain_login_form_when_codes_are_off(self):
        response = self.client.get("/admin/login/")
        self.assertNotIn("otp_token", response.context["form"].fields)

    def test_password_is_enough_when_codes_are_off(self):
        self.assertRedirects(self.login(), "/admin/", fetch_redirect_response=False)
        self.assertEqual(self.client.get("/admin/").status_code, 200)


@override_settings(STORAGES=STORAGES, ADMIN_REQUIRE_OTP=False)
class LockoutTests(AdminLoginTestCase):
    def test_five_wrong_passwords_lock_that_username_from_that_address(self):
        for _ in range(settings.AXES_FAILURE_LIMIT - 1):
            self.assertEqual(self.login(password="wrong").status_code, 200)
        # The failure that reaches the limit is the first one refused.
        self.assertEqual(self.login(password="wrong").status_code, 429)
        # The right password does not get through during the lockout either.
        self.assertEqual(self.login(password=PASSWORD, address="203.0.113.7").status_code, 429)

    def test_another_address_is_not_locked_out(self):
        for _ in range(settings.AXES_FAILURE_LIMIT):
            self.login(password="wrong", address="203.0.113.7")
        response = self.login(password=PASSWORD, address="198.51.100.1")
        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)

    def test_lockout_expires(self):
        self.assertEqual(settings.AXES_COOLOFF_TIME, timedelta(minutes=30))
        for _ in range(settings.AXES_FAILURE_LIMIT):
            self.login(password="wrong")
        self.assertEqual(self.login().status_code, 429)
        AccessAttempt.objects.update(attempt_time=timezone.now() - timedelta(minutes=31))
        self.assertRedirects(self.login(), "/admin/", fetch_redirect_response=False)

    def test_a_successful_login_clears_earlier_failures(self):
        self.login(password="wrong")
        self.login()
        self.assertFalse(AccessAttempt.objects.exists())


class ClientIpTests(TestCase):
    def request(self, **meta):
        return RequestFactory().get("/admin/login/", **meta)

    def test_uses_the_address_nginx_sets(self):
        request = self.request(REMOTE_ADDR="172.18.0.1", HTTP_X_REAL_IP="203.0.113.9")
        self.assertEqual(client_ip(request), "203.0.113.9")

    def test_falls_back_to_the_connection_address(self):
        self.assertEqual(client_ip(self.request(REMOTE_ADDR="172.18.0.1")), "172.18.0.1")
        request = self.request(REMOTE_ADDR="172.18.0.1", HTTP_X_REAL_IP="not-an-address")
        self.assertEqual(client_ip(request), "172.18.0.1")

    def test_ignores_x_forwarded_for(self):
        request = self.request(REMOTE_ADDR="172.18.0.1", HTTP_X_FORWARDED_FOR="203.0.113.9")
        self.assertEqual(client_ip(request), "172.18.0.1")


class AdminSettingsTests(TestCase):
    def setting_in_production(self, value, **extra_env):
        env = os.environ.copy()
        for name in ("DJANGO_SECRET_KEY_FILE", "DB_PASSWORD_FILE", "SENTRY_DSN", "DJANGO_ADMIN_REQUIRE_OTP"):
            env.pop(name, None)
        env.update({
            "DJANGO_DEBUG": "False",
            "DJANGO_SECRET_KEY": secrets.token_urlsafe(60),
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
            "DB_ENGINE": "postgres",
            "DB_PASSWORD": secrets.token_urlsafe(24),
            **extra_env,
        })
        result = subprocess.run(
            [sys.executable, str(settings.BASE_DIR / "manage.py"), "shell", "-c",
             f"from django.conf import settings; print(settings.{value})"],
            cwd=settings.BASE_DIR, env=env, capture_output=True, text=True, check=False,
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        return result.stdout.strip().splitlines()[-1]

    def test_production_requires_a_code_by_default(self):
        self.assertEqual(self.setting_in_production("ADMIN_REQUIRE_OTP"), "True")

    def test_the_code_requirement_can_be_switched_off_in_an_emergency(self):
        result = self.setting_in_production("ADMIN_REQUIRE_OTP", DJANGO_ADMIN_REQUIRE_OTP="false")
        self.assertEqual(result, "False")

    def test_axes_cooloff_is_not_permanent(self):
        self.assertIsNotNone(settings.AXES_COOLOFF_TIME)


class AdminMfaCommandTests(TestCase):
    @classmethod
    def setUpTestData(cls):
        User = get_user_model()
        cls.staff = User.objects.create_user("editor", "e@example.com", PASSWORD, is_staff=True)
        cls.visitor = User.objects.create_user("visitor", "v@example.com", PASSWORD)

    def run_command(self, *args, codes=()):
        out = StringIO()
        with mock.patch("builtins.input", side_effect=list(codes)):
            call_command("admin_mfa", *args, stdout=out)
        return out.getvalue()

    def pending_code(self, *_):
        device = TOTPDevice.objects.get(user=self.staff, confirmed=False)
        return current_code(device)

    def test_enroll_confirms_the_device_with_a_valid_code(self):
        out = StringIO()
        with mock.patch("builtins.input", side_effect=lambda prompt: self.pending_code()):
            call_command("admin_mfa", "enroll", "editor", stdout=out)
        self.assertIn("Setup key:", out.getvalue())
        self.assertTrue(TOTPDevice.objects.get(user=self.staff).confirmed)

    def test_enroll_refuses_non_staff_users(self):
        with self.assertRaisesMessage(CommandError, "not an active staff user"):
            self.run_command("enroll", "visitor")

    def test_enroll_refuses_unknown_users(self):
        with self.assertRaisesMessage(CommandError, "No user named"):
            self.run_command("enroll", "nobody")

    def test_enroll_refuses_to_replace_without_the_flag(self):
        TOTPDevice.objects.create(user=self.staff, name="authenticator", confirmed=True)
        with self.assertRaisesMessage(CommandError, "already has an authenticator"):
            self.run_command("enroll", "editor")
        self.assertEqual(TOTPDevice.objects.filter(user=self.staff).count(), 1)

    def test_enroll_replace_swaps_the_old_device_for_the_new_one(self):
        old = TOTPDevice.objects.create(user=self.staff, name="authenticator", confirmed=True)
        with mock.patch("builtins.input", side_effect=lambda prompt: self.pending_code()):
            call_command("admin_mfa", "enroll", "editor", "--replace", stdout=StringIO())
        devices = TOTPDevice.objects.filter(user=self.staff)
        self.assertEqual(devices.count(), 1)
        self.assertNotEqual(devices.get().pk, old.pk)
        self.assertTrue(devices.get().confirmed)

    def test_enroll_discards_the_device_after_three_wrong_codes(self):
        with self.assertRaisesMessage(CommandError, "No authenticator was set up"):
            self.run_command("enroll", "editor", codes=["x", "y", "z"])
        self.assertFalse(TOTPDevice.objects.filter(user=self.staff).exists())

    def test_enroll_discards_the_device_if_the_prompt_is_abandoned(self):
        with self.assertRaises(CommandError):
            self.run_command("enroll", "editor", codes=[EOFError()])
        self.assertFalse(TOTPDevice.objects.filter(user=self.staff).exists())

    def test_unlock_clears_lockouts_and_code_throttling(self):
        device = TOTPDevice.objects.create(user=self.staff, name="authenticator", confirmed=True)
        device.verify_token("000000")
        device.refresh_from_db()
        self.assertGreater(device.throttling_failure_count, 0)
        AccessAttempt.objects.create(username="editor", ip_address="203.0.113.7", failures_since_start=5)
        self.run_command("unlock", "editor")
        device.refresh_from_db()
        self.assertEqual(device.throttling_failure_count, 0)
        self.assertFalse(AccessAttempt.objects.filter(username="editor").exists())

    def test_reset_removes_every_device(self):
        TOTPDevice.objects.create(user=self.staff, name="authenticator", confirmed=True)
        TOTPDevice.objects.create(user=self.staff, name="spare", confirmed=False)
        self.run_command("reset", "editor")
        self.assertFalse(TOTPDevice.objects.filter(user=self.staff).exists())

    def test_status_lists_staff_without_an_authenticator(self):
        out = self.run_command("status")
        self.assertIn("NOT ENROLLED", out)
        self.assertIn("editor", out)
        self.assertNotIn("visitor", out)
        TOTPDevice.objects.create(user=self.staff, name="authenticator", confirmed=True)
        self.assertIn("Every active staff user has an authenticator", self.run_command("status"))
