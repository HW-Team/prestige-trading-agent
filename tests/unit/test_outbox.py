from typing import Any

import pytest
from sqlalchemy import select

from prestige_trading_agent.adapters import RecordingAdapter
from prestige_trading_agent.db import Database
from prestige_trading_agent.domain import OutboxKind
from prestige_trading_agent.models import OutboxJob
from prestige_trading_agent.outbox import drain_outbox
from prestige_trading_agent.services import enqueue


@pytest.mark.asyncio
async def test_outbox_is_persisted_then_dispatched_once(tmp_path: Any) -> None:
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'outbox.db'}")
    await database.create_schema()
    async with database.session_factory() as session, session.begin():
        await enqueue(session, OutboxKind.ENROLL_LMS, "job-1", {"contact_id": "c1"})
        await enqueue(session, OutboxKind.ENROLL_LMS, "job-1", {"contact_id": "c1"})
    adapter = RecordingAdapter()
    assert await drain_outbox(database, adapter) == 1
    assert await drain_outbox(database, adapter) == 0
    assert len(adapter.deliveries) == 1
    async with database.session_factory() as session:
        job = await session.scalar(select(OutboxJob).where(OutboxJob.dedupe_key == "job-1"))
        assert job is not None and job.processed_at is not None
    await database.dispose()
