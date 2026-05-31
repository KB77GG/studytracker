#!/usr/bin/env python3
"""Apply the material library v2 UI once protected files are editable.

This script is intentionally not run automatically. It backs up the current
template, copies templates/materials_v2.html over templates/materials.html, and
adds the shared admin UI stylesheet/script to templates/base.html if missing.
"""

from __future__ import annotations

from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
BASE_TEMPLATE = ROOT / "templates" / "base.html"
CURRENT_TEMPLATE = ROOT / "templates" / "materials.html"
V2_TEMPLATE = ROOT / "templates" / "materials_v2.html"
ADMIN_CSS = ROOT / "static" / "admin_ui_v2.css"
ADMIN_JS = ROOT / "static" / "admin_ui_v2.js"
BACKUP_TEMPLATE = ROOT / "templates" / "materials.html.pre-ui-v2"

ADMIN_CSS_LINK = (
    '<link href="{{ url_for(\'static\', filename=\'admin_ui_v2.css\') }}" '
    'rel="stylesheet">'
)
ADMIN_JS_SCRIPT = '<script src="{{ url_for(\'static\', filename=\'admin_ui_v2.js\') }}"></script>'
STYLE_CSS_LINK = '<link href="{{ url_for(\'static\', filename=\'style.css\') }}" rel="stylesheet">'


def require_file(path: Path) -> None:
    if not path.exists():
        raise FileNotFoundError(f"Missing required file: {path}")
    if not path.is_file():
        raise FileNotFoundError(f"Expected a file: {path}")


def add_admin_css_link() -> bool:
    html = BASE_TEMPLATE.read_text(encoding="utf-8")
    if "admin_ui_v2.css" in html:
        return False

    if STYLE_CSS_LINK in html:
        html = html.replace(STYLE_CSS_LINK, f"{STYLE_CSS_LINK}\n  {ADMIN_CSS_LINK}", 1)
    else:
        marker = "</head>"
        if marker not in html:
            raise RuntimeError("Could not locate </head> in templates/base.html")
        html = html.replace(marker, f"  {ADMIN_CSS_LINK}\n{marker}", 1)

    BASE_TEMPLATE.write_text(html, encoding="utf-8")
    return True


def add_admin_js_script() -> bool:
    html = BASE_TEMPLATE.read_text(encoding="utf-8")
    if "admin_ui_v2.js" in html:
        return False

    marker = "</body>"
    if marker not in html:
        raise RuntimeError("Could not locate </body> in templates/base.html")

    html = html.replace(marker, f"  {ADMIN_JS_SCRIPT}\n{marker}", 1)
    BASE_TEMPLATE.write_text(html, encoding="utf-8")
    return True


def apply_materials_template() -> bool:
    current = CURRENT_TEMPLATE.read_text(encoding="utf-8")
    v2 = V2_TEMPLATE.read_text(encoding="utf-8")

    if current == v2:
        return False

    if not BACKUP_TEMPLATE.exists():
        BACKUP_TEMPLATE.write_text(current, encoding="utf-8")

    CURRENT_TEMPLATE.write_text(v2, encoding="utf-8")
    return True


def main() -> None:
    for path in (BASE_TEMPLATE, CURRENT_TEMPLATE, V2_TEMPLATE, ADMIN_CSS, ADMIN_JS):
        require_file(path)

    css_changed = add_admin_css_link()
    js_changed = add_admin_js_script()
    template_changed = apply_materials_template()

    print("admin_ui_v2.css link:", "added" if css_changed else "already present")
    print("admin_ui_v2.js script:", "added" if js_changed else "already present")
    print("materials template:", "updated" if template_changed else "already v2")
    print(f"backup: {BACKUP_TEMPLATE}")


if __name__ == "__main__":
    main()
