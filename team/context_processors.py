from django.conf import settings
from django.templatetags.static import static


def branding(request):
    return {
        "site_name": settings.TEAM_NAME,
        "school_name": settings.TEAM_SCHOOL,
        "team_location": settings.TEAM_LOCATION,
        "team_email": settings.TEAM_EMAIL,
        "team_season": settings.TEAM_SEASON,
        "canonical_url": request.build_absolute_uri(request.path),
        "og_image_url": request.build_absolute_uri(static("images/og-image.jpg")),
    }
