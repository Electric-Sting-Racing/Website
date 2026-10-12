"""Read and render package-owned scaffold assets."""

from __future__ import annotations

from importlib.resources import files


ASSET_PACKAGE = "django_layout_scaffolder.assets"


def read_asset(relative_path: str) -> str:
    """Read a UTF-8 asset packaged with the scaffolder."""
    resource = files(ASSET_PACKAGE)
    for part in relative_path.split("/"):
        resource = resource.joinpath(part)
    return resource.read_text(encoding="utf-8")


def render_asset(relative_path: str, **values: str) -> str:
    """Render explicit ``__PLACEHOLDER__`` tokens in an asset.

    Django templates are intentionally not formatted with ``str.format``;
    that would collide with Django's ``{% ... %}`` syntax.
    """
    content = read_asset(relative_path)
    for key, value in values.items():
        content = content.replace(f"__{key.upper()}__", value)
    return content
