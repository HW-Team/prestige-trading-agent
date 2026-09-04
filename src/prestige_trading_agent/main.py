import asyncio
import contextlib
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
from fastapi.staticfiles import StaticFiles
from pydantic import ValidationError
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from prestige_trading_agent.adapters import LiveAdapter, RecordingAdapter
from prestige_trading_agent.agent import AgentRoute, build_agent
from prestige_trading_agent.config import Settings, get_settings
from prestige_trading_agent.db import Database
from prestige_trading_agent.domain import (
    ApprovalRequest,
    ChatRequest,
    FeedbackCreate,
    FormCompletion,
    PaymentCheckRequest,
    PaymentRequest,
)
from prestige_trading_agent.models import (
    AccessRequest,
    Conversation,
    Feedback,
    Lead,
    Message,
    OutboxJob,
)
from prestige_trading_agent.services import (
    InvalidTransition,
    approve_access,
    complete_form,
    conversation_is_checkout,
    crosscheck_google_sheet,
    handle_slip_image,
    ingest_message,
    process_stripe_event,
    validate_slip_with_easyslip,
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

        # Schema bootstrap: SQLite (dev/tests) uses create_all — fast and
        # idempotent; Postgres (production) runs Alembic migrations so schema
        # stays in sync as migrations evolve. Alembic on SQLite also works but
        # spins its own event loop, so keep tests on create_all.
        # Migrations run in a background task: a slow first-boot migration
        # must never block startup and fail Coolify's healthcheck (which
        # caused container rollback and kept the app on the old SQLite).
        if config.database_url.startswith("sqlite"):
            await database.create_schema()
        else:
            from alembic import command
            from alembic.config import Config as AlembicConfig

            def _run_migrations() -> None:
                alembic_cfg = AlembicConfig("alembic.ini")
                alembic_cfg.set_main_option("sqlalchemy.url", config.database_url)
                command.upgrade(alembic_cfg, "head")

            async def _migrate_bg() -> None:
                try:
                    await asyncio.to_thread(_run_migrations)
                    logger.info("alembic_upgrade_done")
                except Exception as exc:
                    # Never crash the app over schema bootstrap; the agent
                    # surfaces DB errors on the endpoints that need tables.
                    logger.warning("alembic_upgrade_failed", error=str(exc))

            app.state.migration_task = asyncio.create_task(_migrate_bg())
        # Preload mem0 (embedding model download) in the background so the
        # first customer webhook is never blocked by a 30s+ model fetch.
        from prestige_trading_agent.memory import preload_memory

        app.state.memory_preload_task = asyncio.create_task(preload_memory())
        app.state.database = database
        app.state.agent = agent
        app.state.adapter = adapter
        logger.info(
            "service_started",
            environment=config.environment,
            database_url=config.database_url,
            outbound_mode=config.outbound_mode,
        )

        # Outbox worker: poll for pending jobs and dispatch them (Messenger /
        # LINE sends, LMS enroll, access provisioning). In "recording" mode the
        # adapter only logs, so this loop is harmless pre-production.
        worker_task: asyncio.Task[None] | None = None

        async def _outbox_loop() -> None:
            from prestige_trading_agent.outbox import drain_outbox

            poll_interval = 2.0
            while True:
                try:
                    await drain_outbox(database, adapter)
                except Exception as exc:
                    logger.warning("outbox_drain_failed", error=str(exc))
                await asyncio.sleep(poll_interval)

        worker_task = asyncio.create_task(_outbox_loop())
        try:
            yield
        finally:
            if worker_task is not None:
                worker_task.cancel()
                with contextlib.suppress(asyncio.CancelledError):
                    await worker_task
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

    # Serve dynamic generated QRs FIRST so /assets/qr-*.png never gets shadowed
    # by the static mount below (which only holds qr-990/qr-3990 from the repo).
    @app.get("/assets/qr-{package}.png", include_in_schema=False)
    async def generated_qr(package: str) -> Response:
        qr_file = data_qr_dir / f"qr-{package}.png"
        if not qr_file.is_file():
            raise HTTPException(status_code=404, detail="QR not generated yet")
        return Response(content=qr_file.read_bytes(), media_type="image/png")

    # Serve static assets (payment QR, test console) from web/.
    assets_dir = (
        Path(__file__).resolve().parent.parent.parent / "web" / "agent-test-console" / "assets"
    )
    if assets_dir.is_dir():
        app.mount("/assets", StaticFiles(directory=str(assets_dir)), name="assets")

    # Serve dynamically generated payment QRs persisted under /data (EasySlip).
    data_qr_dir = Path("/data")
    if data_qr_dir.is_dir():
        app.mount("/data", StaticFiles(directory=str(data_qr_dir)), name="data")

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
        route, _, reply_message_id = await ingest_message(
            session,
            agent,
            external_id=payload.external_id,
            message_id=f"internal:{uuid4()}",
            text=payload.message,
            source="internal",
            source_id=payload.external_id,
            channel="internal",
        )
        # Attach the persisted reply id so the test console can capture
        # feedback against the exact message (kept out of AgentRoute schema).
        if reply_message_id is not None:
            route.reply_message_id = reply_message_id
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
        sig_ok = _verify_hmac(
            config.meta_app_secret.get_secret_value(), body, x_hub_signature_256, "sha256="
        )
        logger.info(
            "meta_webhook_received",
            bytes_in=len(body),
            signature_present=bool(x_hub_signature_256),
            signature_valid=sig_ok,
        )
        if not sig_ok:
            raise HTTPException(status_code=401, detail="Invalid Meta signature")
        try:
            payload: dict[str, Any] = json.loads(body)
        except (json.JSONDecodeError, UnicodeDecodeError) as exc:
            raise HTTPException(status_code=400, detail="Invalid JSON") from exc
        processed = 0
        duplicates = 0
        for entry in payload.get("entry", []):
            for item in entry.get("messaging", []):
                # Two event shapes carry user intent into the funnel:
                #  1) message  — a text/image the customer typed (has a mid)
                #  2) postback — a button tap ("Get started" / ad CTA).
                #     Postbacks have NO message.mid, so the old guard silently
                #     dropped them — those customers never got a reply.
                # EXCEPTION (both shapes): "รับข้อเสนอ / Get offers / accept
                # offer" is the user ACCEPTING a broadcast ad offer (a promo
                # broadcast the page sent them), NOT real buying intent —
                # ignore so the bot doesn't pitch/QR-spam offer-accepters.
                message = item.get("message") or {}
                sender = str((item.get("sender") or {}).get("id", ""))
                message_id = str(message.get("mid", ""))
                postback = item.get("postback")
                logger.info(
                    "meta_webhook_item",
                    sender=sender,
                    message_id=message_id,
                    is_echo=message.get("is_echo"),
                    text=str(message.get("text", ""))[:120],
                    postback_title=str((postback or {}).get("title", ""))[:80],
                )
                offer_accept = (
                    "รับข้อเสนอ" in str(message.get("text", ""))
                    or "get offers" in str(message.get("text", "")).lower()
                    or "รับข้อเสนอ" in str((postback or {}).get("title", "") or "")
                    or "get offers" in str((postback or {}).get("title", "") or "").lower()
                    or "accept" in str((postback or {}).get("payload", "") or "").lower()
                )
                if offer_accept:
                    # Meta ad-offer acceptance (broadcast promo): not real
                    # interest — skip silently.
                    continue
                if postback:
                    message_id = f"postback:{sender}:{item.get('timestamp', '')}"
                    text = str(postback.get("title", "") or "")
                    if not text:
                        # Some CTAs carry only a payload (e.g. the ad offer
                        # button) — still answer so the lead isn't dropped.
                        text = "สนใจข้อเสนอครับ"
                else:
                    text = str(message.get("text", ""))
                if not sender or not message_id or message.get("is_echo"):
                    continue
                _, duplicate, _ = await ingest_message(
                    session,
                    agent,
                    external_id=sender,
                    message_id=message_id,
                    text=text,
                    source="meta_organic",
                    source_id=sender,
                )
                processed += int(not duplicate)
                duplicates += int(duplicate)
                # Slip images: a Messenger image attachment may be a payment
                # slip. If we're mid-checkout, validate it via EasySlip and
                # route the outcome (paid → form+FB group; mismatch → retry).
                attachments = message.get("attachments") or []
                image_urls = [
                    str(a["payload"]["url"])
                    for a in attachments
                    if a.get("type") == "image" and a.get("payload", {}).get("url")
                ]
                if image_urls and conversation_is_checkout(session, sender):
                    await handle_slip_image(session, config, sender, image_urls[0])
            for change in entry.get("changes", []):
                if change.get("field") != "leadgen":
                    continue
                value = change.get("value") or {}
                leadgen_id = str(value.get("leadgen_id", ""))
                if not leadgen_id:
                    continue
                external_id = f"leadgen:{leadgen_id}"
                _, duplicate, _ = await ingest_message(
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

    @app.post("/webhooks/line")
    async def line_events(
        request: Request,
        session: AsyncSession = Depends(session_dependency),
        x_line_signature: str = Header(default=""),
    ) -> dict[str, Any]:
        """LINE Messaging API webhook. Signature = HMAC-SHA256 of the raw body
        using the channel secret; never trust events without a valid signature."""
        body = await request.body()
        if not _verify_hmac(
            config.line_channel_secret.get_secret_value() if config.line_channel_secret else "",
            body,
            x_line_signature,
            "",  # LINE sends raw base64 HMAC, no prefix
        ):
            raise HTTPException(status_code=401, detail="Invalid LINE signature")
        try:
            events = json.loads(body.decode("utf-8")).get("events", [])
        except (json.JSONDecodeError, UnicodeDecodeError):
            raise HTTPException(status_code=400, detail="Invalid LINE payload") from None
        processed = 0
        for event in events:
            if event.get("type") != "message":
                continue
            message = event.get("message", {})
            source = event.get("source", {})
            reply_token = event.get("replyToken", "")
            user_id = source.get("userId", "")
            text = str(message.get("text", ""))
            if not user_id or not text:
                continue
            _, duplicate, _ = await ingest_message(
                session,
                agent,
                external_id=user_id,
                message_id=f"line:{reply_token or user_id}:{message.get('id', '')}",
                text=text,
                source="line",
                source_id=user_id,
                channel="line",
            )
            processed += int(not duplicate)
        return {"status": "accepted", "processed": processed}

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

    @app.get("/admin/memory")
    async def memory_viewer(
        request: Request,
        authorization: str | None = Header(default=None),
    ) -> Response:
        """Mem0 memory viewer — Basic-auth HTML page (user: admin, pw: admin key).

        Lists every memory mem0 holds, grouped by customer, with a search box.
        Reads straight from the local Chroma store at /data/mem0.
        """
        if authorization is None or not authorization.startswith("Basic "):
            return Response(
                content="Unauthorized",
                status_code=401,
                headers={"WWW-Authenticate": 'Basic realm="mem0", charset="UTF-8"'},
            )
        import base64

        try:
            decoded = base64.b64decode(authorization[6:]).decode("utf-8")
            user, _, pw = decoded.partition(":")
        except Exception:
            return Response(content="Unauthorized", status_code=401)
        if user != "admin" or not hmac.compare_digest(
            pw, config.admin_api_key.get_secret_value()
        ):
            return Response(content="Unauthorized", status_code=401)

        from prestige_trading_agent.memory import get_memory

        memory = get_memory()
        rows: list[dict[str, str]] = []
        error = ""
        if memory is None:
            error = "Mem0 not initialized (no memories stored yet)."
        else:
            try:
                import asyncio

                def _load() -> list[dict[str, str]]:
                    coll = memory.vector_store.collection
                    data = coll.get(include=["documents", "metadatas"])
                    out: list[dict[str, str]] = []
                    for doc, meta in zip(
                        data.get("documents", []) or [],
                        data.get("metadatas", []) or [],
                        strict=False,
                    ):
                        out.append(
                            {
                                "user": str((meta or {}).get("user_id", "?")),
                                "memory": str(doc or ""),
                                "updated": str((meta or {}).get("updated_at", ""))[:19],
                            }
                        )
                    return out

                rows = await asyncio.to_thread(_load)
            except Exception as exc:
                error = f"Failed to read mem0 store: {exc}"
        rows.sort(key=lambda r: (r["user"], r["updated"]), reverse=True)

        cards = "".join(
            f'<div class="card"><div class="user">{r["user"]}</div>'
            f'<div class="mem">{r["memory"]}</div>'
            f'<div class="ts">{r["updated"]}</div></div>'
            for r in rows
        )
        html = f"""<!doctype html><html lang="th"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Mem0 — Prestige Agent</title>
<style>
body{{font-family:-apple-system,'Segoe UI',Roboto,sans-serif;background:#f5f6f8;margin:0;padding:24px}}
.wrap{{max-width:860px;margin:0 auto}}
h1{{font-size:20px;color:#1a1a2e;margin:0 0 4px}}
.sub{{color:#888;font-size:13px;margin-bottom:18px}}
input{{width:100%;padding:12px 14px;border:1px solid #ddd;border-radius:10px;font-size:15px;box-sizing:border-box;margin-bottom:18px}}
.card{{background:#fff;border:1px solid #e8e8ef;border-radius:12px;padding:14px 16px;margin-bottom:10px}}
.user{{font-weight:600;font-size:13px;color:#6c5ce7;margin-bottom:6px}}
.mem{{font-size:15px;color:#222;line-height:1.5}}
.ts{{font-size:12px;color:#aaa;margin-top:6px}}
.err{{background:#fdecea;color:#b33939;padding:12px;border-radius:10px;margin-bottom:16px}}
.count{{font-size:12px;color:#aaa;margin-bottom:10px}}
</style></head><body><div class="wrap">
<h1>🧠 Mem0 Memory</h1><div class="sub">Cross-session customer memory — self-hosted (Chroma)</div>
{f'<div class="err">{error}</div>' if error else ''}
<input id="q" placeholder="ค้นหา memory หรือ customer id..." oninput="filter()">
<div class="count" id="cnt"></div>
<div id="list">{cards or '<div class="sub">ยังไม่มี memory — รอลูกค้าคุยกับ agent ก่อน</div>'}</div>
</div>
<script>
const cards=[...document.querySelectorAll('.card')];
function filter(){{const q=document.getElementById('q').value.toLowerCase();
let n=0;for(const c of cards){{const hit=c.textContent.toLowerCase().includes(q);c.style.display=hit?'':'none';if(hit)n++;}}
document.getElementById('cnt').textContent=n+'/'+cards.length;}}
filter();
</script></body></html>"""
        return Response(content=html, media_type="text/html")

    @app.post("/internal/payment", dependencies=[Depends(require_admin)])
    async def internal_payment(
        payload: PaymentRequest, session: AsyncSession = Depends(session_dependency)
    ) -> dict[str, str]:
        """Return the payment QR + bank info + the package's post-payment form.

        Call this when a customer picks a package. 990 → form_990_url,
        3990 → form_3990_url. Always returns the approved QR image URL.
        """
        form_url = {
            "990": config.form_990_url,
            "3990": config.form_3990_url,
            "1580": config.form_1580_url,
        }.get(payload.package, config.form_990_url)
        return {
            "qr_image": config.payment_qr_url,
            "bank_name": config.bank_name,
            "bank_account_name": config.bank_account_name,
            "account_number": config.bank_account_number,
            "promptpay_ref": config.promptpay_ref,
            "instructions": config.payment_instructions,
            "form_url": form_url,
        }

    @app.post("/internal/check-payment", dependencies=[Depends(require_admin)])
    async def internal_check_payment(
        payload: PaymentCheckRequest, session: AsyncSession = Depends(session_dependency)
    ) -> dict[str, Any]:
        """Validate a payment. EasySlip first (if configured), then fall back
        to cross-checking the package's public Google Sheet by identity."""
        sheet_id = config.sheet_3990_id if payload.package == "3990" else config.sheet_990_id
        easyslip = await validate_slip_with_easyslip(
            session,
            config,
            slip_image_url=payload.slip_image_url or "",
            expected_amount=payload.expected_amount,
        )
        if easyslip["ok"]:
            return {"valid": True, "method": "easyslip", **easyslip}
        sheet = await crosscheck_google_sheet(
            session,
            config,
            sheet_id=sheet_id,
            external_id=payload.external_id,
            line_id=payload.line_id,
            phone=payload.phone,
            email=payload.email,
        )
        if sheet["ok"]:
            return {"valid": True, "method": "sheet", **sheet}
        # Neither validated: if the sheet was reachable but no match, it's a
        # genuine pending state; hand off to an admin to review manually.
        return {
            "valid": False,
            "method": "none",
            "reason": sheet["reason"],
            "easyslip_reason": easyslip["reason"],
        }

    @app.post("/internal/feedback", dependencies=[Depends(require_admin)])
    async def submit_feedback(
        payload: FeedbackCreate, session: AsyncSession = Depends(session_dependency)
    ) -> dict[str, str]:
        message = await session.get(Message, payload.message_id)
        if message is None:
            raise HTTPException(status_code=404, detail="Message not found")
        session.add(
            Feedback(
                message_id=message.id,
                rating=payload.rating,
                comment=payload.comment,
                tester=payload.tester,
            )
        )
        await session.flush()
        # Fire-and-forget Telegram push so the operator can act on feedback
        # immediately; never blocks or fails the capture.
        if isinstance(adapter, LiveAdapter):
            rating_label = {
                "good": "👍 ดี",
                "bad": "👎 แก้ไข",
                "needs_work": "👎 ต้องปรับ",
            }.get(payload.rating, payload.rating)
            lines = [
                "📝 **Prestige Agent — Feedback ใหม่**",
                f"คะแนน: {rating_label}",
                f"AI ตอบ: {message.text[:220]}",
            ]
            if payload.comment:
                lines.append(f"ความคิดเห็น: {payload.comment}")
            if payload.tester:
                lines.append(f"ผู้ทดสอบ: {payload.tester}")
            lines.append(f"message_id: `{message.id}`")
            await adapter.notify_feedback("\n".join(lines))
        return {"status": "recorded"}

    @app.get("/admin/feedback", dependencies=[Depends(require_admin)])
    async def list_feedback(
        session: AsyncSession = Depends(session_dependency),
        limit: int = Query(default=200, le=1000),
    ) -> list[dict[str, Any]]:
        rows = (
            await session.scalars(
                select(Feedback).order_by(Feedback.created_at.desc()).limit(limit)
            )
        ).all()
        message_ids = {r.message_id for r in rows}
        messages = {
            m.id: m
            for m in await session.scalars(select(Message).where(Message.id.in_(message_ids)))
        }
        conversation_ids = {m.conversation_id for m in messages.values()}
        conversations = {
            c.id: c
            for c in await session.scalars(
                select(Conversation).where(Conversation.id.in_(conversation_ids))
            )
        }
        return [
            {
                "id": r.id,
                "rating": r.rating,
                "comment": r.comment,
                "tester": r.tester,
                "created_at": r.created_at.isoformat(),
                "message": {
                    "id": r.message_id,
                    "text": messages[r.message_id].text,
                    "direction": messages[r.message_id].direction,
                    "conversation_id": messages[r.message_id].conversation_id,
                    "external_thread_id": conversations[
                        messages[r.message_id].conversation_id
                    ].external_thread_id,
                },
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
