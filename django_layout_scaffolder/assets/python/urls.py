from django.urls import path

from . import views


app_name = "__APP_NAME__"

urlpatterns = [
    path("", views.index, name="index"),
]
