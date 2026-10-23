from datetime import timedelta

from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import Client, TestCase, override_settings
from django.utils import timezone

from team.models import Sponsor

from .models import LoginFailure
from .signals import EDITOR_GROUP

User = get_user_model()
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}
LOGIN_URL = "/admin/login/?next=/admin/"


def attempt(client, username, password):
    return client.post(LOGIN_URL, {"username": username, "password": password})


@override_settings(STORAGES=STORAGES)
class LockoutTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user("admin1", password="correct-horse-battery", is_staff=True)
        User.objects.create_user("admin2", password="another-long-password", is_staff=True)

    def fail(self, username="admin1", times=5, client=None):
        client = client or Client()
        for _ in range(times):
            attempt(client, username, "wrong")

    def test_correct_password_works_before_any_failures(self):
        response = attempt(Client(), "admin1", "correct-horse-battery")
        self.assertEqual(response.status_code, 302)

    def test_repeated_failures_lock_even_the_correct_password(self):
        self.fail()
        response = attempt(Client(), "admin1", "correct-horse-battery")
        self.assertEqual(response.status_code, 200)
        self.assertNotIn("_auth_user_id", self.client.session)

    def test_lockout_is_case_insensitive_on_the_username(self):
        self.fail("Admin1")
        self.assertEqual(attempt(Client(), "ADMIN1", "correct-horse-battery").status_code, 200)

    @override_settings(LOGIN_MAX_FAILURES_PER_IP=100)
    def test_other_accounts_are_not_locked_by_one_username(self):
        self.fail()
        self.assertEqual(attempt(Client(), "admin2", "another-long-password").status_code, 302)

    def test_lockout_ends_after_the_window(self):
        self.fail()
        LoginFailure.objects.update(created_at=timezone.now() - timedelta(minutes=16))
        self.assertEqual(attempt(Client(), "admin1", "correct-horse-battery").status_code, 302)

    def test_attempts_during_lockout_do_not_extend_it(self):
        self.fail()
        before = LoginFailure.objects.count()
        self.fail(times=3)
        self.assertEqual(LoginFailure.objects.count(), before)

    @override_settings(LOGIN_MAX_FAILURES_PER_USER=100, LOGIN_MAX_FAILURES_PER_IP=3)
    def test_one_client_guessing_many_usernames_is_locked(self):
        client = Client(REMOTE_ADDR="203.0.113.9")
        for name in ("a", "b", "c"):
            attempt(client, name, "wrong")
        locked = attempt(Client(REMOTE_ADDR="203.0.113.9"), "admin2", "another-long-password")
        self.assertEqual(locked.status_code, 200)
        other = attempt(Client(REMOTE_ADDR="198.51.100.4"), "admin2", "another-long-password")
        self.assertEqual(other.status_code, 302)

    @override_settings(LOGIN_MAX_FAILURES_PER_USER=100, LOGIN_MAX_FAILURES_PER_IP=2,
                       SECURITY_CLIENT_IP_HEADER="X-Forwarded-For")
    def test_proxy_header_uses_the_last_hop_not_a_spoofed_first_one(self):
        for spoofed in ("1.1.1.1", "2.2.2.2"):
            attempt(Client(HTTP_X_FORWARDED_FOR=f"{spoofed}, 203.0.113.7"), "x", "wrong")
        response = attempt(Client(HTTP_X_FORWARDED_FOR="3.3.3.3, 203.0.113.7"), "admin2", "another-long-password")
        self.assertEqual(response.status_code, 200)

    def test_success_clears_earlier_failures(self):
        self.fail(times=3)
        attempt(Client(), "admin1", "correct-horse-battery")
        self.assertFalse(LoginFailure.objects.filter(username="admin1").exists())

    def test_failures_store_a_hash_not_the_address(self):
        attempt(Client(REMOTE_ADDR="203.0.113.9"), "admin1", "wrong")
        failure = LoginFailure.objects.get()
        self.assertEqual(len(failure.ip_hash), 64)
        self.assertNotIn("203.0.113.9", failure.ip_hash)

    def test_old_failures_are_purged_on_any_sign_in_attempt(self):
        for password in ("wrong", "correct-horse-battery"):
            LoginFailure.objects.create(username="old", ip_hash="x")
            LoginFailure.objects.update(created_at=timezone.now() - timedelta(days=2))
            attempt(Client(), "admin1", password)
            self.assertFalse(LoginFailure.objects.filter(username="old").exists(), password)

    def test_old_failures_are_purged_even_while_locked_out(self):
        self.fail()
        LoginFailure.objects.create(username="old", ip_hash="x")
        LoginFailure.objects.filter(username="old").update(created_at=timezone.now() - timedelta(days=2))
        attempt(Client(), "admin1", "correct-horse-battery")
        self.assertFalse(LoginFailure.objects.filter(username="old").exists())


@override_settings(STORAGES=STORAGES)
class EditorGroupTests(TestCase):
    def test_group_exists_after_migrate(self):
        self.assertTrue(Group.objects.filter(name=EDITOR_GROUP).exists())

    def test_group_covers_site_content_but_not_users_or_groups(self):
        codenames = set(Group.objects.get(name=EDITOR_GROUP).permissions.values_list("codename", flat=True))
        for needed in ("add_sponsor", "change_teammember", "delete_event", "change_car"):
            self.assertIn(needed, codenames)
        self.assertTrue(codenames.isdisjoint({"add_user", "change_user", "change_group", "delete_user"}))
        self.assertFalse({c for c in codenames if c.endswith("loginfailure")})

    def test_editor_can_edit_content_but_not_manage_accounts(self):
        editor = User.objects.create_user("editor", password="editor-password-1", is_staff=True)
        editor.groups.add(Group.objects.get(name=EDITOR_GROUP))
        Sponsor.objects.create(name="Acme", description="Parts")
        client = Client()
        client.force_login(editor)
        self.assertEqual(client.get("/admin/team/sponsor/").status_code, 200)
        self.assertEqual(client.get("/admin/team/sponsor/add/").status_code, 200)
        self.assertEqual(client.get("/admin/auth/user/").status_code, 403)
        self.assertEqual(client.get("/admin/auth/group/").status_code, 403)
