"""Command-line interface for the Django layout scaffolder."""

from __future__ import annotations

import argparse
from collections.abc import Sequence

from .errors import ScaffoldError
from .project import discover_project
from .reporting import Reporter
from .scaffolder import scaffold


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Scaffold a maintainable Django site layout."
    )
    parser.add_argument(
        "project_root",
        nargs="?",
        default=".",
        help="Existing Django project directory (default: current directory).",
    )
    parser.add_argument(
        "--app",
        default="home",
        help="Django app name to create or use (default: home).",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Show planned changes without writing files or running startapp.",
    )
    parser.add_argument(
        "--no-integrate",
        action="store_true",
        help="Create assets only; do not patch settings.py or project urls.py.",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s 0.2.0",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    reporter = Reporter(dry_run=args.dry_run)

    try:
        project = discover_project(args.project_root, args.app)
        scaffold(
            project,
            reporter,
            integrate=not args.no_integrate,
        )
    except ScaffoldError as exc:
        parser.error(str(exc))

    reporter.info("done")
    if args.dry_run:
        reporter.info("dry run: no files were written")
    else:
        reporter.info("run: python manage.py check && python manage.py runserver")
    return 0
