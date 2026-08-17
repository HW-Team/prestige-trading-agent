from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.test import TestModel

from prestige_trading_agent.domain import FunnelPath, FunnelState, NextAction


@dataclass
class AgentDependencies:
    contact_id: str
    conversation_id: str
    current_state: FunnelState = FunnelState.NEW


class AgentRoute(BaseModel):
    reply: str = Field(min_length=1, max_length=2000)
    path: FunnelPath = FunnelPath.UNKNOWN
    next_state: FunnelState = FunnelState.QUALIFYING
    next_action: NextAction = NextAction.NONE
    rationale: str = ""


SYSTEM_PROMPT = """You are Prestige Trading's funnel assistant. Classify intent into newbie,
course, or indicator and provide concise educational help. Never promise financial returns, give
personalized financial advice, or reveal a paid LINE room invite. Newbies receive a form; course
prospects receive checkout; indicator trials create a manual approval request.
Return structured data.
"""


def build_agent(model: str) -> Agent[AgentDependencies, AgentRoute]:
    selected: str | TestModel = TestModel() if model == "test" else model
    agent: Agent[AgentDependencies, AgentRoute] = Agent(
        selected, deps_type=AgentDependencies, output_type=AgentRoute, system_prompt=SYSTEM_PROMPT
    )

    @agent.instructions
    def state_context(ctx: RunContext[AgentDependencies]) -> str:
        return f"Current state: {ctx.deps.current_state}; contact: {ctx.deps.contact_id}"

    return agent


def apply_safety_rules(route: AgentRoute) -> AgentRoute:
    text = route.reply.lower()
    forbidden = ("guaranteed", "guarantee", "no risk", "paid-secret", "paid room")
    unsafe_link = "line.me" in text and route.next_action is not NextAction.SEND_FREE_LINE_INVITE
    if (
        any(term in text for term in forbidden)
        or unsafe_link
        or route.next_action is NextAction.SEND_PAID_ROOM
    ):
        return AgentRoute(
            reply=(
                "I can provide general education only. A team member will help with access safely."
            ),
            path=route.path,
            next_state=FunnelState.HUMAN_HANDOFF,
            next_action=NextAction.HUMAN_HANDOFF,
            rationale="deterministic safety rule",
        )
    return route


def _offline_route(prompt: str) -> AgentRoute:
    lower = prompt.lower()
    if "indicator" in lower or "tradingview" in lower or "trial" in lower:
        return AgentRoute(
            reply="I can place your free indicator trial request into our approval queue.",
            path=FunnelPath.INDICATOR,
            next_state=FunnelState.TRIAL_PENDING,
            next_action=NextAction.CREATE_ACCESS_REQUEST,
        )
    if "course" in lower or "checkout" in lower or "learn" in lower:
        return AgentRoute(
            reply="I can share the course checkout when you are ready.",
            path=FunnelPath.COURSE,
            next_state=FunnelState.CHECKOUT_PENDING,
            next_action=NextAction.SEND_CHECKOUT,
        )
    return AgentRoute(
        reply="Welcome! Complete the free form and I will send the free community invite here.",
        path=FunnelPath.NEWBIE,
        next_state=FunnelState.FORM_PENDING,
        next_action=NextAction.SEND_FORM,
    )


async def route_message(
    agent: Agent[AgentDependencies, AgentRoute], prompt: str, deps: AgentDependencies
) -> AgentRoute:
    if isinstance(agent.model, TestModel):
        return apply_safety_rules(_offline_route(prompt))
    result = await agent.run(prompt, deps=deps)
    return apply_safety_rules(result.output)
