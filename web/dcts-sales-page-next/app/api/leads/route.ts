import { NextRequest } from "next/server";
import { createHmac } from "node:crypto";

/**
 * POST /api/leads
 *
 * Receives a funnel form completion from the browser, validates it, signs it
 * with the backend form webhook secret (HMAC-SHA256 over the RAW body) and
 * forwards it to the prestige-trading-agent FastAPI backend
 * (`POST /webhooks/form`). The signing secret NEVER leaves the server.
 *
 * Body:  { submission_id, external_id, email?, path, data? }
 * Shape matches backend FormCompletion (src/prestige_trading_agent/domain.py).
 */
const BACKEND_URL = (process.env.PRESTIGE_BACKEND_URL ?? "").replace(/\/+$/, "");
const FORM_SECRET = process.env.PRESTIGE_FORM_WEBHOOK_SECRET ?? "";

export async function POST(req: NextRequest) {
  if (!BACKEND_URL || !FORM_SECRET) {
    return Response.json(
      { error: "backend_not_configured", message: "ระบบยังรอการตั้งค่าฝั่งเซิร์ฟเวอร์" },
      { status: 503 },
    );
  }

  const raw = await req.text();
  let parsed: Record<string, unknown>;
  try {
    parsed = JSON.parse(raw);
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  const { submission_id, external_id, email, path, data } = parsed ?? {};
  if (
    typeof submission_id !== "string" ||
    submission_id.length < 1 ||
    submission_id.length > 255 ||
    typeof external_id !== "string" ||
    external_id.length < 1 ||
    external_id.length > 255 ||
    typeof path !== "string" ||
    !["newbie", "course", "indicator", "unknown"].includes(path) ||
    (email !== undefined && email !== null && typeof email !== "string")
  ) {
    return Response.json({ error: "missing_fields" }, { status: 422 });
  }

  // Sign the exact raw bytes the backend will verify.
  const signature = createHmac("sha256", FORM_SECRET).update(raw).digest("hex");

  let upstream: Response;
  try {
    upstream = await fetch(`${BACKEND_URL}/webhooks/form`, {
      method: "POST",
      headers: {
        "content-type": "application/json",
        "x-form-signature": signature,
      },
      body: raw,
      signal: AbortSignal.timeout(10_000),
    });
  } catch {
    return Response.json(
      { error: "backend_unreachable", message: "ระบบฝั่งเซิร์ฟเวอร์ไม่พร้อมใช้งาน" },
      { status: 502 },
    );
  }

  if (!upstream.ok) {
    return Response.json(
      { error: "backend_error", status: upstream.status },
      { status: 502 },
    );
  }

  const body: unknown = await upstream.json();
  return Response.json(body);
}
