from django.urls import path

from . import views
from .feeds import LatestPostsFeed

urlpatterns = [
    path("news/", views.news_list, name="news"),
    path("news/feed.xml", LatestPostsFeed(), name="news-feed"),
    path("news/<slug:slug>/", views.news_detail, name="news-detail"),
]
