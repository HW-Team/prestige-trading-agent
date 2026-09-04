from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from prestige_trading_agent.agent import AgentDependencies, AgentRoute, route_message
from prestige_trading_agent.domain import (
    AccessStatus,
    FormCompletion,
    FunnelPath,
    FunnelState,
    NextAction,
    OutboxKind,
)
from prestige_trading_agent.models import (
    AccessRequest,
    Contact,
    Conversation,
    FormSubmission,
    Lead,
    Message,
    OutboxJob,
    Subscription,
    WebhookEvent,
)


class InvalidTransition(ValueError):
    pass


def _extract_package(*texts: str) -> str | None:
    """Return the DCTS package (990|3990|1580) mentioned in any text, or None.

    Checks full-version markers first because "990" is a substring of
    "3,990" — a bare "990" match would misclassify the full package.
    The temporary promo (1,580 = กิจกรรม Focus Group Coaching 1 เดือน +
    DCTS ฉบับรวบรัด) is checked before "990" so "1,580" never falls through
    to the condensed course.
    """
    for t in texts:
        low = t.lower()
        if "3,990" in low or "3990" in low or "ฉบับเต็ม" in low or "เต็ม" in low:
            return "3990"
        if "1,580" in low or "1580" in low or "590" in low or "focus group" in low:
            return "1580"
        if "990" in low:
            return "990"
    return None


TRANSITIONS: dict[FunnelState, frozenset[FunnelState]] = {
    FunnelState.NEW: frozenset(
        {
            FunnelState.QUALIFYING,
            FunnelState.FORM_PENDING,
            FunnelState.CHECKOUT_PENDING,
            FunnelState.TRIAL_PENDING,
            FunnelState.HUMAN_HANDOFF,
            FunnelState.UNSUBSCRIBED,
        }
    ),
    FunnelState.QUALIFYING: frozenset(
        {
            FunnelState.FORM_PENDING,
            FunnelState.CHECKOUT_PENDING,
            FunnelState.TRIAL_PENDING,
            FunnelState.HUMAN_HANDOFF,
            FunnelState.UNSUBSCRIBED,
        }
    ),
    FunnelState.FORM_PENDING: frozenset(
        {
            FunnelState.FORM_COMPLETED,
            # Customer may express package interest straight from the newbie
            # form (approved doc Scenario A: แนะนำแพ็กเกจ → ลูกค้าเลือก → checkout).
            FunnelState.CHECKOUT_PENDING,
            FunnelState.TRIAL_PENDING,
            FunnelState.HUMAN_HANDOFF,
            FunnelState.UNSUBSCRIBED,
        }
    ),
    FunnelState.FORM_COMPLETED: frozenset(
        {
            FunnelState.FREE_COMMUNITY,
            FunnelState.CHECKOUT_PENDING,
            FunnelState.TRIAL_PENDING,
            FunnelState.HUMAN_HANDOFF,
        }
    ),
    FunnelState.FREE_COMMUNITY: frozenset(
        {
            FunnelState.CHECKOUT_PENDING,
            FunnelState.TRIAL_PENDING,
            FunnelState.HUMAN_HANDOFF,
            FunnelState.UNSUBSCRIBED,
        }
    ),
    FunnelState.CHECKOUT_PENDING: frozenset(
        {FunnelState.PAID_ACTIVE, FunnelState.HUMAN_HANDOFF, FunnelState.UNSUBSCRIBED}
    ),
    FunnelState.PAID_ACTIVE: frozenset({FunnelState.HUMAN_HANDOFF, FunnelState.UNSUBSCRIBED}),
    FunnelState.TRIAL_PENDING: frozenset(
        {FunnelState.TRIAL_APPROVED, FunnelState.HUMAN_HANDOFF, FunnelState.UNSUBSCRIBED}
    ),
    FunnelState.TRIAL_APPROVED: frozenset(
        {FunnelState.PAID_ACTIVE, FunnelState.HUMAN_HANDOFF, FunnelState.UNSUBSCRIBED}
    ),
    FunnelState.HUMAN_HANDOFF: frozenset({FunnelState.QUALIFYING, FunnelState.UNSUBSCRIBED}),
    FunnelState.UNSUBSCRIBED: frozenset(),
}


def transition(current: FunnelState, target: FunnelState) -> FunnelState:
    if current == target:
        return current
    if target not in TRANSITIONS[current]:
        raise InvalidTransition(f"Cannot transition from {current} to {target}")
    return target


async def get_or_create_contact(
    session: AsyncSession, external_id: str, email: str | None = None
) -> Contact:
    contact = await session.scalar(select(Contact).where(Contact.external_id == external_id))
    if contact is None and email:
        contact = await session.scalar(select(Contact).where(Contact.email == email))
    if contact is None:
        contact = Contact(external_id=external_id, email=email)
        session.add(contact)
        await session.flush()
    elif email and not contact.email:
        contact.email = email
    return contact


async def enqueue(
    session: AsyncSession, kind: OutboxKind, dedupe_key: str, payload: dict[str, Any]
) -> OutboxJob:
    existing = await session.scalar(select(OutboxJob).where(OutboxJob.dedupe_key == dedupe_key))
    if existing is not None:
        return existing
    job = OutboxJob(kind=kind, dedupe_key=dedupe_key, payload=payload)
    session.add(job)
    await session.flush()
    return job


async def ingest_message(
    session: AsyncSession,
    agent: Any,
    *,
    external_id: str,
    message_id: str,
    text: str,
    source: str,
    source_id: str,
    channel: str = "messenger",
) -> tuple[AgentRoute, bool, str | None]:
    prior = await session.scalar(
        select(Message).where(Message.channel == channel, Message.external_message_id == message_id)
    )
    if prior is not None:
        return (
            AgentRoute(reply="Event already processed.", rationale="idempotent replay"),
            True,
            None,
        )

    contact = await get_or_create_contact(session, external_id)
    lead = await session.scalar(
        select(Lead).where(Lead.source == source, Lead.source_id == source_id)
    )
    if lead is None:
        lead = Lead(contact_id=contact.id, source=source, source_id=source_id)
        session.add(lead)
        await session.flush()
    thread_id = external_id
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.channel == channel, Conversation.external_thread_id == thread_id
        )
    )
    if conversation is None:
        conversation = Conversation(
            contact_id=contact.id, lead_id=lead.id, channel=channel, external_thread_id=thread_id
        )
        session.add(conversation)
        await session.flush()
    # Load prior turns (exclude this message; it is added below) so the live
    # model has conversation context instead of restarting each turn.
    prior_rows = (
        await session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.direction.in_(("inbound", "outbound")),
            )
            .order_by(Message.created_at, Message.id)
        )
    ).all()
    history = tuple(
        ("user" if m.direction == "inbound" else "assistant", m.text) for m in prior_rows
    )
    session.add(
        Message(
            conversation_id=conversation.id,
            channel=channel,
            external_message_id=message_id,
            direction="inbound",
            text=text,
        )
    )
    # Cross-session memory: recall anything mem0 remembers about this customer
    # and surface it as extra context; then remember this message.
    from prestige_trading_agent.memory import recall, remember

    recalled = await recall(external_id, text)
    if recalled:
        history = (*history, ("system", f"[ความทรงจำเกี่ยวกับลูกค้า] {recalled}"))
    route = await route_message(
        agent,
        text,
        AgentDependencies(contact.id, conversation.id, conversation.state, history),
    )
    await remember(external_id, text)
    try:
        conversation.state = transition(conversation.state, route.next_state)
    except InvalidTransition:
        route = AgentRoute(
            reply=(
                "ขออภัยครับ ข้อมูลส่วนนี้ขออนุญาตส่งต่อให้เจ้าหน้าที่แอดมินดูแลให้ครับ เพื่อความถูกต้องและปลอดภัยของท่าน"
            ),
            path=route.path,
            next_state=FunnelState.HUMAN_HANDOFF,
            next_action=NextAction.HUMAN_HANDOFF,
            rationale="invalid automated state transition",
        )
        if FunnelState.HUMAN_HANDOFF in TRANSITIONS[conversation.state]:
            conversation.state = FunnelState.HUMAN_HANDOFF
    # Persist the bot reply so it appears in the next turn's history.
    outbound = Message(
        conversation_id=conversation.id,
        channel=channel,
        external_message_id=f"reply:{message_id}",
        direction="outbound",
        text=route.reply,
    )
    session.add(outbound)
    await session.flush()
    outbound_id = outbound.id
    lead.path = route.path
    lead.state = conversation.state
    if route.next_action is NextAction.CREATE_ACCESS_REQUEST:
        existing_request = await session.scalar(
            select(AccessRequest).where(
                AccessRequest.contact_id == contact.id, AccessRequest.status == AccessStatus.PENDING
            )
        )
        if existing_request is None:
            session.add(AccessRequest(contact_id=contact.id))
    if channel in {"messenger", "line"}:
        await enqueue(
            session,
            OutboxKind.SEND_MESSAGE,
            f"reply:{message_id}",
            {"recipient_id": external_id, "text": route.reply, "channel": channel},
        )
        # When the customer reaches checkout, send the PromptPay QR image so
        # they can pay immediately in-chat. Fires on the AGENT's routing
        # decision (SEND_CHECKOUT) or an explicit QR re-request ("ขอ qr" /
        # "ยังไม่ได้รับ") — NOT on every message while CHECKOUT_PENDING, and
        # NOT when the customer says they have already paid ("โอนไปแล้ว" /
        # "ส่งสลิป"), which must ask for the slip instead of re-sending QR.
        # Package is read from the current turn (message or agent reply) and,
        # for re-requests, from earlier outbound replies in this conversation.
        # Deduped per customer+package on the auto-send; explicit re-requests
        # get a fresh key so the QR actually resends.
        if channel in {"messenger", "line"}:
            asking_qr = any(
                kw in text.lower() for kw in ("qr", "promptpay", "prompt pay")
            )
            already_paid = any(
                kw in text.lower()
                for kw in ("โอนไปแล้ว", "โอนแล้ว", "โอนเงินแล้ว", "ส่งสลิป", "สลิปแล้ว", "จ่ายแล้ว")
            )
            if (route.next_action is NextAction.SEND_CHECKOUT or asking_qr) and not already_paid:
                package = _extract_package(text, route.reply) or _extract_package(
                    *(m.text for m in prior_rows if m.direction == "outbound")
                )
                if package is not None:
                    dedupe = (
                        f"qr:{external_id}:{package}"
                        if not asking_qr
                        else f"qr:{external_id}:{package}:{message_id}"
                    )
                    await enqueue(
                        session,
                        OutboxKind.SEND_QR_IMAGE,
                        dedupe,
                        {"recipient_id": external_id, "channel": channel, "package": package},
                    )
    return route, False, outbound_id


async def complete_form(session: AsyncSession, form: FormCompletion) -> tuple[FormSubmission, bool]:
    existing = await session.scalar(
        select(FormSubmission).where(FormSubmission.submission_id == form.submission_id)
    )
    if existing is not None:
        return existing, True
    contact = await get_or_create_contact(
        session, form.external_id, str(form.email) if form.email else None
    )
    submission = FormSubmission(
        submission_id=form.submission_id,
        contact_id=contact.id,
        path=form.path,
        payload=form.model_dump(mode="json"),
    )
    session.add(submission)

    leads = list((await session.scalars(select(Lead).where(Lead.contact_id == contact.id))).all())
    for lead in leads:
        if lead.state in {FunnelState.NEW, FunnelState.QUALIFYING}:
            lead.state = transition(lead.state, FunnelState.FORM_PENDING)
        if lead.state is FunnelState.FORM_PENDING:
            lead.state = transition(lead.state, FunnelState.FORM_COMPLETED)
        target = {
            FunnelPath.NEWBIE: FunnelState.FREE_COMMUNITY,
            FunnelPath.COURSE: FunnelState.CHECKOUT_PENDING,
            FunnelPath.INDICATOR: FunnelState.TRIAL_PENDING,
        }.get(form.path)
        if target is not None and target in TRANSITIONS[lead.state]:
            lead.state = transition(lead.state, target)
        lead.path = form.path
        conversations = list(
            (
                await session.scalars(select(Conversation).where(Conversation.lead_id == lead.id))
            ).all()
        )
        for conversation in conversations:
            conversation.state = lead.state

    if form.path is FunnelPath.NEWBIE:
        await enqueue(
            session,
            OutboxKind.SEND_FREE_LINE_INVITE,
            f"form-invite:{form.submission_id}",
            {"recipient_id": form.external_id, "contact_id": contact.id},
        )
    elif form.path is FunnelPath.INDICATOR:
        pending_request = await session.scalar(
            select(AccessRequest).where(
                AccessRequest.contact_id == contact.id,
                AccessRequest.status == AccessStatus.PENDING,
            )
        )
        if pending_request is None:
            session.add(AccessRequest(contact_id=contact.id))
    await session.flush()
    return submission, False


async def process_stripe_event(session: AsyncSession, event: dict[str, Any]) -> bool:
    event_id = str(event["id"])
    prior = await session.scalar(
        select(WebhookEvent).where(
            WebhookEvent.provider == "stripe", WebhookEvent.event_id == event_id
        )
    )
    if prior is not None:
        return True
    record = WebhookEvent(provider="stripe", event_id=event_id, payload=event)
    session.add(record)
    if event.get("type") in {"checkout.session.completed", "invoice.paid"}:
        obj = event["data"]["object"]
        metadata = obj.get("metadata") or {}
        email = (obj.get("customer_details") or {}).get("email") or obj.get("customer_email")
        external_id = metadata.get("external_id") or email or str(obj.get("customer"))
        contact = await get_or_create_contact(session, str(external_id), email)
        provider_id = str(obj.get("subscription") or obj["id"])
        subscription = await session.scalar(
            select(Subscription).where(Subscription.provider_subscription_id == provider_id)
        )
        if subscription is None:
            session.add(
                Subscription(
                    provider_subscription_id=provider_id,
                    contact_id=contact.id,
                    product=str(metadata.get("product", "course")),
                    status="active",
                )
            )
        leads = list(
            (await session.scalars(select(Lead).where(Lead.contact_id == contact.id))).all()
        )
        for lead in leads:
            if FunnelState.PAID_ACTIVE in TRANSITIONS[lead.state]:
                lead.state = transition(lead.state, FunnelState.PAID_ACTIVE)
                conversations = list(
                    (
                        await session.scalars(
                            select(Conversation).where(Conversation.lead_id == lead.id)
                        )
                    ).all()
                )
                for conversation in conversations:
                    conversation.state = lead.state
        safe_payload = {
            "contact_id": contact.id,
            "email": contact.email,
            "product": str(metadata.get("product", "course")),
            "provider_id": provider_id,
        }
        await enqueue(session, OutboxKind.ENROLL_LMS, f"lms:{provider_id}", safe_payload)
        await enqueue(
            session, OutboxKind.PROVISION_PAID_ACCESS, f"paid-access:{provider_id}", safe_payload
        )
        # Paid room = closed Facebook group; admin adds members manually after
        # slip validation + form. Send the confirmation notice to the customer
        # through their active conversation channel (if any).
        convs = list(
            (
                await session.scalars(
                    select(Conversation)
                    .where(Conversation.contact_id == contact.id)
                    .order_by(Conversation.created_at.desc())
                )
            ).all()
        )
        if convs:
            conv = convs[0]
            await enqueue(
                session,
                OutboxKind.SEND_PAID_ROOM,
                f"paid-room:{provider_id}",
                {
                    "recipient_id": conv.external_thread_id,
                    "channel": conv.channel,
                    "package": str(metadata.get("product", "3990")),
                },
            )
    record.processed_at = datetime.now(UTC)
    await session.flush()
    return False


async def approve_access(
    session: AsyncSession, request_id: str, reviewer: str, note: str | None
) -> AccessRequest | None:
    item = await session.get(AccessRequest, request_id)
    if item is None:
        return None
    if item.status is not AccessStatus.PENDING:
        raise InvalidTransition("Access request has already been reviewed")
    item.status = AccessStatus.APPROVED
    item.reviewed_by = reviewer
    item.review_note = note
    item.reviewed_at = datetime.now(UTC)
    leads = list(
        (await session.scalars(select(Lead).where(Lead.contact_id == item.contact_id))).all()
    )
    for lead in leads:
        if FunnelState.TRIAL_APPROVED in TRANSITIONS[lead.state]:
            lead.state = transition(lead.state, FunnelState.TRIAL_APPROVED)
            conversations = list(
                (
                    await session.scalars(
                        select(Conversation).where(Conversation.lead_id == lead.id)
                    )
                ).all()
            )
            for conversation in conversations:
                conversation.state = lead.state
    await enqueue(
        session,
        OutboxKind.NOTIFY_ACCESS_APPROVED,
        f"approval:{item.id}",
        {"contact_id": item.contact_id, "access_request_id": item.id},
    )
    return item


# ---------------------------------------------------------------------------
# Slip validation: EasySlip API primary, Google Sheet cross-check fallback.
# ---------------------------------------------------------------------------


async def validate_slip_with_easyslip(
    session: AsyncSession,
    settings: Any,
    *,
    slip_image_url: str,
    expected_amount: str | None = None,
) -> dict[str, Any]:
    """Validate a payment slip via the EasySlip API (if configured).

    Returns {"ok": bool, "reason": str, "meta": {...}}. When EasySlip is not
    configured (no api key), returns ok=False reason="easyslip_not_configured"
    so the caller can fall back to the Google Sheet cross-check.
    """
    if settings.easyslip_api_key is None:
        return {"ok": False, "reason": "easyslip_not_configured", "meta": {}}
    from prestige_trading_agent.adapters import EasySlipAdapter

    adapter = EasySlipAdapter(settings)
    try:
        result = await adapter.validate(slip_image_url, expected_amount)
        return result
    except Exception as exc:
        return {"ok": False, "reason": f"easyslip_error: {exc}", "meta": {}}


async def crosscheck_google_sheet(
    session: AsyncSession,
    settings: Any,
    *,
    sheet_id: str,
    external_id: str | None = None,
    line_id: str | None = None,
    phone: str | None = None,
    email: str | None = None,
) -> dict[str, Any]:
    """Cross-check a customer against the package's Google Sheet response.

    The approved Google Forms write to two public sheets (one per package).
    A row counts as a match when ANY identity field we have (LINE ID, phone,
    email) matches a row AND that row has a slip attached (col 12 non-empty).
    Returns {"ok": bool, "reason": str, "meta": {"row_index": int|None}}.
    """
    import csv
    import urllib.request

    url = f"https://docs.google.com/spreadsheets/d/{sheet_id}/export?format=csv"
    try:
        with urllib.request.urlopen(url, timeout=20) as resp:
            text = resp.read().decode("utf-8-sig")
    except Exception as exc:
        return {"ok": False, "reason": f"sheet_unreachable: {exc}", "meta": {}}

    rows = list(csv.reader(text.splitlines()))
    if not rows:
        return {"ok": False, "reason": "sheet_empty", "meta": {}}
    header = rows[0]
    col = {
        "line_id": settings.sheet_col_line_id,
        "phone": settings.sheet_col_phone,
        "email": settings.sheet_col_email,
        "fb": settings.sheet_col_fb,
        "slip": settings.sheet_col_slip,
    }
    if max(col.values()) >= len(header):
        return {"ok": False, "reason": "sheet_schema_mismatch", "meta": {}}

    def norm(v: str | None) -> str:
        return (v or "").strip().lower().replace(" ", "")

    candidates = {
        "line_id": norm(line_id),
        "phone": norm(phone),
        "email": norm(email),
        "external_id": norm(external_id),
    }
    for idx, row in enumerate(rows[1:], start=2):  # 1-based for humans
        row_vals = row + [""] * (len(header) - len(row))
        has_slip = bool(row_vals[col["slip"]].strip())
        for key, needle in candidates.items():
            if not needle:
                continue
            if key == "external_id":
                # The external_id often equals the LINE UID in production.
                if needle == norm(row_vals[col["line_id"]]):
                    return {
                        "ok": has_slip,
                        "reason": "matched" if has_slip else "no_slip_yet",
                        "meta": {"row_index": idx, "matched_by": "line_id"},
                    }
                continue
            cell = norm(row_vals[col[key]]) if key in col else ""
            if needle and cell and needle in cell:
                return {
                    "ok": has_slip,
                    "reason": "matched" if has_slip else "no_slip_yet",
                    "meta": {"row_index": idx, "matched_by": key},
                }
    return {"ok": False, "reason": "no_match", "meta": {}}


# ---------------------------------------------------------------------------
# Slip image handling (Messenger/LINE image attachment = payment slip)
# ---------------------------------------------------------------------------


async def conversation_is_checkout(session: AsyncSession, external_id: str) -> bool:
    """True when the customer's active conversation is mid-checkout."""
    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.external_thread_id == external_id,
            Conversation.channel == "messenger",
        )
    )
    return conversation is not None and conversation.state is FunnelState.CHECKOUT_PENDING


async def handle_slip_image(
    session: AsyncSession, settings: Any, external_id: str, image_url: str
) -> None:
    """Validate a slip image (EasySlip → Sheet fallback) and route the outcome.

    - Valid → enqueue post-payment form + FB group invite + mark paid.
    - Invalid → reply asking the customer to re-send the correct slip.
    """
    from prestige_trading_agent.knowledge import PAYMENT_FORMS

    conversation = await session.scalar(
        select(Conversation).where(
            Conversation.external_thread_id == external_id,
            Conversation.channel == "messenger",
        )
    )
    if conversation is None:
        return
    # Determine package from the conversation's recent context — the bot's own
    # checkout replies always name the price (990/3,990), so scan the last few
    # turns. Defaults to 3990 (full version) if nothing names a price.
    recent_rows = (
        await session.scalars(
            select(Message)
            .where(
                Message.conversation_id == conversation.id,
                Message.direction == "outbound",
            )
            .order_by(Message.created_at.desc())
            .limit(6)
        )
    ).all()
    package = _extract_package(*(m.text for m in recent_rows)) or "3990"
    expected = {"990": "990", "3990": "3990", "1580": "1580"}.get(package, "3990")
    result = await validate_slip_with_easyslip(
        session, settings, slip_image_url=image_url, expected_amount=expected
    )
    if not result["ok"]:
        # Sheet cross-check exists only for the two standard courses; the
        # temporary 1,580 promo has no response sheet, so EasySlip is the only
        # source of truth for it.
        if package == "990":
            sheet_id = settings.sheet_990_id
        elif package == "3990":
            sheet_id = settings.sheet_3990_id
        else:
            sheet_id = None
        if sheet_id:
            result = await crosscheck_google_sheet(
                session,
                settings,
                sheet_id=sheet_id,
                external_id=external_id,
            )
        if result["ok"]:
            package = package
    if not result["ok"]:
        await enqueue(
            session,
            OutboxKind.SEND_MESSAGE,
            f"slip-retry:{external_id}",
            {
                "recipient_id": external_id,
                "channel": "messenger",
                "text": (
                    "ขออภัยครับ ตรวจสอบสลิปไม่พบรายการโอนที่ถูกต้องในระบบ "
                    "(ยอดเงินไม่ตรงกับแพ็กเกจหรือไม่พบรายการ) "
                    "กรุณาส่งสลิปโอนเงินอีกครั้ง หรือแจ้งชื่อ-นามสกุลที่โอน "
                    "ให้เจ้าหน้าที่ตรวจสอบให้ครับ"
                ),
            },
        )
        return
    conversation.state = FunnelState.PAID_ACTIVE
    await session.flush()
    await enqueue(
        session,
        OutboxKind.SEND_MESSAGE,
        f"paid:{external_id}",
        {
            "recipient_id": external_id,
            "channel": "messenger",
            "text": (
                "ยินดีด้วยครับ ตรวจพบการชำระเงินเรียบร้อย! "
                f"กรุณากรอกฟอร์มเพื่อรับสิทธิ์: {PAYMENT_FORMS[package]} "
                "แล้วกดเข้ากลุ่ม Facebook ปิดผ่านลิงก์ที่แอดมินส่งให้ เจ้าหน้าที่จะอนุมัติภายใน 24 ชม. ครับ"
            ),
        },
    )
    await enqueue(
        session,
        OutboxKind.SEND_PAID_ROOM,
        f"paid-room:{external_id}",
        {"recipient_id": external_id, "channel": "messenger", "package": package},
    )
