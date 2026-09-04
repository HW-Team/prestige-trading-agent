from datetime import datetime, timedelta
from typing import Any

import pytest
from sqlalchemy import select

from prestige_trading_agent.adapters import RecordingAdapter
from prestige_trading_agent.db import Database
from prestige_trading_agent.domain import OutboxKind
from prestige_trading_agent.models import OutboxJob
from prestige_trading_agent.outbox import MAX_ATTEMPTS, _backoff_delay, drain_outbox
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


class _FailingAdapter:
    """Dispatch always raises — simulates a dead recipient / permanent error."""

    def __init__(self) -> None:
        self.attempts = 0

    async def dispatch(self, kind: Any, payload: dict[str, Any]) -> None:
        self.attempts += 1
        raise RuntimeError("graph api: recipient does not exist")


@pytest.mark.asyncio
async def test_outbox_stops_retrying_after_max_attempts(tmp_path: Any) -> None:
    """A permanently failing job must hit MAX_ATTEMPTS then go quiet — it must
    not retry forever (2s poll ≈ 43k attempts/day) nor block later jobs."""
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'retry.db'}")
    await database.create_schema()
    async with database.session_factory() as session, session.begin():
        job = OutboxJob(
            kind=OutboxKind.SEND_MESSAGE,
            dedupe_key="dead-recipient",
            payload={"recipient_id": "fake", "text": "hi"},
            # Start at the cap so it is skipped immediately (e.g. after a
            # deploy cleaned a hot-looping job).
            attempts=MAX_ATTEMPTS,
        )
        session.add(job)
    adapter = _FailingAdapter()
    assert await drain_outbox(database, adapter) == 0
    assert adapter.attempts == 0  # skipped: already at cap
    async with database.session_factory() as session:
        job = await session.scalar(
            select(OutboxJob).where(OutboxJob.dedupe_key == "dead-recipient")
        )
        assert job is not None and job.processed_at is None
    await database.dispose()


@pytest.mark.asyncio
async def test_outbox_failing_job_backs_off_but_healthy_job_still_drains(tmp_path: Any) -> None:
    """A failing job gets exponential backoff (available_at pushed out) while a
    later healthy job is still delivered — no head-of-line blocking."""
    database = Database(f"sqlite+aiosqlite:///{tmp_path / 'backoff.db'}")
    await database.create_schema()
    async with database.session_factory() as session, session.begin():
        await enqueue(session, OutboxKind.SEND_MESSAGE, "bad", {"recipient_id": "fake"})
        await enqueue(session, OutboxKind.SEND_MESSAGE, "good", {"recipient_id": "real"})
    adapter = _FailingAdapter()
    assert await drain_outbox(database, adapter) == 0  # bad fails, good is behind it in same batch
    async with database.session_factory() as session:
        bad = await session.scalar(select(OutboxJob).where(OutboxJob.dedupe_key == "bad"))
        assert bad is not None and bad.attempts == 1
        # available_at pushed out by backoff, NOT in the past (sqlite returns
        # naive datetimes, so compare against a naive "now").
        assert bad.available_at > datetime.now() - timedelta(seconds=1)
        assert bad.last_error is not None
        # backoff grows: attempt 1 -> 2s, attempt 5 -> 32s
        assert _backoff_delay(1).total_seconds() == 2.0
        assert _backoff_delay(5).total_seconds() == 32.0
        assert _backoff_delay(30).total_seconds() <= 240.0
    await database.dispose()
