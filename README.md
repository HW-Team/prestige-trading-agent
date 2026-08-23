# Prestige Trading Agent

Production-oriented FastAPI and Pydantic AI service for Prestige/DCTS Trading's approved acquisition funnel:

```text
Meta organic DM / Meta Lead Ad
              ↓
       shared conversation agent
       ↙         ↓          ↘
  newbie       course      indicator trial
    form       Stripe       manual approval
      ↓          ↓               ↓
free LINE     LMS + gated     audited queue
community     access jobs    (no card needed)
```

Messenger is the acquisition and reply channel. LINE is destination-only. The service **never stores or sends an open paid-room invite URL**; paid access is represented as an opaque operations job. Only the configured free-community invite can be sent automatically, and only after a signed newbie-form completion.

## Features

- Current Pydantic AI structured-output agent with typed dependencies and deterministic business/safety rules.
- Credential-free offline `TestModel` routing for development and CI; set any Pydantic AI model identifier for live inference.
- Explicit, validated funnel state machine.
- CRM-shaped SQLAlchemy 2 async persistence: contacts, leads, conversations, messages, form submissions, subscriptions, webhook events, TradingView access requests and outbox jobs.
- Sequential webhook idempotency through provider IDs, unique constraints and deterministic outbox dedupe keys.
- Meta webhook verification and HMAC validation for organic DMs and Lead Ads.
- HMAC-signed form completion, Stripe-native webhook verification and API-key-protected admin routes.
- Transactional outbox with local recording and live Messenger/LMS adapters.
- SQLite local mode, PostgreSQL production support, Alembic migration, Docker Compose and CI.

## Quick start

Requirements: Python 3.12+ and [uv](https://docs.astral.sh/uv/).

```bash
cp .env.example .env
# Replace all change-me/replace-me secrets before exposing the service.
uv sync --all-groups
uv run alembic upgrade head
uv run uvicorn prestige_trading_agent.main:app --reload
```

Local defaults use SQLite, the offline model and recording outbound adapter. No Meta, Stripe, LMS or paid-model account is needed for tests.

```bash
uv run pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src
```

OpenAPI is at `http://localhost:8000/docs`.

## DCTS static sales page

The isolated production artifact lives at [`web/dcts-sales-page/`](web/dcts-sales-page/). It is configuration-ready but intentionally unconfigured: checkout, VSL, support, policy, business, and evidence values remain pending approval, and the visible `3,990 THB` price remains provisional. The checked-in state cannot collect payment.

Validate it with:

```bash
python3 web/dcts-sales-page/scripts/validate.py
```

Public deploy-time URLs belong only in `web/dcts-sales-page/config.js`; browser code must never contain secrets or private access links. See the page-level README for the URL allowlist, local server, browser QA, and deployment checklist.

## Configuration

All variables use the `PRESTIGE_` prefix. See `.env.example` for the full list.

| Variable | Purpose |
|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite` locally or `postgresql+asyncpg` in production |
| `MODEL` | `test` for offline deterministic behavior, or a Pydantic AI model identifier |
| `OUTBOUND_MODE` | `recording` or `live` |
| `ADMIN_API_KEY` | Protects internal chat and all admin APIs |
| `META_VERIFY_TOKEN` | Meta GET challenge token |
| `META_APP_SECRET` | Verifies `X-Hub-Signature-256` |
| `META_PAGE_ACCESS_TOKEN` | Required only for live Messenger sends |
| `FORM_WEBHOOK_SECRET` | Verifies `X-Form-Signature` |
| `STRIPE_WEBHOOK_SECRET` | Verifies Stripe's signature header |
| `FREE_LINE_INVITE_URL` | The only LINE URL an automated adapter may send |
| `NEWBIE_FORM_URL` | Newbie deep-linked landing/form path |
| `COURSE_CHECKOUT_URL` | Existing Stripe-compatible course path |
| `INDICATOR_FORM_URL` | No-card indicator trial path |
| `LMS_ENDPOINT`, `LMS_API_KEY` | Optional live LMS enrollment adapter |

Pydantic AI provider credentials are read using that provider's standard environment variables (for example `OPENAI_API_KEY`).

## HTTP contracts

| Method/path | Authentication | Behavior |
|---|---|---|
| `GET /health` | none | Liveness |
| `GET /ready` | none | Database readiness |
| `POST /internal/chat` | `X-API-Key` | Exercise the shared conversation agent |
| `GET /webhooks/meta` | Meta verify token | Webhook subscription challenge |
| `POST /webhooks/meta` | Meta HMAC | Organic DM and Lead Ad ingestion |
| `POST /webhooks/form` | form HMAC | Resume funnel and schedule free invite |
| `POST /webhooks/stripe` | Stripe signature | Paid-event ingestion and gated work |
| `GET /admin/leads` | `X-API-Key` | CRM lead list |
| `GET /admin/access-requests` | `X-API-Key` | TradingView approval queue |
| `POST /admin/access-requests/{id}/approve` | `X-API-Key` | Audited approval |
| `GET /admin/outbox` | `X-API-Key` | Outbox operations view |

Exact sample payloads and signature formats are in [`examples/webhooks.md`](examples/webhooks.md).

## Outbox operation

Business handlers and their outbox jobs commit in the same database transaction. Dispatch is a separate retryable operation:

```bash
uv run python -m prestige_trading_agent.worker --once
```

`recording` mode performs no network calls. `live` mode sends normal/free-invite replies through Meta and enrollment to the LMS. `provision_paid_access` remains an auditable operations action; it intentionally has no open LINE invite implementation. Run the worker on a scheduler or as a separate deployment. Downstream APIs should apply the supplied deterministic provider/dedupe identifiers because delivery is at-least-once.

## Database and migrations

The application creates tables automatically only for zero-config local/test startup. Production deployments should run:

```bash
PRESTIGE_DATABASE_URL=postgresql+asyncpg://... uv run alembic upgrade head
```

To validate migration round trips locally:

```bash
PRESTIGE_DATABASE_URL=sqlite+aiosqlite:///./migration-test.db uv run alembic upgrade head
PRESTIGE_DATABASE_URL=sqlite+aiosqlite:///./migration-test.db uv run alembic downgrade base
```

## Docker

```bash
docker build -t prestige-trading-agent:test .
docker compose up --build
```

Compose starts PostgreSQL, applies migrations, and launches the API. Its placeholder secrets and recording/test modes are safe for local wiring only; inject managed secrets and a live model/outbound mode in production.

## Security and operating notes

- Keep raw webhook bodies unchanged until signature verification is complete.
- Rotate the admin API key and provider secrets through a secret manager.
- Restrict `/internal/*` and `/admin/*` at the network edge in addition to the API key.
- Meta Lead Ads initially create a CRM contact keyed by leadgen ID. A production enrichment job may fetch field data using the page token without changing the conversation workflow.
- The agent gives general educational routing only. Deterministic rules override model text that promises returns, claims no risk or attempts to reveal gated links.
- TradingView has no assumed invite API. Trial approval is manual and auditable.
- Health checks never disclose credentials or database details.
