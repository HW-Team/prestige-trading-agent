import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_health_and_readiness(client: AsyncClient) -> None:
    assert (await client.get("/health")).json() == {"status": "ok"}
    assert (await client.get("/ready")).status_code == 200


@pytest.mark.asyncio
async def test_admin_requires_api_key(client: AsyncClient) -> None:
    assert (await client.get("/admin/leads")).status_code == 401
    response = await client.get("/admin/leads", headers={"X-API-Key": "admin-test"})
    assert response.status_code == 200
    assert response.json() == []
