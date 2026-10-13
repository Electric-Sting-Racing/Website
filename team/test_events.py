from datetime import timedelta

from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .models import Event


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class EventListTests(TestCase):
    def test_events_split_upcoming_and_past(self):
        today = timezone.localdate()
        Event.objects.create(title="Design review", date=today, location="Riverside Hall")
        Event.objects.create(title="Kickoff meeting", date=today - timedelta(days=30), location="Riverside Hall")
        Event.objects.create(title="Private sync", date=today, location="Lab", is_public=False)
        response = self.client.get(reverse("events"))
        self.assertEqual([event.title for event in response.context["events"]], ["Design review"])
        self.assertEqual([event.title for event in response.context["past_events"]], ["Kickoff meeting"])
        self.assertNotContains(response, "Private sync")
        self.assertContains(response, "PAST EVENTS")
