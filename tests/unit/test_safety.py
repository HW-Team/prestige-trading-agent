from prestige_trading_agent.agent import AgentRoute, _route_with_fallback, apply_safety_rules
from prestige_trading_agent.domain import FunnelPath, FunnelState, NextAction


def test_route_fallback_fills_state_and_action_from_path() -> None:
    route = AgentRoute(
        reply="ทดลอง Indicator ได้ครับ",
        path=FunnelPath.INDICATOR,
        next_state=FunnelState.QUALIFYING,
        next_action=NextAction.NONE,
    )
    fixed = _route_with_fallback(route, FunnelState.NEW)
    assert fixed.next_state is FunnelState.TRIAL_PENDING
    assert fixed.next_action is NextAction.CREATE_ACCESS_REQUEST


def test_route_fallback_keeps_current_state_when_target_unreachable() -> None:
    # Mid-checkout prospect asks a beginner question: must NOT regress to form.
    route = AgentRoute(
        reply="มือใหม่เรียนได้ครับ",
        path=FunnelPath.NEWBIE,
        next_state=FunnelState.QUALIFYING,
        next_action=NextAction.NONE,
    )
    fixed = _route_with_fallback(route, FunnelState.CHECKOUT_PENDING)
    assert fixed.next_state is FunnelState.CHECKOUT_PENDING
    assert fixed.next_action is NextAction.NONE


def test_route_fallback_does_not_override_explicit_handoff() -> None:
    route = AgentRoute(
        reply="ส่งต่อแอดมิน",
        path=FunnelPath.COURSE,
        next_state=FunnelState.HUMAN_HANDOFF,
        next_action=NextAction.HUMAN_HANDOFF,
    )
    fixed = _route_with_fallback(route, FunnelState.NEW)
    assert fixed.next_state is FunnelState.HUMAN_HANDOFF
    assert fixed.next_action is NextAction.HUMAN_HANDOFF


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
