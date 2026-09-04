# Feature: DCTS Production Sales Page

The following plan is complete, but validate codebase patterns and task sanity before implementation.

## Feature Description

Promote the approved DCTS mobile-first prototype into an isolated, deployable static production sales page while preserving the verified legacy DTCS brand and the existing FastAPI funnel's security boundaries.

Source authority is intentionally split: the legacy DTCS website defines branding and visual language, while the supplied PDF provides copy, section order, and wireframe intent only. The PDF must not be treated as a branding or visual-design reference.

## User Story

As a Thai prospective DCTS learner
I want to understand the course, risk boundaries, support model and provisional offer clearly on my phone
So that I can make an informed decision and continue only through an approved Stripe checkout.

## Problem Statement

The repository contains a production backend but no frontend surface. The current page is an untracked prototype under `mockups/`, uses external font loading, contains placeholder integrations, and has no deployment-safe public configuration contract. A browser must never contain webhook secrets or bypass signed form and verified Stripe flows.

## Solution Statement

Create a dependency-light static site under `web/dcts-sales-page/` using semantic HTML, CSS and JavaScript. Self-host the approved fonts and images, expose only public runtime URLs through `config.js`, restrict checkout redirects to approved Stripe HTTPS hosts, preserve UTM values, and disable conversion actions when configuration is absent. Add deterministic validation scripts and browser QA. Do not change backend routes.

## Out of Scope / Non-Goals

- Not included: deployment to a public domain. Hosting target is not approved.
- Not included: a live Stripe checkout URL, analytics IDs, policy URLs, business entity details, VSL URL, testimonials or LMS screenshots. These remain visibly pending.
- Not included: direct browser calls to `/webhooks/form` because that endpoint requires an HMAC secret that must never exist in browser code.
- Not included: paid LINE room URLs or payment confirmation logic.
- Not changing: existing FastAPI application, database schema, webhook verification, CRM state machine or outbox behavior.
- Not publishing: unverified performance, authority, scarcity, list-price, discount, access-duration, guarantee or refund claims.

## Feature Metadata

**Feature Type**: New Capability
**Estimated Complexity**: Medium
**Primary Systems Affected**: static sales page, repository documentation, CI validation surface
**Dependencies**: existing browser platform APIs, Playwright already available in the QA environment, Python standard library

## Related Work

**Implements**: approved DCTS Design Gate and UX brief

**Back-references**:

- `.claude/plans/dcts-sales-page-ux-brief.md` - conversion structure and compliance requirements
- `.claude/plans/hwt-166-prestige-trading-agent.md` - inherited backend security and payment boundaries
- `mockups/dcts-sales-page/DESIGN.md` - approved legacy brand tokens

**Forward-references**:

- Production deployment and approved integrations after URLs and legal content are supplied

---

## CONTEXT REFERENCES

### Relevant Codebase Files

- `README.md:1-137` - backend purpose, configuration, webhook contracts and safety boundaries
- `src/prestige_trading_agent/main.py:175-210` - signed form and verified Stripe webhook boundaries that browser code must not bypass
- `src/prestige_trading_agent/config.py:8-33` - existing server-only URL and secret configuration
- `.claude/plans/dcts-sales-page-ux-brief.md:20-296` - audience, funnel, content structure, required assets and compliance constraints
- `mockups/dcts-sales-page/index.html` - approved content and semantic page structure
- `mockups/dcts-sales-page/styles.css` - verified dark legacy brand implementation and responsive layout
- `mockups/dcts-sales-page/script.js` - menu, modal, accordion and sticky CTA behavior
- `mockups/dcts-sales-page/compliance-rules.json` - deterministic visible-copy and source checks
- `mockups/dcts-sales-page/DESIGN.md` - brand tokens and UI constraints

### New Files to Create

- `web/dcts-sales-page/index.html` - production document
- `web/dcts-sales-page/styles.css` - production styles and self-hosted font faces
- `web/dcts-sales-page/app.js` - production interactions and secure public configuration handling
- `web/dcts-sales-page/config.js` - safe unconfigured runtime defaults
- `web/dcts-sales-page/config.example.js` - documented deploy-time public configuration
- `web/dcts-sales-page/assets/*` - optimized campaign images and self-hosted brand fonts
- `web/dcts-sales-page/DESIGN.md` - production design-system source
- `web/dcts-sales-page/compliance-rules.json` - production content contract
- `web/dcts-sales-page/README.md` - configuration, deployment and validation instructions
- `web/dcts-sales-page/scripts/validate.py` - deterministic HTML, asset, security and compliance validation
- `web/dcts-sales-page/scripts/browser-qa.js` - responsive and interaction QA
- `.claude/reports/dcts-production-sales-page-report.md` - implementation report
- `.claude/code-reviews/dcts-production-sales-page.md` - pre-commit review
- `.claude/execution-reports/dcts-production-sales-page.md` - execution reflection
- `.claude/system-reviews/dcts-production-sales-page-review.md` - process review

### Relevant Documentation

- [MDN dialog accessibility guidance](https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Roles/dialog_role)
- [MDN Content Security Policy](https://developer.mozilla.org/en-US/docs/Web/HTTP/CSP)
- [Stripe Payment Links](https://docs.stripe.com/payment-links)
- [Google Fonts repository licenses](https://github.com/google/fonts)

### Patterns to Follow

**Naming:** kebab-case for static paths and data attributes; JavaScript functions use camelCase.

**Failure behavior:** conversion CTA stays visible but opens an explicit pending-configuration dialog when no approved URL exists. No silent failure and no fabricated checkout.

**Security:** only `https:` checkout URLs with hostname `buy.stripe.com` or `checkout.stripe.com` may redirect. No secrets, admin keys, webhook signing values or paid LINE URLs in source.

**Accessibility:** semantic landmarks, skip link, keyboard focus trap, Escape close, 44px minimum controls, visible focus, reduced motion, explicit accordion state.

**Brand:** single dark theme. Obsidian `#0F0F10`, ivory `#F4F1EA`, Prestige gold `#C6A15B`, deep navy `#1D2A38`. Trirong headings, Sarabun body, Montserrat labels, Playfair Display selected numbers.

---

## IMPLEMENTATION PLAN

### Phase 1: Production Foundation

- Create isolated static site directory.
- Copy only approved page, design and campaign assets.
- Self-host required font files and remove production external font dependencies.
- Add runtime public configuration and deployment documentation.

### Phase 2: Core Implementation

- Harden semantic HTML and production metadata.
- Refactor interactions into resilient JavaScript with null-safe initialization.
- Implement secure checkout URL validation and pending state.
- Preserve approved UTM parameters during checkout handoff without exposing secrets.

### Phase 3: Validation and Taste Gate

- Add deterministic content and source validation.
- Run backend regression suite.
- Run responsive browser matrix, keyboard interactions and asset checks.
- Capture desktop and mobile screenshots.
- Apply technical review and taste pre-flight.

### Phase 4: Ship Artifacts

- Write implementation, execution and system-review reports.
- Commit atomically, push branch and open PR against the detected base branch.

---

## STEP-BY-STEP TASKS

### CREATE `web/dcts-sales-page/` production foundation

- **IMPLEMENT**: copy approved HTML/CSS/assets and keep mockup as historical design evidence.
- **IMPLEMENT**: self-host only the needed font weights with `font-display: swap`.
- **GOTCHA**: do not copy PNG source when WebP is already sufficient for production.
- **VALIDATE**: `python3 web/dcts-sales-page/scripts/validate.py --structure`
- **SATISFIES**: AC 1, 2, 7

### CREATE runtime public configuration

- **IMPLEMENT**: `window.DCTS_CONFIG` with checkout, support, VSL and policy URL fields defaulting to empty strings.
- **IMPLEMENT**: validate checkout URLs against HTTPS plus Stripe host allowlist.
- **IMPLEMENT**: preserve only approved UTM keys and never insert server secrets.
- **GOTCHA**: never call the HMAC-signed form webhook from browser code.
- **VALIDATE**: `python3 web/dcts-sales-page/scripts/validate.py --security`
- **SATISFIES**: AC 3, 4, 5

### UPDATE page interactions for production

- **IMPLEMENT**: mobile menu, accordions, modal lifecycle, focus trap, Escape handling, sticky CTA and checkout configuration states.
- **IMPLEMENT**: disabled/pending state when public configuration is absent.
- **PATTERN**: preserve proven interaction behavior from `mockups/dcts-sales-page/script.js`.
- **VALIDATE**: `node --check web/dcts-sales-page/app.js`
- **SATISFIES**: AC 4, 6, 8

### CREATE deterministic validation scripts

- **IMPLEMENT**: parse HTML, resolve local assets, reject prohibited claims and secret markers, require risk language, verify CTA label, ensure no external font dependency and ensure no em/en dash in visible text.
- **IMPLEMENT**: browser QA at 390x844 and 1440x900 with console/network capture and interaction assertions.
- **VALIDATE**: `python3 web/dcts-sales-page/scripts/validate.py`
- **SATISFIES**: AC 2-10

### UPDATE repository documentation

- **IMPLEMENT**: document static site validation and configuration-ready state in root README.
- **IMPLEMENT**: document missing approved values explicitly.
- **VALIDATE**: `python3 web/dcts-sales-page/scripts/validate.py --docs`
- **SATISFIES**: AC 9, 10

### RUN full validation and review

- **VALIDATE**: `uv run pytest -q`
- **VALIDATE**: `uv run ruff check .`
- **VALIDATE**: `uv run ruff format --check .`
- **VALIDATE**: `uv run mypy src`
- **VALIDATE**: `python3 web/dcts-sales-page/scripts/validate.py`
- **VALIDATE**: run local HTTP server and `browser-qa.js`
- **VALIDATE**: inspect mobile and desktop screenshots against taste pre-flight
- **SATISFIES**: AC 1-10

---

## TESTING STRATEGY

### Static Validation

- HTML parses without errors.
- Every local image, CSS, JavaScript, icon and font path resolves.
- No forbidden performance/scarcity/guarantee copy appears.
- Required risk language appears.
- No secret-marker names or paid LINE URLs appear.
- CTA label is consistent.
- Checkout code rejects non-HTTPS and non-Stripe hosts.
- Production page has no Google Fonts runtime request.

### Browser Integration

- Desktop navigation stays one line.
- Mobile has no horizontal overflow.
- Hero CTA is visible in the first viewport.
- Mobile sticky CTA appears after the hero.
- Menu, FAQ and curriculum accordions update ARIA state.
- Video and checkout dialogs open, trap focus and close with Escape.
- Missing approved checkout produces a pending state and no navigation.
- Images load and browser console/network remain clean.

### Backend Regression

The existing 22-test backend suite, Ruff, formatting and mypy must remain passing.

### Edge Cases

- `window.DCTS_CONFIG` missing entirely.
- Checkout URL empty.
- Checkout URL uses HTTP.
- Checkout URL uses an unapproved host.
- Current page contains unexpected query values.
- Reduced-motion mode.
- 320px-wide viewport.
- JavaScript unavailable: core content and legal disclaimer remain readable.

---

## VALIDATION COMMANDS

### Level 1: Syntax and Style

```bash
node --check web/dcts-sales-page/app.js
python3 web/dcts-sales-page/scripts/validate.py
uv run ruff check .
uv run ruff format --check .
```

### Level 2: Type and Unit Tests

```bash
uv run mypy src
uv run pytest -q
```

### Level 3: Browser Integration

```bash
python3 -m http.server 8788 --bind 127.0.0.1 --directory web/dcts-sales-page
NODE_PATH=/opt/data/profiles/rook-hw-team/node_modules node web/dcts-sales-page/scripts/browser-qa.js
```

### Level 4: Manual Validation

- Inspect 390x844, 768x1024 and 1440x900 screenshots.
- Verify CTA contrast, heading wraps, theme lock, image treatment and long-page rhythm.
- Confirm no real checkout or payment is triggered in unconfigured mode.

---

## ACCEPTANCE CRITERIA

- [ ] AC 1: Production artifact lives under `web/dcts-sales-page/`, separate from mockup and backend package.
- [ ] AC 2: Page preserves verified legacy brand and self-hosts production fonts/assets.
- [ ] AC 3: No browser secret or paid LINE room URL exists in source.
- [ ] AC 4: Checkout redirects only to configured approved Stripe HTTPS hosts.
- [ ] AC 5: Signed form and Stripe verification boundaries remain server-side and unchanged.
- [ ] AC 6: Mobile and desktop interactions are keyboard accessible and responsive.
- [ ] AC 7: Hero, images and CTA render without horizontal overflow or missing assets.
- [ ] AC 8: Unconfigured integrations fail safely and explain what is pending.
- [ ] AC 9: Compliance validator rejects prohibited claims and requires risk language.
- [ ] AC 10: Backend tests, lint, formatting, mypy and frontend validation pass.

---

## OPEN QUESTIONS / ASSUMPTIONS

User said “go ahead”; these are explicit assumptions for execution:

- Assumed: no public deployment in this ticket because domain and hosting target are unknown.
- Assumed: `3,990 THB` remains visibly provisional until client approval.
- Assumed: checkout remains unconfigured and cannot collect payment.
- Assumed: the approved public checkout will use `buy.stripe.com` or `checkout.stripe.com`.
- Assumed: real VSL, coach portrait, testimonials, evidence, legal URLs and business details remain pending.
- Assumed: the legacy dark DTCS marketing brand overrides the earlier light prototype direction.

## NOTES

A framework is intentionally not introduced. This is a single static marketing surface and the repository has no frontend framework to inherit. Native HTML/CSS/JavaScript minimizes bundle and dependency risk, supports static hosting, and preserves the backend's independent deployment boundary. A later deployment ticket can add CDN headers and domain-specific CSP without rebuilding business logic.

## AMENDMENTS

- 2026-08-18 - Initial plan created after CZ approved the verified legacy-brand Design Gate.
