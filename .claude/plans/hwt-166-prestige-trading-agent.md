# HWT-166 — Prestige/DCTS Trading Agent Implementation Plan

## Goal
Build a production-ready Pydantic AI + FastAPI service for the approved Messenger → form/Stripe → LINE community funnel. It must run locally without external credentials, expose real webhook contracts, persist idempotent CRM-shaped records, and swap in live Meta/Stripe/model credentials through environment variables.

## Locked decisions
- Messenger is acquisition; LINE is destination-only in v1.
- Existing forms remain link-outs; signed form webhook resumes the Messenger conversation and sends the LINE invite.
- Meta Lead Ads and organic Messenger DMs use one agent/state machine.
- Free group invite is automatic after form completion. Paid rooms never expose open invite links.
- Payments use Stripe; course checkout remains compatible with existing checkout.
- Backoffice is a small CRM-shaped database, migration-ready.
- One landing page with three deep-linked paths: newbie, course, indicator.
- Free trial requires no card.
- TradingView access is an approval queue because no official invite API is assumed.
- LMS enrollment is an outbound adapter triggered by paid Stripe events.

## Step-by-step tasks
1. Scaffold a Python 3.12+ `uv` project with FastAPI, Pydantic AI, SQLAlchemy/Alembic, httpx, Stripe, structured logging, pytest, Ruff and mypy.
   VALIDATE: `uv sync --all-groups`
2. Add typed settings, domain enums/schemas and CRM-shaped persistence for contacts, leads, conversations, messages, form submissions, subscriptions, webhook events, access requests and outbox jobs.
   VALIDATE: `uv run python -m compileall src`
3. Implement repositories/services, explicit state transitions, idempotency and transaction-safe outbox behavior.
   VALIDATE: `uv run pytest tests/unit -q`
4. Implement the Pydantic AI agent with typed dependencies and structured routing output; use deterministic safety/business rules around model output. Support an offline test model and provider configuration.
   VALIDATE: `uv run pytest tests/test_agent.py -q`
5. Implement FastAPI endpoints: health/readiness, internal chat, Meta verification + events, signed form completion, Stripe webhook, and API-key-protected admin read/approval endpoints.
   VALIDATE: `uv run pytest tests/integration -q`
6. Implement outbound adapters for Meta Messenger, LINE-invite-via-Messenger, TradingView approval queue, LMS enrollment and a local recording adapter.
   VALIDATE: `uv run pytest tests/test_adapters.py -q`
7. Add Alembic migration, Dockerfile, compose file, `.env.example`, CI workflow, operational README and webhook examples.
   VALIDATE: `docker build -t prestige-trading-agent:test .`
8. Run full validation and a live smoke test against a locally started server.
   VALIDATE: `uv run ruff check . && uv run mypy src && uv run pytest -q`

## Acceptance criteria
- Duplicate webhook deliveries do not create duplicate leads/messages/subscriptions.
- Organic DM and Lead Ad events converge on the same conversation service.
- A completed free/newbie form schedules the free LINE invite through Messenger.
- Paid Stripe success schedules LMS enrollment and gated-access work without leaking paid-room links.
- Trial requests create a TradingView approval item; approval is auditable via admin API.
- Invalid Meta verification, form signature, Stripe signature and admin API key are rejected.
- The agent can be exercised with no paid model/API account in tests.
- Test, lint, type-check, Docker build and live health/chat smoke tests pass.

## Assumptions
- Client-specific URLs, Meta IDs/tokens, Stripe secret and LMS endpoint are not yet supplied and remain environment configuration.
- SQLite is the zero-config dev/test database; PostgreSQL is the production target through `DATABASE_URL`.
- No frontend/admin dashboard is included in the agent repository; admin workflows are API-first.
