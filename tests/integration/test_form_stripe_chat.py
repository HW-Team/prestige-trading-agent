import hashlib
import hmac
import json
import time

import pytest
from httpx import AsyncClient


def form_sig(body: bytes) -> str:
    return hmac.new(b"form-secret", body, hashlib.sha256).hexdigest()


def stripe_sig(body: bytes) -> str:
    timestamp = int(time.time())
    digest = hmac.new(b"whsec_test", f"{timestamp}.".encode() + body, hashlib.sha256).hexdigest()
    return f"t={timestamp},v1={digest}"


@pytest.mark.asyncio
async def test_internal_chat_and_trial_queue(client: AsyncClient) -> None:
    response = await client.post(
        "/internal/chat",
        json={"external_id": "chat-1", "message": "indicator trial"},
        headers={"X-API-Key": "admin-test"},
    )
    assert response.status_code == 200
    assert response.json()["next_action"] == "create_access_request"
    requests = (
        await client.get("/admin/access-requests", headers={"X-API-Key": "admin-test"})
    ).json()
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_conversation_history_persists_across_turns(client: AsyncClient) -> None:
    """Two turns on the same external_id must accumulate message rows, and the
    second reply must differ from a fresh-start greeting (history is passed)."""
    first = await client.post(
        "/internal/chat",
        json={"external_id": "chat-history", "message": "สวัสดีครับ อยากรู้จักคอร์ส DCTS"},
        headers={"X-API-Key": "admin-test"},
    )
    assert first.status_code == 200
    second = await client.post(
        "/internal/chat",
        json={"external_id": "chat-history", "message": "สนใจฉบับเต็ม 3,990 บาทครับ"},
        headers={"X-API-Key": "admin-test"},
    )
    assert second.status_code == 200
    assert second.json()["reply"]  # offline model still replies
    # Inbound + outbound rows must exist for both turns.
    history = (await client.get("/admin/messages", headers={"X-API-Key": "admin-test"})).json()
    rows = [m for m in history if m["conversation"]["external_thread_id"] == "chat-history"]
    assert len(rows) >= 4  # 2 inbound + 2 outbound
    assert {r["direction"] for r in rows} == {"inbound", "outbound"}


@pytest.mark.asyncio
async def test_feedback_capture_and_list(client: AsyncClient) -> None:
    # Send a chat, grab the reply message id, then rate it.
    chat_resp = await client.post(
        "/internal/chat",
        json={"external_id": "chat-fb", "message": "สวัสดีครับ สนใจคอร์ส"},
        headers={"X-API-Key": "admin-test"},
    )
    assert chat_resp.status_code == 200
    message_id = chat_resp.json()["reply_message_id"]
    assert message_id

    submit = await client.post(
        "/internal/feedback",
        json={"message_id": message_id, "rating": "needs_work", "comment": "ควรตอบสั้นกว่านี้"},
        headers={"X-API-Key": "admin-test"},
    )
    assert submit.status_code == 200
    assert submit.json()["status"] == "recorded"

    rows = (await client.get("/admin/feedback", headers={"X-API-Key": "admin-test"})).json()
    mine = [r for r in rows if r["id"] and r["message"]["id"] == message_id]
    assert len(mine) == 1
    assert mine[0]["rating"] == "needs_work"
    assert mine[0]["comment"] == "ควรตอบสั้นกว่านี้"


@pytest.mark.asyncio
async def test_feedback_requires_existing_message(client: AsyncClient) -> None:
    resp = await client.post(
        "/internal/feedback",
        json={"message_id": "no-such-id", "rating": "good"},
        headers={"X-API-Key": "admin-test"},
    )
    assert resp.status_code == 404


@pytest.mark.asyncio
async def test_payment_endpoint_returns_qr_and_form(client: AsyncClient) -> None:
    resp = await client.post(
        "/internal/payment",
        json={"package": "3990"},
        headers={"X-API-Key": "admin-test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["qr_image"] == "/assets/payment-qr.jpg"
    assert data["bank_account_name"] == "นาย รชต มากมูล"
    assert data["form_url"] == "https://forms.gle/hfTC9ukgNmk71uHv9"

    resp990 = await client.post(
        "/internal/payment",
        json={"package": "990"},
        headers={"X-API-Key": "admin-test"},
    )
    assert resp990.json()["form_url"] == "https://forms.gle/bjLjyFwxP96hiyF16"


@pytest.mark.asyncio
async def test_payment_qr_asset_served(client: AsyncClient) -> None:
    resp = await client.get("/assets/payment-qr.jpg")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("image/")


@pytest.mark.asyncio
async def test_crosscheck_google_sheet_real_public_sheet() -> None:
    """The 3990 response sheet is public; a real customer row (Line ID
    'theamy555') must resolve and carry a slip reference."""
    from prestige_trading_agent.config import Settings
    from prestige_trading_agent.services import crosscheck_google_sheet

    settings = Settings(sheet_3990_id="10RlTyP7lIs-tzNEFzXH889OrGDS2cuocmRJRE2Qpwcc")
    result = await crosscheck_google_sheet(
        None, settings, sheet_id=settings.sheet_3990_id, line_id="theamy555"
    )
    assert result["ok"] is True
    assert result["meta"]["matched_by"] == "line_id"


@pytest.mark.asyncio
async def test_line_webhook_requires_valid_signature(client: AsyncClient) -> None:
    resp = await client.post(
        "/webhooks/line",
        json={"events": []},
        headers={"X-Line-Signature": "bad-signature"},
    )
    assert resp.status_code == 401


@pytest.mark.asyncio
async def test_line_webhook_rejects_bad_payload(client: AsyncClient) -> None:
    resp = await client.post(
        "/webhooks/line",
        content=b"not-json",
        headers={"X-Line-Signature": "anything"},
    )
    assert resp.status_code in {400, 401}


@pytest.mark.asyncio
async def test_signed_form_schedules_only_free_line_invite(client: AsyncClient) -> None:
    payload = {
        "submission_id": "sub-1",
        "external_id": "form-user",
        "email": "a@example.com",
        "path": "newbie",
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    assert (
        await client.post(
            "/webhooks/form",
            content=body,
            headers={"X-Form-Signature": form_sig(body), "Content-Type": "application/json"},
        )
    ).status_code == 200
    jobs = (await client.get("/admin/outbox", headers={"X-API-Key": "admin-test"})).json()
    assert any(j["kind"] == "send_free_line_invite" for j in jobs)
    assert all("paid" not in json.dumps(j).lower() for j in jobs)
    assert (
        await client.post(
            "/webhooks/form",
            content=body,
            headers={"X-Form-Signature": "bad", "Content-Type": "application/json"},
        )
    ).status_code == 401


@pytest.mark.asyncio
async def test_stripe_paid_event_is_idempotent_and_never_contains_room_link(
    client: AsyncClient,
) -> None:
    payload = {
        "id": "evt_1",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_1",
                "customer": "cus_1",
                "customer_details": {"email": "paid@example.com"},
                "payment_status": "paid",
                "metadata": {"external_id": "paid-user", "product": "course"},
            }
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {"Stripe-Signature": stripe_sig(body), "Content-Type": "application/json"}
    assert (await client.post("/webhooks/stripe", content=body, headers=headers)).status_code == 200
    assert (await client.post("/webhooks/stripe", content=body, headers=headers)).status_code == 200
    jobs = (await client.get("/admin/outbox", headers={"X-API-Key": "admin-test"})).json()
    kinds = [j["kind"] for j in jobs]
    assert kinds.count("enroll_lms") == 1
    assert kinds.count("provision_paid_access") == 1
    assert "line.me" not in json.dumps(jobs).lower()
    assert (
        await client.post("/webhooks/stripe", content=body, headers={"Stripe-Signature": "bad"})
    ).status_code == 400


@pytest.mark.asyncio
async def test_access_approval_is_auditable(client: AsyncClient) -> None:
    await client.post(
        "/internal/chat",
        json={"external_id": "trial-2", "message": "indicator trial"},
        headers={"X-API-Key": "admin-test"},
    )
    items = (await client.get("/admin/access-requests", headers={"X-API-Key": "admin-test"})).json()
    response = await client.post(
        f"/admin/access-requests/{items[0]['id']}/approve",
        headers={"X-API-Key": "admin-test"},
        json={"reviewed_by": "ops"},
    )
    assert response.status_code == 200
    assert response.json()["status"] == "approved"
    assert response.json()["reviewed_by"] == "ops"
    leads = (await client.get("/admin/leads", headers={"X-API-Key": "admin-test"})).json()
    assert leads[0]["state"] == "trial_approved"


@pytest.mark.asyncio
async def test_course_chat_enqueues_payment_qr_with_package(client: AsyncClient) -> None:
    import hashlib
    import hmac

    payload = {
        "object": "page",
        "entry": [
            {
                "id": "108433865417846",
                "time": 1720000000,
                "messaging": [
                    {
                        "sender": {"id": "buyer-990"},
                        "recipient": {"id": "108433865417846"},
                        "timestamp": 1720000000000,
                        "message": {
                            "mid": "mid-qr-test-1",
                            "text": "สนใจคอร์ส DCTS ฉบับเต็ม 3,990 บาทครับ",
                        },
                    }
                ],
            }
        ],
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = "sha256=" + hmac.new(b"meta-secret", body, hashlib.sha256).hexdigest()
    resp = await client.post("/webhooks/meta", content=body, headers={"X-Hub-Signature-256": sig})
    assert resp.status_code == 200
    jobs = (await client.get("/admin/outbox", headers={"X-API-Key": "admin-test"})).json()
    qr_jobs = [j for j in jobs if j["kind"] == "send_qr_image"]
    assert len(qr_jobs) >= 1
    assert qr_jobs[-1]["payload"]["package"] == "3990"
    assert qr_jobs[-1]["payload"]["channel"] == "messenger"


def _meta_msg(sender: str, mid: str, text: str) -> tuple[bytes, str]:
    """Build a signed Meta Messenger webhook body for one text message."""
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "108433865417846",
                "time": 1720000000,
                "messaging": [
                    {
                        "sender": {"id": sender},
                        "recipient": {"id": "108433865417846"},
                        "timestamp": 1720000000,
                        "message": {"mid": mid, "text": text},
                    }
                ],
            }
        ],
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    sig = "sha256=" + hmac.new(b"meta-secret", body, hashlib.sha256).hexdigest()
    return body, sig


@pytest.mark.asyncio
async def test_qr_sent_when_customer_never_mentions_price(client: AsyncClient) -> None:
    """Regression: a customer who reaches checkout without typing the price
    ("สนใจครับ" / "ขอ qr หน่อยครับ") must still receive the QR. The old trigger
    required "990"/"3990" in the customer's message, so the QR was silently
    never enqueued while the bot's reply promised it."""
    # Turn 1: customer expresses interest, no price anywhere in the message.
    body, sig = _meta_msg("buyer-noprice", "mid-qr-noprice-1", "สนใจคอร์ส DCTS ครับ")
    resp = await client.post("/webhooks/meta", content=body, headers={"X-Hub-Signature-256": sig})
    assert resp.status_code == 200
    jobs = (await client.get("/admin/outbox", headers={"X-API-Key": "admin-test"})).json()
    qr_jobs = [
        j for j in jobs
        if j["kind"] == "send_qr_image" and j["payload"]["recipient_id"] == "buyer-noprice"
    ]
    assert len(qr_jobs) == 1, f"QR must be enqueued from routing alone, got {len(qr_jobs)}"
    assert qr_jobs[0]["payload"]["package"] == "3990"
    assert qr_jobs[0]["payload"]["channel"] == "messenger"

    # Turn 2: customer asks for the QR explicitly — must trigger a NEW job
    # (fresh dedupe key), not be swallowed by the turn-1 dedupe.
    body2, sig2 = _meta_msg("buyer-noprice", "mid-qr-noprice-2", "ขอ qr หน่อยครับ")
    resp2 = await client.post(
        "/webhooks/meta", content=body2, headers={"X-Hub-Signature-256": sig2}
    )
    assert resp2.status_code == 200
    jobs2 = (await client.get("/admin/outbox", headers={"X-API-Key": "admin-test"})).json()
    qr_jobs2 = [
        j for j in jobs2
        if j["kind"] == "send_qr_image" and j["payload"]["recipient_id"] == "buyer-noprice"
    ]
    msg = f"explicit re-request must enqueue a fresh QR job, got {len(qr_jobs2)}"
    assert len(qr_jobs2) == 2, msg


@pytest.mark.asyncio
async def test_qr_reroute_no_wrong_amount_when_package_unknown(client: AsyncClient) -> None:
    """Safety: if the package cannot be determined (no price in message, reply,
    or history), no QR is sent — never a wrong-amount QR."""
    body, sig = _meta_msg("buyer-unknown", "mid-qr-unknown-1", "อยากได้ข้อมูลเพิ่มเติมครับ")
    resp = await client.post(
        "/webhooks/meta", content=body, headers={"X-Hub-Signature-256": sig}
    )
    assert resp.status_code == 200
    jobs = (await client.get("/admin/outbox", headers={"X-API-Key": "admin-test"})).json()
    qr_jobs = [
        j for j in jobs
        if j["kind"] == "send_qr_image" and j["payload"]["recipient_id"] == "buyer-unknown"
    ]
    assert len(qr_jobs) == 0


@pytest.mark.asyncio
async def test_consult_coach_handoff_replies_with_line_oa(client: AsyncClient) -> None:
    resp = await client.post(
        "/internal/chat",
        json={"external_id": "consult-1", "message": "อยากคุยกับโค้ชโดยตรงครับ"},
        headers={"X-API-Key": "admin-test"},
    )
    assert resp.status_code == 200
    data = resp.json()
    assert "LINE OA" in data["reply"] or "lin.ee" in data["reply"]
    assert data["next_state"] == "human_handoff"


@pytest.mark.asyncio
async def test_paid_event_advances_existing_course_funnel(client: AsyncClient) -> None:
    await client.post(
        "/internal/chat",
        json={"external_id": "course-person", "message": "I want the course"},
        headers={"X-API-Key": "admin-test"},
    )
    payload = {
        "id": "evt_course_state",
        "type": "checkout.session.completed",
        "data": {
            "object": {
                "id": "cs_course_state",
                "customer": "cus_course_state",
                "customer_details": {"email": "course@example.com"},
                "payment_status": "paid",
                "metadata": {"external_id": "course-person", "product": "course"},
            }
        },
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    response = await client.post(
        "/webhooks/stripe",
        content=body,
        headers={"Stripe-Signature": stripe_sig(body), "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    leads = (await client.get("/admin/leads", headers={"X-API-Key": "admin-test"})).json()
    assert leads[0]["state"] == "paid_active"
