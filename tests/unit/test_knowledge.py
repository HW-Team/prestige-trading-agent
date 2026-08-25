"""Integrity tests: approved knowledge from the Prestige Trading Club Google Doc.

Doc: "แบบเก็บข้อมูลสำหรับตั้งค่า AI Agent — Prestige Trading Club"
(document 1xoHY-hlSmuKFgyE2ddeoe7G1zOCLu4G82mR0dE_Jxnw), อนุมัติแล้ว 22 Aug 2569.

These tests guard the exact approved values so a bad edit cannot silently
change prices, package names, forbidden claims, or public links.
"""

from prestige_trading_agent.agent import SYSTEM_PROMPT
from prestige_trading_agent.knowledge import (
    APPROVED_DISCLAIMER,
    BRAND_NAME,
    DOWNSELLS,
    FAQS,
    FORBIDDEN_CLAIMS,
    HANDOFF_RULES,
    PACKAGES,
    PAYMENT_FORMS,
    PUBLIC_LINKS,
    SCENARIOS,
    SEGMENTS,
    SUPPORT_CHANNELS,
    UPSELLS,
    build_system_prompt,
)


def test_brand_name_is_approved() -> None:
    assert BRAND_NAME == "โค้ชกอล์ฟ Rachata : ยกระดับชีวิตด้วยอาชีพเทรดเดอร์"


def test_two_approved_packages_with_exact_prices() -> None:
    assert len(PACKAGES) == 2
    assert PACKAGES[0].name == "DCTS ฉบับรวบรัด (Fast-Track Edition)"
    assert PACKAGES[0].price == "990 บาท"
    assert PACKAGES[1].name == "DCTS ฉบับเต็ม (Full Master Edition)"
    assert PACKAGES[1].price == "3,990 บาท"
    for pkg in PACKAGES:
        assert "การันตี" in pkg.conditions  # every package reminds no-guarantee


def test_portfolio_claim_uses_3000_usd_not_100k_baht() -> None:
    """Team feedback (พี่ Pana, 2026-08-24): the $300 plan target is 3,000$/mo,
    NOT 100,000 บาท/เดือน. The old number must never reappear."""
    prompt = build_system_prompt()
    assert "100,000" not in prompt
    assert "3,000$" in prompt


def test_payment_forms_are_approved_google_forms() -> None:
    assert PAYMENT_FORMS["990"] == "https://forms.gle/bjLjyFwxP96hiyF16"
    assert PAYMENT_FORMS["3990"] == "https://forms.gle/hfTC9ukgNmk71uHv9"
    assert PAYMENT_FORMS["990"] in build_system_prompt()
    assert PAYMENT_FORMS["3990"] in build_system_prompt()


def test_ten_approved_faqs() -> None:
    assert len(FAQS) == 10
    assert "การันตี" in FAQS[8].answer  # FAQ 9 = no guarantee of returns
    assert FAQS[9].handoff is True  # FAQ 10 = contact LINE OA admin


def test_forbidden_claims_include_thai_guarantees() -> None:
    for claim in (
        "การันตีกำไร",
        "รวยเร็ว",
        "ไม่มีความเสี่ยง",
        "ซิกแนลแม่น 100%",
        "รับฝากเทรด",
        "ระดมทุน",
    ):
        assert claim in FORBIDDEN_CLAIMS


def test_public_links_are_approved_domains_only() -> None:
    assert PUBLIC_LINKS["beginner_form"].startswith("https://prestigetradingclub.com/")
    assert PUBLIC_LINKS["checkout"] == "https://lin.ee/WcilwHP"
    assert PUBLIC_LINKS["lms"].startswith("https://prestigetradingclub.com/")
    assert PUBLIC_LINKS["privacy_policy"].startswith("https://prestigetradingclub.com/")
    assert PUBLIC_LINKS["terms"].startswith("https://prestigetradingclub.com/")
    # No paid LINE room link anywhere in public links.
    for url in PUBLIC_LINKS.values():
        assert "lin.ee/WcilwHP" in url or "prestigetradingclub.com" in url or "forms.gle" in url
    # No legacy bravotradeacademy URLs may survive.
    assert "bravotradeacademy" not in " ".join(PUBLIC_LINKS.values())


def test_support_channel_is_line_oa() -> None:
    assert SUPPORT_CHANNELS["line_oa"] == "@prestigeclub"
    assert SUPPORT_CHANNELS["line_link"] == "https://lin.ee/WcilwHP"


def test_four_segments_and_indicator_collection_fields() -> None:
    assert set(SEGMENTS) == {"newbie", "course", "indicator", "existing"}
    collect = SEGMENTS["indicator"]["collect"]
    for field in ("ชื่อ-นามสกุล", "อีเมล", "TradingView Username", "เบอร์โทร"):
        assert field in collect


def test_upsell_and_downsell_are_approved() -> None:
    assert len(UPSELLS) == 1
    assert "3,990 บาท" in UPSELLS[0]["offer"]
    assert "7 วัน" in UPSELLS[0]["cooldown_days"]
    assert len(DOWNSELLS) == 1
    assert "990 บาท" in DOWNSELLS[0]["offer"]
    assert "Public Layer" in DOWNSELLS[0]["still_decline"]


def test_handoff_rules_cover_topics_with_sla() -> None:
    assert len(HANDOFF_RULES) == 5
    topics = {rule["topic"] for rule in HANDOFF_RULES}
    assert "การชำระเงินหรือสิทธิ์ใช้งานมีปัญหา" in topics
    assert "ขอคืนเงินหรือยกเลิก" in topics
    assert "TradingView หรือ Indicator เข้าไม่ได้" in topics
    assert "คำถามที่ไม่มีข้อมูลยืนยัน" in topics
    assert "ต้องการคุยกับโค้ชหรือที่ปรึกษาโดยตรง" in topics
    for rule in HANDOFF_RULES:
        assert rule["sla"]


def test_scenarios_cover_all_situations() -> None:
    assert set(SCENARIOS) == {
        "newbie_start",
        "course_interest",
        "indicator_trial",
        "unclear",
        "payment_success",
        "consult_coach",
    }


def test_disclaimer_is_approved() -> None:
    assert "การลงทุนในตลาดการเงินมีความเสี่ยง" in APPROVED_DISCLAIMER
    assert "มิใช่การการันตีผลตอบแทนในอนาคต" in APPROVED_DISCLAIMER


def test_system_prompt_includes_brand_and_safety() -> None:
    assert BRAND_NAME in SYSTEM_PROMPT
    assert "3,990 บาท" in SYSTEM_PROMPT
    assert "990 บาท" in SYSTEM_PROMPT
    assert APPROVED_DISCLAIMER in SYSTEM_PROMPT
    assert "ห้ามส่งลิงก์ห้อง LINE เสียเงิน" in SYSTEM_PROMPT
    # Paid room link is never part of the prompt itself.
    assert "lin.ee/WcilwHP" in SYSTEM_PROMPT  # free/public OA link only
