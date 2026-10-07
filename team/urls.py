from django.urls import path

from . import views


urlpatterns = [
    path("healthz/", views.healthz, name="healthz"),
    path("", views.home, name="home"),
    path("team/", views.roster, name="roster"),
    path("cars/", views.cars, name="cars"),
    path("cars/<slug:slug>/", views.car_detail, name="car-detail"),
    path("sponsors/", views.sponsors, name="sponsors"),
    path("events/", views.events, name="events"),
    path("gallery/", views.gallery, name="gallery"),
    path("contact/", views.contact, name="contact"),
]
