from prestige_trading_agent.agent import AgentRoute, apply_safety_rules
from prestige_trading_agent.domain import FunnelPath, FunnelState, NextAction


def test_paid_room_link_is_never_returned() -> None:
    unsafe = AgentRoute(
        reply="Join https://line.me/paid-secret now",
        path=FunnelPath.COURSE,
        next_state=FunnelState.PAID_ACTIVE,
        next_action=NextAction.SEND_PAID_ROOM,
    )
    safe = apply_safety_rules(unsafe)
    assert "paid-secret" not in safe.reply
    assert safe.next_action is NextAction.HUMAN_HANDOFF


def test_financial_promises_are_blocked() -> None:
    unsafe = AgentRoute(reply="Guaranteed profit with no risk", path=FunnelPath.INDICATOR)
    assert "guarante" not in apply_safety_rules(unsafe).reply.lower()
