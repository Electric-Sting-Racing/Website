"""Human-readable reporting for CLI runs."""

from __future__ import annotations

from pathlib import Path


class Reporter:
    """Keep user-facing output consistent and easy to test."""

    def __init__(self, *, dry_run: bool = False) -> None:
        self.dry_run = dry_run

    def created(self, path: Path) -> None:
        self._action("would create" if self.dry_run else "created", path)

    def updated(self, path: Path) -> None:
        self._action("would update" if self.dry_run else "updated", path)

    def skipped(self, path: Path, reason: str = "already exists") -> None:
        self._action("skipped", path, reason)

    def info(self, message: str) -> None:
        print(f"[django-layout] {message}")

    def warning(self, message: str) -> None:
        print(f"[django-layout] warning: {message}")

    @staticmethod
    def _action(action: str, path: Path, reason: str | None = None) -> None:
        suffix = f" ({reason})" if reason else ""
        print(f"[django-layout] {action} {path}{suffix}")
