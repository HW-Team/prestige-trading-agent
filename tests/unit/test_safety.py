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


def test_paid_line_room_link_never_appears_in_reply() -> None:
    unsafe = AgentRoute(
        reply="เข้าห้องเรียนได้ที่ https://lin.ee/PaidRoomSecret",
        path=FunnelPath.COURSE,
        next_state=FunnelState.PAID_ACTIVE,
        next_action=NextAction.NONE,
    )
    safe = apply_safety_rules(unsafe)
    assert "lin.ee" not in safe.reply
    assert safe.next_action is NextAction.HUMAN_HANDOFF


def test_financial_promises_are_blocked() -> None:
    unsafe = AgentRoute(reply="Guaranteed profit with no risk", path=FunnelPath.INDICATOR)
    assert "guarante" not in apply_safety_rules(unsafe).reply.lower()


def test_thai_guarantee_claims_are_blocked() -> None:
    for claim in ("การันตีกำไร 100%", "รวยเร็วแน่นอน", "ซิกแนลแม่น 100%", "ไม่มีความเสี่ยง"):
        unsafe = AgentRoute(reply=f"สมัครเลยครับ {claim} ได้ผลแน่นอน", path=FunnelPath.COURSE)
        safe = apply_safety_rules(unsafe)
        assert claim not in safe.reply
        assert safe.next_action is NextAction.HUMAN_HANDOFF


def test_free_line_invite_action_allows_public_group_link() -> None:
    safe_route = AgentRoute(
        reply="เข้ากลุ่มฟรีได้ที่ https://lin.ee/WcilwHP",
        path=FunnelPath.NEWBIE,
        next_state=FunnelState.FREE_COMMUNITY,
        next_action=NextAction.SEND_FREE_LINE_INVITE,
    )
    safe = apply_safety_rules(safe_route)
    assert safe.next_action is NextAction.SEND_FREE_LINE_INVITE
    assert "lin.ee/WcilwHP" in safe.reply
