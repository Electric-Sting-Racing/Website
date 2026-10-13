from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings
from django.urls import reverse


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class GalleryImageTests(TestCase):
    def test_gallery_photos_are_sized_and_responsive(self):
        response = self.client.get(reverse("gallery"))
        self.assertContains(response, 'width="2048" height="1536"')
        self.assertContains(response, "team-launch-800.webp 800w")
        for image in response.context["images"]:
            for path, _ in image["srcset_paths"]:
                self.assertIsNotNone(finders.find(path), path)
