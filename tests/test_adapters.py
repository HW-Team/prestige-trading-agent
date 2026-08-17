import pytest

from prestige_trading_agent.adapters import RecordingAdapter
from prestige_trading_agent.domain import OutboxKind


@pytest.mark.asyncio
async def test_recording_adapter_records_without_network() -> None:
    adapter = RecordingAdapter()
    await adapter.dispatch(OutboxKind.ENROLL_LMS, {"contact_id": "1"})
    assert adapter.deliveries[0].kind is OutboxKind.ENROLL_LMS
