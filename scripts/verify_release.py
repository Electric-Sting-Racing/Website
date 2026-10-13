"""Dependency-free structural checks for templates and static assets, not a Django test.

These checks catch broken builds (unbalanced template tags, missing static
files, unknown routes, malformed CSS/SVG, Python syntax errors). They do not
pin page copy, colors, or prices, so content can change without editing CI.
"""

import ast
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
SKIP_DIRS = {".git", ".venv", "venv", "__pycache__", "node_modules", "staticfiles"}
checks = 0


def check(condition, message):
    global checks
    if not condition:
        raise RuntimeError(message)
    checks += 1


def route_names():
    names = set()
    for urls in ROOT.glob("*/urls.py"):
        tree = ast.parse(urls.read_text())
        names.update(
            kw.value.value
            for node in ast.walk(tree) if isinstance(node, ast.Call)
            for kw in node.keywords
            if kw.arg == "name" and isinstance(kw.value, ast.Constant)
        )
    return names


def check_templates(routes):
    closing = {"endif": "if", "endfor": "for", "endblock": "block", "endwith": "with",
               "endautoescape": "autoescape", "endfilter": "filter", "endcomment": "comment"}
    for path in (ROOT / "templates").rglob("*.html"):
        source = path.read_text()
        for asset in re.findall(r"{%\s*static\s+['\"]([^'\"]+)", source):
            check((ROOT / "static" / asset).is_file(), f"{path.name}: missing asset {asset}")
        for route in re.findall(r"{%\s*url\s+['\"]([^'\"]+)", source):
            check(route in routes, f"{path.name}: unknown route {route}")
        stack = []
        for tag in re.findall(r"{%\s*(.*?)\s*%}", source, re.S):
            kind = tag.split()[0]
            if kind in closing.values():
                stack.append(kind)
            elif kind in closing:
                check(bool(stack) and stack[-1] == closing[kind], f"{path.name}: mismatched {kind}")
                stack.pop()
            elif kind == "empty":
                check(bool(stack) and stack[-1] == "for", f"{path.name}: empty outside a loop")
            elif kind in ("else", "elif"):
                check(bool(stack) and stack[-1] == "if", f"{path.name}: {kind} outside if")
        check(not stack, f"{path.name}: unclosed template tags {stack}")


def check_static():
    for css_file in (ROOT / "static").rglob("*.css"):
        css = css_file.read_text()
        check(css.count("{") == css.count("}"), f"{css_file.name}: CSS braces are unbalanced")
        for asset in re.findall(r"url\(['\"]?([^)'\"]+)", css):
            if not asset.startswith(("http", "data:", "#")):
                check((css_file.parent / asset).is_file(), f"{css_file.name}: missing CSS asset {asset}")
    for svg in (ROOT / "static").rglob("*.svg"):
        ET.parse(svg)
        check(True, f"{svg}: XML")


def check_python():
    for file in ROOT.rglob("*.py"):
        if not SKIP_DIRS.intersection(file.parts):
            ast.parse(file.read_text(), filename=str(file))
            check(True, f"{file}: syntax")


def main():
    check_templates(route_names())
    check_static()
    check_python()
    print(f"PASS: {checks} structural checks")
    print("Django tests and browser rendering are separate checks, not executed by this script.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, SyntaxError, ET.ParseError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
