from django.conf import settings
from django.core.paginator import Paginator
from django.http import Http404
from django.shortcuts import get_object_or_404, render

from .models import Post

PAGE_SIZE = 9


def news_list(request):
    page = Paginator(Post.objects.live(), PAGE_SIZE).get_page(request.GET.get("page"))
    return render(request, "news/list.html", {"page": page})


def news_detail(request, slug):
    post = get_object_or_404(Post, slug=slug)
    # Staff may open drafts and scheduled posts to check them before visitors can.
    preview = not post.is_live
    if preview and not (request.user.is_authenticated and request.user.is_staff):
        raise Http404("No post matches the given query.")
    return render(request, "news/detail.html", {
        "post": post,
        "preview": preview,
        # View context overrides the site-wide defaults, giving each post its own link preview.
        "og_title": f"{post.title} | {settings.TEAM_NAME}",
        "meta_description": post.summary,
    })
