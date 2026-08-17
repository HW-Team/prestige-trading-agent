from collections.abc import AsyncIterator

import pytest
from httpx import ASGITransport, AsyncClient

from prestige_trading_agent.config import Settings
from prestige_trading_agent.main import create_app


@pytest.fixture
async def client(tmp_path) -> AsyncIterator[AsyncClient]:
    settings = Settings(
        database_url=f"sqlite+aiosqlite:///{tmp_path / 'test.db'}",
        admin_api_key="admin-test",
        meta_verify_token="verify-test",
        meta_app_secret="meta-secret",
        form_webhook_secret="form-secret",
        stripe_webhook_secret="whsec_test",
        outbound_mode="recording",
        model="test",
        free_line_invite_url="https://line.me/R/ti/g/free-test",
    )
    app = create_app(settings)
    async with (
        app.router.lifespan_context(app),
        AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as ac,
    ):
        yield ac
