from collections import defaultdict

from django.conf import settings
from django.contrib.staticfiles.storage import staticfiles_storage
from django.db import DatabaseError, connection
from django.http import JsonResponse
from django.shortcuts import get_object_or_404, render
from django.views.decorators.http import require_GET

from .content import ENGINEERING_SYSTEMS, FEATURED_GALLERY_IMAGES, PROGRAM_METRICS, PROGRAM_PHASES
from .models import Car, Event, GalleryImage, Sponsor, SponsorshipTier, TeamMember


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


def gallery(request):
    try:
        featured_images = [
            {
                **image,
                "image_url": staticfiles_storage.url(image["image_path"]),
            }
            for image in FEATURED_GALLERY_IMAGES
        ]
    except ValueError:
        # The manifest is created during the production image build. This
        # fallback keeps the gallery available in local test environments.
        featured_images = [
            {
                **image,
                "image_url": f"{settings.STATIC_URL}{image['image_path']}",
            }
            for image in FEATURED_GALLERY_IMAGES
        ]

    managed_images = list(GalleryImage.objects.filter(is_published=True))
    return render(request, "team/gallery.html", {"images": [*featured_images, *managed_images]})


def contact(request):
    return render(request, "team/contact.html")
