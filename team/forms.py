import hashlib
import time
from datetime import timedelta

from django import forms
from django.conf import settings
from django.core import signing
from django.utils import timezone

from .models import Inquiry

FORM_SALT = "team.inquiry-form"
# People need a few seconds to write a message; scripts post immediately.
MIN_FILL_SECONDS = 3
MAX_FORM_AGE_SECONDS = 24 * 60 * 60


def sender_hash(request):
    """Salted hash of the client address, used only to throttle repeat senders."""
    address = request.META.get("REMOTE_ADDR", "")
    return hashlib.sha256(f"{settings.SECRET_KEY}:{address}".encode()).hexdigest()


def new_form_token():
    """Signed render time, echoed back by the page so too-fast posts can be spotted."""
    return signing.dumps(time.time(), salt=FORM_SALT)


class InquiryForm(forms.ModelForm):
    # Honeypot: hidden from people, filled in by most form-spamming bots.
    website = forms.CharField(required=False, label="Leave this field empty")

    class Meta:
        model = Inquiry
        fields = ["name", "email", "organization", "topic", "message"]
        labels = {
            "name": "Your name",
            "email": "Email address",
            "organization": "Company or school (optional)",
            "topic": "What is this about?",
            "message": "Message",
        }
        widgets = {"message": forms.Textarea(attrs={"rows": 6})}

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.looks_like_spam = False
        self.fields["name"].widget.attrs["autocomplete"] = "name"
        self.fields["email"].widget.attrs["autocomplete"] = "email"
        self.fields["organization"].widget.attrs["autocomplete"] = "organization"
        self.fields["website"].widget.attrs.update({"tabindex": "-1", "autocomplete": "off"})

    def clean(self):
        cleaned = super().clean()
        if cleaned.get("website"):
            self.looks_like_spam = True
            return cleaned
        try:
            started = signing.loads(
                self.data.get("form_token", ""), salt=FORM_SALT, max_age=MAX_FORM_AGE_SECONDS
            )
        except signing.BadSignature:
            raise forms.ValidationError("This form expired. Please check your message and send it again.")
        if time.time() - started < MIN_FILL_SECONDS:
            self.looks_like_spam = True
        return cleaned


def recent_inquiries_from(sender):
    window = timezone.now() - timedelta(hours=1)
    return Inquiry.objects.filter(sender_hash=sender, created_at__gte=window).count()
