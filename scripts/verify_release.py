"""Dependency-free checks for the exact v6 release contents, not a Django test."""

import ast
import hashlib
from pathlib import Path
import re
import sys
import xml.etree.ElementTree as ET


ROOT = Path(__file__).resolve().parents[1]
LOGO = "images/electric-sting-mascot-v4.webp"
LOGO_SHA256 = "5944c4876e5b27005bf2f2cec0934874ff6b9f6c4ed4a300b2819cebcf698793"
checks = 0


def check(condition, message):
    global checks
    if not condition:
        raise RuntimeError(message)
    checks += 1


def main():
    check(hashlib.sha256((ROOT / "static" / LOGO).read_bytes()).hexdigest() == LOGO_SHA256,
          "Logo differs from the supplied IMG_1217(1).webp attachment")
    check(not (ROOT / "static/images/electric-sting-logo.webp").exists(), "Obsolete logo still bundled")
    check(not (ROOT / "static/css/site.css").exists(), "Obsolete stylesheet still bundled")

    route_tree = ast.parse((ROOT / "team/urls.py").read_text())
    routes = {
        kw.value.value
        for node in ast.walk(route_tree) if isinstance(node, ast.Call)
        for kw in node.keywords
        if kw.arg == "name" and isinstance(kw.value, ast.Constant)
    }
    closing = {"endif": "if", "endfor": "for", "endblock": "block", "endwith": "with",
               "endautoescape": "autoescape", "endfilter": "filter", "endcomment": "comment"}
    for path in (ROOT / "templates").rglob("*.html"):
        source = path.read_text()
        check(not re.search(r"\b(?:django|admin)\b", source, re.I), f"{path.name}: public admin instructions remain")
        for forbidden in ("{empty}", "roadmap-marker", "Read the build brief",
                          "electric-sting-logo.webp", "css/site.css",
                          "Add team members in the Django admin"):
            check(forbidden not in source, f"{path.name}: stale content: {forbidden}")
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

    base = (ROOT / "templates/base.html").read_text()
    check(base.count(LOGO) == 3, "Header, footer, and favicon must use the new mascot")
    check('content="es-sponsorship-v6"' in base, "Release marker missing")
    check("css/site-v5.css" in base, "New stylesheet not referenced")
    check("js/site-v5.js" in base, "New JavaScript not referenced")
    css = (ROOT / "static/css/site-v5.css").read_text()
    check(css.count("{") == css.count("}"), "CSS braces are unbalanced")
    for color in ("#020805", "#062017", "#0a2e20", "#a7ff38", "#3be95e"):
        check(color in css, f"Missing neon palette color {color}")
    check("roadmap-marker" not in css and "roadmap-list::before" not in css, "Old roadmap decoration remains")
    for old_color in ("#d3d69d", "#36a63b"):
        check(old_color not in css.lower(), "Old muted theme remains")
    for asset in re.findall(r"url\(['\"]?([^)'\"]+)", css):
        if not asset.startswith(("http", "data:")):
            check((ROOT / "static/css" / asset).is_file(), f"Missing CSS asset: {asset}")

    home = (ROOT / "templates/team/home.html").read_text()
    check("View the design plan" in home, "Design CTA missing")
    check("Five sections." in home and "Six systems." not in home, "Wrong homepage sections")
    check('loading="lazy" decoding="async"' in home, "Team photo must lazy-load")
    check('fetchpriority="high"' in home, "Hero mascot must remain high priority")
    check('loading="lazy"' in (ROOT / "templates/team/gallery.html").read_text(), "Gallery lazy loading missing")
    check(".reveal.is-pending" in css and "translateY(28px)" in css, "Scroll reveal styles missing")
    check("prefers-reduced-motion" in css and "@media print" in css, "Motion/print fallback missing")
    check("max-width: 580px" in css and "max-width: 1050px" in css, "Responsive layouts missing")
    check(".nav-ready .primary-nav" in css, "No-JS navigation fallback missing")
    for name in ("home", "cars", "car_detail"):
        page = (ROOT / f"templates/team/{name}.html").read_text()
        check("not been built yet" in page, f"{name}: pre-build statement missing")
        check("image_url" not in page, f"{name}: legacy demo car photo can still render")
        check(LOGO in page, f"{name}: new mascot missing")
    roster = (ROOT / "templates/team/roster.html").read_text()
    check("{% if grouped_members %}" in roster, "Empty roster should not show a placeholder section")
    check('class="lead-badge">Section lead' in roster, "Visible lead badge missing")
    tree = ast.parse((ROOT / "team/models.py").read_text())
    member = next(node for node in tree.body if isinstance(node, ast.ClassDef) and node.name == "TeamMember")
    choices = next(node for node in member.body if isinstance(node, ast.Assign) and node.targets[0].id == "SUBTEAM_CHOICES")
    expected = [("high_voltage", "High Voltage"), ("powertrain", "Powertrain"),
                ("low_voltage_controls", "Low Voltage/Controls"), ("frame", "Frame"), ("suspensions", "Suspensions")]
    check(ast.literal_eval(choices.value) == expected, "Roster choices/order must match requested five sections")
    content_tree = ast.parse((ROOT / "team/content.py").read_text())
    systems = next(node for node in content_tree.body if isinstance(node, ast.Assign) and node.targets[0].id == "ENGINEERING_SYSTEMS")
    check([item[1] for item in ast.literal_eval(systems.value)] == [label for _, label in expected], "Home and roster sections differ")
    check((ROOT / "team/migrations/0004_roster_sections.py").is_file(), "Roster data migration missing")
    package_tree = ast.parse((ROOT / "team/migrations/0005_restore_sponsorship_packages.py").read_text())
    packages = next(node for node in package_tree.body if isinstance(node, ast.Assign) and node.targets[0].id == "PACKAGES")
    check(ast.literal_eval(packages.value) == (
        ("Bronze", "$500+", "Bronze Leaf", "1", "Extra small", False, False),
        ("Silver", "$1,500+", "Silver Tulip", "1", "Small", False, True),
        ("Gold", "$3,500+", "Gold Rose", "2", "Medium", True, True),
        ("Platinum", "$5,000+", "Platinum Orchid", "3", "Large", True, True),
    ), "Original sponsorship package amounts/benefits changed")
    check('path("stories/' not in (ROOT / "team/urls.py").read_text(), "Blog route returned")
    for file in ROOT.rglob("*.py"):
        if not any(part in {".venv", "__pycache__"} for part in file.parts):
            ast.parse(file.read_text(), filename=str(file))
            check(True, f"{file}: syntax")
    for file in (ROOT / "static").rglob("*.svg"):
        ET.parse(file)
        check(True, f"{file}: XML")
    print(f"PASS: {checks} archive/source checks; mascot SHA-256 {LOGO_SHA256}")
    print("Django tests and browser rendering are separate checks, not executed by this script.")


if __name__ == "__main__":
    try:
        main()
    except (OSError, RuntimeError, SyntaxError, ET.ParseError) as exc:
        print(f"FAIL: {exc}", file=sys.stderr)
        sys.exit(1)
