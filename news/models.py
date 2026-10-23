from django.db import models
from django.urls import reverse
from django.utils import timezone

from .markup import render_markdown


class PostQuerySet(models.QuerySet):
    def live(self):
        """Posts visitors can see: published, and not scheduled for later."""
        return self.filter(is_published=True, published_at__lte=timezone.now())


class Post(models.Model):
    title = models.CharField(max_length=160)
    slug = models.SlugField(
        unique=True, max_length=120,
        help_text="The web address of the post. Filled in from the title; change it only before publishing.",
    )
    summary = models.CharField(
        max_length=240, help_text="One or two sentences shown in the news list and in link previews.",
    )
    body = models.TextField(help_text="Write in Markdown. The cheat sheet above the box shows the basics.")
    cover_image_url = models.URLField(blank=True, help_text="Optional https link to a photo for the top of the post.")
    cover_image_alt = models.CharField(
        max_length=180, blank=True, help_text="Describe the photo for people who cannot see it.",
    )
    author_name = models.CharField(max_length=80, blank=True, help_text="For example: Aero team, or your name.")
    is_published = models.BooleanField(
        "published", default=False, help_text="Leave unticked to keep working on it. Only staff can see drafts.",
    )
    published_at = models.DateTimeField(
        default=timezone.now,
        help_text="Choose a future time to schedule the post; it appears on its own once that time arrives.",
    )
    updated_at = models.DateTimeField(auto_now=True)

    objects = PostQuerySet.as_manager()

    class Meta:
        ordering = ["-published_at", "-id"]

    def __str__(self):
        return self.title

    def get_absolute_url(self):
        return reverse("news-detail", kwargs={"slug": self.slug})

    @property
    def is_live(self):
        return self.is_published and self.published_at <= timezone.now()

    @property
    def status(self):
        if not self.is_published:
            return "Draft"
        return "Published" if self.is_live else "Scheduled"

    @property
    def body_html(self):
        return render_markdown(self.body)
