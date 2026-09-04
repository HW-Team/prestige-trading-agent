# Implementation Report - DCTS Production Sales Page

**Plan**: `.claude/plans/dcts-production-sales-page.md`
**Branch**: `feature/dcts-production-sales-page`
**Status**: COMPLETE

## Summary

Built an isolated static production sales page under `web/dcts-sales-page/` from the approved legacy-brand prototype. The artifact self-hosts campaign images and four font families, fails safely when public integrations are unconfigured, restricts checkout handoff to approved Stripe HTTPS hosts, and preserves only allowlisted UTM parameters.

## Tasks completed

- Production HTML, CSS, approved WebP assets, favicon, and design source -> `web/dcts-sales-page/` (CREATE)
- Eight subsetted WOFF2 font files and four SIL OFL license files -> `web/dcts-sales-page/assets/fonts/` (CREATE)
- Empty runtime defaults and deploy-time example -> `config.js`, `config.example.js` (CREATE)
- Null-safe menu, accordion, modal, focus trap, sticky CTA, public-link, and checkout behavior -> `app.js` (CREATE)
- Deterministic structure, asset, security, copy, and docs checks -> `scripts/validate.py` (CREATE)
- Five-viewport Playwright interaction, console, network, responsive, and checkout QA -> `scripts/browser-qa.js` (CREATE)
- Deployment and pending-value documentation -> page and root `README.md` (CREATE/UPDATE)
- Desktop, tablet, mobile, narrow, and reduced-motion captures -> `web/dcts-sales-page/qa/` (CREATE)

## Tests added

- Static validator checks required structure, local asset resolution, font self-hosting/licenses, WebP-only campaign assets, empty runtime defaults, secret markers, no direct browser submission, prohibited claims, required risk copy, provisional price labelling, CTA consistency, and visible dash rules.
- Browser QA checks 390x844, 768x1024, 1440x900, 320x700, and reduced-motion mode; menu, curriculum/FAQ accordion ARIA, both dialogs, focus restoration/trapping, pending checkout state, Stripe host rejection, UTM allowlist, no overflow, local-only network, fonts, images, and sticky CTA.

## Validation results

- `uv run pytest -q`: 22 passed
- `uv run mypy src`: success, 11 source files
- `uv run ruff check .`: passed after formatting validator source
- `uv run ruff format --check .`: 41 files already formatted
- `python3 web/dcts-sales-page/scripts/validate.py`: passed
- Browser QA: passed 5 viewport/motion profiles, 5 screenshots, no console/network errors
- Lighthouse after optimization: accessibility 100%, best practices 100%, SEO 100%, LCP 2.57s, CLS 0.00015, 318 KB transferred; Speed Index was unavailable because headless Chrome did not capture Lighthouse screenshots
- Live preview verification: root, CSS, JavaScript, configuration, robots, responsive hero image, and font returned HTTP 200

## Deviations from the plan

- Browser QA also covers 320x700 and reduced-motion profiles beyond the three required screenshots.
- Font license texts are included beside self-hosted fonts.
- Published an authenticated permanent non-transactional preview at `https://hidden-island-9ezx.here.now/` after CZ explicitly requested hosting.

## Issues encountered

- Chromium reports `frame-ancestors` as invalid in a meta-delivered CSP, so that directive was removed from the document policy and remains explicitly required at the hosting edge.
- Initial lazy-image QA treated an offscreen image as missing; QA now eagerly resolves image load state before asset assertions.
- Initial TTF/image payload transferred about 1.76 MB. Subsetted WOFF2 fonts and responsive WebP variants reduced the audited transfer to 318 KB.
- Lighthouse's robots audit was blocked by `connect-src 'none'`; restricting connections to same-origin fixed robots/SEO without allowing third-party requests.
