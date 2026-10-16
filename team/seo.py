from django.contrib.sitemaps import Sitemap
from django.http import HttpResponse
from django.urls import reverse
from django.views.decorators.http import require_GET

from .models import Car


class StaticPageSitemap(Sitemap):
    def items(self):
        return ["home", "roster", "cars", "sponsors", "events", "gallery", "contact"]

    def location(self, item):
        return reverse(item)


class CarSitemap(Sitemap):
    def items(self):
        return Car.objects.all()


SITEMAPS = {"pages": StaticPageSitemap, "cars": CarSitemap}

DEFAULT_DESCRIPTION = "{site_name} — a student-built electric Formula SAE team."

# Per-page link preview and search snippet text, keyed by URL name.
PAGE_META = {
    "roster": ("The team", "Meet the students building Sacramento State's first electric Formula SAE car."),
    "cars": ("Car in development", "Our first electric formula car is still in design. See the plan and how the build will progress."),
    "car-detail": ("Car in development", "Our first electric formula car is still in design. See the plan and how the build will progress."),
    "sponsors": ("Sponsor Electric Sting", "Sponsorship packages, benefits, and current partners for the Electric Sting Racing build."),
    "events": ("Events", "Design reviews, test days, and recruitment events open to the public."),
    "gallery": ("Gallery", "Photos of the people, tools, and small victories behind each build."),
    "contact": ("Join the build", "Join the team, partner with us, or ask a question. No racing experience required."),
}


def page_meta(request, site_name):
    """Return link-preview title and description for the page being rendered."""
    match = getattr(request, "resolver_match", None)
    label, description = PAGE_META.get(match.url_name if match else None, (None, None))
    return {
        "og_title": f"{label} | {site_name}" if label else f"{site_name} | Electric Formula SAE",
        "meta_description": description or DEFAULT_DESCRIPTION.format(site_name=site_name),
    }


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
