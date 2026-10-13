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
