import hashlib
import hmac
import json
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from pathlib import Path
from typing import Any
from uuid import uuid4

import stripe
import structlog
import uvicorn
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request, Response, status
from fastapi.encoders import jsonable_encoder
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from prestige_trading_agent.adapters import LiveAdapter, RecordingAdapter
from prestige_trading_agent.agent import AgentRoute, build_agent
from prestige_trading_agent.config import Settings, get_settings
from prestige_trading_agent.db import Database
from prestige_trading_agent.domain import ApprovalRequest, ChatRequest, FormCompletion
from prestige_trading_agent.models import (
    AccessRequest,
    Conversation,
    Lead,
    Message,
    OutboxJob,
)
from prestige_trading_agent.services import (
    InvalidTransition,
    approve_access,
    complete_form,
    ingest_message,
    process_stripe_event,
)

logger = structlog.get_logger()


def _verify_hmac(secret: str, body: bytes, supplied: str, prefix: str = "") -> bool:
    expected = prefix + hmac.new(secret.encode(), body, hashlib.sha256).hexdigest()
    return hmac.compare_digest(expected, supplied)


def create_app(settings: Settings | None = None) -> FastAPI:
    config = settings or get_settings()
    database = Database(config.database_url)
    agent = build_agent(
        config.model,
        base_url=config.model_base_url,
        api_key=config.model_api_key.get_secret_value() if config.model_api_key else None,
    )
    adapter = RecordingAdapter() if config.outbound_mode == "recording" else LiveAdapter(config)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        if config.environment != "production":
            await database.create_schema()
        app.state.database = database
        app.state.agent = agent
        app.state.adapter = adapter
        logger.info("service_started", environment=config.environment)
        yield
        await database.dispose()

    app = FastAPI(title="Prestige Trading Agent", version="0.1.0", lifespan=lifespan)

    async def session_dependency() -> AsyncIterator[AsyncSession]:
        async with database.session_factory() as session:
            try:
                yield session
                await session.commit()
            except Exception:
                await session.rollback()
                raise

    def require_admin(x_api_key: str | None = Header(default=None)) -> None:
        if x_api_key is None or not hmac.compare_digest(
            x_api_key, config.admin_api_key.get_secret_value()
        ):
            raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid API key")

    @app.get("/health")
    async def health() -> dict[str, str]:
        return {"status": "ok"}

    @app.get("/ready")
    async def ready(session: AsyncSession = Depends(session_dependency)) -> dict[str, str]:
        await session.execute(text("SELECT 1"))
        return {"status": "ready"}

    @app.get("/test", include_in_schema=False)
    async def test_console() -> Response:
        """Dev-only chat test console (serves the HTML with the admin key injected)."""
        if config.environment == "production":
            raise HTTPException(status_code=404, detail="Not found in production")
        html = (
            Path(__file__).resolve().parent.parent.parent
            / "web"
            / "agent-test-console"
            / "index.html"
        ).read_text(encoding="utf-8")
        injected = html.replace(
            "const API_KEY = null;",
            f"const API_KEY = {json.dumps(config.admin_api_key.get_secret_value())};",
        )
        return Response(content=injected, media_type="text/html")

    @app.post("/internal/chat", response_model=AgentRoute, dependencies=[Depends(require_admin)])
    async def internal_chat(
        payload: ChatRequest, session: AsyncSession = Depends(session_dependency)
    ) -> AgentRoute:
        route, _ = await ingest_message(
            session,
            agent,
            external_id=payload.external_id,
            message_id=f"internal:{uuid4()}",
            text=payload.message,
            source="internal",
            source_id=payload.external_id,
            channel="internal",
        )
        return route

    @app.get("/webhooks/meta")
    async def verify_meta(
        hub_mode: str | None = Query(default=None, alias="hub.mode"),
        hub_verify_token: str | None = Query(default=None, alias="hub.verify_token"),
        hub_challenge: str | None = Query(default=None, alias="hub.challenge"),
    ) -> Response:
        valid = (
            hub_mode == "subscribe"
            and hub_verify_token is not None
            and hmac.compare_digest(hub_verify_token, config.meta_verify_token.get_secret_value())
            and hub_challenge is not None
        )
        if not valid:
            raise HTTPException(status_code=403, detail="Meta verification failed")
        return Response(content=hub_challenge, media_type="text/plain")

    @app.post("/webhooks/meta")
    async def meta_events(
        request: Request,
        session: AsyncSession = Depends(session_dependency),
        x_hub_signature_256: str = Header(default=""),
    ) -> dict[str, Any]:
        body = await request.body()
        if not _verify_hmac(
            config.meta_app_secret.get_secret_value(), body, x_hub_signature_256, "sha256="
        ):
            raise HTTPException(status_code=401, detail="Invalid Meta signature")
        try:
            payload: dict[str, Any] = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc
        processed = 0
        duplicates = 0
        for entry in payload.get("entry", []):
            for item in entry.get("messaging", []):
                message = item.get("message") or {}
                sender = str((item.get("sender") or {}).get("id", ""))
                message_id = str(message.get("mid", ""))
                if not sender or not message_id or message.get("is_echo"):
                    continue
                _, duplicate = await ingest_message(
                    session,
                    agent,
                    external_id=sender,
                    message_id=message_id,
                    text=str(message.get("text", "")),
                    source="meta_organic",
                    source_id=sender,
                )
                processed += int(not duplicate)
                duplicates += int(duplicate)
            for change in entry.get("changes", []):
                if change.get("field") != "leadgen":
                    continue
                value = change.get("value") or {}
                leadgen_id = str(value.get("leadgen_id", ""))
                if not leadgen_id:
                    continue
                external_id = f"leadgen:{leadgen_id}"
                _, duplicate = await ingest_message(
                    session,
                    agent,
                    external_id=external_id,
                    message_id=f"leadgen:{leadgen_id}",
                    text="Meta Lead Ad form submitted",
                    source="meta_lead_ad",
                    source_id=leadgen_id,
                    # A Lead Ads leadgen ID is not a Messenger PSID and cannot be used
                    # as a Graph API message recipient. Keep it in the shared funnel
                    # service without scheduling an invalid Messenger send.
                    channel="lead_ad",
                )
                processed += int(not duplicate)
                duplicates += int(duplicate)
        return {"status": "accepted", "processed": processed, "duplicates": duplicates}

    @app.post("/webhooks/form")
    async def form_events(
        request: Request,
        session: AsyncSession = Depends(session_dependency),
        x_form_signature: str = Header(default=""),
    ) -> dict[str, Any]:
        body = await request.body()
        if not _verify_hmac(config.form_webhook_secret.get_secret_value(), body, x_form_signature):
            raise HTTPException(status_code=401, detail="Invalid form signature")
        try:
            form = FormCompletion.model_validate_json(body)
        except ValidationError as exc:
            raise HTTPException(status_code=422, detail=jsonable_encoder(exc.errors())) from exc
        submission, duplicate = await complete_form(session, form)
        return {
            "status": "accepted",
            "submission_id": submission.submission_id,
            "duplicate": duplicate,
        }

    @app.post("/webhooks/stripe")
    async def stripe_events(
        request: Request,
        session: AsyncSession = Depends(session_dependency),
        stripe_signature: str = Header(default="", alias="Stripe-Signature"),
    ) -> dict[str, Any]:
        body = await request.body()
        try:
            event = stripe.Webhook.construct_event(
                body, stripe_signature, config.stripe_webhook_secret.get_secret_value()
            )
        except (ValueError, stripe.SignatureVerificationError) as exc:
            raise HTTPException(status_code=400, detail="Invalid Stripe webhook") from exc
        event_data: dict[str, Any] = event.to_dict()
        duplicate = await process_stripe_event(session, event_data)
        return {"status": "accepted", "duplicate": duplicate}

    @app.get("/admin/leads", dependencies=[Depends(require_admin)])
    async def list_leads(session: AsyncSession = Depends(session_dependency)) -> Any:
        items = list((await session.scalars(select(Lead).order_by(Lead.created_at))).all())
        return jsonable_encoder(items)

    @app.get("/admin/access-requests", dependencies=[Depends(require_admin)])
    async def list_access_requests(session: AsyncSession = Depends(session_dependency)) -> Any:
        items = list(
            (await session.scalars(select(AccessRequest).order_by(AccessRequest.created_at))).all()
        )
        return jsonable_encoder(items)

    @app.get("/admin/messages", dependencies=[Depends(require_admin)])
    async def list_messages(
        session: AsyncSession = Depends(session_dependency),
        limit: int = Query(default=200, le=1000),
    ) -> list[dict[str, Any]]:
        rows = (
            await session.scalars(select(Message).order_by(Message.created_at.desc()).limit(limit))
        ).all()
        conversation_ids = {r.conversation_id for r in rows}
        conversations = {
            c.id: c
            for c in await session.scalars(
                select(Conversation).where(Conversation.id.in_(conversation_ids))
            )
        }
        return [
            {
                "id": r.id,
                "conversation_id": r.conversation_id,
                "conversation": {
                    "id": r.conversation_id,
                    "external_thread_id": conversations[r.conversation_id].external_thread_id,
                },
                "direction": r.direction,
                "text": r.text,
                "created_at": r.created_at.isoformat(),
            }
            for r in rows
        ]

    @app.post("/admin/access-requests/{request_id}/approve", dependencies=[Depends(require_admin)])
    async def approve_access_request(
        request_id: str,
        approval: ApprovalRequest,
        session: AsyncSession = Depends(session_dependency),
    ) -> Any:
        try:
            item = await approve_access(session, request_id, approval.reviewed_by, approval.note)
        except InvalidTransition as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        if item is None:
            raise HTTPException(status_code=404, detail="Access request not found")
        return jsonable_encoder(item)

    @app.get("/admin/outbox", dependencies=[Depends(require_admin)])
    async def list_outbox(session: AsyncSession = Depends(session_dependency)) -> Any:
        items = list(
            (await session.scalars(select(OutboxJob).order_by(OutboxJob.created_at))).all()
        )
        return jsonable_encoder(items)

    return app


app = create_app()


def run() -> None:
    uvicorn.run("prestige_trading_agent.main:app", host="0.0.0.0", port=8000)
