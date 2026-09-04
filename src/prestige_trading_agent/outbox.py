from datetime import UTC, datetime, timedelta

from sqlalchemy import select

from prestige_trading_agent.adapters import OutboundAdapter
from prestige_trading_agent.db import Database
from prestige_trading_agent.models import OutboxJob

# A job that keeps failing (bad recipient, dead webhook, permanent Graph API
# error) must not retry forever: with a 2s poll that is ~43k attempts/day and
# it blocks every later job in FIFO order. Cap attempts and space retries with
# exponential backoff so the worker stays responsive for healthy jobs.
MAX_ATTEMPTS = 25
BACKOFF_BASE_SECONDS = 2.0


def _backoff_delay(attempts: int) -> timedelta:
    """Exponential backoff: 2s, 4s, 8s ... capped at ~4 min."""
    return timedelta(seconds=min(BACKOFF_BASE_SECONDS * (2 ** (attempts - 1)), 240))


async def drain_outbox(database: Database, adapter: OutboundAdapter, limit: int = 100) -> int:
    processed = 0
    now = datetime.now(UTC)
    async with database.session_factory() as session:
        jobs = list(
            (
                await session.scalars(
                    select(OutboxJob)
                    .where(
                        OutboxJob.processed_at.is_(None),
                        OutboxJob.available_at <= now,
                        OutboxJob.attempts < MAX_ATTEMPTS,
                    )
                    .order_by(OutboxJob.created_at)
                    .limit(limit)
                )
            ).all()
        )
        for job in jobs:
            try:
                await adapter.dispatch(job.kind, job.payload)
            except Exception as exc:
                job.attempts += 1
                job.last_error = str(exc)
                job.available_at = now + _backoff_delay(job.attempts)
            else:
                job.attempts += 1
                job.processed_at = datetime.now(UTC)
                processed += 1
        await session.commit()
    return processed
