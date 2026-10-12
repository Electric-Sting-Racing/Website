"""Small immutable models used across the scaffolding workflow."""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True, slots=True)
class TextPatch:
    """The result of a pure text transformation."""

    text: str
    notes: tuple[str, ...] = ()
    warnings: tuple[str, ...] = ()


@dataclass(frozen=True, slots=True)
class ProjectInfo:
    """The Django project paths needed by the scaffold workflow."""

    root: Path
    app_name: str
    manage_py: Path
    project_package: str | None
    settings_py: Path | None
    urls_py: Path | None

    @property
    def app_dir(self) -> Path:
        """Return the app directory, relative to the project root."""
        return self.root / self.app_name
