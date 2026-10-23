from django.conf import settings
from django.db import DatabaseError
from django.templatetags.static import static

from .models import Sponsor
from .seo import organization_jsonld, page_meta


def _featured_sponsors():
    # Sitewide credit must never take a page down if the database is unavailable.
    try:
        return list(Sponsor.objects.filter(active=True)[:6])
    except DatabaseError:
        return []


def _home_jsonld(request):
    match = getattr(request, "resolver_match", None)
    if not match or match.url_name != "home":
        return ""
    return organization_jsonld(request, settings.TEAM_NAME, settings.TEAM_SCHOOL, settings.TEAM_EMAIL)


def branding(request):
    return {
        "organization_jsonld": _home_jsonld(request),
        "featured_sponsors": _featured_sponsors(),
        **page_meta(request, settings.TEAM_NAME),
        "site_name": settings.TEAM_NAME,
        "school_name": settings.TEAM_SCHOOL,
        "team_location": settings.TEAM_LOCATION,
        "team_email": settings.TEAM_EMAIL,
        "team_season": settings.TEAM_SEASON,
        "canonical_url": request.build_absolute_uri(request.path),
        "og_image_url": request.build_absolute_uri(static("images/og-image.jpg")),
    }
