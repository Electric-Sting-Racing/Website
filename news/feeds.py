from django.conf import settings
from django.contrib.syndication.views import Feed
from django.urls import reverse

from .models import Post


class LatestPostsFeed(Feed):
    description = "News from the build."

    def title(self):
        return f"{settings.TEAM_NAME.title()} news"

    def link(self):
        return reverse("news")

    def items(self):
        return Post.objects.live()[:20]

    def item_title(self, item):
        return item.title

    def item_description(self, item):
        return item.summary

    def item_pubdate(self, item):
        return item.published_at

    def item_updateddate(self, item):
        return item.updated_at

    def item_author_name(self, item):
        return item.author_name or None
