import re
from dataclasses import dataclass

from pydantic import BaseModel, Field
from pydantic_ai import Agent, ModelSettings, RunContext
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
    # Prior turns as (role, text) — role is "user" or "assistant". Lets the
    # live model see the conversation so it does not restart with a greeting
    # on later turns. Newest message last.
    history: tuple[tuple[str, str], ...] = ()


class AgentRoute(BaseModel):
    reply: str = Field(min_length=1, max_length=2000)
    path: FunnelPath = FunnelPath.UNKNOWN
    next_state: FunnelState = FunnelState.QUALIFYING
    next_action: NextAction = NextAction.NONE
    rationale: str = ""
    # Set server-side after ingest so the test console can attach feedback to
    # the exact reply message; never produced by the model.
    reply_message_id: str | None = None


SYSTEM_PROMPT = build_system_prompt()


def build_agent(
    model: str,
    *,
    base_url: str | None = None,
    api_key: str | None = None,
) -> Agent[AgentDependencies, AgentRoute]:
    """Build the funnel agent.

    ``model == "test"`` uses the offline deterministic model. Otherwise a live
    OpenAI-compatible endpoint is wired (e.g. DeepSeek) when ``base_url`` and
    ``api_key`` are provided; a bare model name falls back to pydantic-ai's
    default provider resolution.
    """
    if model == "test":
        selected: str | TestModel = TestModel()
    elif base_url and api_key:
        from pydantic_ai.models.openai import OpenAIChatModel
        from pydantic_ai.providers.openai import OpenAIProvider

        selected = OpenAIChatModel(
            model,
            provider=OpenAIProvider(base_url=base_url, api_key=api_key),
            settings=ModelSettings(
                # DeepSeek's thinking mode rejects tool_choice used for
                # structured output; disable it so AgentRoute parsing works.
                extra_body={"thinking": {"type": "disabled"}},
            ),
        )
    else:
        selected = model
    agent: Agent[AgentDependencies, AgentRoute] = Agent(
        selected, deps_type=AgentDependencies, output_type=AgentRoute, system_prompt=SYSTEM_PROMPT
    )

    @agent.instructions
    def state_context(ctx: RunContext[AgentDependencies]) -> str:
        parts = [f"Current state: {ctx.deps.current_state}; contact: {ctx.deps.contact_id}"]
        if ctx.deps.history:
            transcript = "\n".join(
                f"{'ลูกค้า' if role == 'user' else 'AI'}: {text}" for role, text in ctx.deps.history
            )
            parts.append(f"บทสนทนาก่อนหน้า:\n{transcript}")
        return "\n".join(parts)

    return agent


def apply_safety_rules(route: AgentRoute) -> AgentRoute:
    text = route.reply.lower()
    # Financial promises / guarantee claims are forbidden in any form.
    unsafe_claim = any(term.lower() in text for term in FORBIDDEN_CLAIMS)
    # URL policy: the only links allowed are the approved public ones
    # (LINE OA lin.ee/WcilwHP + prestigetradingclub.com + forms.gle). Any other http link —
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
    if (
        "คุยกับโค้ช" in lower
        or "คุยกับคน" in lower
        or "ปรึกษา" in lower
        or "โค้ช" in lower
        or "consult" in lower
        or "coach" in lower
        or "ติดต่อแอดมิน" in lower
        or "อยากคุย" in lower
    ):
        return AgentRoute(
            reply=SCENARIOS["consult_coach"]["reply"],
            path=FunnelPath.COURSE,
            next_state=FunnelState.HUMAN_HANDOFF,
            next_action=NextAction.HUMAN_HANDOFF,
            rationale="customer wants to talk to a human (coach/consultant)",
        )
    # Payment / QR request mid-checkout: the customer is NOT expressing new
    # intent — they want the payment QR. Keep the funnel at checkout so the
    # QR enqueue (services) fires on the state; SEND_CHECKOUT re-prompts it.
    if any(
        kw in lower for kw in ("qr", "promptpay", "prompt pay", "โอน", "สลิป", "จ่าย")
    ):
        return AgentRoute(
            reply=SCENARIOS["course_checkout"]["reply"],
            path=FunnelPath.COURSE,
            next_state=FunnelState.CHECKOUT_PENDING,
            next_action=NextAction.SEND_CHECKOUT,
            rationale="customer asks for payment QR while at checkout",
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


def _default_route_for(path: FunnelPath) -> tuple[FunnelState, NextAction]:
    """Deterministic funnel progression for a classified path.

    Mirrors the offline router so the live model's free-form reply never
    drifts the state machine: path classification drives the canonical
    first state/action; the model supplies the reply text.
    """
    if path is FunnelPath.INDICATOR:
        return FunnelState.TRIAL_PENDING, NextAction.CREATE_ACCESS_REQUEST
    if path is FunnelPath.COURSE:
        return FunnelState.CHECKOUT_PENDING, NextAction.SEND_CHECKOUT
    if path is FunnelPath.NEWBIE:
        return FunnelState.FORM_PENDING, NextAction.SEND_FORM
    return FunnelState.QUALIFYING, NextAction.NONE


def _route_with_fallback(route: AgentRoute, current_state: FunnelState) -> AgentRoute:
    """Fill state/action from the classified path when the model left them at
    the default (qualifying/none) — keeps the funnel deterministic while the
    model composes the reply.

    The target state is only applied when it is reachable from the current
    state (mirrors the services transition map); otherwise the current state
    is kept so an informational question mid-funnel never regresses or
    strands the prospect.
    """
    if route.next_action is NextAction.NONE and route.next_state in {
        FunnelState.QUALIFYING,
        FunnelState.NEW,
    }:
        state, action = _default_route_for(route.path)
        if state in {FunnelState.QUALIFYING}:
            route.next_state = current_state
        elif (
            current_state
            in {
                FunnelState.NEW,
                FunnelState.QUALIFYING,
                FunnelState.FORM_COMPLETED,
                FunnelState.FREE_COMMUNITY,
                FunnelState.HUMAN_HANDOFF,
            }
            or state is current_state
        ):
            # Reachable funnel entry/advance (FORM_COMPLETED/FREE_COMMUNITY can
            # go to checkout/trial; NEW/QUALIFYING can start any path).
            route.next_state = state
            route.next_action = action
        else:
            # Mid-funnel (FORM_PENDING / CHECKOUT_PENDING / TRIAL_PENDING /
            # PAID_ACTIVE): keep current state, don't regress.
            route.next_state = current_state
        route.rationale = f"{route.rationale}; deterministic path routing".strip("; ")
    return route


async def route_message(
    agent: Agent[AgentDependencies, AgentRoute], prompt: str, deps: AgentDependencies
) -> AgentRoute:
    if isinstance(agent.model, TestModel):
        return apply_safety_rules(_offline_route(prompt))
    result = await agent.run(prompt, deps=deps)
    return apply_safety_rules(_route_with_fallback(result.output, deps.current_state))
