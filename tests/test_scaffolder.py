from __future__ import annotations

import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from django_layout_scaffolder.asset_loader import render_asset
from django_layout_scaffolder.errors import ScaffoldError
from django_layout_scaffolder.filesystem import write_if_missing
from django_layout_scaffolder.patchers import (
    patch_home_view,
    patch_project_urls,
    patch_settings,
)
from django_layout_scaffolder.project import discover_project, validate_app_name
from django_layout_scaffolder.reporting import Reporter
from django_layout_scaffolder.scaffolder import scaffold


class AssetTests(unittest.TestCase):
    def test_base_template_renders_app_namespace(self) -> None:
        template = render_asset("templates/base.html", app_namespace="home")

        self.assertIn("{% url 'home:index' %}", template)
        self.assertNotIn("__APP_NAMESPACE__", template)


class PatcherTests(unittest.TestCase):
    def test_settings_patch_is_idempotent(self) -> None:
        source = '''
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

INSTALLED_APPS = [
    "django.contrib.admin",
]

TEMPLATES = [{
    "DIRS": [],
}]

STATIC_URL = "static/"
'''

        first = patch_settings(source, "home")
        second = patch_settings(first.text, "home")

        self.assertIn('"home",', first.text)
        self.assertIn('"DIRS": [BASE_DIR / "templates"]', first.text)
        self.assertIn('STATICFILES_DIRS = [BASE_DIR / "static"]', first.text)
        self.assertEqual(first.text, second.text)

    def test_project_url_patch_adds_include_and_is_idempotent(self) -> None:
        source = '''
from django.contrib import admin
from django.urls import path

urlpatterns = [
    path("admin/", admin.site.urls),
]
'''

        first = patch_project_urls(source, "home")
        second = patch_project_urls(first.text, "home")

        self.assertIn("from django.urls import include, path", first.text)
        self.assertIn('path("", include("home.urls"))', first.text)
        self.assertEqual(first.text, second.text)

    def test_project_url_patch_respects_existing_root_route(self) -> None:
        source = 'from django.urls import path\n\nurlpatterns = [path("", existing)]\n'

        result = patch_project_urls(source, "home")

        self.assertEqual(result.text, source)
        self.assertTrue(result.warnings)

    def test_home_view_extends_a_fresh_startapp_file(self) -> None:
        result = patch_home_view("from django.shortcuts import render\n", "home")

        self.assertIn("def index(request):", result.text)
        self.assertIn('render(request, "home/index.html")', result.text)

    def test_home_view_does_not_overwrite_existing_logic(self) -> None:
        source = "from django.http import HttpResponse\n\ndef existing(request):\n    pass\n"

        result = patch_home_view(source, "home")

        self.assertEqual(result.text, source)
        self.assertTrue(result.warnings)


class ProjectTests(unittest.TestCase):
    def test_discovery_finds_standard_project_package(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            (root / "manage.py").write_text(
                "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')\n",
                encoding="utf-8",
            )

            project = discover_project(root, "home")

            self.assertEqual(project.project_package, "config")
            self.assertEqual(project.settings_py, root / "config" / "settings.py")
            self.assertEqual(project.urls_py, root / "config" / "urls.py")

    def test_invalid_app_name_is_rejected(self) -> None:
        with self.assertRaises(ScaffoldError):
            validate_app_name("not-a-python-package")

    def test_scaffold_wires_a_standard_project(self) -> None:
        with TemporaryDirectory() as directory:
            root = Path(directory)
            config = root / "config"
            app = root / "home"
            config.mkdir()
            app.mkdir()
            (root / "manage.py").write_text(
                "os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'config.settings')\n",
                encoding="utf-8",
            )
            (config / "settings.py").write_text(
                '''
from pathlib import Path
BASE_DIR = Path(__file__).resolve().parent.parent
INSTALLED_APPS = []
TEMPLATES = [{"DIRS": []}]
STATIC_URL = "static/"
''',
                encoding="utf-8",
            )
            (config / "urls.py").write_text(
                "from django.urls import path\n\nurlpatterns = []\n",
                encoding="utf-8",
            )
            (app / "views.py").write_text(
                "from django.shortcuts import render\n",
                encoding="utf-8",
            )

            project = discover_project(root, "home")
            scaffold(project, Reporter())

            self.assertTrue((root / "templates" / "base.html").exists())
            self.assertTrue((root / "static" / "css" / "site.css").exists())
            self.assertIn("def index(request):", (app / "views.py").read_text())
            self.assertIn('"home",', (config / "settings.py").read_text())
            self.assertIn('include("home.urls")', (config / "urls.py").read_text())


class FilesystemTests(unittest.TestCase):
    def test_write_if_missing_is_non_destructive(self) -> None:
        with TemporaryDirectory() as directory:
            path = Path(directory) / "nested" / "file.txt"
            reporter = Reporter()

            self.assertTrue(write_if_missing(path, "first", reporter))
            self.assertFalse(write_if_missing(path, "second", reporter))
            self.assertEqual(path.read_text(encoding="utf-8"), "first")


if __name__ == "__main__":
    unittest.main()
