"""Orchestrate a Django layout scaffold from small, testable operations."""

from __future__ import annotations

from .asset_loader import render_asset
from .filesystem import apply_text_patch, write_if_missing
from .models import ProjectInfo
from .patchers import patch_home_view, patch_project_urls, patch_settings
from .project import ensure_app
from .reporting import Reporter


def scaffold(
    project: ProjectInfo,
    reporter: Reporter,
    *,
    integrate: bool = True,
) -> None:
    """Create layout assets and optionally integrate them into Django."""
    ensure_app(project, reporter)

    assets = {
        project.root / "templates" / "base.html": render_asset(
            "templates/base.html", app_namespace=project.app_name
        ),
        project.app_dir / "templates" / project.app_name / "index.html": render_asset(
            "templates/home/index.html"
        ),
        project.app_dir / "urls.py": render_asset(
            "python/urls.py", app_name=project.app_name
        ),
        project.root / "static" / "css" / "site.css": render_asset(
            "static/css/site.css"
        ),
    }

    for path, content in assets.items():
        write_if_missing(path, content, reporter)

    view_path = project.app_dir / "views.py"
    if view_path.exists():
        apply_text_patch(
            view_path,
            lambda source: patch_home_view(source, project.app_name),
            reporter,
        )
    else:
        write_if_missing(
            view_path,
            render_asset("python/views.py", app_name=project.app_name),
            reporter,
        )

    if not integrate:
        reporter.info("skipped settings and project URL integration")
        return

    if project.settings_py:
        apply_text_patch(
            project.settings_py,
            lambda source: patch_settings(source, project.app_name),
            reporter,
        )
    else:
        reporter.warning("could not detect settings.py; update it manually")

    if project.urls_py:
        apply_text_patch(
            project.urls_py,
            lambda source: patch_project_urls(source, project.app_name),
            reporter,
        )
    else:
        reporter.warning("could not detect project urls.py; update it manually")
