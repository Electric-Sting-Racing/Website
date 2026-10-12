"""Safe, idempotent filesystem operations."""

from __future__ import annotations

from collections.abc import Callable
from pathlib import Path

from .models import TextPatch
from .reporting import Reporter


def write_if_missing(path: Path, content: str, reporter: Reporter) -> bool:
    """Create a file only when it does not already exist."""
    if path.exists():
        reporter.skipped(path)
        return False

    if not reporter.dry_run:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(content, encoding="utf-8")
    reporter.created(path)
    return True


def apply_text_patch(
    path: Path,
    transform: Callable[[str], TextPatch],
    reporter: Reporter,
) -> bool:
    """Apply a pure text transformation without clobbering a file."""
    if not path.exists():
        reporter.warning(f"cannot patch missing file: {path}")
        return False

    original = path.read_text(encoding="utf-8")
    result = transform(original)

    for note in result.notes:
        reporter.info(note)
    for warning in result.warnings:
        reporter.warning(warning)

    if result.text == original:
        reporter.skipped(path, "no changes needed")
        return False

    if not reporter.dry_run:
        path.write_text(result.text, encoding="utf-8")
    reporter.updated(path)
    return True
