import pytest

from prestige_trading_agent.agent import AgentDependencies, build_agent, route_message
from prestige_trading_agent.domain import FunnelPath, NextAction


@pytest.mark.asyncio
async def test_offline_agent_returns_structured_newbie_route() -> None:
    result = await route_message(
        build_agent("test"),
        "ผมเป็นมือใหม่ ไม่มีพื้นฐาน เริ่มต้นยังไงดีครับ",
        AgentDependencies(contact_id="c1", conversation_id="v1"),
    )
    assert result.path is FunnelPath.NEWBIE
    assert result.next_action is NextAction.SEND_FORM
    assert result.reply


@pytest.mark.asyncio
async def test_offline_agent_routes_indicator_trial_to_approval() -> None:
    result = await route_message(
        build_agent("test"),
        "สนใจทดลอง Indicator บน TradingView ครับ",
        AgentDependencies(contact_id="c1", conversation_id="v1"),
    )
    assert result.path is FunnelPath.INDICATOR
    assert result.next_action is NextAction.CREATE_ACCESS_REQUEST


@pytest.mark.asyncio
async def test_offline_agent_routes_course_to_checkout() -> None:
    result = await route_message(
        build_agent("test"),
        "สนใจคอร์ส DCTS ฉบับเต็ม 3,990 บาทครับ",
        AgentDependencies(contact_id="c1", conversation_id="v1"),
    )
    assert result.path is FunnelPath.COURSE
    assert result.next_action is NextAction.SEND_CHECKOUT


@pytest.mark.asyncio
async def test_offline_agent_ambiguous_intent_asks_qualifying_question() -> None:
    result = await route_message(
        build_agent("test"),
        "สวัสดี",
        AgentDependencies(contact_id="c1", conversation_id="v1"),
    )
    assert result.path is FunnelPath.UNKNOWN
    assert result.next_state.value == "qualifying"
    assert result.reply
