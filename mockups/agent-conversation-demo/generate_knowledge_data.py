#!/usr/bin/env python3
"""Generate knowledge-data.js from the approved Python knowledge module.

Keeps the here.now conversation demo in exact parity with the backend agent:
every reply, package, FAQ, and scenario string comes from
src/prestige_trading_agent/knowledge.py (approved Google Doc source).
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src"))

from prestige_trading_agent.knowledge import (
    APPROVED_DISCLAIMER,
    BRAND_INTRO,
    BRAND_NAME,
    DOWNSELLS,
    FAQS,
    FINANCIAL_POLICY,
    FORBIDDEN_CLAIMS,
    HANDOFF_RULES,
    PACKAGES,
    PUBLIC_LINKS,
    RESPONSE_RULES,
    SCENARIOS,
    SEGMENTS,
    SUPPORT_CHANNELS,
    TONE,
    UPSELLS,
)

payload = {
    "brand": {
        "name": BRAND_NAME,
        "intro": BRAND_INTRO,
        "tone": TONE,
        "support": SUPPORT_CHANNELS,
        "disclaimer": APPROVED_DISCLAIMER,
    },
    "packages": [p.__dict__ for p in PACKAGES],
    "financial_policy": FINANCIAL_POLICY,
    "segments": SEGMENTS,
    "faqs": [f.__dict__ for f in FAQS],
    "scenarios": SCENARIOS,
    "upsells": UPSELLS,
    "downsells": DOWNSELLS,
    "handoff_rules": HANDOFF_RULES,
    "links": PUBLIC_LINKS,
    "response_rules": RESPONSE_RULES,
    "forbidden_claims": FORBIDDEN_CLAIMS,
}

out = Path(__file__).resolve().parent / "knowledge-data.js"
out.write_text(
    "// AUTO-GENERATED from knowledge.py — do not edit by hand.\nconst KNOWLEDGE = "
    + json.dumps(payload, ensure_ascii=False, indent=1)
    + ";\n",
    encoding="utf-8",
)
print(f"wrote {out} ({out.stat().st_size} bytes)")
