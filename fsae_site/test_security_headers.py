import re
from pathlib import Path

from django.conf import settings
from django.test import TestCase, override_settings

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def directives(policy):
    return {part.split()[0]: part.split()[1:] for part in policy.split(";") if part.strip()}


@override_settings(STORAGES=STORAGES)
class SecurityHeaderTests(TestCase):
    def test_public_pages_send_a_strict_csp(self):
        for path in ("/", "/team/", "/contact/", "/no-such-page/"):
            with self.subTest(path=path):
                response = self.client.get(path)
                policy = directives(response["Content-Security-Policy"])
                self.assertEqual(policy["script-src"], ["'self'"])
                self.assertEqual(policy["object-src"], ["'none'"])
                self.assertEqual(policy["frame-ancestors"], ["'none'"])
                self.assertEqual(policy["form-action"], ["'self'"])
                self.assertEqual(policy["base-uri"], ["'self'"])
                self.assertNotIn("'unsafe-inline'", response["Content-Security-Policy"])
                self.assertNotIn("'unsafe-eval'", response["Content-Security-Policy"])

    def test_csp_allows_only_configured_font_hosts(self):
        policy = directives(self.client.get("/")["Content-Security-Policy"])
        self.assertEqual(policy["style-src"], ["'self'", "https://fonts.googleapis.com"])
        self.assertEqual(policy["font-src"], ["'self'", "https://fonts.gstatic.com"])
        with override_settings(CSP_STYLE_HOSTS=[], CSP_FONT_HOSTS=[]):
            policy = directives(self.client.get("/")["Content-Security-Policy"])
        self.assertEqual(policy["style-src"], ["'self'"])
        self.assertEqual(policy["font-src"], ["'self'"])

    @override_settings(CSP_REPORT_ONLY=True)
    def test_report_only_mode_does_not_enforce(self):
        response = self.client.get("/")
        self.assertIn("Content-Security-Policy-Report-Only", response)
        self.assertNotIn("Content-Security-Policy", response)

    def test_admin_gets_only_the_safe_subset(self):
        response = self.client.get("/admin/login/")
        policy = directives(response["Content-Security-Policy"])
        self.assertEqual(set(policy), {"object-src", "base-uri", "frame-ancestors"})

    def test_permissions_policy_disables_sensors_and_payment(self):
        value = self.client.get("/")["Permissions-Policy"]
        for feature in ("camera=()", "microphone=()", "geolocation=()", "payment=()"):
            self.assertIn(feature, value)

    def test_existing_hardening_headers_are_still_sent(self):
        response = self.client.get("/")
        self.assertEqual(response["X-Content-Type-Options"], "nosniff")
        self.assertEqual(response["X-Frame-Options"], "DENY")
        self.assertEqual(response["Referrer-Policy"], "same-origin")
        self.assertEqual(response["Cross-Origin-Opener-Policy"], "same-origin")

    def test_request_bodies_are_capped(self):
        self.assertLessEqual(settings.DATA_UPLOAD_MAX_MEMORY_SIZE, 1024 * 1024)
        self.assertLessEqual(settings.SESSION_COOKIE_AGE, 24 * 60 * 60)

    def test_oversized_bodies_are_refused_before_the_view_runs(self):
        too_big = str(settings.DATA_UPLOAD_MAX_MEMORY_SIZE + 1)
        response = self.client.post("/admin/login/", {"username": "x"}, CONTENT_LENGTH=too_big)
        self.assertEqual(response.status_code, 413)
        self.assertIn("Permissions-Policy", response)

    def test_normal_posts_are_not_refused(self):
        self.assertEqual(self.client.post("/admin/login/", {"username": "x", "password": "y"}).status_code, 200)


class TemplatesStayCspCompatibleTests(TestCase):
    """The enforced CSP blocks inline code, so templates must not grow any."""

    def test_templates_have_no_inline_script_style_or_handlers(self):
        templates = Path(settings.BASE_DIR, "templates").rglob("*.html")
        problems = []
        for path in templates:
            html = path.read_text(encoding="utf-8")
            for tag in re.findall(r"<script\b[^>]*>", html):
                if "src=" not in tag and "application/ld+json" not in tag:
                    problems.append(f"{path.name}: inline script {tag}")
            if re.search(r"<style\b", html):
                problems.append(f"{path.name}: <style> block")
            if re.search(r"""\sstyle\s*=\s*["']""", html):
                problems.append(f"{path.name}: style attribute")
            if re.search(r"""\son[a-z]+\s*=\s*["']""", html):
                problems.append(f"{path.name}: inline event handler")
        self.assertEqual(problems, [])
