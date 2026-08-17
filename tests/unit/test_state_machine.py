import pytest

from prestige_trading_agent.domain import FunnelState
from prestige_trading_agent.services import InvalidTransition, transition


def test_valid_funnel_transition() -> None:
    assert transition(FunnelState.NEW, FunnelState.QUALIFYING) is FunnelState.QUALIFYING


def test_invalid_funnel_transition_is_rejected() -> None:
    with pytest.raises(InvalidTransition):
        transition(FunnelState.NEW, FunnelState.PAID_ACTIVE)


def test_terminal_unsubscribed_state_cannot_transition() -> None:
    with pytest.raises(InvalidTransition):
        transition(FunnelState.UNSUBSCRIBED, FunnelState.NEW)
