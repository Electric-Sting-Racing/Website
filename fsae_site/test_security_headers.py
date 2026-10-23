import re
from html.parser import HTMLParser
from pathlib import Path

from django.conf import settings
from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.models import Group
from django.test import TestCase, override_settings
from django.urls import NoReverseMatch, reverse
from django.utils import timezone

from fsae_site.middleware import ADMIN_BASELINE_CSP, build_csp
from news.models import Post
from team.models import Car, Event, GalleryImage, Sponsor, SponsorshipTier, TeamMember

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

    def test_styles_and_fonts_load_only_from_this_site(self):
        response = self.client.get("/")
        policy = directives(response["Content-Security-Policy"])
        self.assertEqual(policy["style-src"], ["'self'"])
        self.assertEqual(policy["font-src"], ["'self'"])
        self.assertNotIn("googleapis", response["Content-Security-Policy"])
        self.assertNotIn("gstatic", response["Content-Security-Policy"])

    def test_a_configured_host_is_added_to_the_policy(self):
        with override_settings(CSP_STYLE_HOSTS=["https://styles.example"], CSP_FONT_HOSTS=["https://fonts.example"]):
            policy = directives(self.client.get("/")["Content-Security-Policy"])
        self.assertEqual(policy["style-src"], ["'self'", "https://styles.example"])
        self.assertEqual(policy["font-src"], ["'self'", "https://fonts.example"])

    @override_settings(CSP_REPORT_ONLY=True)
    def test_report_only_mode_does_not_enforce(self):
        response = self.client.get("/")
        self.assertIn("Content-Security-Policy-Report-Only", response)
        self.assertNotIn("Content-Security-Policy", response)

    def test_admin_gets_the_full_policy(self):
        admin_header = self.client.get("/admin/login/")["Content-Security-Policy"]
        self.assertEqual(admin_header, self.client.get("/")["Content-Security-Policy"])
        policy = directives(admin_header)
        for name in ("default-src", "script-src", "style-src"):
            self.assertEqual(policy[name], ["'self'"])
        self.assertNotIn("unsafe-inline", admin_header)
        self.assertNotIn("unsafe-eval", admin_header)

    @override_settings(CSP_REPORT_ONLY=True)
    def test_report_only_still_enforces_the_admin_baseline(self):
        response = self.client.get("/admin/login/")
        self.assertEqual(response["Content-Security-Policy"], ADMIN_BASELINE_CSP)
        self.assertEqual(directives(response["Content-Security-Policy-Report-Only"])["script-src"], ["'self'"])
        self.assertNotIn("Content-Security-Policy", self.client.get("/"))

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


class InlineCodeFinder(HTMLParser):
    """Collects markup that an enforced policy without 'unsafe-inline' would block."""

    def __init__(self):
        super().__init__()
        self.problems = []

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        if tag == "script" and "src" not in attrs and attrs.get("type") not in ("application/json", "application/ld+json"):
            self.problems.append("inline <script>")
        if tag == "style":
            self.problems.append("<style> block")
        for name, value in attrs.items():
            if name == "style":
                self.problems.append("style attribute")
            elif name.startswith("on"):
                self.problems.append(f"{name} handler")
            elif name in ("href", "src", "action", "formaction") and (value or "").strip().lower().startswith("javascript:"):
                self.problems.append(f"javascript: {name}")


@override_settings(STORAGES=STORAGES)
class AdminPagesStayCspCompatibleTests(TestCase):
    """Every admin page the site can render must work under the enforced policy.

    This cannot run JavaScript. Django's own admin tests cover its scripts under default-src 'self'.
    """

    @classmethod
    def setUpTestData(cls):
        cls.superuser = get_user_model().objects.create_superuser("csp-admin", "csp@example.com", "csp-password-1")
        Group.objects.create(name="Editors")
        TeamMember.objects.create(name="A Member", role="Lead", subteam="business")
        Car.objects.create(name="ES-01", season="2027", slug="es-01", tagline="t", description="d")
        Sponsor.objects.create(name="A Sponsor", website="https://sponsor.example", logo_url="https://sponsor.example/l.png")
        SponsorshipTier.objects.create(name="Bronze", amount="$500+", badge="Bronze Leaf")
        Event.objects.create(title="Open day", date=timezone.localdate(), location="Lab")
        GalleryImage.objects.create(title="Photo", image_url="https://img.example/p.jpg", alt_text="A photo")
        Post.objects.create(
            title="Hello", slug="hello", summary="s", is_published=True,
            body='<script>alert(1)</script> <p style="x" onclick="y()">hi</p> ![i](https://img.example/i.png)',
            cover_image_url="https://img.example/c.png",
        )

    def admin_urls(self):
        urls = ["/admin/", "/admin/password_change/", "/admin/team/teammember/add/?_to_field=id&_popup=1"]
        for model, model_admin in admin.site._registry.items():
            info = (model._meta.app_label, model._meta.model_name)
            instance = model._default_manager.first()
            urls.append(reverse("admin:%s_%s_changelist" % info))
            if model_admin.has_add_permission(self._request()):
                urls.append(reverse("admin:%s_%s_add" % info))
            if instance is not None:
                for view in ("change", "delete", "history"):
                    try:
                        urls.append(reverse("admin:%s_%s_%s" % (*info, view), args=[instance.pk]))
                    except NoReverseMatch:
                        pass
        return urls

    def _request(self):
        request = self.client.request().wsgi_request
        request.user = self.superuser
        return request

    def problems_in(self, url, response):
        problems = []
        if response.status_code not in (200, 302):
            problems.append(f"{url}: status {response.status_code}")
        if response.get("Content-Security-Policy") != build_csp():
            problems.append(f"{url}: not the full policy")
        if response.status_code == 200 and "text/html" in response.get("Content-Type", ""):
            finder = InlineCodeFinder()
            finder.feed(response.content.decode())
            problems.extend(f"{url}: {problem}" for problem in sorted(set(finder.problems)))
        return problems

    def test_every_registered_admin_page_renders_without_inline_code(self):
        problems = self.problems_in("/admin/login/", self.client.get("/admin/login/"))
        self.client.force_login(self.superuser)
        user_id = self.superuser.pk
        urls = [*self.admin_urls(), f"/admin/auth/user/{user_id}/password/"]
        for url in urls:
            problems.extend(self.problems_in(url, self.client.get(url)))
        confirmation = self.client.post("/admin/team/teammember/", {
            "action": "delete_selected", "_selected_action": [TeamMember.objects.first().pk],
        })
        problems.extend(self.problems_in("delete_selected confirmation", confirmation))
        problems.extend(self.problems_in("logout", self.client.post("/admin/logout/")))
        self.assertEqual(problems, [])
        self.assertGreater(len(urls), 40)

    def test_the_checker_finds_inline_code(self):
        finder = InlineCodeFinder()
        finder.feed(
            '<script>x()</script><style>a{}</style><p style="a" onclick="b()"></p>'
            '<a href="javascript:x()">y</a><script src="/a.js"></script><script type="application/json">{}</script>'
        )
        self.assertEqual(
            sorted(finder.problems),
            ["<style> block", "inline <script>", "javascript: href", "onclick handler", "style attribute"],
        )
