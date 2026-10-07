from django.contrib import admin, messages

from .models import Car, Event, GalleryImage, Sponsor, SponsorshipTier, TeamMember


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "subteam", "year", "is_lead", "active")
    list_filter = ("subteam", "is_lead", "active")
    search_fields = ("name", "role", "bio")
    list_editable = ("subteam", "is_lead", "active")
    ordering = ("subteam", "-is_lead", "sort_order", "name")
    readonly_fields = ("previous_subteam",)
    fieldsets = (
        ("Roster", {"fields": ("name", "role", "subteam", "is_lead", "active", "sort_order")}),
        ("Profile", {"fields": ("year", "joined_year", "bio", "photo_url")}),
        ("Migration reference", {"fields": ("previous_subteam",), "classes": ("collapse",)}),
    )

    def changelist_view(self, request, extra_context=None):
        if request.method == "GET":
            count = self.get_queryset(request).filter(subteam="").count()
            if count:
                self.message_user(
                    request,
                    f"{count} member(s) need a section assignment before appearing on the roster. "
                    "Their profiles and lead settings have been preserved. Check Migration reference for the old section.",
                    level=messages.WARNING,
                )
        return super().changelist_view(request, extra_context)


@admin.register(Car)
class CarAdmin(admin.ModelAdmin):
    list_display = ("name", "season", "is_current", "featured")
    list_filter = ("is_current", "featured", "season")
    prepopulated_fields = {"slug": ("name", "season")}
    search_fields = ("name", "tagline", "description")


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    list_display = ("name", "tier", "active", "sort_order")
    list_filter = ("tier", "active")
    search_fields = ("name", "description")


@admin.register(SponsorshipTier)
class SponsorshipTierAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "badge", "sort_order", "active")
    list_filter = ("active", "school_tour", "logo_on_merch")
    search_fields = ("name", "badge", "amount")


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "location", "is_public")
    list_filter = ("is_public", "date")
    search_fields = ("title", "location", "description")


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ("title", "published_at", "is_published")
    list_filter = ("is_published",)
    search_fields = ("title", "caption", "alt_text")
