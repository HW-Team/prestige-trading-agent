import pytest

from prestige_trading_agent.domain import FunnelState
from prestige_trading_agent.services import InvalidTransition, transition


def test_valid_funnel_transition() -> None:
    assert transition(FunnelState.NEW, FunnelState.QUALIFYING) is FunnelState.QUALIFYING


def test_newbie_form_can_jump_to_checkout() -> None:
    # Approved doc Scenario A: มือใหม่ → แนะนำแพ็กเกจ → ลูกค้าเลือก → checkout
    assert transition(FunnelState.FORM_PENDING, FunnelState.CHECKOUT_PENDING) is (
        FunnelState.CHECKOUT_PENDING
    )


def test_newbie_form_can_jump_to_indicator_trial() -> None:
    assert (
        transition(FunnelState.FORM_PENDING, FunnelState.TRIAL_PENDING) is FunnelState.TRIAL_PENDING
    )


def test_invalid_funnel_transition_is_rejected() -> None:
    with pytest.raises(InvalidTransition):
        transition(FunnelState.NEW, FunnelState.PAID_ACTIVE)


def test_terminal_unsubscribed_state_cannot_transition() -> None:
    with pytest.raises(InvalidTransition):
        transition(FunnelState.UNSUBSCRIBED, FunnelState.NEW)
