import pytest

from prestige_trading_agent.agent import AgentDependencies, build_agent, route_message
from prestige_trading_agent.domain import FunnelPath, NextAction


@pytest.mark.asyncio
async def test_offline_agent_returns_structured_newbie_route() -> None:
    result = await route_message(
        build_agent("test"),
        "I am a complete beginner and want the free community",
        AgentDependencies(contact_id="c1", conversation_id="v1"),
    )
    assert result.path is FunnelPath.NEWBIE
    assert result.next_action is NextAction.SEND_FORM
    assert result.reply


@pytest.mark.asyncio
async def test_offline_agent_routes_indicator_trial_to_approval() -> None:
    result = await route_message(
        build_agent("test"),
        "Can I trial the TradingView indicator?",
        AgentDependencies(contact_id="c1", conversation_id="v1"),
    )
    assert result.path is FunnelPath.INDICATOR
    assert result.next_action is NextAction.CREATE_ACCESS_REQUEST
