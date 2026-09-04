from functools import lru_cache
from typing import Literal

from pydantic import SecretStr
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Environment-backed application configuration."""

    model_config = SettingsConfigDict(env_file=".env", env_prefix="PRESTIGE_", extra="ignore")

    environment: Literal["development", "test", "production"] = "development"
    database_url: str = "sqlite+aiosqlite:///./prestige.db"
    admin_api_key: SecretStr = SecretStr("change-me")
    meta_verify_token: SecretStr = SecretStr("change-me")
    meta_app_secret: SecretStr = SecretStr("change-me")
    meta_page_access_token: SecretStr | None = None
    meta_app_id: str | None = None
    meta_page_id: str | None = None
    form_webhook_secret: SecretStr = SecretStr("change-me")
    stripe_webhook_secret: SecretStr = SecretStr("change-me")
    model: str = "test"
    model_base_url: str | None = None
    model_api_key: SecretStr | None = None
    outbound_mode: Literal["recording", "live"] = "recording"
    free_line_invite_url: str = "https://lin.ee/WcilwHP"
    newbie_form_url: str = "https://prestigetradingclub.com/"
    course_checkout_url: str = "https://lin.ee/WcilwHP"
    indicator_form_url: str = "https://lin.ee/WcilwHP"
    lms_endpoint: str | None = "https://prestigetradingclub.com/"
    lms_api_key: SecretStr | None = None
    support_line_oa: str = "@prestigeclub"
    privacy_policy_url: str = "https://prestigetradingclub.com/privacy-policy"
    terms_of_service_url: str = "https://prestigetradingclub.com/terms-of-service"
    # Optional: push tester feedback to a Telegram chat (e.g. the HW Team
    # channel) the moment it is captured, so the agent operator can act on it.
    telegram_bot_token: SecretStr | None = None
    telegram_chat_id: str | None = None

    # ---- Temporary promo (ชั่วคราว): Focus Group Coaching 1 เดือน ราคา 1,580 ----
    # Set PRESTIGE_PROMO_1580_ACTIVE=false (or an ISO end date in
    # PRESTIGE_PROMO_1580_UNTIL) to stop the bot offering the promo — it then
    # pitches only the two standard packages (990/3,990).
    promo_1580_active: bool = True
    promo_1580_until: str | None = None

    # ---- Payment: PromptPay QR + bank (approved 2026-08-24) ----
    bank_name: str = "ธนาคารกสิกรไทย (KBank)"
    bank_account_name: str = "นาย รชต มากมูล"
    bank_account_number: str = "xxx-x-x6834-x"  # as printed on the official QR
    promptpay_ref: str = "004999003379228"
    payment_instructions: str = (
        "สแกน QR เพื่อโอนค่าคอร์ส แล้วส่งสลิปโอนเงินกลับมาในแชท เจ้าหน้าที่จะตรวจสอบและเปิดสิทธิ์ให้ภายใน 15 นาทีครับ"
    )

    # ---- Post-payment Google Forms (one per package) ----
    form_990_url: str = "https://forms.gle/hfTC9ukgNmk71uHv9"
    form_3990_url: str = "https://forms.gle/bjLjyFwxP96hiyF16"
    # โปรชันชั่วคราว (Focus Group Coaching 1 เดือน) — ฟอร์มลงทะเบียนกิจกรรม
    form_1580_url: str = "https://forms.gle/4voumeTBqC5dC8Rx9"

    # ---- Google Sheets for cross-checking paid customers ----
    # Both are public "anyone with link" response sheets from the forms above.
    sheet_990_id: str = "1VCzHIRomvtX9d1zXqyx77HPClKhMznpRARzfD94dBk8"
    sheet_3990_id: str = "10RlTyP7lIs-tzNEFzXH889OrGDS2cuocmRJRE2Qpwcc"
    # Column indexes (0-based) in both sheets — locked by test.
    sheet_col_line_id: int = 6
    sheet_col_phone: int = 3
    sheet_col_email: int = 5
    sheet_col_fb: int = 4
    sheet_col_slip: int = 12

    # ---- Paid access: closed Facebook group (invite link per package, admin approves join) ----
    facebook_group_invite_990: str | None = None
    facebook_group_invite_3990: str | None = None
    # Focus Group Coaching 1 เดือน (โปรชันชั่วคราว) — ทีมอาจใช้กลุ่มเฉพาะของกิจกรรม
    facebook_group_invite_1580: str | None = None

    # ---- Payment QR ----
    payment_qr_url: str = "/assets/payment-qr.jpg"
    public_base_url: str = "https://agent.prestigetradingclub.com"

    # ---- EasySlip slip validation + QR generation ----
    easyslip_api_key: SecretStr | None = None
    easyslip_base_url: str = "https://api.easyslip.com/v1"
    easyslip_merchant_name: str = "รชต มากมูล"
    # PromptPay proxy to embed in generated QR codes (msisdn OR natId OR eWalletId).
    easyslip_proxy_msisdn: str | None = None
    easyslip_proxy_natid: str | None = None
    easyslip_proxy_ewalletid: str | None = None

    # ---- LINE Messaging API ----
    line_channel_access_token: SecretStr | None = None
    line_channel_secret: SecretStr | None = None
    line_verify_token: SecretStr = SecretStr("change-me")


@lru_cache
def get_settings() -> Settings:
    return Settings()
