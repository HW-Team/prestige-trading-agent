# System Review - DCTS Production Sales Page

## What worked

- Starting from the approved prototype kept the legacy brand and content contract stable.
- Task-level static gates caught structural/security issues before browser QA.
- Runtime public configuration is isolated from application logic and defaults closed.
- Browser QA exercises real behavior rather than relying only on source heuristics.
- Local screenshots made the hero/taste check concrete across required breakpoints.
- Performance audit caught production-weight TTF and oversized-image delivery that functional QA could not detect.

## Process observations

- CSP directives supported only in HTTP headers should not be placed in a document meta policy. The page README now requires hosting-edge security headers.
- Lazy assets need explicit load orchestration in first-viewport QA; `complete === false` is not proof of a broken asset when `loading=lazy` is expected.
- The static validator and browser tests complement each other: source checks enforce regulated-copy/security invariants, while browser tests enforce actual focus, ARIA, overflow, local-network, and pending-state behavior.
- Self-hosting is not sufficient by itself: production fonts should be WOFF2 and subset to the supported scripts, and large campaign images need responsive source candidates.

## Follow-up boundary

The here.now URL is a permanent review preview, not the final production domain. A separate activation ticket should supply the final hosting/domain target, legal/business copy, real public URLs, reviewed evidence/media, final price decision, and edge headers. None should be inferred or activated from the preview.
