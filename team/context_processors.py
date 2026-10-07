from django.conf import settings


def branding(request):
    return {
        "site_name": settings.TEAM_NAME,
        "school_name": settings.TEAM_SCHOOL,
        "team_location": settings.TEAM_LOCATION,
        "team_email": settings.TEAM_EMAIL,
        "team_season": settings.TEAM_SEASON,
    }
