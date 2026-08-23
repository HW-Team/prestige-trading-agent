import re
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, RunContext
from pydantic_ai.models.test import TestModel

from prestige_trading_agent.domain import FunnelPath, FunnelState, NextAction
from prestige_trading_agent.knowledge import (
    APPROVED_URL_PREFIXES,
    FORBIDDEN_CLAIMS,
    SCENARIOS,
    build_system_prompt,
)


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


SYSTEM_PROMPT = build_system_prompt()


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
    # Financial promises / guarantee claims are forbidden in any form.
    unsafe_claim = any(term.lower() in text for term in FORBIDDEN_CLAIMS)
    # URL policy: the only links allowed are the approved public ones
    # (LINE OA lin.ee/WcilwHP + bravotradeacademy.com). Any other http link —
    # especially a lin.ee / line.me paid room invite — triggers a handoff.
    urls = re.findall(r"https?://[^\s)\]]+", route.reply, flags=re.IGNORECASE)
    # Case-insensitive whitelist match (lin.ee paths are case-sensitive).
    allowed = tuple(p.lower() for p in APPROVED_URL_PREFIXES)
    unsafe_url = any(not url.lower().startswith(allowed) for url in urls)
    if unsafe_claim or unsafe_url or route.next_action is NextAction.SEND_PAID_ROOM:
        return AgentRoute(
            reply=(
                "ขออภัยครับ ข้อมูลนี้อยู่นอกเหนือขอบเขตที่ผมให้บริการได้ "
                "ขออนุญาตประสานงานให้เจ้าหน้าที่แอดมินเข้ามาดูแลโดยเร็วที่สุดครับ"
            ),
            path=route.path,
            next_state=FunnelState.HUMAN_HANDOFF,
            next_action=NextAction.HUMAN_HANDOFF,
            rationale="deterministic safety rule",
        )
    return route


def _offline_route(prompt: str) -> AgentRoute:
    lower = prompt.lower()
    if "indicator" in lower or "tradingview" in lower or "ทดลอง" in lower or "trial" in lower:
        return AgentRoute(
            reply=SCENARIOS["indicator_trial"]["reply"],
            path=FunnelPath.INDICATOR,
            next_state=FunnelState.TRIAL_PENDING,
            next_action=NextAction.CREATE_ACCESS_REQUEST,
            rationale="indicator trial intent",
        )
    if "course" in lower or "checkout" in lower or "คอร์ส" in lower or "learn" in lower:
        return AgentRoute(
            reply=SCENARIOS["course_interest"]["reply"],
            path=FunnelPath.COURSE,
            next_state=FunnelState.CHECKOUT_PENDING,
            next_action=NextAction.SEND_CHECKOUT,
            rationale="course intent",
        )
    if "มือใหม่" in lower or "beginner" in lower or "เริ่ม" in lower or "newbie" in lower:
        return AgentRoute(
            reply=SCENARIOS["newbie_start"]["reply"],
            path=FunnelPath.NEWBIE,
            next_state=FunnelState.FORM_PENDING,
            next_action=NextAction.SEND_FORM,
            rationale="newbie intent",
        )
    return AgentRoute(
        reply=(
            "สวัสดีครับ ยินดีให้คำแนะนำเกี่ยวกับระบบ DCTS ค่ะ/ครับ "
            "ไม่ทราบว่าท่านสนใจรายละเอียดคอร์สเรียน หรือต้องการปรึกษาแนวทางการเทรดครับ?"
        ),
        path=FunnelPath.UNKNOWN,
        next_state=FunnelState.QUALIFYING,
        next_action=NextAction.NONE,
        rationale="ambiguous intent",
    )


async def route_message(
    agent: Agent[AgentDependencies, AgentRoute], prompt: str, deps: AgentDependencies
) -> AgentRoute:
    if isinstance(agent.model, TestModel):
        return apply_safety_rules(_offline_route(prompt))
    result = await agent.run(prompt, deps=deps)
    return apply_safety_rules(result.output)
