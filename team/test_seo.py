import json
import re

from django.template.loader import render_to_string
from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Car


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class SeoTests(TestCase):
    def test_pages_have_canonical_and_link_preview_tags(self):
        response = self.client.get(reverse("events"))
        self.assertContains(response, '<link rel="canonical" href="http://testserver/events/">', html=False)
        self.assertContains(response, 'property="og:image" content="http://testserver/static/images/og-image.jpg"')
        self.assertContains(response, 'name="twitter:card" content="summary_large_image"')

    def test_robots_and_sitemap(self):
        car = Car.objects.create(name="ES 01", season="2027", slug="es-01", tagline="Test.", description="Test.")
        robots = self.client.get("/robots.txt")
        self.assertEqual(robots["Content-Type"], "text/plain")
        self.assertContains(robots, "Sitemap: http://testserver/sitemap.xml")
        sitemap = self.client.get("/sitemap.xml")
        self.assertContains(sitemap, "<loc>http://testserver/events/</loc>")
        self.assertContains(sitemap, f"<loc>http://testserver{car.get_absolute_url()}</loc>")

    def test_custom_error_pages(self):
        response = self.client.get("/no-such-page/")
        self.assertEqual(response.status_code, 404)
        self.assertContains(response, "Wrong turn", status_code=404)
        self.assertIn("went <em>wrong.</em>", render_to_string("500.html"))

    def test_each_page_has_its_own_link_preview_text(self):
        seen = set()
        for name in ("home", "roster", "cars", "sponsors", "events", "gallery", "contact"):
            with self.subTest(page=name):
                html = self.client.get(reverse(name)).content.decode()
                title = re.search(r'property="og:title" content="([^"]*)"', html).group(1)
                description = re.search(r'name="description" content="([^"]*)"', html).group(1)
                self.assertIn(f'property="og:description" content="{description}"', html)
                seen.add((title, description))
        self.assertEqual(len(seen), 7)
        self.assertContains(self.client.get(reverse("events")), 'property="og:title" content="Events | ELECTRIC STING RACING"')

    def test_missing_page_is_not_indexable_or_canonical(self):
        response = self.client.get("/no-such-page/")
        self.assertContains(response, '<meta name="robots" content="noindex">', status_code=404)
        self.assertNotContains(response, 'rel="canonical"', status_code=404)
        self.assertNotContains(response, 'property="og:url"', status_code=404)
        self.assertIn('name="robots" content="noindex"', render_to_string("500.html"))

    def test_each_car_page_has_its_own_link_preview_text(self):
        first = Car.objects.create(name="ES 01", season="2027", slug="es-01", tagline="Test.", description="Test.")
        second = Car.objects.create(name="ES 02", season="2028", slug="es-02", tagline="Test.", description="Test.")
        seen = set()
        for car in (first, second):
            with self.subTest(car=car.name):
                html = self.client.get(car.get_absolute_url()).content.decode()
                title = re.search(r'property="og:title" content="([^"]*)"', html).group(1)
                description = re.search(r'name="description" content="([^"]*)"', html).group(1)
                self.assertIn(f"{car.name} ({car.season}), in design", title)
                self.assertIn(f"for the {car.season} season", description)
                self.assertIn("still in design", description)
                self.assertIn(f'property="og:description" content="{description}"', html)
                seen.add((title, description))
        self.assertEqual(len(seen), 2)

    def test_home_page_describes_the_team_as_structured_data(self):
        html = self.client.get(reverse("home")).content.decode()
        match = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S)
        data = json.loads(match.group(1))
        self.assertEqual(data["@type"], "Organization")
        self.assertEqual(data["name"], "Electric Sting Racing")
        self.assertEqual(data["url"], "http://testserver/")
        self.assertEqual(data["logo"], "http://testserver/static/images/electric-sting-mascot-v4.webp")
        self.assertEqual(data["parentOrganization"]["name"], "Sacramento State")

    def test_structured_data_is_only_on_the_home_page(self):
        for name in ("roster", "sponsors", "contact"):
            self.assertNotContains(self.client.get(reverse(name)), "application/ld+json")

    @override_settings(TEAM_NAME="Sting </script><b>Racing")
    def test_structured_data_cannot_close_its_script_tag(self):
        html = self.client.get(reverse("home")).content.decode()
        block = re.search(r'<script type="application/ld\+json">(.*?)</script>', html, re.S).group(1)
        self.assertNotIn("<", block)
        self.assertIn("\\u003c/", block)
