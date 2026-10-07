from django.db import models
from django.urls import reverse


class TeamMember(models.Model):
    SUBTEAM_CHOICES = [
        ("high_voltage", "High Voltage"),
        ("powertrain", "Powertrain"),
        ("low_voltage_controls", "Low Voltage/Controls"),
        ("frame", "Frame"),
        ("suspensions", "Suspensions"),
    ]

    name = models.CharField(max_length=120)
    role = models.CharField(max_length=120)
    subteam = models.CharField(
        "section", max_length=24, choices=SUBTEAM_CHOICES, blank=True, default="",
        help_text="Choose a section to publish this member on the roster. Unassigned members remain in admin.",
    )
    previous_subteam = models.CharField(
        max_length=24, blank=True, editable=False,
        help_text="Original section preserved during the five-section upgrade for reference.",
    )
    year = models.CharField(max_length=32, blank=True, help_text="e.g. Class of 2027")
    bio = models.TextField(blank=True)
    photo_url = models.URLField(blank=True)
    joined_year = models.PositiveIntegerField(null=True, blank=True)
    is_lead = models.BooleanField(
        "section lead", default=False,
        help_text="Show a Section lead badge and list this member first. Multiple co-leads are supported.",
    )
    active = models.BooleanField(default=True)
    sort_order = models.PositiveIntegerField(default=0)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "team member"
        verbose_name_plural = "team members"

    def __str__(self):
        return f"{self.name} — {self.role}"


class Car(models.Model):
    name = models.CharField(max_length=80)
    season = models.CharField(max_length=32, help_text="e.g. 2026")
    slug = models.SlugField(unique=True)
    tagline = models.CharField(max_length=180)
    description = models.TextField()
    image_url = models.URLField(blank=True)
    top_speed = models.CharField(max_length=40, blank=True)
    acceleration = models.CharField(max_length=40, blank=True, help_text="e.g. 0–60 mph")
    peak_power = models.CharField(max_length=40, blank=True)
    accumulator = models.CharField(max_length=60, blank=True)
    chassis = models.CharField(max_length=80, blank=True)
    featured = models.BooleanField(default=False)
    is_current = models.BooleanField(default=False)

    class Meta:
        ordering = ["-season", "-is_current", "name"]

    def __str__(self):
        return f"{self.name} ({self.season})"

    def get_absolute_url(self):
        return reverse("car-detail", kwargs={"slug": self.slug})


class Sponsor(models.Model):
    TIER_CHOICES = [
        ("champion", "Champion"),
        ("builder", "Builder"),
        ("partner", "Partner"),
        ("supporter", "Supporter"),
    ]

    name = models.CharField(max_length=120)
    tier = models.CharField(max_length=20, choices=TIER_CHOICES, default="partner")
    website = models.URLField(blank=True)
    logo_url = models.URLField(blank=True)
    description = models.CharField(max_length=240, blank=True)
    sort_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["tier", "sort_order", "name"]

    def __str__(self):
        return self.name


class SponsorshipTier(models.Model):
    """A package a prospective sponsor can understand at a glance."""

    name = models.CharField(max_length=80)
    amount = models.CharField(max_length=40, help_text="e.g. $500+")
    badge = models.CharField(max_length=80, help_text="e.g. Bronze Leaf")
    social_posts = models.CharField(max_length=20, default="1")
    logo_size = models.CharField(max_length=40, default="Small")
    school_tour = models.BooleanField(default=False)
    logo_on_merch = models.BooleanField(default=False)
    sort_order = models.PositiveIntegerField(default=0)
    active = models.BooleanField(default=True)

    class Meta:
        ordering = ["sort_order", "name"]
        verbose_name = "sponsorship tier"
        verbose_name_plural = "sponsorship tiers"

    def __str__(self):
        return f"{self.name} — {self.amount}"


class Event(models.Model):
    title = models.CharField(max_length=180)
    date = models.DateField()
    time = models.CharField(max_length=40, blank=True)
    location = models.CharField(max_length=180)
    description = models.TextField(blank=True)
    registration_url = models.URLField(blank=True)
    is_public = models.BooleanField(default=True)

    class Meta:
        ordering = ["date", "title"]

    def __str__(self):
        return f"{self.title} — {self.date}"


class GalleryImage(models.Model):
    title = models.CharField(max_length=160)
    caption = models.CharField(max_length=240, blank=True)
    image_url = models.URLField()
    alt_text = models.CharField(max_length=180)
    published_at = models.DateTimeField(auto_now_add=True)
    is_published = models.BooleanField(default=True)

    class Meta:
        ordering = ["-published_at"]

    def __str__(self):
        return self.title
