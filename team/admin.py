from django.contrib import admin, messages
from django.utils.html import format_html

from .models import Car, Event, GalleryImage, Sponsor, SponsorshipTier, TeamMember


@admin.register(TeamMember)
class TeamMemberAdmin(admin.ModelAdmin):
    list_display = ("name", "role", "subteam", "year", "is_lead", "active")
    list_filter = ("subteam", "is_lead", "active")
    search_fields = ("name", "role", "bio")
    list_editable = ("subteam", "is_lead", "active")
    ordering = ("subteam", "-is_lead", "sort_order", "name")
    readonly_fields = ("previous_subteam",)
    actions = ["archive_members", "restore_members"]
    fieldsets = (
        ("Roster", {"fields": ("name", "role", "subteam", "is_lead", "active", "sort_order")}),
        ("Profile", {"fields": ("year", "joined_year", "bio", "photo_url")}),
        ("Migration reference", {"fields": ("previous_subteam",), "classes": ("collapse",)}),
    )

    @admin.action(description="Archive selected members (hide from the roster, keep their record)")
    def archive_members(self, request, queryset):
        self.message_user(request, f"{queryset.update(active=False)} member(s) archived.", messages.SUCCESS)

    @admin.action(description="Restore selected members to the roster")
    def restore_members(self, request, queryset):
        self.message_user(request, f"{queryset.update(active=True)} member(s) restored.", messages.SUCCESS)

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
    list_display = ("name", "season", "is_current")
    list_filter = ("is_current", "season")
    prepopulated_fields = {"slug": ("name", "season")}
    search_fields = ("name", "tagline", "description")
    fieldsets = (
        ("Shown on the website", {
            "fields": ("name", "season", "slug", "is_current"),
            "description": "The name and season appear on the car pages and the home page. "
                           "Ticking <b>current</b> makes this the featured car and clears it on every other car.",
        }),
        ("Kept for later (not shown yet)", {
            "fields": ("tagline", "description", "image_url", "top_speed", "acceleration",
                       "peak_power", "accumulator", "chassis", "featured"),
            "classes": ("collapse",),
            "description": "The public car pages do not show these yet, so you can leave them empty.",
        }),
    )

    def get_form(self, request, obj=None, **kwargs):
        form = super().get_form(request, obj, **kwargs)
        # Fields the site does not display should not block saving.
        for name in ("tagline", "description"):
            form.base_fields[name].required = False
        return form


@admin.register(Sponsor)
class SponsorAdmin(admin.ModelAdmin):
    list_display = ("logo", "name", "tier", "active", "sort_order")
    list_display_links = ("logo", "name")
    list_filter = ("tier", "active")
    list_editable = ("tier", "active", "sort_order")
    search_fields = ("name", "description")
    actions = ["show_on_site", "hide_from_site"]

    @admin.display(description="Logo")
    def logo(self, obj):
        if not obj.logo_url:
            return "-"
        return format_html('<img src="{}" alt="" height="28">', obj.logo_url)

    @admin.action(description="Show selected sponsors on the site")
    def show_on_site(self, request, queryset):
        self.message_user(request, f"{queryset.update(active=True)} sponsor(s) are now shown.", messages.SUCCESS)

    @admin.action(description="Hide selected sponsors from the site")
    def hide_from_site(self, request, queryset):
        self.message_user(request, f"{queryset.update(active=False)} sponsor(s) are now hidden.", messages.SUCCESS)


@admin.register(SponsorshipTier)
class SponsorshipTierAdmin(admin.ModelAdmin):
    list_display = ("name", "amount", "badge", "sort_order", "active")
    list_editable = ("sort_order", "active")
    list_filter = ("active",)
    search_fields = ("name", "badge", "amount")
    fieldsets = (
        ("Package", {"fields": ("name", "amount", "badge", "sort_order", "active")}),
        ("Rows in the sponsorship comparison table", {
            "fields": ("logo_size", "website_recognition", "social_media_recognition",
                       "progress_updates", "event_invitations", "recruiting", "merchandise"),
            "description": "Each field is one row of the table on the Sponsor page. "
                           "An empty row shows \u201cSee the full proposal\u201d.",
        }),
        ("Kept for later (not shown yet)", {
            "fields": ("social_posts", "school_tour", "logo_on_merch"),
            "classes": ("collapse",),
            "description": "The sponsor page does not show these yet.",
        }),
    )


@admin.register(Event)
class EventAdmin(admin.ModelAdmin):
    list_display = ("title", "date", "location", "is_public")
    list_filter = ("is_public", "date")
    search_fields = ("title", "location", "description")


@admin.register(GalleryImage)
class GalleryImageAdmin(admin.ModelAdmin):
    list_display = ("thumbnail", "title", "published_at", "is_published")
    list_display_links = ("thumbnail", "title")
    list_filter = ("is_published",)
    list_editable = ("is_published",)
    search_fields = ("title", "caption", "alt_text")

    @admin.display(description="Photo")
    def thumbnail(self, obj):
        return format_html('<img src="{}" alt="" height="40">', obj.image_url)


admin.site.site_header = "Electric Sting site admin"
admin.site.site_title = "Electric Sting admin"
admin.site.index_title = "Edit the team website"
