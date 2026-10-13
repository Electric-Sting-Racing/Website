from django.contrib.sitemaps.views import sitemap
from django.urls import path

from . import views
from .seo import SITEMAPS, robots_txt


urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("robots.txt", robots_txt, name="robots-txt"),
    path("sitemap.xml", sitemap, {"sitemaps": SITEMAPS}, name="sitemap"),
    path("", views.home, name="home"),
    path("team/", views.roster, name="roster"),
    path("cars/", views.cars, name="cars"),
    path("cars/<slug:slug>/", views.car_detail, name="car-detail"),
    path("sponsors/", views.sponsors, name="sponsors"),
    path("events/", views.events, name="events"),
    path("gallery/", views.gallery, name="gallery"),
    path("contact/", views.contact, name="contact"),
]
