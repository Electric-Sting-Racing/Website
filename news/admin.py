from django.contrib import admin, messages
from django.forms import Textarea
from django.utils import timezone
from django.utils.html import format_html

from .models import Post

CHEAT_SHEET = format_html(
    "<p><b>Writing tips.</b> Leave a blank line between paragraphs. "
    "<code># Heading</code> starts a section and <code>## Subheading</code> a smaller one "
    "(the post title is already the page title). <code>**bold**</code> and <code>*italic*</code> style text. "
    "Start lines with <code>- </code> for a bullet list or <code>1. </code> for a numbered one. "
    "<code>[link text](https://example.com)</code> makes a link. "
    "<code>![what the photo shows](https://example.com/photo.jpg)</code> adds a photo from the web. "
    "<code>&gt; </code> at the start of a line quotes someone.</p>"
    "<p>Use <b>Save and continue editing</b>, then <b>Preview</b> below to see it as visitors will. "
    "A post stays hidden until <b>Published</b> is ticked and its date has arrived.</p>"
)


@admin.register(Post)
class PostAdmin(admin.ModelAdmin):
    list_display = ("title", "status", "published_at", "author_name")
    list_filter = ("is_published",)
    search_fields = ("title", "summary", "body")
    date_hierarchy = "published_at"
    prepopulated_fields = {"slug": ("title",)}
    readonly_fields = ("preview",)
    actions = ["publish_now", "unpublish"]

    class Media:
        css = {"all": ("css/news-admin.css",)}

    fieldsets = (
        (None, {"fields": ("title", "slug", "summary")}),
        ("Content", {"fields": ("body", "preview"), "description": CHEAT_SHEET}),
        ("Photo", {"fields": ("cover_image_url", "cover_image_alt")}),
        ("Publishing", {"fields": ("author_name", "is_published", "published_at")}),
    )

    def formfield_for_dbfield(self, db_field, request, **kwargs):
        field = super().formfield_for_dbfield(db_field, request, **kwargs)
        if db_field.name == "body":
            field.widget = Textarea(attrs={"rows": 24, "class": "vLargeTextField"})
        return field

    @admin.display(description="Status", ordering="is_published")
    def status(self, obj):
        return obj.status

    @admin.display(description="Preview")
    def preview(self, obj):
        if not obj or not obj.pk:
            return "Save the post first, then reopen it to see a preview here."
        return format_html(
            '<p><a href="{}" target="_blank" rel="noopener">Open the full page in a new tab</a>'
            '{}</p><hr><div class="news-preview-pane">{}</div>',
            obj.get_absolute_url(),
            "" if obj.is_live else " (only staff can see it until it is published)",
            obj.body_html,
        )

    @admin.action(description="Publish selected posts now")
    def publish_now(self, request, queryset):
        now = timezone.now()
        # update() skips auto_now, and the sitemap and feed read updated_at.
        count = queryset.update(is_published=True, published_at=now, updated_at=now)
        self.message_user(request, f"Published {count} post(s).", messages.SUCCESS)

    @admin.action(description="Move selected posts back to drafts")
    def unpublish(self, request, queryset):
        count = queryset.update(is_published=False, updated_at=timezone.now())
        self.message_user(request, f"{count} post(s) are drafts again.", messages.SUCCESS)
