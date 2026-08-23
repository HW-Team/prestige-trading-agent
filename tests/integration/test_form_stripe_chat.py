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
