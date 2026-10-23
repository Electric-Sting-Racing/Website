"""Exercise the site against a migrated database while connected as the restricted web role.

Run it with the web role's DB_USER and DB_PASSWORD set. Everything it writes is rolled back.
"""

import os
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
os.environ.setdefault("DJANGO_SETTINGS_MODULE", "fsae_site.settings")

import django

django.setup()

from django.contrib.auth import get_user_model
from django.db import connection, transaction
from django.test import Client, override_settings

from team.models import TeamMember

# Plain static storage, so pages render without running collectstatic first. The admin check signs in
# without an authenticator code, which matters only once sign-in codes are required.
STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def expect(condition, message):
    if not condition:
        raise SystemExit(f"FAIL: {message}")


def main():
    with connection.cursor() as cursor:
        cursor.execute("select current_user, rolsuper from pg_roles where rolname = current_user")
        user, superuser = cursor.fetchone()
    expect(not superuser, f"{user} is a superuser")

    client = Client()
    for path in ("/healthz/", "/", "/team/", "/news/", "/sponsors/"):
        status = client.get(path).status_code
        expect(status == 200, f"GET {path} returned {status}")

    with transaction.atomic():
        member = TeamMember.objects.create(name="Role check", role="Check", subteam="frame")
        member.role = "Updated"
        member.save()
        user_model = get_user_model()
        admin = user_model.objects.create_superuser("role-check", "role-check@example.com", "role-check-0123456789")
        client.force_login(admin)
        status = client.get("/admin/team/teammember/").status_code
        expect(status == 200, f"GET the admin member list returned {status}")
        client.logout()
        client.post("/admin/login/", {"username": "nobody", "password": "wrong"})
        member.delete()
        transaction.set_rollback(True)
    print(f"PASS: the site reads and writes as {user}")


if __name__ == "__main__":
    with override_settings(STORAGES=STORAGES, ADMIN_REQUIRE_OTP=False):
        main()
