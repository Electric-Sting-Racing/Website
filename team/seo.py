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


@require_GET
def robots_txt(request):
    lines = [
        "User-agent: *",
        "Disallow: /admin/",
        f"Sitemap: {request.build_absolute_uri(reverse('sitemap'))}",
    ]
    return HttpResponse("\n".join(lines) + "\n", content_type="text/plain")
