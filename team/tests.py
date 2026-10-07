import hashlib
import importlib
import os
from pathlib import Path
import secrets
import subprocess
import sys
from types import SimpleNamespace

from django.apps import apps
from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.staticfiles import finders
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TestCase, TransactionTestCase, override_settings
from django.urls import reverse

from .models import Car, SponsorshipTier, TeamMember


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class PublicSiteTests(TestCase):
    def setUp(self):
        self.car = Car.objects.create(
            name="ELECTRIC STING 01",
            season="2027",
            slug="electric-sting-27",
            tagline="A test design.",
            description="Legacy demo copy should not present a completed car.",
            image_url="https://example.com/legacy-demo-car.jpg",
            top_speed="999 mph",
            is_current=True,
        )
        TeamMember.objects.create(name="Test Lead", role="Captain", subteam="high_voltage", active=True)

    def test_home_uses_design_plan_link(self):
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "View the design plan")
        self.assertContains(response, self.car.get_absolute_url())
        self.assertContains(response, "The car has not been built yet.")
        self.assertNotContains(response, "Read the build brief")
        self.assertNotContains(response, self.car.image_url)
        self.assertNotContains(response, "roadmap-marker")

    def test_car_detail_is_explicitly_pre_build(self):
        response = self.client.get(self.car.get_absolute_url())
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "The car has not been built yet.")
        self.assertContains(response, "IN DESIGN")
        self.assertNotContains(response, self.car.image_url)
        self.assertNotContains(response, self.car.top_speed)
        self.assertNotContains(response, self.car.description)

    def test_car_list_has_no_legacy_stock_image(self):
        response = self.client.get(reverse("cars"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "NOT YET BUILT")
        self.assertNotContains(response, self.car.image_url)
        self.assertNotContains(response, "{empty}")

    def test_new_logo_and_stylesheet_on_every_public_page(self):
        for name in ("home", "roster", "cars", "sponsors", "events", "gallery", "contact"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertContains(response, "/static/images/electric-sting-mascot-v4.webp")
                self.assertContains(response, "/static/css/site-v5.css")
                self.assertContains(response, 'content="es-sponsorship-v6"')
                self.assertNotContains(response, "electric-sting-logo.webp")
                self.assertNotContains(response, "{empty}")
                self.assertNotContains(response, 'href="/stories/')

    def test_logo_is_exact_supplied_attachment(self):
        logo = Path(finders.find("images/electric-sting-mascot-v4.webp"))
        self.assertEqual(
            hashlib.sha256(logo.read_bytes()).hexdigest(),
            "5944c4876e5b27005bf2f2cec0934874ff6b9f6c4ed4a300b2819cebcf698793",
        )
        self.assertFalse((settings.BASE_DIR / "static/images/electric-sting-logo.webp").exists())

    def test_roster_with_members_has_no_placeholder(self):
        response = self.client.get(reverse("roster"))
        self.assertContains(response, "Test Lead")
        self.assertNotContains(response, "Add team members in the Django admin")
        self.assertNotContains(response, "{empty}")

    def test_empty_roster_has_no_placeholder(self):
        TeamMember.objects.all().delete()
        response = self.client.get(reverse("roster"))
        self.assertEqual(response.status_code, 200)
        self.assertNotContains(response, "Add team members in the Django admin")
        self.assertNotContains(response, "{empty}")
        self.assertNotContains(response, "0 MEMBERS")

    def test_empty_car_list_has_public_message(self):
        Car.objects.all().delete()
        response = self.client.get(reverse("cars"))
        self.assertContains(response, "Our first car is in design.")
        self.assertNotContains(response, "Django admin")
        self.assertNotContains(response, "{empty}")

    def test_home_without_car_still_loads(self):
        Car.objects.all().delete()
        response = self.client.get(reverse("home"))
        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "electric-sting-mascot-v4.webp")

    def test_gallery_includes_supplied_team_photos(self):
        response = self.client.get(reverse("gallery"))
        self.assertContains(response, "team-launch.webp")
        self.assertContains(response, "team-outreach.webp")

    def test_blog_routes_are_removed(self):
        for path in ("/stories/", "/stories/built-from-zero/"):
            self.assertEqual(self.client.get(path).status_code, 404)

    def test_sponsors_loads_with_package_matrix(self):
        SponsorshipTier.objects.create(name="Bronze", amount="$500+", badge="Bronze Leaf")
        response = self.client.get(reverse("sponsors"))
        self.assertContains(response, "Bronze Leaf")

    def test_healthz_checks_database(self):
        response = self.client.get(reverse("healthz"))
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})

    def test_exact_sections_in_order_on_home_and_roster(self):
        labels = ["High Voltage", "Powertrain", "Low Voltage/Controls", "Frame", "Suspensions"]
        self.assertEqual([label for _, label in TeamMember.SUBTEAM_CHOICES], labels)
        response = self.client.get(reverse("roster"))
        self.assertEqual([group[1] for group in response.context["grouped_members"]], labels)
        home = self.client.get(reverse("home"))
        self.assertEqual([item[1] for item in home.context["engineering_systems"]], labels)
        self.assertContains(home, "Five sections.")
        self.assertNotContains(home, "Six systems.")

    def test_leads_and_coleads_are_badged_and_sorted_first(self):
        TeamMember.objects.all().delete()
        regular = TeamMember.objects.create(name="A Member", role="Engineer", subteam="frame", sort_order=0)
        lead = TeamMember.objects.create(name="Z Lead", role="Engineer", subteam="frame", is_lead=True, sort_order=90)
        colead = TeamMember.objects.create(name="B Co-lead", role="Engineer", subteam="frame", is_lead=True, sort_order=20)
        response = self.client.get(reverse("roster"))
        frame = next(group[2] for group in response.context["grouped_members"] if group[0] == "frame")
        self.assertEqual(frame, [colead, lead, regular])
        self.assertContains(response, '<span class="lead-badge">Section lead</span>', count=2, html=True)

    def test_unassigned_and_inactive_profiles_stay_private(self):
        TeamMember.objects.create(name="Unassigned Profile", role="Engineer", subteam="")
        TeamMember.objects.create(name="Inactive Profile", role="Engineer", subteam="frame", is_lead=True, active=False)
        response = self.client.get(reverse("roster"))
        self.assertNotContains(response, "Unassigned Profile")
        self.assertNotContains(response, "Inactive Profile")
        self.assertEqual(response.context["member_count"], 1)

    def test_empty_roster_still_has_five_sections(self):
        TeamMember.objects.all().delete()
        response = self.client.get(reverse("roster"))
        self.assertEqual(len(response.context["grouped_members"]), 5)
        for key, label in TeamMember.SUBTEAM_CHOICES:
            self.assertContains(response, f'id="{key}"')
            self.assertContains(response, label)
        self.assertNotContains(response, "Section lead")

    def test_admin_can_assign_section_and_lead(self):
        user = get_user_model().objects.create_superuser("roster-admin", "admin@example.com", "test-only-password")
        self.client.force_login(user)
        response = self.client.post(reverse("admin:team_teammember_add"), {
            "name": "New Lead", "role": "Engineer", "subteam": "suspensions",
            "is_lead": "on", "active": "on", "sort_order": "0", "_save": "Save",
        })
        self.assertEqual(response.status_code, 302)
        member = TeamMember.objects.get(name="New Lead")
        self.assertTrue(member.is_lead)
        self.assertEqual(member.subteam, "suspensions")
        model_admin = admin.site._registry[TeamMember]
        self.assertIn("subteam", model_admin.list_editable)
        self.assertIn("is_lead", model_admin.list_editable)
        response = self.client.get(reverse("roster"))
        self.assertContains(response, "New Lead")
        self.assertContains(response, "Section lead")

    def test_admin_warns_about_unassigned_profiles(self):
        user = get_user_model().objects.create_superuser("review-admin", "review@example.com", "test-only-password")
        self.client.force_login(user)
        TeamMember.objects.create(name="Review Member", role="Engineer", previous_subteam="chassis")
        response = self.client.get(reverse("admin:team_teammember_changelist"))
        self.assertContains(response, "1 member(s) need a section assignment")
        self.assertContains(response, "Review Member")

    def test_lazy_images_and_mobile_controls(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, 'loading="lazy" decoding="async" width="2048" height="1536"')
        self.assertContains(response, 'fetchpriority="high"')
        self.assertContains(response, '/static/js/site-v5.js')
        self.assertContains(response, 'aria-controls="primary-nav"')
        self.assertContains(response, 'name="viewport"')
        self.assertNotContains(response, 'loading="eager"')
        gallery = self.client.get(reverse("gallery"))
        self.assertContains(gallery, 'loading="lazy" decoding="async"', count=2)


    def test_public_empty_pages_have_no_admin_instructions(self):
        SponsorshipTier.objects.all().delete()
        for name in ("home", "roster", "cars", "sponsors", "events", "gallery", "contact"):
            with self.subTest(page=name):
                response = self.client.get(reverse(name))
                self.assertEqual(response.status_code, 200)
                self.assertNotIn("django", response.content.decode().lower())
                self.assertNotIn("admin", response.content.decode().lower())
        self.assertContains(self.client.get(reverse("events")), "Upcoming events will be announced here.")
        self.assertContains(self.client.get(reverse("sponsors")), "Contact the team for sponsorship options.")


class SponsorshipPackageMigrationTests(TestCase):
    def setUp(self):
        SponsorshipTier.objects.all().delete()
        self.migration = importlib.import_module("team.migrations.0005_restore_sponsorship_packages")

    def restore(self):
        self.migration.restore_packages(apps, SimpleNamespace(connection=connection))

    def test_restores_original_amounts_and_benefits_without_demo_data(self):
        member_count = TeamMember.objects.count()
        self.restore()
        actual = list(SponsorshipTier.objects.values_list(
            "name", "amount", "badge", "social_posts", "logo_size", "school_tour", "logo_on_merch",
        ))
        self.assertEqual(actual, [
            ("Bronze", "$500+", "Bronze Leaf", "1", "Extra small", False, False),
            ("Silver", "$1,500+", "Silver Tulip", "1", "Small", False, True),
            ("Gold", "$3,500+", "Gold Rose", "2", "Medium", True, True),
            ("Platinum", "$5,000+", "Platinum Orchid", "3", "Large", True, True),
        ])
        self.assertEqual(TeamMember.objects.count(), member_count)

    def test_preserves_edits_and_disabled_packages_and_is_idempotent(self):
        existing = SponsorshipTier.objects.create(name="bronze", amount="$750+", badge="Custom", active=False)
        self.restore()
        self.restore()
        self.assertEqual(SponsorshipTier.objects.count(), 4)
        existing.refresh_from_db()
        self.assertEqual(existing.amount, "$750+")
        self.assertEqual(existing.badge, "Custom")
        self.assertFalse(existing.active)


class RosterMigrationTests(TransactionTestCase):
    old_target = [("team", "0003_remove_article")]
    new_target = [("team", "0004_roster_sections")]

    def test_migration_preserves_every_profile_and_lead_setting(self):
        executor = MigrationExecutor(connection)
        executor.migrate(self.old_target)
        try:
            old_model = executor.loader.project_state(self.old_target).apps.get_model("team", "TeamMember")
            old_sections = ["battery", "drivetrain", "controls", "chassis", "aero", "business"]
            for section in old_sections:
                old_model.objects.create(name=section, role="Engineer", subteam=section, is_lead=True, bio="Keep this bio")
            executor = MigrationExecutor(connection)
            executor.migrate(self.new_target)
            new_model = executor.loader.project_state(self.new_target).apps.get_model("team", "TeamMember")
            expected = {"battery": "high_voltage", "drivetrain": "powertrain", "controls": "low_voltage_controls"}
            self.assertEqual(new_model.objects.count(), 6)
            for member in new_model.objects.all():
                self.assertEqual(member.subteam, expected.get(member.name, ""))
                self.assertEqual(member.previous_subteam, member.name)
                self.assertTrue(member.is_lead)
                self.assertEqual(member.bio, "Keep this bio")
            executor = MigrationExecutor(connection)
            executor.migrate(self.old_target)
            restored = executor.loader.project_state(self.old_target).apps.get_model("team", "TeamMember")
            self.assertEqual(set(restored.objects.values_list("subteam", flat=True)), set(old_sections))
        finally:
            executor = MigrationExecutor(connection)
            executor.migrate(executor.loader.graph.leaf_nodes())


class ProductionSecretSettingsTests(TestCase):
    def run_production_check(self, secret_key, db_password):
        env = os.environ.copy()
        for name in ("DJANGO_SECRET_KEY_FILE", "DB_PASSWORD_FILE", "SENTRY_DSN"):
            env.pop(name, None)
        env.update({
            "DJANGO_DEBUG": "False",
            "DJANGO_SECRET_KEY": secret_key,
            "DJANGO_ALLOWED_HOSTS": "example.com",
            "DJANGO_CSRF_TRUSTED_ORIGINS": "https://example.com",
            "DB_ENGINE": "postgres",
            "DB_PASSWORD": db_password,
        })
        return subprocess.run(
            [sys.executable, str(settings.BASE_DIR / "manage.py"), "check"],
            cwd=settings.BASE_DIR,
            env=env,
            capture_output=True,
            text=True,
            check=False,
        )

    def test_production_rejects_short_django_secret_key(self):
        result = self.run_production_check(
            "replace-with-secret-manager-value",
            secrets.token_urlsafe(32),
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("at least 50 characters", result.stderr)

    def test_production_rejects_example_database_password(self):
        result = self.run_production_check(
            secrets.token_urlsafe(48),
            "replace-with-secret-manager-value",
        )
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("DB_PASSWORD must not use the example placeholder", result.stderr)
