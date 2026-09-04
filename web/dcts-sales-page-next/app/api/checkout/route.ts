import { NextRequest } from "next/server";

/**
 * POST /api/checkout
 *
 * Server-side checkout creation. Two modes:
 *
 * 1. STRIPE_SECRET_KEY + STRIPE_PRICE_ID set  -> creates a Stripe Checkout
 *    Session via the REST API (no SDK needed) with metadata
 *    { name, phone, email, utm_* } so the backend webhook can attach the
 *    payment to the CRM lead. Secrets never reach the browser.
 * 2. Otherwise -> returns the approved NEXT_PUBLIC_CHECKOUT_URL payment link
 *    if it is a buy.stripe.com / checkout.stripe.com host (same guard the
 *    static page had), else { mode: "pending" }.
 *
 * Body: { name, phone, email, utm?: { utm_source?, ... } }
 */

const STRIPE_SECRET_KEY = process.env.STRIPE_SECRET_KEY ?? "";
const STRIPE_PRICE_ID = process.env.STRIPE_PRICE_ID ?? "";
const APPROVED_CHECKOUT_HOSTS = new Set(["buy.stripe.com", "checkout.stripe.com"]);
const UTM_KEYS = ["utm_source", "utm_medium", "utm_campaign", "utm_content", "utm_term"] as const;

function parseHttpsUrl(value: string): URL | null {
  if (typeof value !== "string" || !value.trim()) return null;
  try {
    const url = new URL(value.trim());
    if (url.protocol !== "https:" || url.username || url.password) return null;
    return url;
  } catch {
    return null;
  }
}

function isApprovedCheckoutUrl(value: string): boolean {
  const url = parseHttpsUrl(value);
  return Boolean(url && APPROVED_CHECKOUT_HOSTS.has(url.hostname));
}

function cleanUtm(input: unknown): Record<string, string> {
  const out: Record<string, string> = {};
  if (input && typeof input === "object") {
    const rec = input as Record<string, unknown>;
    for (const key of UTM_KEYS) {
      const v = rec[key];
      if (typeof v === "string" && v && v.length <= 200) out[key] = v;
    }
  }
  return out;
}

export async function POST(req: NextRequest) {
  let body: Record<string, unknown>;
  try {
    body = await req.json();
  } catch {
    return Response.json({ error: "invalid_json" }, { status: 400 });
  }

  const name = typeof body.name === "string" ? body.name.trim() : "";
  const phone = typeof body.phone === "string" ? body.phone.trim() : "";
  const email = typeof body.email === "string" ? body.email.trim() : "";

  if (!name || !phone || !email) {
    return Response.json(
      { error: "missing_fields", message: "กรุณากรอกชื่อ เบอร์โทร และอีเมลให้ครบ" },
      { status: 422 },
    );
  }
  if (!/^[^@\s]+@[^@\s]+\.[^@\s]+$/.test(email)) {
    return Response.json({ error: "invalid_email", message: "รูปแบบอีเมลไม่ถูกต้อง" }, { status: 422 });
  }
  if (name.length > 255 || phone.length > 40 || email.length > 255) {
    return Response.json({ error: "field_too_long" }, { status: 422 });
  }

  const utm = cleanUtm(body.utm);
  const origin = new URL(req.url).origin;

  // Mode 1 — real Checkout Session (server-side Stripe)
  if (STRIPE_SECRET_KEY && STRIPE_PRICE_ID) {
    const params = new URLSearchParams();
    params.set("mode", "payment");
    params.set("success_url", `${origin}/?status=success`);
    params.set("cancel_url", `${origin}/?status=cancelled`);
    params.set("line_items[0][price]", STRIPE_PRICE_ID);
    params.set("line_items[0][quantity]", "1");
    params.set("metadata[name]", name);
    params.set("metadata[phone]", phone);
    params.set("metadata[email]", email);
    for (const [k, v] of Object.entries(utm)) params.set(`metadata[${k}]`, v);

    let session: { url?: string; error?: { message?: string } };
    try {
      const res = await fetch("https://api.stripe.com/v1/checkout/sessions", {
        method: "POST",
        headers: {
          Authorization: `Bearer ${STRIPE_SECRET_KEY}`,
          "content-type": "application/x-www-form-urlencoded",
        },
        body: params.toString(),
        signal: AbortSignal.timeout(15_000),
      });
      session = (await res.json()) as typeof session;
      if (!res.ok || !session.url) {
        return Response.json(
          { error: "stripe_error", message: session.error?.message ?? "สร้างคำสั่งชำระเงินไม่สำเร็จ" },
          { status: 502 },
        );
      }
    } catch {
      return Response.json(
        { error: "stripe_unreachable", message: "ระบบชำระเงินไม่พร้อมใช้งาน" },
        { status: 502 },
      );
    }

    return Response.json({ mode: "session", url: session.url });
  }

  // Mode 2 — approved Payment Link fallback (same guard as the static page)
  const checkoutUrl = process.env.NEXT_PUBLIC_CHECKOUT_URL ?? "";
  if (!isApprovedCheckoutUrl(checkoutUrl)) {
    return Response.json(
      { mode: "pending", message: "ระบบชำระเงินยังรอ URL ที่ได้รับอนุมัติ จึงยังไม่สามารถดำเนินการต่อได้" },
      { status: 200 },
    );
  }
  const destination = new URL(checkoutUrl.trim());
  for (const [k, v] of Object.entries(utm)) destination.searchParams.set(k, v);
  return Response.json({ mode: "payment_link", url: destination.href });
}
