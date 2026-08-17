from dataclasses import dataclass
from typing import Any, Protocol

import httpx

from prestige_trading_agent.config import Settings
from prestige_trading_agent.domain import OutboxKind


class OutboundAdapter(Protocol):
    async def dispatch(self, kind: OutboxKind, payload: dict[str, Any]) -> None: ...


@dataclass(frozen=True)
class Delivery:
    kind: OutboxKind
    payload: dict[str, Any]


class RecordingAdapter:
    def __init__(self) -> None:
        self.deliveries: list[Delivery] = []

    async def dispatch(self, kind: OutboxKind, payload: dict[str, Any]) -> None:
        self.deliveries.append(Delivery(kind, payload.copy()))


class LiveAdapter:
    """Network adapter. Paid access is always an opaque operational action, never an invite URL."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=15)

    async def _send_meta(self, recipient_id: str, text: str) -> None:
        token = self.settings.meta_page_access_token
        if token is None:
            raise RuntimeError("PRESTIGE_META_PAGE_ACCESS_TOKEN is required for live Messenger")
        response = await self.client.post(
            "https://graph.facebook.com/v23.0/me/messages",
            params={"access_token": token.get_secret_value()},
            json={"recipient": {"id": recipient_id}, "message": {"text": text}},
        )
        response.raise_for_status()

    async def dispatch(self, kind: OutboxKind, payload: dict[str, Any]) -> None:
        if kind is OutboxKind.SEND_MESSAGE:
            await self._send_meta(str(payload["recipient_id"]), str(payload["text"]))
        elif kind is OutboxKind.SEND_FREE_LINE_INVITE:
            await self._send_meta(
                str(payload["recipient_id"]),
                f"Your free community invite: {self.settings.free_line_invite_url}",
            )
        elif kind is OutboxKind.ENROLL_LMS:
            if not self.settings.lms_endpoint or not self.settings.lms_api_key:
                raise RuntimeError("LMS endpoint and API key are required for live enrollment")
            response = await self.client.post(
                self.settings.lms_endpoint,
                headers={"Authorization": f"Bearer {self.settings.lms_api_key.get_secret_value()}"},
                json=payload,
            )
            response.raise_for_status()
        elif kind in {OutboxKind.PROVISION_PAID_ACCESS, OutboxKind.NOTIFY_ACCESS_APPROVED}:
            # These deliberately remain queue/ops actions: no paid room URL exists in this adapter.
            return
