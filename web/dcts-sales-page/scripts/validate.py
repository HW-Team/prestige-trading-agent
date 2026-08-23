#!/usr/bin/env python3
"""Deterministic validation for the isolated DCTS static sales page."""

from __future__ import annotations

import argparse
import json
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parents[1]
REPO_ROOT = ROOT.parents[1]
RULES = json.loads((ROOT / "compliance-rules.json").read_text(encoding="utf-8"))


class PageParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.assets: list[str] = []
        self.visible: list[str] = []
        self.ctas: list[str] = []
        self._hidden_depth = 0
        self._cta_depth = 0

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        values = dict(attrs)
        if tag in {"script", "style", "template"}:
            self._hidden_depth += 1
        if "data-open-signup" in values:
            self._cta_depth += 1
        for key in ("src", "href", "poster"):
            value = values.get(key)
            if value:
                self.assets.append(value)
        srcset = values.get("srcset")
        if srcset:
            self.assets.extend(part.strip().split()[0] for part in srcset.split(","))
        alt = values.get("alt")
        if alt:
            self.visible.append(alt)

    def handle_endtag(self, tag: str) -> None:
        if tag in {"script", "style", "template"} and self._hidden_depth:
            self._hidden_depth -= 1
        if tag in {"button", "a"} and self._cta_depth:
            self._cta_depth -= 1

    def handle_data(self, data: str) -> None:
        if self._hidden_depth == 0 and data.strip():
            self.visible.append(data.strip())
            if self._cta_depth:
                self.ctas.append(data.strip())


def source_files() -> list[Path]:
    extensions = {".html", ".css", ".js", ".json", ".md", ".svg"}
    return sorted(
        path
        for path in ROOT.rglob("*")
        if path.is_file()
        and path.suffix in extensions
        and "qa" not in path.parts
        and path.name != "compliance-rules.json"
    )


def parse_page() -> PageParser:
    parser = PageParser()
    parser.feed((ROOT / "index.html").read_text(encoding="utf-8"))
    parser.close()
    return parser


def local_path(reference: str) -> Path | None:
    if reference.startswith(("#", "data:", "mailto:", "tel:")):
        return None
    parsed = urlparse(reference)
    if parsed.scheme or parsed.netloc:
        return None
    clean = parsed.path.lstrip("/")
    return ROOT / clean


def check_structure(errors: list[str]) -> None:
    required = [
        "index.html",
        "styles.css",
        "app.js",
        "config.js",
        "config.example.js",
        "DESIGN.md",
        "compliance-rules.json",
        "README.md",
        "favicon.svg",
        "robots.txt",
        "assets/dcts-emblem.svg",
        "assets/hero-learning.webp",
        "assets/hero-learning-480.webp",
        "assets/hero-learning-720.webp",
        "assets/checklist-method.webp",
        "assets/checklist-method-640.webp",
        "Dockerfile",
        "nginx.conf",
        "scripts/validate.py",
        "scripts/browser-qa.js",
    ]
    for relative in required:
        if not (ROOT / relative).is_file():
            errors.append(f"missing required file: {relative}")
    fonts = sorted((ROOT / "assets/fonts").glob("*.woff2"))
    if len(fonts) < 8:
        errors.append(f"expected at least 8 self-hosted WOFF2 font files, found {len(fonts)}")
    legacy_fonts = sorted((ROOT / "assets/fonts").glob("*.ttf"))
    if legacy_fonts:
        errors.append(f"uncompressed production font files are prohibited: {legacy_fonts}")
    licenses = sorted((ROOT / "assets/fonts").glob("OFL-*.txt"))
    if len(licenses) != 4:
        errors.append(f"expected 4 font license files, found {len(licenses)}")
    production_pngs = list((ROOT / "assets").glob("*.png"))
    if production_pngs:
        errors.append(f"production PNG copies are prohibited: {production_pngs}")
    for asset in (ROOT / "assets").glob("*.webp"):
        if asset.stat().st_size == 0:
            errors.append(f"empty WebP asset: {asset.relative_to(ROOT)}")


def check_assets(errors: list[str], parser: PageParser) -> None:
    css = (ROOT / "styles.css").read_text(encoding="utf-8")
    references = parser.assets + re.findall(r"url\((?:['\"]?)([^)'\"]+)", css)
    for reference in references:
        path = local_path(reference)
        if path is not None and not path.is_file():
            errors.append(f"unresolved local asset: {reference}")
    if "fonts.googleapis.com" in css or "fonts.gstatic.com" in css:
        errors.append("external Google Fonts dependency found in CSS")
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    if "fonts.googleapis.com" in html or "fonts.gstatic.com" in html:
        errors.append("external Google Fonts dependency found in HTML")
    if css.count("font-display: swap") < 8:
        errors.append("each required self-hosted font face must use font-display: swap")


def check_security(errors: list[str]) -> None:
    combined = "\n".join(path.read_text(encoding="utf-8") for path in source_files())
    lowered = combined.lower()
    for marker in RULES["forbidden_source_values"]:
        if marker.lower() in lowered:
            errors.append(f"forbidden secret marker found: {marker}")
    extra_markers = ["x-form-signature", "page_access_token", "webhook_signing", "paid_line"]
    for marker in extra_markers:
        if marker in lowered:
            errors.append(f"forbidden browser-source marker found: {marker}")
    app = (ROOT / "app.js").read_text(encoding="utf-8")
    for required in ["https:", "buy.stripe.com", "checkout.stripe.com", "APPROVED_UTM_KEYS"]:
        if required not in app:
            errors.append(f"checkout security implementation missing: {required}")
    if re.search(r"fetch\s*\(", app) or "XMLHttpRequest" in app:
        errors.append("browser code must not submit directly to an application endpoint")
    html = (ROOT / "index.html").read_text(encoding="utf-8")
    if "connect-src 'self'" not in html:
        errors.append("CSP must restrict browser connections to same-origin resources")
    config = (ROOT / "config.js").read_text(encoding="utf-8")
    values = re.findall(r":\s*[\"']([^\"']*)[\"']", config)
    if any(values):
        errors.append("checked-in config.js must default every public URL to an empty string")


def check_compliance(errors: list[str], parser: PageParser) -> None:
    visible = " ".join(parser.visible)
    for phrase in RULES["forbidden_visible_copy"]:
        if phrase in visible:
            errors.append(f"forbidden visible claim: {phrase}")
    for phrase in RULES["required_visible_copy"]:
        if phrase not in visible:
            errors.append(f"required visible copy missing: {phrase}")
    if "3,990 THB" not in visible or "รอยืนยันราคาและเงื่อนไข" not in visible:
        errors.append("3,990 THB must remain visibly provisional")
    if "\N{EM DASH}" in visible or "\N{EN DASH}" in visible:
        errors.append("visible copy contains an em/en dash")
    normalized_ctas = [re.sub(r"\s+", " ", cta).strip() for cta in parser.ctas]
    wrong = [cta for cta in normalized_ctas if cta and cta != RULES["cta_label"]]
    if wrong:
        errors.append(f"inconsistent signup CTA labels: {wrong}")


def check_docs(errors: list[str]) -> None:
    root_readme = (REPO_ROOT / "README.md").read_text(encoding="utf-8")
    for required in [
        "web/dcts-sales-page",
        "configuration-ready",
        "3,990 THB",
        "scripts/validate.py",
    ]:
        if required not in root_readme:
            errors.append(f"root README missing static-site documentation: {required}")
    page_readme = (ROOT / "README.md").read_text(encoding="utf-8")
    for required in ["checkoutUrl", "buy.stripe.com", "config.js", "pending approval"]:
        if required not in page_readme:
            errors.append(f"page README missing deployment detail: {required}")


def main() -> int:
    argument_parser = argparse.ArgumentParser()
    group = argument_parser.add_mutually_exclusive_group()
    group.add_argument("--structure", action="store_true")
    group.add_argument("--security", action="store_true")
    group.add_argument("--docs", action="store_true")
    args = argument_parser.parse_args()
    errors: list[str] = []
    parser = parse_page()

    if args.structure:
        check_structure(errors)
        check_assets(errors, parser)
        label = "structure"
    elif args.security:
        check_security(errors)
        label = "security"
    elif args.docs:
        check_docs(errors)
        label = "docs"
    else:
        check_structure(errors)
        check_assets(errors, parser)
        check_security(errors)
        check_compliance(errors, parser)
        check_docs(errors)
        label = "full"

    if errors:
        print(f"DCTS {label} validation failed ({len(errors)} error(s)):", file=sys.stderr)
        for error in errors:
            print(f"- {error}", file=sys.stderr)
        return 1
    print(f"DCTS {label} validation passed")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
