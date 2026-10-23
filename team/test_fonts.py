import re

from django.contrib.staticfiles import finders
from django.test import TestCase, override_settings

STORAGES = {
    "default": {"BACKEND": "django.core.files.storage.FileSystemStorage"},
    "staticfiles": {"BACKEND": "django.contrib.staticfiles.storage.StaticFilesStorage"},
}


@override_settings(STORAGES=STORAGES)
class SelfHostedFontTests(TestCase):
    def test_every_font_face_file_exists(self):
        css_path = finders.find("css/site-v5.css")
        with open(css_path, encoding="utf-8") as handle:
            css = handle.read()
        urls = re.findall(r"@font-face[^}]*url\('\.\./(fonts/[^']+)'\)", css)
        self.assertEqual(len(urls), 7)
        for url in urls:
            self.assertTrue(finders.find(url), f"{url} is referenced but missing")

    def test_pages_load_no_third_party_font_hosts(self):
        for name in ("/", "/team/", "/sponsors/", "/contact/"):
            html = self.client.get(name).content.decode()
            self.assertNotIn("fonts.googleapis.com", html, name)
            self.assertNotIn("fonts.gstatic.com", html, name)
            self.assertEqual(html.count('rel="preload"'), 3, name)
            self.assertIn("/static/fonts/SpaceGrotesk-var-latin.woff2", html, name)
