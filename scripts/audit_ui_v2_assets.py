#!/usr/bin/env python3
"""Audit StudyTracker UI v2 assets.

The current project environment can create/read new UI v2 files even when some
legacy files are protected by macOS. This script keeps those new assets honest:
it verifies template syntax, CSS/JS structure, cross-file references, and can
optionally render the standalone preview through Playwright.
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]

FILES = {
    "css": ROOT / "static" / "admin_ui_v2.css",
    "js": ROOT / "static" / "admin_ui_v2.js",
    "preview": ROOT / "static" / "admin_ui_v2_preview.html",
    "materials": ROOT / "templates" / "materials_v2.html",
    "macros": ROOT / "templates" / "_admin_v2_macros.html",
    "backlog": ROOT / "docs" / "ui_optimization_backlog.md",
    "apply_script": ROOT / "scripts" / "apply_materials_v2.py",
    "preview_validator": ROOT / "scripts" / "validate_admin_ui_v2_preview.cjs",
}

REQUIRED_CSS_SELECTORS = [
    ".admin-v2-panel",
    ".admin-v2-tabs",
    ".admin-v2-toolbar",
    ".admin-v2-control",
    ".admin-v2-table",
    ".admin-v2-badge",
    ".admin-v2-row-action",
    ".admin-v2-empty",
    ".admin-v2-loading",
    ".admin-v2-error",
    ".admin-v2-stat-grid",
    ".admin-v2-stat",
    ".admin-v2-detail",
    ".admin-v2-form",
    ".admin-v2-form-grid",
    ".admin-v2-field",
]

REQUIRED_JS_EXPORTS = [
    "badge",
    "debounce",
    "empty",
    "error",
    "escapeHtml",
    "fetchJson",
    "formatDate",
    "loading",
    "rowAction",
    "setText",
    "table",
    "titleCell",
]

REQUIRED_MACROS = [
    "badge",
    "button",
    "count",
    "detail",
    "empty",
    "error",
    "field",
    "form_section",
    "loading",
    "meta_list",
    "search_control",
    "select_control",
    "stat",
    "stat_grid",
    "tab",
    "toolbar",
]

REQUIRED_MATERIAL_TYPES = [
    "grammar",
    "translation",
    "reading_vocab_choice",
    "ielts_reading_practice",
    "speaking",
    "speaking_part1",
    "speaking_part2_3",
    "speaking_reading",
    "writing",
]

def fail(message: str) -> None:
    raise RuntimeError(message)


def read(path: Path) -> str:
    if not path.exists():
        fail(f"Missing file: {path}")
    return path.read_text(encoding="utf-8")


def check_jinja() -> None:
    try:
        from jinja2 import Environment
    except ImportError as exc:
        fail(f"jinja2 is required for template audit: {exc}")

    env = Environment()
    for key in ("materials", "macros"):
        source = read(FILES[key])
        env.parse(source)
        print(f"jinja ok: {FILES[key].relative_to(ROOT)}")

    macros = read(FILES["macros"])
    for name in REQUIRED_MACROS:
        if f"macro {name}(" not in macros:
            fail(f"Missing Jinja macro: {name}")
    print("macros ok: templates/_admin_v2_macros.html")


def check_css() -> None:
    css = read(FILES["css"])
    if css.count("{") != css.count("}"):
        fail("admin_ui_v2.css has unbalanced braces")
    for selector in REQUIRED_CSS_SELECTORS:
        if selector not in css:
            fail(f"Missing CSS selector: {selector}")
    print("css ok: static/admin_ui_v2.css")


def node_executable() -> str | None:
    candidates = [
        os.environ.get("NODE"),
        shutil.which("node"),
        "/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/bin/node",
    ]
    for candidate in candidates:
        if candidate and Path(candidate).exists():
            return candidate
    return None


def check_js() -> None:
    js = read(FILES["js"])
    for name in REQUIRED_JS_EXPORTS:
        if name not in js:
            fail(f"Missing AdminUIV2 helper: {name}")

    node = node_executable()
    if node:
        subprocess.run([node, "--check", str(FILES["js"])], check=True)
        print("js syntax ok: static/admin_ui_v2.js")
    else:
        print("js syntax skipped: node executable not found")


def check_cross_references() -> None:
    materials = read(FILES["materials"])
    preview = read(FILES["preview"])
    backlog = read(FILES["backlog"])
    apply_script = read(FILES["apply_script"])
    preview_validator = read(FILES["preview_validator"])

    for material_type in REQUIRED_MATERIAL_TYPES:
        if material_type not in materials:
            fail(f"materials_v2 missing material type: {material_type}")

    for required in (
        "admin_ui_v2.css",
        "admin_ui_v2.js",
        "materialsTable",
        "tasksTable",
        "reportsPreview",
        "gradingPreview",
        "formPreview",
        "admin-v2-stat-grid",
        "admin-v2-detail",
        "admin-v2-form",
    ):
        if required not in preview:
            fail(f"preview missing reference: {required}")

    for required in ("admin_ui_v2.css", "admin_ui_v2.js", "materials_v2.html"):
        if required not in apply_script:
            fail(f"apply script missing reference: {required}")
        if required not in backlog:
            fail(f"backlog missing reference: {required}")

    for required in ("admin_ui_v2_preview.html", "admin-ui-v2-preview-desktop.png", "admin-ui-v2-preview-mobile.png"):
        if required not in preview_validator and required not in backlog:
            fail(f"preview validation docs missing reference: {required}")

    print("cross references ok")


def run_preview_validator() -> None:
    node = node_executable()
    if not node:
        fail("Cannot render preview: node executable not found")

    env = os.environ.copy()
    bundled_modules = "/Users/zhouxin/.cache/codex-runtimes/codex-primary-runtime/dependencies/node/node_modules"
    if Path(bundled_modules).exists():
        env["NODE_PATH"] = bundled_modules

    subprocess.run([node, str(FILES["preview_validator"])], check=True, env=env)
    print("preview render ok")


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--render-preview",
        action="store_true",
        help="also run Playwright preview rendering and screenshot assertions",
    )
    args = parser.parse_args()

    try:
        for path in FILES.values():
            if not path.exists():
                fail(f"Missing expected UI v2 asset: {path}")

        check_jinja()
        check_css()
        check_js()
        check_cross_references()
        if args.render_preview:
            run_preview_validator()
    except Exception as exc:
        print(f"ui v2 audit failed: {exc}", file=sys.stderr)
        return 1

    print("ui v2 audit ok")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
