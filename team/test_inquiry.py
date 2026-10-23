import time
from unittest import mock

from django.core import mail, signing
from django.test import Client, TestCase, override_settings
from django.urls import reverse

from .forms import FORM_SALT
from .models import Inquiry


def token(age_seconds=30):
    return signing.dumps(time.time() - age_seconds, salt=FORM_SALT)


def payload(**overrides):
    data = {
        "name": "Casey Rivera",
        "email": "casey@example.com",
        "organization": "Rivera Machining",
        "topic": "sponsor",
        "message": "We can machine hubs in-kind.",
        "website": "",
        "form_token": token(),
    }
    data.update(overrides)
    return data


@override_settings(STORAGES={
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
})
class InquiryFormTests(TestCase):
    url = "/contact/"

    def test_form_renders_with_csrf_token_and_preselected_topic(self):
        response = self.client.get(self.url, {"topic": "sponsor"})
        self.assertContains(response, "csrfmiddlewaretoken")
        self.assertContains(response, 'name="form_token"')
        self.assertContains(response, '<option value="sponsor" selected>')

    def test_sponsor_page_links_to_prefilled_form(self):
        response = self.client.get(reverse("sponsors"))
        self.assertContains(response, "/contact/?topic=sponsor#inquiry-form")
        self.assertNotContains(response, "mailto:electricsting@csus.edu?subject")

    def test_valid_submission_is_saved_emailed_and_confirmed(self):
        response = self.client.post(self.url, payload(), follow=True)
        self.assertRedirects(response, "/contact/#inquiry-form", fetch_redirect_response=False)
        self.assertContains(response, "Your message reached the team")
        inquiry = Inquiry.objects.get()
        self.assertEqual(inquiry.topic, "sponsor")
        self.assertEqual(len(inquiry.sender_hash), 64)
        self.assertEqual(len(mail.outbox), 1)
        self.assertEqual(mail.outbox[0].reply_to, ["casey@example.com"])
        self.assertIn("machine hubs", mail.outbox[0].body)

    def test_post_without_csrf_token_is_rejected(self):
        client = Client(enforce_csrf_checks=True)
        response = client.post(self.url, payload())
        self.assertEqual(response.status_code, 403)
        self.assertFalse(Inquiry.objects.exists())

    def test_honeypot_is_accepted_silently_but_not_stored(self):
        response = self.client.post(self.url, payload(website="http://spam.example"))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Inquiry.objects.exists())
        self.assertEqual(mail.outbox, [])

    def test_instant_submission_is_treated_as_spam(self):
        response = self.client.post(self.url, payload(form_token=token(age_seconds=0)))
        self.assertEqual(response.status_code, 302)
        self.assertFalse(Inquiry.objects.exists())

    def test_missing_or_tampered_token_asks_to_retry(self):
        for bad in ("", "not-a-token"):
            response = self.client.post(self.url, payload(form_token=bad))
            self.assertEqual(response.status_code, 200)
            self.assertContains(response, "This form expired")
        self.assertFalse(Inquiry.objects.exists())

    def test_invalid_fields_show_errors_and_keep_input(self):
        response = self.client.post(self.url, payload(email="nope", message=""))
        self.assertContains(response, "Enter a valid email address.")
        self.assertContains(response, "Casey Rivera")
        self.assertFalse(Inquiry.objects.exists())

    @override_settings(INQUIRY_HOURLY_LIMIT=1)
    def test_repeat_sender_is_throttled(self):
        self.client.post(self.url, payload())
        response = self.client.post(self.url, payload(message="Second message"))
        self.assertContains(response, "Too many messages")
        self.assertEqual(Inquiry.objects.count(), 1)

    def test_mail_failure_still_saves_and_confirms(self):
        with mock.patch("team.views.EmailMessage.send", side_effect=OSError("smtp down")):
            with self.assertLogs("team.views", level="ERROR"):
                response = self.client.post(self.url, payload(), follow=True)
        self.assertContains(response, "Your message reached the team")
        self.assertEqual(Inquiry.objects.count(), 1)
