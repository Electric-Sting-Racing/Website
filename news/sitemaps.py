from django.contrib.sitemaps import Sitemap

from .models import Post


class PostSitemap(Sitemap):
    def items(self):
        return Post.objects.live()

    def lastmod(self, item):
        return item.updated_at
