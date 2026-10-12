"""Conservative, idempotent text patchers for standard Django files."""

from __future__ import annotations

import re

from .models import TextPatch


def patch_settings(source: str, app_name: str) -> TextPatch:
    """Patch a conventional Django settings file without reformatting it."""
    updated = source
    notes: list[str] = []
    warnings: list[str] = []

    app_entry = re.compile(
        rf"^\s*['\"]{re.escape(app_name)}(?:\.apps\.[A-Za-z_]\w*)?['\"]\s*,?\s*$",
        re.M,
    )
    if not app_entry.search(updated):
        installed_apps = re.search(r"INSTALLED_APPS\s*=\s*\[", updated)
        if installed_apps:
            updated = (
                updated[: installed_apps.end()]
                + f'\n    "{app_name}",'
                + updated[installed_apps.end() :]
            )
            notes.append(f'added "{app_name}" to INSTALLED_APPS')
        else:
            warnings.append("could not find a list-style INSTALLED_APPS")

    empty_dirs = re.search(r"(?P<quote>['\"])DIRS(?P=quote)\s*:\s*\[\s*\]", updated)
    if empty_dirs:
        quote = empty_dirs.group("quote")
        replacement = f'{quote}DIRS{quote}: [BASE_DIR / "templates"]'
        updated = updated[: empty_dirs.start()] + replacement + updated[empty_dirs.end() :]
        notes.append("configured the project templates directory")
    elif "BASE_DIR / \"templates\"" not in updated and "BASE_DIR / 'templates'" not in updated:
        warnings.append("set TEMPLATES DIRS to [BASE_DIR / \"templates\"] manually")

    static_dirs = re.search(r"^\s*STATICFILES_DIRS\s*=", updated, re.M)
    if not static_dirs:
        marker = '\n\n# Added by django-layout-scaffolder.\nSTATICFILES_DIRS = [BASE_DIR / "static"]\n'
        updated = updated.rstrip() + marker
        notes.append("configured the project static directory")
    elif "BASE_DIR / \"static\"" not in updated and "BASE_DIR / 'static'" not in updated:
        warnings.append("left existing STATICFILES_DIRS unchanged; add BASE_DIR / \"static\"")

    return TextPatch(updated, tuple(notes), tuple(warnings))


def patch_project_urls(source: str, app_name: str) -> TextPatch:
    """Include the generated app at the root when no root route exists."""
    include_expression = f'include("{app_name}.urls")'
    if include_expression in source or f"include('{app_name}.urls')" in source:
        return TextPatch(source, (f"project URLs already include {app_name}.urls",))

    if re.search(r"path\(\s*['\"]\s*['\"]\s*,", source):
        return TextPatch(
            source,
            warnings=("found an existing root URL; add the home include manually",),
        )

    updated = source
    import_line = re.search(
        r"^from django\.urls import (?P<imports>[^\n]+)$", updated, re.M
    )
    if import_line:
        imports = {item.strip() for item in import_line.group("imports").split(",")}
        if "include" not in imports:
            replacement = import_line.group(0).replace(
                "import ", "import include, ", 1
            )
            updated = updated[: import_line.start()] + replacement + updated[import_line.end() :]
    elif "from django.urls import" in updated:
        return TextPatch(
            source,
            warnings=("could not safely update a multi-line django.urls import",),
        )
    else:
        updated = "from django.urls import include, path\n\n" + updated

    urlpatterns = re.search(r"urlpatterns\s*=\s*\[", updated)
    if not urlpatterns:
        return TextPatch(
            source,
            warnings=("could not find urlpatterns; add the home include manually",),
        )

    route = f'    path("", include("{app_name}.urls")),\n'
    updated = updated[: urlpatterns.end()] + "\n" + route.rstrip("\n") + updated[urlpatterns.end() :]
    return TextPatch(updated, (f"included {app_name}.urls at the project root",))


def patch_home_view(source: str, app_name: str) -> TextPatch:
    """Add the generated view to a fresh ``startapp`` views module."""
    if re.search(r"^\s*def\s+index\s*\(", source, re.M):
        return TextPatch(source, ("homepage view already exists",))

    if source.strip() == "from django.shortcuts import render":
        addition = (
            f'\n\n\ndef index(request):\n'
            f'    return render(request, "{app_name}/index.html")\n'
        )
        return TextPatch(source.rstrip() + addition, ("added the homepage view",))

    if not source.strip():
        content = (
            "from django.shortcuts import render\n\n\n"
            "def index(request):\n"
            f'    return render(request, "{app_name}/index.html")\n'
        )
        return TextPatch(content, ("created the homepage view",))

    return TextPatch(
        source,
        warnings=(f"could not safely modify {app_name}/views.py; add an index view manually",),
    )
