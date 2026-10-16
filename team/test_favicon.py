from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class FaviconTests(TestCase):
    def test_pages_use_small_favicon_and_touch_icon(self):
        response = self.client.get(reverse("home"))
        self.assertContains(response, "icons/favicon.ico")
        self.assertContains(response, "icons/apple-touch-icon.png")
        self.assertNotContains(response, 'rel="icon" type="image/webp"')
