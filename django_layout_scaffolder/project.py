"""Django project discovery and app creation."""

from __future__ import annotations

import re
import subprocess
import sys
from pathlib import Path

from .errors import ScaffoldError
from .models import ProjectInfo
from .reporting import Reporter


APP_NAME_PATTERN = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*$")
SETTINGS_MODULE_PATTERN = re.compile(
    r"DJANGO_SETTINGS_MODULE\s*['\"]?\s*,\s*['\"]([\w.]+)\.settings"
)


def validate_app_name(app_name: str) -> None:
    """Reject names that cannot safely be a Python/Django app package."""
    if not APP_NAME_PATTERN.fullmatch(app_name):
        raise ScaffoldError(
            f"invalid app name {app_name!r}; use a Python identifier such as 'home'"
        )


def detect_project_package(manage_py: Path) -> str | None:
    """Infer the Django project package from ``manage.py``."""
    if not manage_py.exists():
        return None

    source = manage_py.read_text(encoding="utf-8")
    match = SETTINGS_MODULE_PATTERN.search(source)
    return match.group(1) if match else None


def discover_project(project_root: str | Path, app_name: str) -> ProjectInfo:
    """Find the files a scaffold run can safely operate on."""
    validate_app_name(app_name)
    root = Path(project_root).expanduser().resolve()
    manage_py = root / "manage.py"
    if not manage_py.is_file():
        raise ScaffoldError(
            f"{manage_py} was not found; run this from an existing Django project"
        )

    package = detect_project_package(manage_py)
    settings_py = urls_py = None
    if package:
        package_path = root / Path(*package.split("."))
        settings_py = package_path / "settings.py"
        urls_py = package_path / "urls.py"

    return ProjectInfo(
        root=root,
        app_name=app_name,
        manage_py=manage_py,
        project_package=package,
        settings_py=settings_py,
        urls_py=urls_py,
    )


def ensure_app(project: ProjectInfo, reporter: Reporter) -> None:
    """Create the app with Django's own command when it is missing."""
    if project.app_dir.exists():
        return

    command = [sys.executable, str(project.manage_py), "startapp", project.app_name]
    if reporter.dry_run:
        reporter.info("would run: " + " ".join(command))
        return

    reporter.info(f"creating Django app {project.app_name}")
    try:
        subprocess.run(command, cwd=project.root, check=True)
    except subprocess.CalledProcessError as exc:
        raise ScaffoldError(f"Django could not create app {project.app_name}") from exc

    if not project.app_dir.is_dir():
        raise ScaffoldError(f"Django reported success but {project.app_dir} is missing")
