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


class EasySlipAdapter:
    """EasySlip API client — slip verification + PromptPay QR generation.

    Docs: https://document.easyslip.com
      - POST /v1/qr/generate  → PromptPay/merchant QR (returns base64 PNG)
      - GET  /v1/verify?payload= → verify a slip from its QR payload string
    """

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=30)

    async def generate_qr(
        self, amount: float | None = None, ref1: str | None = None
    ) -> dict[str, Any]:
        """Generate a PromptPay QR (base64 PNG + payload string).

        Uses the configured proxy (msisdn/natId) from settings. Returns
        {"ok": bool, "reason": str, "image": base64, "mime": str, "payload": str}.
        """
        key = self.settings.easyslip_api_key
        if key is None:
            return {"ok": False, "reason": "easyslip_not_configured", "meta": {}}
        body: dict[str, Any] = {"type": "PROMPTPAY"}
        if self.settings.easyslip_proxy_msisdn:
            body["msisdn"] = self.settings.easyslip_proxy_msisdn
        elif self.settings.easyslip_proxy_natid:
            body["natId"] = self.settings.easyslip_proxy_natid
        if amount is not None:
            body["amount"] = round(float(amount), 2)
        response = await self.client.post(
            f"{self.settings.easyslip_base_url}/qr/generate",
            headers={"Authorization": f"Bearer {key.get_secret_value()}"},
            json=body,
        )
        if response.status_code != 200:
            return {"ok": False, "reason": f"easyslip_http_{response.status_code}", "meta": {}}
        data = response.json()
        qr = data.get("data") or {}
        return {
            "ok": True,
            "reason": "ok",
            "image": qr.get("image", ""),
            "mime": qr.get("mime", "image/png"),
            "payload": qr.get("payload", ""),
        }

    async def verify_payload(self, payload: str, check_duplicate: bool = True) -> dict[str, Any]:
        """Verify a slip from its QR payload string (the modern approach —
        customers scanning a QR produce a payload we can re-verify)."""
        key = self.settings.easyslip_api_key
        if key is None:
            return {"ok": False, "reason": "easyslip_not_configured", "meta": {}}
        response = await self.client.get(
            f"{self.settings.easyslip_base_url}/verify",
            headers={"Authorization": f"Bearer {key.get_secret_value()}"},
            params={"payload": payload, "checkDuplicate": str(check_duplicate).lower()},
        )
        if response.status_code != 200:
            return {"ok": False, "reason": f"easyslip_http_{response.status_code}", "meta": {}}
        data = response.json()
        slip = data.get("data") or {}
        amount = (slip.get("amount") or {}).get("amount")
        receiver = (slip.get("receiver") or {}).get("account", {}).get("name", {})
        receiver_name = receiver.get("th") or receiver.get("en") or ""
        return {
            "ok": bool(amount is not None),
            "reason": "ok",
            "meta": {
                "trans_ref": slip.get("transRef"),
                "date": slip.get("date"),
                "amount": amount,
                "receiver": receiver_name,
                "sender": (slip.get("sender") or {}).get("account", {}).get("name", {}),
                "duplicate": data.get("status") == "duplicate_slip",
            },
        }

    async def validate(
        self, slip_image_url: str, expected_amount: str | None = None
    ) -> dict[str, Any]:
        key = self.settings.easyslip_api_key
        if key is None:
            return {"ok": False, "reason": "easyslip_not_configured", "meta": {}}
        response = await self.client.post(
            f"{self.settings.easyslip_base_url}/validate",
            headers={"Authorization": f"Bearer {key.get_secret_value()}"},
            json={"image_url": slip_image_url, "log": False},
        )
        if response.status_code != 200:
            return {"ok": False, "reason": f"easyslip_http_{response.status_code}", "meta": {}}
        data = response.json()
        trans = data.get("transRef") or data.get("data") or {}
        amount = trans.get("amount")
        paid = trans.get("paid")
        ok = bool(paid)
        if expected_amount and amount is not None:
            try:
                ok = ok and abs(float(amount) - float(expected_amount)) < 0.01
            except (TypeError, ValueError):
                ok = False
        merchant = self.settings.easyslip_merchant_name.strip().lower()
        receiver = str(trans.get("receiver") or trans.get("payee") or "")
        if merchant and receiver and merchant not in receiver.lower():
            ok = False
        return {
            "ok": ok,
            "reason": "ok" if ok else "mismatch",
            "meta": {
                "amount": amount,
                "paid": paid,
                "date": trans.get("date"),
                "receiver": receiver,
                "raw": data,
            },
        }


class LiveAdapter:
    """Network adapter. Paid access is always an opaque operational action, never an invite URL."""

    def __init__(self, settings: Settings, client: httpx.AsyncClient | None = None) -> None:
        self.settings = settings
        self.client = client or httpx.AsyncClient(timeout=15)

    async def notify_feedback(self, text: str) -> bool:
        """Best-effort push of tester feedback to the configured Telegram chat.

        Returns False (never raises) when Telegram is not configured or the
        push fails — feedback capture must not depend on the notification.
        """
        token = self.settings.telegram_bot_token
        chat_id = self.settings.telegram_chat_id
        if token is None or not chat_id:
            return False
        try:
            response = await self.client.post(
                f"https://api.telegram.org/bot{token.get_secret_value()}/sendMessage",
                json={"chat_id": chat_id, "text": text, "disable_web_page_preview": True},
            )
            return response.status_code == 200
        except Exception:
            return False

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

    async def _send_line(self, recipient_id: str, text: str) -> None:
        token = self.settings.line_channel_access_token
        if token is None:
            raise RuntimeError("PRESTIGE_LINE_CHANNEL_ACCESS_TOKEN is required for live LINE")
        response = await self.client.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {token.get_secret_value()}",
                "Content-Type": "application/json",
            },
            json={"to": recipient_id, "messages": [{"type": "text", "text": text}]},
        )
        response.raise_for_status()

    async def dispatch(self, kind: OutboxKind, payload: dict[str, Any]) -> None:
        if kind is OutboxKind.SEND_MESSAGE:
            channel = str(payload.get("channel", "messenger"))
            if channel == "line":
                await self._send_line(str(payload["recipient_id"]), str(payload["text"]))
            else:
                await self._send_meta(str(payload["recipient_id"]), str(payload["text"]))
        elif kind is OutboxKind.SEND_FREE_LINE_INVITE:
            await self._send_meta(
                str(payload["recipient_id"]),
                f"Your free community invite: {self.settings.free_line_invite_url}",
            )
        elif kind is OutboxKind.SEND_PAID_ROOM:
            # Paid access = closed Facebook group. Meta deprecated the Groups
            # member API, so we send the invite link and the customer joins;
            # the group admin approves the join request manually.
            link = self.settings.facebook_group_invite_url
            msg = (
                "ชำระเงินเรียบร้อยครับ 🎉 กรุณากรอกฟอร์มและกดเข้ากลุ่ม Facebook ปิดผ่านลิงก์นี้ "
                f"{link} เจ้าหน้าที่จะอนุมัติภายใน 24 ชม. ครับ"
                if link
                else "ชำระเงินเรียบร้อยครับ 🎉 เจ้าหน้าที่จะส่งลิงก์เข้ากลุ่ม Facebook ปิดให้ภายใน 24 ชม. ครับ"
            )
            if str(payload.get("channel", "messenger")) == "line":
                await self._send_line(str(payload["recipient_id"]), msg)
            else:
                await self._send_meta(str(payload["recipient_id"]), msg)
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
