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
