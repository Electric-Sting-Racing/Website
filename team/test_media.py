from django.test import TestCase, override_settings
from django.urls import reverse

from .models import Sponsor, TeamMember


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class AdminMediaTests(TestCase):
    def test_roster_shows_member_photo_when_set(self):
        TeamMember.objects.create(name="Ada", role="Driver", subteam="frame", photo_url="https://example.com/ada.jpg")
        TeamMember.objects.create(name="Grace", role="Engineer", subteam="frame")
        response = self.client.get(reverse("roster"))
        self.assertContains(response, 'src="https://example.com/ada.jpg"')
        self.assertContains(response, "<span>G</span>", html=False)

    def test_sponsor_cards_use_logos_and_skip_dead_links(self):
        Sponsor.objects.create(name="Acme", website="https://acme.example", logo_url="https://acme.example/logo.png")
        Sponsor.objects.create(name="Local Shop")
        response = self.client.get(reverse("sponsors"))
        self.assertContains(response, 'src="https://acme.example/logo.png"')
        self.assertContains(response, 'href="https://acme.example"')
        self.assertContains(response, '<div class="sponsor-card">')
        self.assertNotContains(response, 'href="#"')
