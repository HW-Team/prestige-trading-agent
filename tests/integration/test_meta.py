import hashlib
import hmac
import json

import pytest
from httpx import AsyncClient


def signature(body: bytes) -> str:
    return "sha256=" + hmac.new(b"meta-secret", body, hashlib.sha256).hexdigest()


@pytest.mark.asyncio
async def test_meta_verification(client: AsyncClient) -> None:
    ok = await client.get(
        "/webhooks/meta",
        params={"hub.mode": "subscribe", "hub.verify_token": "verify-test", "hub.challenge": "42"},
    )
    assert ok.text == "42"
    assert (
        await client.get("/webhooks/meta", params={"hub.verify_token": "bad"})
    ).status_code == 403


@pytest.mark.asyncio
async def test_duplicate_organic_dm_is_idempotent(client: AsyncClient) -> None:
    payload = {
        "object": "page",
        "entry": [
            {
                "messaging": [
                    {
                        "sender": {"id": "user-1"},
                        "recipient": {"id": "page"},
                        "timestamp": 1,
                        "message": {"mid": "m-1", "text": "newbie"},
                    }
                ]
            }
        ],
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {"X-Hub-Signature-256": signature(body), "Content-Type": "application/json"}
    assert (await client.post("/webhooks/meta", content=body, headers=headers)).status_code == 200
    duplicate = await client.post("/webhooks/meta", content=body, headers=headers)
    assert duplicate.status_code == 200
    leads = (await client.get("/admin/leads", headers={"X-API-Key": "admin-test"})).json()
    assert len(leads) == 1


@pytest.mark.asyncio
async def test_lead_ad_converges_and_invalid_signature_rejected(client: AsyncClient) -> None:
    payload = {
        "object": "page",
        "entry": [
            {
                "changes": [
                    {
                        "field": "leadgen",
                        "value": {
                            "leadgen_id": "lead-1",
                            "page_id": "page",
                            "form_id": "form",
                            "created_time": 1,
                        },
                    }
                ]
            }
        ],
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    assert (
        await client.post(
            "/webhooks/meta",
            content=body,
            headers={"X-Hub-Signature-256": signature(body), "Content-Type": "application/json"},
        )
    ).status_code == 200
    assert (
        await client.post(
            "/webhooks/meta",
            content=body,
            headers={"X-Hub-Signature-256": "sha256=bad", "Content-Type": "application/json"},
        )
    ).status_code == 401
    jobs = (await client.get("/admin/outbox", headers={"X-API-Key": "admin-test"})).json()
    assert all(job["kind"] != "send_message" for job in jobs)


@pytest.mark.asyncio
async def test_postback_button_tap_gets_reply(client: AsyncClient) -> None:
    """Regression: a customer tapping a button ("Get started" / "รับข้อเสนอ" /
    ad offer CTA) sends a postback with NO message.mid. The old handler
    silently skipped it, so that customer never got a reply. A postback must
    enter the funnel like a normal message."""
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "108433865417846",
                "time": 1720000000,
                "messaging": [
                    {
                        "sender": {"id": "postback-buyer"},
                        "recipient": {"id": "108433865417846"},
                        "timestamp": 1720000000000,
                        "postback": {"title": "รับข้อเสนอ", "payload": "GET_STARTED"},
                    }
                ],
            }
        ],
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {"X-Hub-Signature-256": signature(body), "Content-Type": "application/json"}
    assert (await client.post("/webhooks/meta", content=body, headers=headers)).status_code == 200
    jobs = (await client.get("/admin/outbox", headers={"X-API-Key": "admin-test"})).json()
    mine = [j for j in jobs if j.get("payload", {}).get("recipient_id") == "postback-buyer"]
    assert any(j["kind"] == "send_message" for j in mine), "postback tap must get a bot reply"


@pytest.mark.asyncio
async def test_postback_with_only_payload_still_gets_reply(client: AsyncClient) -> None:
    """Ad-offer CTAs can send a postback with only a payload (no title). The
    lead must not be dropped silently."""
    payload = {
        "object": "page",
        "entry": [
            {
                "id": "108433865417846",
                "time": 1720000000,
                "messaging": [
                    {
                        "sender": {"id": "payload-buyer"},
                        "recipient": {"id": "108433865417846"},
                        "timestamp": 1720000000000,
                        "postback": {"payload": "OFFER_990"},
                    }
                ],
            }
        ],
    }
    body = json.dumps(payload, separators=(",", ":")).encode()
    headers = {"X-Hub-Signature-256": signature(body), "Content-Type": "application/json"}
    assert (await client.post("/webhooks/meta", content=body, headers=headers)).status_code == 200
    jobs = (await client.get("/admin/outbox", headers={"X-API-Key": "admin-test"})).json()
    mine = [j for j in jobs if j.get("payload", {}).get("recipient_id") == "payload-buyer"]
    assert any(j["kind"] == "send_message" for j in mine), "payload-only postback must still reply"
