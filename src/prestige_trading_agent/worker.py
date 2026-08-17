import argparse
import asyncio

from prestige_trading_agent.adapters import LiveAdapter, RecordingAdapter
from prestige_trading_agent.config import get_settings
from prestige_trading_agent.db import Database
from prestige_trading_agent.outbox import drain_outbox


async def run_once() -> int:
    settings = get_settings()
    database = Database(settings.database_url)
    adapter = RecordingAdapter() if settings.outbound_mode == "recording" else LiveAdapter(settings)
    try:
        return await drain_outbox(database, adapter)
    finally:
        await database.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Dispatch pending Prestige outbox jobs")
    parser.add_argument("--once", action="store_true", help="Drain one batch and exit")
    parser.parse_args()
    processed = asyncio.run(run_once())
    print(f"processed={processed}")


if __name__ == "__main__":
    main()
