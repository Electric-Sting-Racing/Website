from collections import defaultdict

import logging

from django.conf import settings
from django.contrib import messages
from django.contrib.staticfiles.storage import staticfiles_storage
from django.core.mail import EmailMessage
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, redirect, render
from django.urls import reverse
from django.views.decorators.http import require_GET

from .content import ENGINEERING_SYSTEMS, FEATURED_GALLERY_IMAGES, PROGRAM_METRICS, PROGRAM_PHASES
from .forms import InquiryForm, new_form_token, recent_inquiries_from, sender_hash
from .models import Car, Event, GalleryImage, Sponsor, SponsorshipTier, TeamMember


logger = logging.getLogger(__name__)

SENT_MESSAGE = "Thanks. Your message reached the team and we will reply by email."


def _group_by_choice(items, choices, field_name, include_empty=False):
    """Group an evaluated iterable without issuing one query per choice."""
    grouped = defaultdict(list)
    for item in items:
        grouped[getattr(item, field_name)].append(item)

    return [
        (key, label, grouped[key])
        for key, label in choices
        if include_empty or grouped[key]
    ]


@require_GET
def healthz(request):
    """Return a small readiness signal for the container and load balancer."""
    try:
        connection.ensure_connection()
    except DatabaseError:
        response = JsonResponse({"status": "unhealthy"}, status=503)
    else:
        response = JsonResponse({"status": "ok"})

    response["Cache-Control"] = "no-store"
    return response


def home(request):
    current_car = Car.objects.order_by("-is_current", "-season", "name").first()
    context = {
        "current_car": current_car,
        "sponsors": list(Sponsor.objects.filter(active=True)[:8]),
        "program_phases": PROGRAM_PHASES,
        "engineering_systems": ENGINEERING_SYSTEMS,
        "program_metrics": PROGRAM_METRICS,
    }
    return render(request, "team/home.html", context)


def roster(request):
    members = list(TeamMember.objects.filter(
        active=True, subteam__in=[key for key, _ in TeamMember.SUBTEAM_CHOICES],
    ).order_by("-is_lead", "sort_order", "name"))
    return render(request, "team/roster.html", {
        "grouped_members": _group_by_choice(members, TeamMember.SUBTEAM_CHOICES, "subteam", include_empty=True),
        "member_count": len(members),
    })


def cars(request):
    return render(request, "team/cars.html", {"cars": Car.objects.all()})


def car_detail(request, slug):
    car = get_object_or_404(Car, slug=slug)
    return render(request, "team/car_detail.html", {"car": car})


def sponsors(request):
    active_sponsors = list(Sponsor.objects.filter(active=True))
    return render(request, "team/sponsors.html", {
        "sponsor_groups": _group_by_choice(active_sponsors, Sponsor.TIER_CHOICES, "tier"),
        "sponsorship_tiers": list(SponsorshipTier.objects.filter(active=True)),
    })


def events(request):
    return render(request, "team/events.html", {"events": Event.objects.filter(is_public=True)})


def _static_url(path):
    try:
        return staticfiles_storage.url(path)
    except ValueError:
        # The manifest is created during the production image build. This
        # fallback keeps the gallery available in local test environments.
        return f"{settings.STATIC_URL}{path}"


def gallery(request):
    featured_images = [
        {
            **image,
            "image_url": _static_url(image["image_path"]),
            "srcset": ", ".join(f"{_static_url(path)} {width}w" for path, width in image["srcset_paths"]),
        }
        for image in FEATURED_GALLERY_IMAGES
    ]

    managed_images = list(GalleryImage.objects.filter(is_published=True))
    return render(request, "team/gallery.html", {"images": [*featured_images, *managed_images]})


def _notify_team(inquiry):
    """Email the team a copy. The inquiry is already saved, so a mail failure is only logged."""
    body = (
        f"{inquiry.name} <{inquiry.email}>\n"
        f"Organization: {inquiry.organization or '-'}\n"
        f"Topic: {inquiry.get_topic_display()}\n\n{inquiry.message}\n"
    )
    try:
        EmailMessage(
            subject=f"[Website] {inquiry.get_topic_display()}",
            body=body,
            to=[settings.TEAM_EMAIL],
            reply_to=[inquiry.email],
        ).send()
    except Exception:
        logger.exception("Could not email inquiry %s", inquiry.pk)


def contact(request):
    if request.method == "POST":
        form = InquiryForm(request.POST)
        sender = sender_hash(request)
        if form.is_valid():
            if form.looks_like_spam:
                # Look successful to bots without storing or forwarding anything.
                messages.success(request, SENT_MESSAGE)
                return redirect(f"{reverse('contact')}#inquiry-form")
            if recent_inquiries_from(sender) >= settings.INQUIRY_HOURLY_LIMIT:
                form.add_error(None, "Too many messages from your connection. Please email the team directly.")
            else:
                inquiry = form.save(commit=False)
                inquiry.sender_hash = sender
                inquiry.save()
                _notify_team(inquiry)
                messages.success(request, SENT_MESSAGE)
                return redirect(f"{reverse('contact')}#inquiry-form")
    else:
        topic = request.GET.get("topic")
        form = InquiryForm(initial={"topic": topic} if topic else None)
    return render(request, "team/contact.html", {"form": form, "form_token": new_form_token()})
