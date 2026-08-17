from datetime import UTC, datetime

from sqlalchemy import select

from prestige_trading_agent.adapters import OutboundAdapter
from prestige_trading_agent.db import Database
from prestige_trading_agent.models import OutboxJob


async def drain_outbox(database: Database, adapter: OutboundAdapter, limit: int = 100) -> int:
    processed = 0
    async with database.session_factory() as session:
        jobs = list(
            (
                await session.scalars(
                    select(OutboxJob)
                    .where(OutboxJob.processed_at.is_(None))
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
            else:
                job.attempts += 1
                job.processed_at = datetime.now(UTC)
                processed += 1
        await session.commit()
    return processed
