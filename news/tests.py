from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import Client, TestCase, override_settings
from django.urls import reverse
from django.utils import timezone

from .markup import render_markdown
from .models import Post

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


def make_post(slug="first", **overrides):
    data = {
        "title": f"Post {slug}",
        "slug": slug,
        "summary": f"Summary for {slug}.",
        "body": "Hello **team**.",
        "is_published": True,
        "published_at": timezone.now() - timedelta(hours=1),
    }
    data.update(overrides)
    return Post.objects.create(**data)


class MarkdownTests(TestCase):
    def test_basic_formatting(self):
        html = render_markdown("Hello **bold** and *italic*.\n\n- one\n- two")
        self.assertIn("<strong>bold</strong>", html)
        self.assertIn("<em>italic</em>", html)
        self.assertIn("<ul>", html)

    def test_headings_start_at_h2_because_the_title_is_the_h1(self):
        html = render_markdown("# Section\n\n## Subsection")
        self.assertNotIn("<h1", html)
        self.assertEqual(html.count("<h2"), 1)
        self.assertEqual(html.count("<h3"), 1)

    def test_scripts_handlers_and_dangerous_links_are_removed(self):
        html = render_markdown(
            "<script>alert(1)</script>\n\n"
            '<img src="https://x.example/a.jpg" onerror="alert(2)">\n\n'
            "[click](javascript:alert(3))\n\n"
            '<iframe src="https://evil.example"></iframe>\n\n'
            '<a href="data:text/html;base64,AAAA">d</a>'
        )
        for bad in ("<script", "onerror", "javascript:", "<iframe", "data:text"):
            self.assertNotIn(bad, html)

    def test_links_get_rel_and_images_load_lazily(self):
        html = render_markdown("[site](https://example.com) ![alt text](https://example.com/p.jpg)")
        self.assertIn('rel="noopener noreferrer"', html)
        self.assertIn('loading="lazy"', html)
        self.assertIn('alt="alt text"', html)

    def test_relative_and_mailto_links_survive(self):
        html = render_markdown("[a](/team/) [b](mailto:team@example.com)")
        self.assertIn('href="/team/"', html)
        self.assertIn('href="mailto:team@example.com"', html)

    def test_empty_body_is_fine(self):
        self.assertEqual(render_markdown(""), "")


@override_settings(STORAGES=STORAGES)
class PublicViewTests(TestCase):
    def test_list_shows_only_live_posts_newest_first(self):
        make_post("older", published_at=timezone.now() - timedelta(days=2))
        make_post("newer")
        make_post("draft", is_published=False)
        make_post("later", published_at=timezone.now() + timedelta(days=1))
        html = self.client.get(reverse("news")).content.decode()
        self.assertLess(html.index("Post newer"), html.index("Post older"))
        self.assertNotIn("Post draft", html)
        self.assertNotIn("Post later", html)

    def test_empty_list_has_a_friendly_message(self):
        self.assertContains(self.client.get(reverse("news")), "No updates yet")

    def test_list_is_paginated(self):
        for number in range(11):
            make_post(f"p{number}", published_at=timezone.now() - timedelta(minutes=number))
        first = self.client.get(reverse("news"))
        self.assertContains(first, "Older")
        self.assertContains(self.client.get(reverse("news"), {"page": 2}), "Newer")
        self.assertEqual(self.client.get(reverse("news"), {"page": "junk"}).status_code, 200)

    def test_detail_renders_markdown_and_its_own_link_preview(self):
        post = make_post(summary="A short summary.", body="# Section\n\nText here.")
        response = self.client.get(post.get_absolute_url())
        self.assertContains(response, "<h2")
        self.assertContains(response, "Text here.")
        self.assertContains(response, 'property="og:title" content="Post first | ELECTRIC STING RACING"')
        self.assertContains(response, 'name="description" content="A short summary."')
        self.assertNotContains(response, "noindex")

    def test_draft_and_scheduled_posts_are_hidden_from_visitors(self):
        draft = make_post("draft", is_published=False)
        later = make_post("later", published_at=timezone.now() + timedelta(days=1))
        for post in (draft, later):
            self.assertEqual(self.client.get(post.get_absolute_url()).status_code, 404)

    def test_staff_can_preview_unpublished_posts_without_indexing(self):
        draft = make_post("draft", is_published=False)
        staff = get_user_model().objects.create_user("staff", password="long-staff-password", is_staff=True)
        client = Client()
        client.force_login(staff)
        response = client.get(draft.get_absolute_url())
        self.assertContains(response, "Preview: draft")
        self.assertContains(response, 'name="robots" content="noindex"')

    def test_non_staff_users_cannot_preview(self):
        draft = make_post("draft", is_published=False)
        user = get_user_model().objects.create_user("member", password="long-member-password")
        client = Client()
        client.force_login(user)
        self.assertEqual(client.get(draft.get_absolute_url()).status_code, 404)

    def test_unknown_slug_is_404(self):
        self.assertEqual(self.client.get("/news/nope/").status_code, 404)

    def test_posts_cannot_inject_script_into_the_page(self):
        post = make_post(body="<script>alert(1)</script>Safe text")
        html = self.client.get(post.get_absolute_url()).content.decode()
        self.assertNotIn("alert(1)", html)
        self.assertIn("Safe text", html)

    def test_navigation_links_to_news(self):
        self.assertContains(self.client.get("/"), f'href="{reverse("news")}"')


@override_settings(STORAGES=STORAGES)
class DiscoveryTests(TestCase):
    def test_sitemap_lists_live_posts_only(self):
        live = make_post("live")
        make_post("draft", is_published=False)
        sitemap = self.client.get("/sitemap.xml").content.decode()
        self.assertIn(f"http://testserver{live.get_absolute_url()}", sitemap)
        self.assertNotIn("/news/draft/", sitemap)
        self.assertIn("http://testserver/news/", sitemap)

    def test_feed_lists_live_posts(self):
        make_post("live", summary="Live summary.")
        make_post("draft", is_published=False)
        response = self.client.get(reverse("news-feed"))
        self.assertEqual(response["Content-Type"], "application/rss+xml; charset=utf-8")
        self.assertContains(response, "Live summary.")
        self.assertNotContains(response, "Post draft")

    def test_each_archive_page_has_its_own_canonical_url(self):
        for number in range(11):
            make_post(f"p{number}", published_at=timezone.now() - timedelta(minutes=number))
        first = self.client.get(reverse("news")).content.decode()
        second = self.client.get(reverse("news"), {"page": 2}).content.decode()
        self.assertIn('<link rel="canonical" href="http://testserver/news/">', first)
        self.assertIn('<link rel="canonical" href="http://testserver/news/?page=2">', second)
        self.assertIn('property="og:url" content="http://testserver/news/?page=2"', second)

    def test_list_page_advertises_the_feed(self):
        self.assertContains(self.client.get(reverse("news")), 'type="application/rss+xml"')


@override_settings(STORAGES=STORAGES)
class AdminTests(TestCase):
    def setUp(self):
        self.admin = get_user_model().objects.create_superuser("root", password="long-root-password")
        self.client.force_login(self.admin)

    def test_add_form_shows_the_writing_tips(self):
        response = self.client.get("/admin/news/post/add/")
        self.assertContains(response, "Writing tips")
        self.assertContains(response, "Leave a blank line between paragraphs")

    def test_new_posts_default_to_draft(self):
        response = self.client.get("/admin/news/post/add/")
        self.assertContains(response, 'name="is_published"')
        self.assertNotContains(response, 'name="is_published" checked')

    def test_change_form_shows_a_sanitized_preview(self):
        post = make_post(body="Hi <script>alert(1)</script> there")
        response = self.client.get(f"/admin/news/post/{post.pk}/change/")
        self.assertContains(response, "Open the full page in a new tab")
        self.assertNotContains(response, "<script>alert(1)")

    def test_publish_and_unpublish_actions(self):
        draft = make_post("draft", is_published=False, published_at=timezone.now() - timedelta(days=5))
        url = "/admin/news/post/"
        self.client.post(url, {"action": "publish_now", "_selected_action": [draft.pk]})
        draft.refresh_from_db()
        self.assertTrue(draft.is_live)
        self.assertGreater(draft.updated_at, timezone.now() - timedelta(minutes=1))
        self.client.post(url, {"action": "unpublish", "_selected_action": [draft.pk]})
        draft.refresh_from_db()
        self.assertEqual(draft.status, "Draft")

    def test_changelist_shows_status(self):
        make_post("later", published_at=timezone.now() + timedelta(days=1))
        self.assertContains(self.client.get("/admin/news/post/"), "Scheduled")
