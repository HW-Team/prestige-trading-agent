import hashlib
import hmac
import json

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_duplicate_form_does_not_schedule_duplicate_invite(client: AsyncClient) -> None:
    body = json.dumps(
        {"submission_id": "same", "external_id": "person", "path": "newbie"},
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(b"form-secret", body, hashlib.sha256).hexdigest()
    headers = {"X-Form-Signature": signature, "Content-Type": "application/json"}
    first = await client.post("/webhooks/form", content=body, headers=headers)
    second = await client.post("/webhooks/form", content=body, headers=headers)
    assert first.json()["duplicate"] is False
    assert second.json()["duplicate"] is True
    jobs = (await client.get("/admin/outbox", headers={"X-API-Key": "admin-test"})).json()
    assert [job["kind"] for job in jobs].count("send_free_line_invite") == 1


@pytest.mark.asyncio
async def test_form_completion_advances_existing_funnel(client: AsyncClient) -> None:
    await client.post(
        "/internal/chat",
        json={"external_id": "advancing-person", "message": "I am a beginner"},
        headers={"X-API-Key": "admin-test"},
    )
    body = json.dumps(
        {
            "submission_id": "advance-form",
            "external_id": "advancing-person",
            "path": "newbie",
        },
        separators=(",", ":"),
    ).encode()
    signature = hmac.new(b"form-secret", body, hashlib.sha256).hexdigest()
    response = await client.post(
        "/webhooks/form",
        content=body,
        headers={"X-Form-Signature": signature, "Content-Type": "application/json"},
    )
    assert response.status_code == 200
    leads = (await client.get("/admin/leads", headers={"X-API-Key": "admin-test"})).json()
    assert leads[0]["state"] == "free_community"


@pytest.mark.asyncio
async def test_distinct_indicator_forms_reuse_pending_access_request(client: AsyncClient) -> None:
    for submission_id in ("indicator-1", "indicator-2"):
        body = json.dumps(
            {
                "submission_id": submission_id,
                "external_id": "same-indicator-person",
                "path": "indicator",
            },
            separators=(",", ":"),
        ).encode()
        signature = hmac.new(b"form-secret", body, hashlib.sha256).hexdigest()
        response = await client.post(
            "/webhooks/form",
            content=body,
            headers={"X-Form-Signature": signature, "Content-Type": "application/json"},
        )
        assert response.status_code == 200

    requests = (
        await client.get("/admin/access-requests", headers={"X-API-Key": "admin-test"})
    ).json()
    assert len(requests) == 1
