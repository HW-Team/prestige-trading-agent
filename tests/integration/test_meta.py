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
